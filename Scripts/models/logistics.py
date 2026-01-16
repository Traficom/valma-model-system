import numpy as np
from typing import Dict, Tuple
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import utils.log as log

class FreightDetourInference:
    def __init__(self, impedance: Dict[str, np.ndarray], model_parameters: dict, 
                 lc_indices: np.ndarray) -> None:
        self.impedance = impedance
        self.lc_indices = lc_indices
        self.demand = None

        # Estimation parameters
        self.constant = model_parameters["constant"]
        self.impedance_coeff = model_parameters["impedance"]
        self.size = model_parameters["size"]

        # Threading parameters
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
        FreightDetourInference.__init__(self, costs, model_parameters, lc_indices)
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
    
    def process_batch(self, origin_offset: int, n: int, k_plus1: int,
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
        demand_batch = self.demand[origin_offset:origin_offset 
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


def run_logistics_model(model: LogisticsModule, iteration: int) -> Tuple[np.ndarray]:
        """Domestic logistics model entry point
        Process full matrix in origin batches to limit memory usage
        Process full matrix in origin batches in parallel
        """
        n_zones = model.demand.shape[0]
        k_plus1 = len(model.lc_indices) + 1
        final_demand = np.zeros((n_zones, n_zones), dtype=np.float32)
        total_per_route = np.zeros((k_plus1,), dtype=np.float32)
        lock = Lock()
        
        # Create list of batch arguments including shared arrays
        batch_args = [
            (offset, n_zones, k_plus1, final_demand, total_per_route, lock)
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
            f"orig_demand {np.sum(model.demand)}, final_demand {np.sum(final_demand)}"
        )
        return final_demand, total_per_route
