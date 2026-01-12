from typing import Dict, Iterable
from numpy import ndarray
import copy

import utils.log as log
from assignment.assignment_period import AssignmentPeriod
from assignment.long_dist_period import WholeDayPeriod
from assignment.datatypes.transit import TransitMode
import parameters.assignment as param


class OffPeakPeriod(AssignmentPeriod):
    """Off-peak assignment period.

    The major difference compared to a regular assignment period is that
    bus speeds are taken from free-flow assignment in demand-calculation loop
    and transit assignment is hence not iterated.

    Car assignment is performed as usual.
    """

    def prepare(self, dist_unit_cost: Dict[str, float],
                day_scenario: int, save_matrices: bool):
        """Prepare network for assignment.

        Calculate road toll cost and specify car assignment.
        Set boarding penalties and attribute names.

        Parameters
        ----------
        dist_unit_cost : dict
            key : str
                Assignment class (car_work/truck/...)
            value : float
                Length multiplier to calculate link cost
        day_scenario : int
            EMME scenario linked to the whole day
        save_matrices : bool
            Whether matrices will be saved in Emme format for all time periods.
        """
        self._prepare_cars(dist_unit_cost, save_matrices)
        self._prepare_walk_and_bike(save_matrices=True)
        self._end_assignment_classes.add("walk")
        self._prepare_other(day_scenario, save_matrices)

    def _prepare_other(self, day_scenario: Dict[str, float],
                       save_matrices: bool):
        long_dist_transit_modes = {mode: TransitMode(
                mode, self, day_scenario, save_matrices, save_matrices)
            for mode in param.long_dist_simple_classes}
        self.assignment_modes.update(long_dist_transit_modes)
        self._prepare_transit(
            day_scenario, save_standard_matrices=True,
            save_extra_matrices=save_matrices,
            transit_classes=param.local_transit_classes)

    def init_assign(self):
        self._init_assign_transit()
        log.info("Pedestrian assignment started...")
        self.walk_mode.assign()
        log.info(f"Pedestrians assigned for scenario {self.emme_scenario.id}")
        self._set_bike_vdfs()
        self._assign_bikes()
        return self.get_soft_mode_impedances()

    def _init_assign_transit(self):
        """Assign transit for one time period with free-flow bus speed."""
        self._set_car_vdfs(use_free_flow_speeds=True)
        stopping_criteria = copy.copy(
            param.stopping_criteria["coarse"])
        stopping_criteria["max_iterations"] = 0
        self._assign_cars(stopping_criteria)
        self._assign_transit(
            param.local_transit_classes,
            delete_strat_files=self._delete_strat_files)

    def get_soft_mode_impedances(self):
        return self._get_impedances([self.bike_mode.name, self.walk_mode.name])

    def assign(self, modes: Iterable[str]) -> Dict[str, Dict[str, ndarray]]:
        """Assign cars for one time period.

        Parameters
        ----------
        modes : Set of str
            The assignment classes for which impedance matrices will be returned

        Get travel impedance matrices for one time period from assignment.
        Transit impedance is fetched from free-flow init assignment.

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (car_work/transit/...) : numpy 2-d matrix
        """
        if not self._separate_emme_scenarios:
            self._calc_background_traffic(include_trucks=True)
        self._assign_cars(self.stopping_criteria["coarse"])
        mtxs = self._get_impedances(modes)
        self._check_congestion()
        for ass_cl in param.car_classes:
            del mtxs["dist"][ass_cl]
        del mtxs["toll_cost"]
        del mtxs["train_users"]
        return mtxs


class TransitAssignmentPeriod(OffPeakPeriod):
    """Transit-only assignment period.

    The major difference compared to a regular assignment period is that
    bus speeds are taken from free-flow assignment and transit assignment
    is hence not iterated.

    Car assignment is not performed at all.
    """
    def __init__(self, *args, **kwargs):
        AssignmentPeriod.__init__(self, *args, **kwargs)
        self._end_assignment_classes -= set(
            param.private_classes + param.truck_classes)


    def prepare(self, dist_unit_cost: Dict[str, float],
                day_scenario: int, save_matrices: bool):
        """Prepare network for assignment.

        Calculate road toll cost and specify car assignment.
        Set boarding penalties and attribute names.

        Parameters
        ----------
        dist_unit_cost : dict
            key : str
                Assignment class (car_work/truck/...)
            value : float
                Length multiplier to calculate link cost
        day_scenario : int
            EMME scenario linked to the whole day
        save_matrices : bool
            Whether matrices will be saved in Emme format for all time periods.
        """
        self._prepare_cars(
            dist_unit_cost, save_matrices=False, car_classes=["car_leisure"],
            truck_classes=[])
        self.car_mode = self.assignment_modes.pop("car_leisure")
        self._prepare_other(day_scenario, save_matrices)

    def init_assign(self):
        self._init_assign_transit()
        self.car_mode.get_matrices()
        return []

    def get_soft_mode_impedances(self):
        return []

    def assign_trucks_init(self):
        pass

    def assign(self, *args) -> Dict[str, Dict[str, ndarray]]:
        """Get local transit impedance matrices for one time period.

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (transit_work/transit_leisure) : numpy 2-d matrix
        """
        mtxs = self._get_impedances(param.local_transit_classes)
        del mtxs["dist"]
        del mtxs["train_users"]
        return mtxs

    def end_assign(self,
                   assign_transit=True) -> Dict[str, Dict[str, ndarray]]:
        """Get transit impedance matrices for one time period.

        Long-distance mode impedances are included if assignment period
        was created with delete_extra_matrices option disabled.

        Parameters
        ----------
        assign_transit : bool (optional)
            Whether to assign transit for this time period

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (transit_work/...) : numpy 2-d matrix
        """
        if not assign_transit:
            return {}
        self._assign_transit(
            param.simple_transit_classes, calc_network_results=True,
            delete_strat_files=self._delete_strat_files)
        self._calc_transit_link_results()
        mtxs = self._get_impedances(self._end_assignment_classes)
        for tc in self.assignment_modes:
            self.assignment_modes[tc].release_matrices()
        return mtxs


class EndAssignmentOnlyPeriod(AssignmentPeriod):
    def assign(self, *args) -> None:
        return None
