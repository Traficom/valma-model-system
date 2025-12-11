from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Optional, Iterable
import numpy # type: ignore
import pandas
if TYPE_CHECKING:
    from datahandling.matrixdata import MatrixData


import utils.log as log
from utils.validate_assignment import divide_matrices, output_od_los
import parameters.assignment as param
import parameters.zone as zone_param
from assignment.abstract_assignment import AssignmentModel, Period


class MockAssignmentModel(AssignmentModel):
    def __init__(self, matrices: MatrixData,
                 use_free_flow_speeds: bool = False,
                 time_periods: Dict[str, str]=param.time_periods,
                 delete_extra_matrices: bool = False,
                 delete_strat_files: bool = False):
        self.matrices = matrices
        log.info("Reading matrices from " + str(self.matrices.path))
        self.use_free_flow_speeds = use_free_flow_speeds
        end_ass_classes = ((param.private_classes + param.local_transit_classes)
            if delete_extra_matrices else param.transport_classes)
        self.time_periods = {}
        cls = globals()
        for tp, class_name in time_periods.items():
            self.time_periods[tp] = (cls[class_name] if class_name in cls
                                     else MockPeriod)
        self.assignment_periods = [self.time_periods[tp](
                tp, matrices, end_ass_classes)
            for tp in time_periods]

    @property
    def zone_numbers(self) -> List[int]:
        """List of all zone numbers."""
        return next(iter(self.assignment_periods)).zone_numbers

    @property
    def mapping(self) -> Dict[int, int]:
        """Dictionary of zone numbers and corresponding indices."""
        return next(iter(self.assignment_periods)).mapping

    @property
    def nr_zones(self) -> int:
        """int: Number of zones in assignment model."""
        return len(self.zone_numbers)

    @property
    def beeline_dist(self):
        with self.matrices.open("beeline", "") as mtx:
            matrix = mtx["all"]
        return matrix

    def calc_transit_cost(self, fare):
        pass

    def aggregate_results(self, resultdata, mapping):
        pass

    def calc_noise(self, mapping):
        return pandas.Series(0.0, mapping.drop_duplicates())

    def prepare_network(self, car_dist_unit_cost: Dict[str, float], *args):
        for ap in self.assignment_periods:
            ap.dist_unit_cost = car_dist_unit_cost

    def init_assign(self):
        pass


