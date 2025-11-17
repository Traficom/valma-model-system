from __future__ import annotations
from typing import TYPE_CHECKING, Dict
from abc import ABC, abstractmethod
import numpy

import parameters.assignment as param
from assignment.datatypes.path_analysis import PathAnalysis
from assignment.datatypes.emme_matrix import EmmeMatrix, PermanentEmmeMatrix
if TYPE_CHECKING:
    from assignment.assignment_period import AssignmentPeriod


LENGTH_ATTR = "length"


class AssignmentMode(ABC):
    """Abstract base class for specifying mode assignment and matrices.

    A mode is assignment-period-specific, so that each mode-period
    combination has its own matrices.

    All modes have one demand matrix, which is "permanent".
    This means that it cannot be initialized or cleared after creation,
    so that additional demand can safely be added to it at any time.
    Demand initialisation is done by setting matrix to zero.
    """
    def __init__(self, name: str, assignment_period: AssignmentPeriod,
                 save_matrices: bool = False):
        """Initialize mode.

        Parameters
        ----------
        name : str
            Mode name
        assignment_period : AssignmentPeriod
            Assignment period to link to the mode
        save_matrices : bool (optional)
            Whether matrices will be saved in Emme format for all time periods
        """
        self.name = name
        self.emme_scenario = assignment_period.emme_scenario
        self.emme_project = assignment_period.emme_project
        self.time_period = assignment_period.name
        self._save_matrices = save_matrices
        self._matrices: Dict[str, EmmeMatrix] = {}
        self.demand = PermanentEmmeMatrix(
            "demand", f"demand_{self.name}_{self.time_period}",
            self.emme_project, self.emme_scenario.id, default_value=0)

    def _create_matrix(self, mtx_type: str, default_value: float = 999999):
        args = (
            mtx_type, f"{mtx_type}_{self.name}_{self.time_period}",
            self.emme_project, self.emme_scenario.id, default_value)
        mtx = (PermanentEmmeMatrix(*args) if self._save_matrices
               else EmmeMatrix(*args))
        self._matrices[mtx_type] = mtx
        return mtx

    def init_matrices(self):
        for mtx in self._matrices.values():
            mtx.init()

    def _soft_release_matrices(self):
        """Release matrices that are not PermanentMatrix."""
        for mtx in self._matrices.values():
            mtx.release()

    def release_matrices(self):
        """Release matrices, unless mode initialized with save_matrices=True."""
        if not self._save_matrices:
            for mtx in self._matrices.values():
                mtx.hard_release()

    @abstractmethod
    def get_matrices(self) -> Dict[str, numpy.ndarray]:
        """Get all LOS matrices.

        Return
        ------
        dict
            key : str
                LOS type (time/cost/...)
            value : numpy.ndarray
                2-D matrix in float32
        """
        pass


class SoftMode(AssignmentMode):
    def __init__(self, *args, **kwargs):
        AssignmentMode.__init__(self, *args, **kwargs)
        self.dist = self._create_matrix("dist")
        self.time = self._create_matrix("time")
        self._specify()

    def _specify(self):
        pass

    def get_matrices(self):
        mtxs = {**self.dist.item, **self.time.item}
        self._soft_release_matrices()
        return mtxs


class BikeMode(SoftMode):
    def _specify(self):
        self.spec = {
            "type": "SOLA_TRAFFIC_ASSIGNMENT",
            "classes": [
                {
                    "mode": param.main_mode,
                    "demand": self.demand.id,
                    "results": {
                        "od_travel_times": {
                            "shortest_paths": self.time.id,
                        },
                        "link_volumes": f"@{self.name}_{self.time_period}",
                    },
                    "path_analyses": [
                        PathAnalysis(LENGTH_ATTR, self.dist.id).spec,
                    ],
                }
            ],
            "stopping_criteria": {
                "max_iterations": 1,
                "best_relative_gap": 1,
                "relative_gap": 1,
                "normalized_gap": 1,
            },
            "performance_settings": param.performance_settings
        }


class WalkMode(SoftMode):
    def assign(self):
        self.init_matrices()
        no_penalty = dict.fromkeys(["at_nodes", "on_lines", "on_segments"])
        no_penalty["global"] = {
            "penalty": 0,
            "perception_factor": 1,
        }
        num_proc = "number_of_processors"
        spec = {
            "type": "EXTENDED_TRANSIT_ASSIGNMENT",
            "modes": param.aux_modes,
            "demand": self.demand.id,
            "waiting_time": {
                "headway_fraction": 0.01,
                "effective_headways": "hdw",
                "spread_factor": 1,
                "perception_factor": 0,
            },
            "boarding_time": no_penalty,
            "boarding_cost": no_penalty,
            "in_vehicle_time": {
                "perception_factor": 1,
            },
            "in_vehicle_cost": None,
            "flow_distribution_at_origins": {
                "choices_at_origins": "OPTIMAL_STRATEGY",
            },
            "flow_distribution_at_regular_nodes_with_aux_transit_choices": {
                "choices_at_regular_nodes": "OPTIMAL_STRATEGY",
            },
            "flow_distribution_between_lines": {
                "consider_total_impedance": True,
            },
            "journey_levels": [],
            "performance_settings": {
                num_proc: param.performance_settings[num_proc],
            },
        }
        spec["aux_transit_by_mode"] = [{
            "mode": mode,
            "cost": None,
            "cost_perception_factor": 1.0,
            "time": param.aux_transit_time_attr,
            "time_perception_factor": 1.0,
        } for mode in param.aux_modes]
        subset = "by_mode_subset"
        result_spec = {
            "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
            "total_impedance": self.time.id,
            subset: {
                "modes": param.aux_modes,
                "distance": self.dist.id,
            },
        }
        self.emme_project.transit_assignment(
            specification=spec, scenario=self.emme_scenario,
            add_volumes=True, save_strategies=True, class_name=self.name)
        self.emme_project.matrix_results(
            result_spec, scenario=self.emme_scenario,
            class_name=self.name)
