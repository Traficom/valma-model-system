import numpy as np
from typing import Dict, Tuple
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import utils.log as log

class FreightDetourInference:
    def __init__(self, impedance: Dict[str, np.ndarray], model_parameters: dict, ) -> None:
        self.impedance = impedance
        self.constant = model_parameters["constant"]
        self.impedance_coeff = model_parameters["impedance"]
        self.size = model_parameters["size"]
        self.batch_size = 15
        self.max_workers = 16

    def softmax(self, x: np.ndarray, axis: int = -1) -> np.ndarray:
        """Compute numerically stable softmax."""
        x_max = np.max(x, axis=axis, keepdims=True)
        exp_x = np.exp(x - x_max)
        return exp_x / np.sum(exp_x, axis=axis, keepdims=True)

    def sumexp(self, x: np.ndarray, axis: int = -1) -> Tuple[np.ndarray]:
        """Compute numerically stable exp(x), sum(exp(x)) and log(sum(exp(x)))."""
        x_max = np.max(x, axis=axis, keepdims=True)
        exp_x = np.exp(x - x_max)
        sum_exp = np.sum(exp_x, axis=axis)
        logsum_exp = x_max.flatten() + np.log(sum_exp)
        return exp_x, sum_exp, logsum_exp

class LogisticsModule(FreightDetourInference):
    def __init__(self, costs: Dict[str, np.ndarray], model_parameters: dict, 
                 lc_indices: np.ndarray, lc_sizes: np.ndarray):
        FreightDetourInference.__init__(self, costs, model_parameters)
        self.lc_indices = lc_indices
        self.size *= np.log(lc_sizes)
        self.scale = 5.0

    def compute_utilities(self, origin_indices: np.ndarray, 
                          destination_indices: np.ndarray) -> np.ndarray:
        """Compute utilities for detour and direct routes 
        for given origins and destinations.
        """
        k = self.lc_indices.shape[0]
        # Expand dimensions for broadcasting
        o_idx_exp = np.expand_dims(origin_indices, axis=1) # Shape: (n, 1)
        d_idx_exp = np.expand_dims(destination_indices, axis=1) # Shape: (n, 1)
        lc_exp = np.broadcast_to(self.lc_indices, (len(origin_indices), k)) # Shape: (n, k)
        
        truck_cost = self.impedance["truck"]["cost"]
        # utilities for routes through k logistics centers
        detour_utilities = (
            self.impedance_coeff["orig_lc_detour"] * truck_cost[o_idx_exp, lc_exp]
            + self.impedance_coeff["lc_dest_detour"] * truck_cost[lc_exp, d_idx_exp]
            + self.constant["detour"]) + self.size

        # utilities for direct routes
        direct_utilities = ((self.impedance_coeff["orig_dest_direct"]
                            * truck_cost[origin_indices, destination_indices])
                            + self.constant["direct"])
        # combine detour and direct
        return np.concatenate([detour_utilities, 
                               np.expand_dims(direct_utilities, axis=1)], axis=1)
    
    def forward(self, probs_indices: np.ndarray) -> np.ndarray:
        # compute only for origins with data
        origin_set = probs_indices[:,0]
        # compute only for destination with data
        destination_set = probs_indices[:,1]
        weighted = self.compute_utilities(origin_indices=origin_set, 
                                          destination_indices=destination_set)
        
        # Now you have 2 top-level utilities: direct_util vs. detour_util_top
        detour_util = weighted[:, :-1] / self.scale
        exp_x_detour, detour_util_sum_exp, logsum_exp = self.sumexp(detour_util, axis=1)
        direct_util = weighted[:, -1] / self.scale
        top_level_utilities = np.stack([direct_util, logsum_exp], axis=1)
        p_top = self.softmax(top_level_utilities, axis=1)
        
        # Combine into final choice probabilities
        p_direct = np.expand_dims(p_top[:, 0], axis=1)
        p_detour = (np.expand_dims(p_top[:, 1], axis=1) 
                    * (exp_x_detour / np.expand_dims(detour_util_sum_exp, axis=1)))
        probs_batch = np.concatenate([p_detour, p_direct], axis=1)
        return probs_batch
    
    def process_batch(self, origin_offset: int, n: int, k_plus1: int, demand: np.ndarray,
                      final_demand: np.ndarray, total_per_route: np.ndarray, lock: Lock):
        """Process a single batch of origins."""
        current_batch_size = min(self.batch_size, n - origin_offset)
        
        # Create indices using meshgrid
        origin_indices = np.arange(origin_offset, origin_offset
                                   + current_batch_size, dtype=np.int32)
        dest_indices = np.arange(n, dtype=np.int32)
        o_grid, d_grid = np.meshgrid(origin_indices, dest_indices, indexing='ij')
        eval_indices = np.stack([o_grid.ravel(), d_grid.ravel()], axis=1)

        # Get probabilities and reshape
        probs_batch_flat = self.forward(probs_indices=eval_indices)
        probs_batch = probs_batch_flat.reshape(current_batch_size, n, k_plus1)
        
        # Get demand batch and expand dimensions
        demand_batch = demand[origin_offset:origin_offset 
                              + current_batch_size, :, np.newaxis]
        
        # Compute distribution using broadcasting
        dist_batch = demand_batch * probs_batch
        
        # Process detours and compute updates
        detours = dist_batch[:, :, :-1]
        direct = dist_batch[:, :, -1]
        orig_to_c = np.sum(detours, axis=1)
        c_to_dest = np.sum(detours, axis=0)
        route_totals = np.sum(dist_batch, axis=(0, 1))
        
        # Update shared arrays with lock to ensure thread safety
        with lock:
            final_demand[origin_offset:origin_offset 
                         + current_batch_size, self.lc_indices] += orig_to_c
            final_demand[self.lc_indices] += c_to_dest.T
            final_demand[origin_offset:origin_offset+current_batch_size, :] += direct
            total_per_route += route_totals
        
        return origin_offset, current_batch_size


