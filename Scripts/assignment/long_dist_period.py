from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Iterable
import numpy

import utils.log as log
from assignment.assignment_period import AssignmentPeriod
import parameters.assignment as param
from assignment.datatypes.transit import TransitMode
if TYPE_CHECKING:
    from assignment.emme_bindings.emme_project import EmmeProject

class WholeDayPeriod(AssignmentPeriod):
    """
    EMME assignment definition for long-distance trips.

    This period represents the whole day and only long-distance modes.
    Cars are assigned with free-flow speed.
    """
    def __init__(self, *args, **kwargs):
        AssignmentPeriod.__init__(self, *args, **kwargs)
        self._long_distance_trips_assigned = False
        for criteria in self.stopping_criteria.values():
                criteria["max_iterations"] = 0

    def prepare(self, dist_unit_cost: Dict[str, float],
                time_unit_cost: Dict[str, float],
                day_scenario: int, save_matrices: bool):
        """Prepare network for assignment.

        Calculate road toll cost and specify car assignment.
        Set boarding penalties and attribute names.

        Parameters
        ----------
        dist_unit_cost : dict
            key : str
                Assignment class (car/truck/...)
            value : float
                Length multiplier to calculate link cost
        time_unit_cost : dict
            key : str
                Assignment class (car_work/truck/...)
            value : float
                Value of time in euros per hour for truck modes
        day_scenario : int
            EMME scenario linked to the whole day
        save_matrices : bool
            Whether matrices will be saved in Emme format for all time periods
        """
        self._prepare_cars(
            dist_unit_cost, time_unit_cost, save_matrices, param.car_classes,
            truck_classes=[])
        self._prepare_walk_and_bike(save_matrices=True)
        self._prepare_transit(
            day_scenario, save_standard_matrices=True,
            save_extra_matrices=save_matrices,
            transit_classes=param.simple_transit_classes,
            mixed_classes=param.mixed_mode_classes,
            dist_unit_cost=dist_unit_cost["car"])

    def init_assign(self):
        log.info("Pedestrian assignment started...")
        self.walk_mode.assign()
        log.info(f"Pedestrians assigned for scenario {self.emme_scenario.id}")
        self._set_bike_vdfs()
        self._assign_bikes()
        self._set_car_vdfs(use_free_flow_speeds=True)
        return []

    def get_soft_mode_impedances(self):
        return self._get_impedances([self.bike_mode.name, self.walk_mode.name])

    def assign_trucks_init(self):
         pass

    def assign(self, modes: Iterable[str]
            ) -> Dict[str, Dict[str, numpy.ndarray]]:
        """Assign cars and long-distance transit for whole day.

        Get travel impedance matrices.

        Parameters
        ----------
        modes : Set of str
            The assignment classes for which impedance matrices will be returned

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (car/transit/...) : numpy 2-d matrix
        """
        self._assign_cars(self.stopping_criteria["coarse"])
        self._assign_transit(param.transit_classes)
        self._long_distance_trips_assigned = True
        mtxs = self._get_impedances(modes)
        for ass_cl in param.car_classes:
            if ass_cl in mtxs["dist"]:
                del mtxs["dist"][ass_cl]
        del mtxs["toll_cost"]
        return mtxs

    def end_assign(self,
                   assign_transit=True) -> Dict[str, Dict[str, numpy.ndarray]]:
        """Assign cars and long-distance transit for whole day.

        Get travel impedance matrices.

        Parameters
        ----------
        assign_transit : bool (optional)
            Whether to assign transit (default: true)

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (car/transit/...) : numpy 2-d matrix
        """
        self._assign_cars(self.stopping_criteria["fine"])
        if assign_transit:
            if self._long_distance_trips_assigned:
                strategy_paths = self._strategy_paths
                for transit_class in param.transit_classes:
                    tc: TransitMode = self.assignment_modes[transit_class]
                    tc.calc_transit_network_results()
                    if self._delete_strat_files:
                        strategy_paths[transit_class].unlink(missing_ok=True)
            else:
                self._assign_transit(
                    param.transit_classes, calc_network_results=True,
                    delete_strat_files=self._delete_strat_files)
        return self._get_impedances(
            param.car_classes + param.transit_classes + ("walk",))
