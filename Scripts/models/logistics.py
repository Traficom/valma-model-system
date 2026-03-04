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
        self.size = model_parameters["size"] * np.log(lc_sizes)
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
                            * truck_cost[o_idx_exp, d_idx_exp])
                            + self.constant["direct"])
        # combine detour and direct
        return np.concatenate([detour_utilities, direct_utilities], axis=1)
    
    def forward(self, origin_indices: np.ndarray, 
                destination_indices: np.ndarray) -> np.ndarray:
        weighted = self.compute_utilities(origin_indices, destination_indices)

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
        origin_indices = o_grid.ravel()
        destination_indices = d_grid.ravel()

        # Get probabilities and reshape
        probs_batch_flat = self.forward(origin_indices, destination_indices)
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
                 fin_borders: dict, is_export: bool):
        FreightDetourInference.__init__(self, impedance, model_parameters)
        self.fin_borders = fin_borders # Finland border - zone index
        self.is_export = is_export
        self.leg1_modes = list(impedance["leg_one"])
        self.leg2_modes = list(impedance["leg_two"])
        self.leg3_modes = list(impedance["leg_three"])

    def compute_utilities(self) -> Tuple[np.ndarray]:
        """Compute utility components for the three legs used in trade route choice
        origin - origin BCP - destination BCP - destination
        
        Returns
        -------
        Tuple[np.ndarray]
            leg one: origin -> origin BCP
            leg two: origin BCP -> dest BCP
            leg three: dest BCP -> destinations
        """
        util_parts_one = {}
        for mode in self.leg1_modes:
            cost_mtx = self.impedance["leg_one"][mode]["cost"]
            beta = self.get_impedance_beta(mode)
            util_parts_one[mode] = beta * cost_mtx
        util_one = np.concatenate(list(util_parts_one.values()), axis=1)
        
        util_parts_two = {}
        for mode in self.leg2_modes:
            item = self.impedance["leg_two"][mode]
            beta = self.get_impedance_beta(mode)
            util_two = beta * item["cost"]
            util_two += self.add_constants(mode, util_two.shape)
            if "frequency" in item and self.impedance_coeff.get("leg_two_frequency"):
                freq_mtx = item["frequency"]
                freq_mtx[freq_mtx == np.inf] = -np.inf
                util_two += self.impedance_coeff["leg_two_frequency"] * freq_mtx
            util_parts_two[mode] = util_two
        util_two = np.concatenate(list(util_parts_two.values()), axis=1)

        util_parts_three = {}
        for mode in self.leg3_modes:
            cost_mtx = self.impedance["leg_three"][mode]["cost"]
            beta = self.get_impedance_beta(mode)
            util_three = beta * cost_mtx
            util_parts_three[mode] = util_three
        util_three = np.concatenate(list(
            util_parts_three.values()) * len(self.leg2_modes), axis=0)
        return util_one, util_two, util_three
    
    def get_impedance_beta(self, mode: str) -> float:
        """Fetch mode specific coefficient from model specification
        
        Returns
        -------
        float
            estimated coefficient
        """
        coeffs = self.impedance_coeff.get("general_cost")
        coeffs = self.impedance_coeff.get("leg_cost") if not coeffs else coeffs
        if isinstance(coeffs, float):
            beta = coeffs
        else:
            if mode in coeffs:
                beta = coeffs[mode]
            elif isinstance(coeffs["leg_one"], float):
                beta = coeffs["leg_one"]
            else:
                beta = coeffs["leg_one"][mode]
        return beta

    def add_constants(self, mode, util_two_shape) -> np.ndarray:
        """Sums second leg specific mode-border constants
        
        Returns
        -------
        numpy.ndarray
            constant matrix
        """
        constants_mtx = np.zeros(util_two_shape, dtype="float32")
        border_constants = {}
        if mode in self.constant:
            for class_items in self.constant[mode].values():
                borders = set(self.fin_borders) & set(class_items[1])
                border_constants.update({border: class_items[0] for border in borders})
        for border, constant in border_constants.items():
            idx = self.fin_borders[border]
            if self.is_export:
                constants_mtx[idx, :] += constant
            else:
                constants_mtx[:, idx] += constant
        return constants_mtx

    def forward(self) -> Tuple[np.ndarray]:
        """Compute choice probabilities

        Returns
        -------
        Tuple[np.ndarray]
            probability of choosing upper alternative i
            probability of choosing lower alternative j given choice of i
        """
        util_one, util_two, util_three = self.compute_utilities()

        # origins, origin bcp, dest bcp * leg2 modes, destinations
        util1_util2 = util_one[:, :, None] + util_two[None, :, :]
        route_util = util1_util2[:, :, :, None] + util_three[None, None, :, :]

        n_origin, n_orig_alt = util_one.shape
        n_dest_bcp_alt = util_two.shape[1]
        n_dest = util_three.shape[1]

        route_flat = route_util.reshape(n_origin, n_orig_alt * n_dest_bcp_alt, n_dest)
        route_probs_flat = self.softmax(route_flat, axis=1)
        route_probs = route_probs_flat.reshape(n_origin, n_orig_alt, n_dest_bcp_alt, n_dest)
        
        prob_origin_bcp = np.sum(route_probs, axis=2)
        denom = prob_origin_bcp[:, :, None]
        prob_leg2_given_bcp = np.zeros_like(route_probs)
        np.divide(route_probs, denom, out=prob_leg2_given_bcp, where=denom > 0.0)
        return prob_origin_bcp, prob_leg2_given_bcp

    def process_batch(self, origin_offset: int, n_origin: int, n_dest: int, 
                      n_orig_bcp: int, n_dest_bcp: int, demand: np.ndarray, 
                      flow_leg1: np.ndarray, flow_leg2: np.ndarray, 
                      flow_leg3: np.ndarray, lock: Lock) -> None:
        """Distribute demand across logit route alternatives and aggregate flows"""
        current_batch_size = min(self.batch_size, n_origin - origin_offset)
        prob_o_bcp, prob_d_bcp = self.forward()
        
        offset_batch = origin_offset + current_batch_size
        prob_o_bcp_batch = prob_o_bcp[origin_offset:offset_batch]
        prob_d_bcp_batch = prob_d_bcp[origin_offset:offset_batch]
        # (batch, n_orig_alt, n_dest) → (batch, n_dest, n_orig_alt)
        prob_o_bcp_batch = np.moveaxis(prob_o_bcp_batch, 2, 1)
        # (batch, n_orig_alt, n_dest_bcp_alt, n_dest) → (batch, n_dest, n_orig_alt, n_dest_bcp_alt)
        prob_d_bcp_batch = np.moveaxis(prob_d_bcp_batch, 3, 1)

        demand_batch = demand[origin_offset:offset_batch, :]
        demand_routed = (
            demand_batch[:, :, None, None]
            * prob_o_bcp_batch[:, :, :, None]
            * prob_d_bcp_batch
        )
        
        # for batches, sum over origins and destinations
        flow_leg1_batch = np.sum(demand_batch[:, :, None] * prob_o_bcp_batch, axis=1)

        flow_leg2_batch = np.sum(demand_routed, axis=(0, 1))
        flow_leg2_batch = flow_leg2_batch.reshape(
            len(self.leg1_modes), n_orig_bcp,
            len(self.leg2_modes), len(self.leg3_modes), n_dest_bcp
        ).sum(axis=(0, 3))
        flow_leg2_batch = flow_leg2_batch.reshape(n_orig_bcp, -1)

        dest_flow = np.sum(demand_routed, axis=(0, 2))
        dest_flow = dest_flow.reshape(
            n_dest, len(self.leg2_modes), len(self.leg3_modes), n_dest_bcp
        ).sum(axis=1)
        dest_flow = dest_flow.transpose(2, 1, 0)
        flow_leg3_batch = dest_flow.reshape(n_dest_bcp, -1)

        with lock:
            flow_leg1[origin_offset:origin_offset + current_batch_size, :] += flow_leg1_batch
            flow_leg2[:, :] += flow_leg2_batch
            flow_leg3[:, :] += flow_leg3_batch


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
        external export/import trade demand

    Returns
    -------
    dict
        Leg name (one/two/three) : Mode
            Name (truck/container_ship...) : numpy 2d array
    """
    n_origin, n_dest = demand.shape
    # Use truck as reference mode since it's always present in mode alternatives
    n_orig_bcp = model.impedance["leg_one"]["truck"]["cost"].shape[1]
    n_dest_bcp = model.impedance["leg_three"]["truck"]["cost"].shape[0]
    
    flow_leg1 = np.zeros((n_origin, n_orig_bcp), dtype=np.float32)
    flow_leg2 = np.zeros((n_orig_bcp, n_dest_bcp * len(model.leg2_modes)), dtype=np.float32)
    flow_leg3 = np.zeros((n_dest_bcp, n_dest), dtype=np.float32)
    lock = Lock()
    
    batch_args = [
        (offset, n_origin, n_dest, n_orig_bcp, n_dest_bcp, demand, 
         flow_leg1, flow_leg2, flow_leg3, lock)
        for offset in range(0, n_origin, model.batch_size)
    ]
    with ThreadPoolExecutor(max_workers=model.max_workers) as executor:
        futures = [executor.submit(model.process_batch, *args) for args in batch_args]
        _ = [f.result() for f in futures]

    trade_demand = {
        "leg_one": matrix_mode_slicer(flow_leg1, model.leg1_modes, n_orig_bcp),
        "leg_two": matrix_mode_slicer(flow_leg2, model.leg2_modes, n_dest_bcp),
        "leg_three": matrix_mode_slicer(flow_leg3, model.leg3_modes, n_dest)
    }
    return trade_demand

def matrix_mode_slicer(leg_demand, modes, n_zones):
    """Slice leg specific demand matrices to leg's modes
    
    Returns
    -------
    dict
        mode : 2d array
    """
    flow_matrices = {}
    for i, mode in enumerate(modes):
        col = slice(i * n_zones, (i + 1) * n_zones)
        flow_matrices[mode] = leg_demand[:, col]
    return flow_matrices
