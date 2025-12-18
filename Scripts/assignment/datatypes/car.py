from __future__ import annotations
from typing import TYPE_CHECKING, Union


import parameters.assignment as param
from assignment.datatypes.assignment_mode import AssignmentMode, LENGTH_ATTR
from assignment.datatypes.path_analysis import PathAnalysis
from models.logit import divide
if TYPE_CHECKING:
    from assignment.assignment_period import AssignmentPeriod


class VehicleMode(AssignmentMode):
    def __init__(self, name: str, assignment_period: AssignmentPeriod,
                 dist_unit_cost: float, include_toll_cost: bool,
                 save_matrices: bool = False):
        """Initialize car mode.

        Parameters
        ----------
        name : str
            Mode name
        assignment_period : AssignmentPeriod
            Assignment period to link to the mode
        dist_unit_cost : float
            Length multiplier to calculate link cost
        include_toll_cost : bool
            Whether network links have "hinta" attribute defined
        save_matrices : bool (optional)
            Whether matrices will be saved in Emme format for all time periods
        """
        AssignmentMode.__init__(self, name, assignment_period, save_matrices)
        self.vot_inv = param.vot_inv[param.vot_classes[self.name]]
        self.gen_cost = self._create_matrix("gen_cost")
        self.dist = self._create_matrix("dist")
        self.dist_unit_cost = dist_unit_cost
        self._include_toll_cost = include_toll_cost
        perception_factor = self.vot_inv
        if include_toll_cost:
            self.toll_cost = self._create_matrix("toll_cost")
            self.link_cost_attr = f"@cost_{self.name[:10]}_{self.time_period}"
            self.emme_project.create_extra_attribute(
                "LINK", self.link_cost_attr, "total cost",
                overwrite=True, scenario=self.emme_scenario)
        else:
            perception_factor *= self.dist_unit_cost
            self.link_cost_attr = LENGTH_ATTR

        # Specify
        self.spec = {
            "mode": param.assignment_modes[self.name],
            "demand": self.demand.id,
            "generalized_cost": {
                "link_costs": self.link_cost_attr,
                "perception_factor": perception_factor,
            },
            "results": {
                "link_volumes": f"@{self.name}_{self.time_period}",
                "od_travel_times": {
                    "shortest_paths": self.gen_cost.id
                }
            },
            "path_analyses": []
        }
        self.add_analysis(LENGTH_ATTR, self.dist.id)
        if self._include_toll_cost:
            self.add_analysis(
                f"@toll_cost_{self.time_period}", self.toll_cost.id)

    def add_analysis (self,
                      link_component: str,
                      od_values: Union[int, str]):
        analysis = PathAnalysis(link_component, od_values)
        self.spec["path_analyses"].append(analysis.spec)

    def get_matrices(self):
        cost = self.dist_unit_cost * self.dist.data
        if self._include_toll_cost:
            cost += self.toll_cost.data
        time = self._get_time(cost)
        m = {"cost": cost, "time": time, **self.dist.item}
        if self._include_toll_cost:
            m.update(self.toll_cost.item)
        self._soft_release_matrices()
        # fix the emme path analysis results
        # (dist and cost are zero if path not found but we want it to
        # be the default value 999999)
        path_not_found = time > 999999
        for mtx_type in ("cost", "dist"):
            m[mtx_type][path_not_found] = 999999
        return m

    def _get_time(self, cost):
        return self.gen_cost.data - self.vot_inv*cost


class CarMode(VehicleMode):
    def __init__(self, *args, **kwargs):
        VehicleMode.__init__(self, *args, **kwargs)
        self.free_flow_time = self._create_matrix("free_flow_time")
        self.add_analysis(param.free_flow_time_attr, self.free_flow_time.id)
        self.max_congestion = 0.0

    def _get_time(self, cost):
        time = self.gen_cost.data - self.vot_inv*cost
        free_flow_time = self.free_flow_time.data
        congested_time = time - free_flow_time
        self.max_congestion: float = divide(congested_time, free_flow_time).max()
        return free_flow_time + param.congested_time_weight*congested_time


class TruckMode(VehicleMode):
    def __init__(self, *args, **kwargs):
        VehicleMode.__init__(self, *args, **kwargs)
        self.time = self._create_matrix("time")
        self.add_analysis(f"@truck_time_{self.time_period}", self.time.id)

    def _get_time(self, *args):
        return self.time.data