class TradeRouteModule(FreightDetourInference):
    def __init__(self, impedance: Dict[str, np.ndarray], model_parameters: dict, 
                 fin_bcp_map: dict):
        FreightDetourInference.__init__(self, impedance, model_parameters)
        self.fin_bcp_map = fin_bcp_map # Finland border - zone index
        self.leg2_modes = list(impedance["leg_two"])

    def compute_utilities(self, origin_indices: np.ndarray, 
                          cluster_indices: np.ndarray) -> Tuple[np.ndarray]:
        """Compute utility components for the three legs used in trade route choice.

        Parameters
        ----------
        
        Returns
        -------
        Tuple[np.ndarray]
            leg one: origin -> origin BCP
            leg two: origin BCP -> dest BCP
            leg three: dest BCP -> destinations
        """
        origin_indices = np.asarray(origin_indices, dtype=np.int32)
        cluster_indices = np.asarray(cluster_indices, dtype=np.int32)
        split1_mode_len = len(self.impedance["leg_one"])

        util_parts_one = {}
        for mode in self.impedance["leg_one"]:
            cost_mtx = self.impedance["leg_one"][mode]["cost"]
            util_one = self.impedance_coeff["leg_one_cost"] * cost_mtx[origin_indices, :]
            util_parts_one[mode] = util_one
        util_one = np.concatenate(list(util_parts_one.values()), axis=1)
        
        util_parts_two = {}
        for mode in self.leg2_modes:
            item = self.impedance["leg_two"][mode]
            cost_mtx = item["cost"]
            util_two = self.impedance_coeff["leg_two_cost"] * cost_mtx
            if "frequency" in item:
                freq_mtx = item["frequency"]
                freq_mtx[freq_mtx == np.inf] = -np.inf
                util_two += self.impedance_coeff["leg_two_frequency"] * freq_mtx
                bcp_set = set(self.fin_bcp_map) & set(self.constant)
                for bcp in bcp_set:
                    row_idx = self.fin_bcp_map[bcp]
                    util_two[row_idx, :] += self.constant[bcp]
            util_parts_two[mode] = np.repeat(util_two, repeats=split1_mode_len, axis=0)
        util_two = np.concatenate(list(util_parts_two.values()), axis=1)

        truck_leg_three_mtx = self.impedance["leg_three"]["truck"]["cost"][:, cluster_indices]
        util_three = (self.impedance_coeff["leg_three_cost"] * truck_leg_three_mtx).T
        util_three = np.concatenate([util_three] * len(util_parts_one), axis=1)
        return util_one, util_two, util_three

    def forward(self, probs_indices: np.ndarray) -> Tuple[np.ndarray]:
        """Compute top-level and conditional bottom probabilities for
        foreign route choice.

        Returns (P_top, P_bottom_given_top):
        - P_top: marginal probability of selecting a top alternative
                 (domestic BCP + split_one mode), shape (n_pairs, n_top_alts)
        - P_bottom_given_top: conditional probability of bottom alternatives
                 given the top choice, shape (n_pairs, n_top_alts, n_bottom_alts)
        """
        origin_set = probs_indices[:, 0]
        cluster_set = probs_indices[:, 1]
        split_one, split_two, split_three = self.compute_utilities(origin_set, cluster_set)

        # split_two repeats utilities over border control points in the pattern:
        #   [bcp0-for-all-modes, bcp1-for-all-modes, ...]
        # whereas top_util columns are ordered as:
        #   [mode0-bcp0, mode0-bcp1, ..., mode1-bcp0, mode1-bcp1, ...]
        # reshape and transpose to align
        n_pairs, n_top_alts = split_one.shape
        n_bottom_alts = split_two.shape[1]
        n_split_one = len(self.impedance["leg_one"])
        k_bcp = split_two.shape[0] // n_split_one  # number of domestic BCPs (k_dom)

        # (n_split_one, k_bcp, n_bottom_alts) -> (k_bcp, n_split_one, n_bottom_alts)
        # -> (k_bcp * n_split_one, n_bottom_alts) == (n_top_alts, n_bottom_alts)
        split_two = split_two.reshape(n_split_one, k_bcp, n_bottom_alts)
        split_two = split_two.transpose(1, 0, 2)
        split_two = split_two.reshape(n_top_alts, n_bottom_alts)

        # V[p, i_top, j_bottom] -> (n_pairs, n_top_alts, n_bottom_alts)
        route_util = (
            split_one[:, :, None] # (n_pairs, n_top_alts, 1)
            + split_two[None, :, :] # (1, n_top_alts, n_bottom_alts)
            + split_three[:, None, :] # (n_pairs, 1, n_bottom_alts)
        )

        # Flatten top and bottom into a single "route" axis
        route_logits_2d = route_util.reshape(n_pairs, n_top_alts * n_bottom_alts)
        route_probs_flat = self.softmax(route_logits_2d, axis=1) 
        # Reshape back to (pair, top, bottom)
        route_probs = route_probs_flat.reshape(n_pairs, n_top_alts, n_bottom_alts)

        # Marginal over bottom alternatives: P_top[p, i_top] = sum_j P_route[p, i_top, j]
        P_top = np.sum(route_probs, axis=2)

        # Conditional bottom choice: P(bottom | top), shape (n_pairs, n_top_alts, n_bottom_alts)
        denom = P_top[:, :, None]

        # Safely compute conditional probabilities without evaluating the
        # division where denom == 0
        P_bottom_given_top = np.zeros_like(route_probs)
        np.divide(route_probs, denom, out=P_bottom_given_top, where=denom > 0.0)
        return P_top, P_bottom_given_top

    def process_batch(self, origin_offset: int, n_origin: int, n_cluster: int,
                      flow_leg1: np.ndarray, flow_leg2: np.ndarray, 
                      flow_leg3: np.ndarray, lock: Lock) -> Tuple[np.ndarray]:
        """Process a batch of origins for foreign route choice inference.
        
        Key dimension tracking:
        - P_top shape: (n_pairs, k_dom_sel) where k_dom_sel = len(split_one_modes) 
        - P_bottom shape: (n_pairs, k_dom_sel, k_for*n_alt2)
        - dist_BD_BF shape: (n_origins_batch, n_clusters, k_dom_sel, k_for*n_alt2)
        - flow_B_batch shape after sum(axis=0,1): (k_dom_sel, k_for*n_alt2)
        """
        current_batch_size = min(self.batch_size, n_origin - origin_offset)
        origin_indices = np.arange(origin_offset, origin_offset + current_batch_size,
                                   dtype=np.int32)
        cluster_indices = np.arange(n_cluster, dtype=np.int32)
        o_grid, c_grid = np.meshgrid(origin_indices, cluster_indices, indexing='ij')
        eval_indices = np.stack([o_grid.ravel(), c_grid.ravel()], axis=1)
        P_top, P_bottom = self.forward(eval_indices)
        
        # Number of split one alternatives
        k_dom_sel = P_top.shape[1]  
        # P_bottom.shape[2] is already k_for*n_alt2, concatenated in compute_foreign_utilities
        k_for_n_alt2 = P_bottom.shape[2]
        P_bd = P_top.reshape(current_batch_size, n_cluster, k_dom_sel)
        P_bf_given_bd = P_bottom.reshape(current_batch_size, n_cluster, k_dom_sel, k_for_n_alt2)

        demand_batch = self.demand[origin_offset:origin_offset + current_batch_size, :]
        dist_BD_BF = (
            demand_batch[:, :, None, None]
            * P_bd[:, :, :, None]
            * P_bf_given_bd)
        
        # Get dimensions needed for aggregation
        k_orig_borders = self.impedance["leg_one"]["truck"].shape[1]
        k_dest_borders = self.impedance["leg_three"]["truck"].shape[0]
        n_alt2 = len(self.leg2_modes)
        
        # Form batches
        flow_A_batch = np.sum(demand_batch[:, :, None] * P_bd, axis=1)
        
        # Aggregate flow_B_batch from (k_dom_sel, k_for*n_alt2) to (k_dom, k_for*n_alt2)
        # by summing across split_one modes
        # flow_B_batch shape is (k_dom_sel=k_dom*m1, k_for*n_alt2) where m1=len(split_one_modes)
        # Reshape to (m1, k_dom, k_for*n_alt2) to separate modes from BCPs
        flow_B_batch = np.sum(dist_BD_BF, axis=(0, 1)) # (k_dom_sel, k_for*n_alt2)
        num_split_one_modes = k_dom_sel // k_orig_borders  # Calculate number of split_one modes
        flow_B_batch_aggregated = flow_B_batch.reshape(
            num_split_one_modes, k_orig_borders, k_dest_borders * n_alt2).sum(axis=0)

        # Compute flow_C
        tmp = np.sum(dist_BD_BF, axis=0)  # (n_cluster, k_dom_sel, k_for*n_alt2)
        tmp = np.sum(tmp, axis=1) # sum over k_dom_sel dimension -> (n_cluster, k_for*n_alt2)
        flow_C_batch = tmp.T # transpose to (k_for*n_alt2, n_cluster)
        flow_C_batch = flow_C_batch.reshape(n_alt2, k_dest_borders, n_cluster).sum(axis=0)

        with lock:
            flow_leg1[origin_offset:origin_offset + current_batch_size, :] += flow_A_batch.astype(flow_leg1.dtype, copy=False)
            # flow_B_batch_aggregated now has shape (k_dom, k_for*n_alt2) which matches flow_B
            flow_leg2[:, :] += flow_B_batch_aggregated.astype(flow_leg2.dtype, copy=False)
            flow_leg3[:, :] += flow_C_batch.astype(flow_leg3.dtype, copy=False)
        return origin_offset, current_batch_size


