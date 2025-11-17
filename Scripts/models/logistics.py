import numpy as np
from typing import NamedTuple, Sequence, Union
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

class DDMParameters(NamedTuple):
    orig_lc_detour: float
    lc_dest_detour: float
    constant_detour: float
    orig_dest_direct: float
    constant_direct: float
    size_factor: float
    
class DetourDistributionInference:
    def __init__(self, cost_matrix: np.ndarray, ddm_params: DDMParameters, lc_indices: Sequence[int], lc_sizes: Sequence[int]) -> None:
        self.lc_size_factors = ddm_params.size_factor * np.log(lc_sizes)
        self.cost_matrix = cost_matrix
        self.lc_indices = lc_indices
        self.lc_sizes = lc_sizes
        self.orig_lc_detour = ddm_params.orig_lc_detour
        self.lc_dest_detour = ddm_params.lc_dest_detour
        self.constant_detour = ddm_params.constant_detour
        self.orig_dest_direct = ddm_params.orig_dest_direct
        self.constant_direct = ddm_params.constant_direct
        self.size_factor = ddm_params.size_factor
        self.scale = 5.0

    def softmax(self, x: np.ndarray, axis: int = -1) -> np.ndarray:
        """Compute numerically stable softmax."""
        x_max = np.max(x, axis=axis, keepdims=True)
        exp_x = np.exp(x - x_max)
        return exp_x / np.sum(exp_x, axis=axis, keepdims=True)

    def sumexp(self, x: np.ndarray, axis: int = -1) -> tuple[np.ndarray, np.ndarray]:
        """Compute numerically stable exp and sum(exp(x)) and log(sum(exp))."""
        x_max = np.max(x, axis=axis, keepdims=True)
        exp_x = np.exp(x - x_max)
        sum_exp = np.sum(exp_x, axis=axis)
        logsum_exp = x_max.flatten() + np.log(sum_exp)
        return exp_x, sum_exp, logsum_exp
    
    def compute_utilities(self, origin_indices: Union[Sequence[int], np.ndarray] = None, 
                        destination_indices: Union[Sequence[int], np.ndarray] = None) -> np.ndarray:
        """Compute utilities for detour and direct routes for given origins and destinations."""
        k = self.lc_indices.shape[0]
        
        # Expand dimensions for broadcasting
        o_idx_exp = np.expand_dims(origin_indices, axis=1) # Shape: (n, 1)
        d_idx_exp = np.expand_dims(destination_indices, axis=1) # Shape: (n, 1)
        lc_exp = np.broadcast_to(self.lc_indices, (len(origin_indices), k)) # Shape: (n, k)
        
        # utilities for routes through k logistics centers
        detour_utilities = (self.orig_lc_detour * self.cost_matrix[o_idx_exp, lc_exp] +
                 self.lc_dest_detour * self.cost_matrix[lc_exp, d_idx_exp] +
                 self.constant_detour) + self.lc_size_factors # Shape: (n, k)
        
        # utilities for direct routes
        direct_utilities = self.orig_dest_direct * self.cost_matrix[origin_indices, destination_indices] + self.constant_direct
        
        # combine detour and direct
        return np.concatenate([detour_utilities, np.expand_dims(direct_utilities, axis=1)], axis=1)

    def forward(self, probs_indices: np.ndarray) -> np.ndarray:
        # compute only for origins with data
        origin_set = probs_indices[:,0]
        # compute only for destination with data
        destination_set = probs_indices[:,1]
        
        weighted = self.compute_utilities(origin_indices=origin_set, destination_indices=destination_set)
        
        # Now you have 2 top-level utilities: direct_util vs. detour_util_top
        detour_util = weighted[:, :-1] / self.scale
        exp_x_detour, detour_util_sum_exp, logsum_exp = self.sumexp(detour_util, axis=1)
        direct_util = weighted[:, -1] / self.scale
        top_level_utilities = np.stack([direct_util, logsum_exp], axis=1)
        p_top = self.softmax(top_level_utilities, axis=1)
        
        # Combine into final choice probabilities
        p_direct = np.expand_dims(p_top[:, 0], axis=1)
        p_detour = np.expand_dims(p_top[:, 1], axis=1) * (exp_x_detour / np.expand_dims(detour_util_sum_exp, axis=1))
        
        probs_batch = np.concatenate([p_detour, p_direct], axis=1)
        return probs_batch
    
def process_batch(origin_offset: int, batch_size: int, n: int, k_plus1: int,
                  model: DetourDistributionInference, demand: np.ndarray,
                  lcs: Sequence[int], final_demand: np.ndarray,
                  total_per_route: np.ndarray, lock: Lock):
    """Process a single batch of origins."""
    
    current_batch_size = min(batch_size, n - origin_offset)
    
    # Create indices using meshgrid
    origin_indices = np.arange(origin_offset, origin_offset + current_batch_size, dtype=np.int32)
    dest_indices = np.arange(n, dtype=np.int32)
    o_grid, d_grid = np.meshgrid(origin_indices, dest_indices, indexing='ij')
    eval_indices = np.stack([o_grid.ravel(), d_grid.ravel()], axis=1)
    
    # Get probabilities and reshape
    probs_batch_flat = model.forward(probs_indices=eval_indices)
    probs_batch = probs_batch_flat.reshape(current_batch_size, n, k_plus1)
    
    # Get demand batch and expand dimensions
    demand_batch = demand[origin_offset:origin_offset+current_batch_size, :, np.newaxis]
    
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
        final_demand[origin_offset:origin_offset+current_batch_size, lcs] += orig_to_c
        final_demand[lcs] += c_to_dest.T
        final_demand[origin_offset:origin_offset+current_batch_size, :] += direct
        total_per_route += route_totals
    
    return origin_offset, current_batch_size

def process_logistics_inference(model: DetourDistributionInference, n_zones: int, demand: np.ndarray) -> None:

    # Process full matrix in origin batches to limit memory usage
    # Process full matrix in origin batches in parallel
    k_plus1 = len(model.lc_indices) + 1
    batch_size = 15
    final_demand = np.zeros((n_zones, n_zones), dtype=np.float32)
    total_per_route = np.zeros((k_plus1,), dtype=np.float32)
    lock = Lock()
    
    # Create list of batch arguments including shared arrays
    batch_args = [
        (offset, batch_size, n_zones, k_plus1, model, demand, model.lc_indices, final_demand, total_per_route, lock)
        for offset in range(0, n_zones, batch_size)
    ]
    
    # Process batches in parallel
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(process_batch, *args) for args in batch_args]
        results = [future.result() for future in futures]
    
    # after processing all batches
    detour_total = np.sum(total_per_route[:-1])
    direct_total = total_per_route[-1]
    print(f"Total demand via logistics centers: {detour_total:.4f}")
    print(f"Total direct demand: {direct_total:.4f}")
    
    print("Final demand matrix including detour legs and direct:")
    print(f'orig_demand: {np.sum(demand)}, final_demand: {np.sum(final_demand)}')

    # output the final demand matrix
    return final_demand