class MockPeriod(Period):
    def __init__(self,
                 name: str, matrices: MatrixData,
                 end_assignment_classes: Iterable[str]):
        self.name = name
        self.matrices = matrices
        self.assignment_modes = param.simple_transport_classes
        self._end_assignment_classes = set(end_assignment_classes)

    @property
    def zone_numbers(self) -> List[int]:
        """List of all zone numbers."""
        with self.matrices.open("beeline", "") as mtx:
            zone_numbers = mtx.zone_numbers
        return zone_numbers

    @property
    def mapping(self)  -> Dict[int, int]:
        """Dictionary of zone numbers and corresponding indices."""
        with self.matrices.open("beeline", "") as mtx:
            mapping = mtx.mapping
        return mapping

    def init_assign(self):
        return self.get_soft_mode_impedances()

    def get_soft_mode_impedances(self):
        """Get travel impedance matrices for walk and bike.

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (walk/bike) : numpy 2-d matrix
        """
        return self._get_impedances(["walk", "bike"])

    def assign_trucks_init(self):
        pass

    def assign(self, modes: Iterable[str]
            ) -> Dict[str, Dict[str, numpy.ndarray]]:
        """Get travel impedance matrices for one time period from files.

        Parameters
        ----------
        modes : Set of str
            The assignment classes for which impedance matrices will be returned

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (car_work/transit_leisure/...) : numpy 2-d matrix
        """
        mtxs = self._get_impedances(modes)
        for ass_cl in param.car_classes:
            mtxs["cost"][ass_cl] = (self.dist_unit_cost[ass_cl]
                                    * mtxs["dist"][ass_cl])
        if "toll_cost" in mtxs:
            for ass_cl in mtxs["toll_cost"]:
                mtxs["cost"][ass_cl] += mtxs["toll_cost"][ass_cl]
            del mtxs["toll_cost"]
        for ass_cl in param.car_classes + param.transit_classes:
            if ass_cl in mtxs["dist"]:
                del mtxs["dist"][ass_cl]
        return mtxs

    def end_assign(self) -> Dict[str, Dict[str, numpy.ndarray]]:
        """ Get travel impedance matrices for one time period from files.

        Long-distance mode impedances are included if assignment period
        was created with delete_extra_matrices option disabled.

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (car_work/transit_leisure/...) : numpy 2-d matrix
        """
        return self._get_impedances(self._end_assignment_classes)

    def _get_impedances(
            self, assignment_classes: Iterable[str],
            impedance_output: Iterable[str] = param.basic_impedance_output):
        impedance_output = [mtx_type for mtx_type in impedance_output
            if mtx_type != "toll_cost"]
        mtxs = {mtx_type: self._get_matrices(mtx_type, assignment_classes)
            for mtx_type in impedance_output}
        # TODO This is a temporary solution to maintain backwards compability.
        # Fresh LOS matrices will from now on include toll_cost,
        # so when the old LOS matrix folders are no longer in use,
        # we can remove this separate handling of toll_cost.
        try:
            mtxs["toll_cost"] = self._get_matrices(
                "toll_cost", assignment_classes)
        except FileNotFoundError:
            pass
        for mtx_type in mtxs:
            for mode, mtx in mtxs[mtx_type].items():
                output_od_los(mtx, self.mapping, mtx_type, mode)
        for mode in mtxs["time"]:
            try:
                divide_matrices(
                    mtxs["dist"][mode], mtxs["time"][mode]/60,
                    f"OD speed (km/h) {mode}")
            except KeyError:
                pass
        return mtxs

    def _get_matrices(self,
                      mtx_type: str,
                      assignment_classes: Iterable[str]
            ) -> Dict[str, numpy.ndarray]:
        """Get all matrices of specified type.
        
        Parameters
        ----------
        mtx_type : str
            Type (demand/time/transit/...)
        assignment_classes : Set of str
            The assignment classes for which impedance matrices will be returned

        Return
        ------
        dict
            Subtype (car_work/truck/inv_time/...) : numpy 2-d matrix
                Matrix of the specified type
        """
        with self.matrices.open(
                mtx_type, self.name, transport_classes=[]) as mtx:
            matrix_list = set(assignment_classes) & set(mtx.matrix_list)
            matrices = {mode: mtx[mode] for mode in matrix_list}
            new_zone_numbers = mtx.zone_numbers
        for mode in matrices:
            if numpy.any(matrices[mode] > 1e10):
                log.warn(f"Matrix with infinite values: {mtx_type} : {mode}.")
            idx = numpy.where(numpy.isin(self.zone_numbers, new_zone_numbers))[0]
            matrices[mode] = matrices[mode][idx[:, None], idx]
        return matrices

    def get_matrix(self,
                    ass_class: str,
                    matrix_type: str = "demand") -> numpy.ndarray:
        with self.matrices.open(matrix_type, self.name) as mtx:
            matrix = mtx[ass_class]
            new_zone_numbers = mtx.zone_numbers
        idx = numpy.where(numpy.isin(self.zone_numbers, new_zone_numbers))[0]
        return matrix[idx[:, None], idx]

    def set_matrix(self,
                    ass_class: str,
                    matrix: numpy.ndarray):
        with self.matrices.open("demand", self.name, self.zone_numbers, m='a') as mtx:
            mtx[ass_class] = matrix


class WholeDayPeriod(MockPeriod):
    def __init__(self, *args, **kwargs):
        MockPeriod.__init__(self, *args, **kwargs)
        self.assignment_modes = (param.car_classes
                                 + param.long_distance_transit_classes)

    def end_assign(self) -> Dict[str, Dict[str, numpy.ndarray]]:
        """ Get travel impedance matrices for whole day from files.

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (car_work/transit_leisure/...) : numpy 2-d matrix
        """
        return self._get_impedances(self.assignment_modes)

    def _get_impedances(self, assignment_classes):
        return MockPeriod._get_impedances(
            self, assignment_classes, param.impedance_output)


class OffPeakPeriod(MockPeriod):
    def end_assign(self) -> Dict[str, Dict[str, numpy.ndarray]]:
        """Get travel impedance matrices for one time period from files.

        Long-distance mode impedances are included if assignment period
        was created with delete_extra_matrices option disabled.

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (car_work/transit_leisure/...) : numpy 2-d matrix
        """
        self._end_assignment_classes.add("walk")
        return self._get_impedances(self._end_assignment_classes)


class TransitAssignmentPeriod(OffPeakPeriod):
    def __init__(self, *args, **kwargs):
        MockPeriod.__init__(self, *args, **kwargs)
        self.assignment_modes = param.simple_transit_classes
        self._end_assignment_classes -= set(
            param.private_classes + param.truck_classes)

    def assign(self, *args) -> Dict[str, Dict[str, numpy.ndarray]]:
        """Get local transit impedance matrices for one time period.

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (transit_work/transit_leisure) : numpy 2-d matrix
        """
        mtxs = self._get_impedances(param.local_transit_classes)
        del mtxs["dist"]
        if "toll_cost" in mtxs:
            del mtxs["toll_cost"]
        return mtxs


class EndAssignmentOnlyPeriod(MockPeriod):
    def assign(self, *args) -> None:
        return None