def run_logistics_model(model: LogisticsModule, demand: np.ndarray, 
                        iteration: int) -> Tuple[np.ndarray]:
    """Using given truck demand full matrix, calculates share of direct demand
    between OD pairs and share of detoured demand between OD pairs that route
    through designated logistics centers.
    Processes demand matrix in origin batches and in parallel to limit memory usage.
    
    Parameters
    ----------
    model : LogisticsModule
        LogisticsModule class object
    demand : np.ndarray
        calculated truck demand for commodity
    iteration : int
        ordinal iteration number
        
    Returns
    -------
    Tuple[np.ndarray]
        processed truck demand matrix and totals for detoured and direct demand
    """
    n_zones = demand.shape[0]
    k_plus1 = len(model.lc_indices) + 1
    final_demand = np.zeros((n_zones, n_zones), dtype=np.float32)
    total_per_route = np.zeros((k_plus1,), dtype=np.float32)
    lock = Lock()
    
    # Create list of batch arguments including shared arrays
    batch_args = [
        (offset, n_zones, k_plus1, demand, final_demand, total_per_route, lock)
        for offset in range(0, n_zones, model.batch_size)
    ]
    
    # Process batches in parallel
    with ThreadPoolExecutor(max_workers=model.max_workers) as executor:
        futures = [executor.submit(model.process_batch, *args) for args in batch_args]
        _ = [future.result() for future in futures]
    
    # after processing all batches
    detour_total = np.sum(total_per_route[:-1])
    direct_total = total_per_route[-1]
    log.info(
        f"Logistics module results after iteration {iteration}:\n"
        f"Total demand via logistics centers {detour_total:.4f}\n"
        f"Total direct demand {direct_total:.4f}\n"
        "Final demand matrix including detour legs and direct for\n"
        f"orig_demand {np.sum(demand)}, final_demand {np.sum(final_demand)}"
    )
    return final_demand, total_per_route

def run_trade_model(model: TradeRouteModule, demand: np.ndarray):
    """Using given trade demand, calculates share of demand for mode-route 
    alternatives between Finnish zones and foreign country clusters
    through designated border control points.
    
    Used variable bcp refers to these border control points, as in, pass through
    points within Finland and country clusters.

    Parameters
    ----------
    model : TradeRouteModule
        TradeRouteModule class object
    demand : np.ndarray
        external export/import trade demand for some

    Returns
    -------
    __type__
        _description_
    """
    n_origin, n_cluster = demand.shape
    k_orig_bcp = model.impedance["leg_one"]["truck"]["cost"].shape[1]
    k_dest_bcp = model.impedance["leg_three"]["truck"]["cost"].shape[0]
    
    leg1_modes = len(list(model.impedance["leg_one"]))
    k_orig_dims = k_orig_bcp * leg1_modes
    k_dest_dims = k_dest_bcp * len(model.leg2_modes)
    
    flow_leg1 = np.zeros((n_origin, k_orig_dims), dtype=np.float32)
    flow_leg2 = np.zeros((k_orig_bcp, k_dest_dims), dtype=np.float32)
    flow_leg3 = np.zeros((k_dest_bcp, n_cluster), dtype=np.float32)
    lock = Lock()
    
    batch_args = [
        (offset, n_origin, n_cluster, flow_leg1, flow_leg2, flow_leg3, lock)
        for offset in range(0, n_origin, model.batch_size)
    ]
    with ThreadPoolExecutor(max_workers=model.max_workers) as executor:
        futures = [executor.submit(model.process_batch, *args) for args in batch_args]
        _ = [f.result() for f in futures]

    # Extract split one modes
    flow_leg1_matrices = {}
    for i, mode in enumerate(leg1_modes):
        sl = slice(i * k_orig_bcp, (i + 1) * k_orig_bcp)
        flow_leg1_matrices[mode] = flow_leg1[:, sl]

    # Extract split two modes
    flow_leg2_matrices = {}
    for j, mode in enumerate(model.leg2_modes):
        col = slice(j * k_dest_bcp, (j + 1) * k_dest_bcp)
        block = flow_leg2[:, col]  # (k_dom, k_for)
        flow_leg2_matrices[mode] = block
    
    flow_leg3_matrices = {"truck": flow_leg3}
    return flow_leg1_matrices, flow_leg2_matrices, flow_leg3_matrices
