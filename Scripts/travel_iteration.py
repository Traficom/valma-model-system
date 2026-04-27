import threading
import multiprocessing
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Set, Union, Iterable, Optional, cast
import numpy # type: ignore
import pandas
import random
from collections import defaultdict
from assignment.abstract_assignment import AssignmentModel
from assignment.emme_assignment import EmmeAssignmentModel
from assignment.assignment_period import AssignmentPeriod
from assignment.mock_assignment import MockAssignmentModel

import utils.log as log
import assignment.departure_time as dt
from datahandling.resultdata import ResultsData
from datahandling.zonedata import ZoneData
from datahandling.matrixdata import MatrixData
from demand.trips import DemandModel
from demand.external import ExternalPurpose
from datatypes.purpose import new_tour_purpose
from datatypes.purpose import Purpose, TourPurpose, SecDestPurpose
from datatypes.demand import Demand
import parameters.assignment as param
import parameters.zone as zone_param


class ModelSystem:
    """Object keeping track of all sub-models and tasks in model system.
    
    Parameters
    ----------
    zone_data_path : Path
        Path where input data for forecast year are found
    cost_data_path : Path
        Path where cost data for forecast year are found
    base_zone_data_path : Path
        Directory path where input data for base year are found
    base_matrices_path : Path
        Directory path where base demand matrices are found
    results_path : Path
        Directory path where to store results
    assignment_model : assignment.abstract_assignment.AssignmentModel
        Assignment model wrapper used in model runs,
        can be EmmeAssignmentModel or MockAssignmentModel
    submodel: str
        Name of submodel, used for choosing appropriate zone mapping
    mode_dest_calibration_path : Path (optional)
        File path (.json) where mode and destination choice calibration
        coefficients are found
    municipality_calibration_path : Path (optional)
        File path (.txt) where municipality calibration coefficients are found
    long_dist_matrices_path: Path (optional)
        Directory path where long-distance demand is found.
        If None, long-distance demand is taken from base matrices.
    freight_matrices_path: Path (optional)
        Directory path where freight demand is found.
        If None, freight demand is taken from base matrices.
    """

    def __init__(self,
                 zone_data_path: Path,
                 cost_data_path: Path,
                 base_matrices_path: Path,
                 results_path: Path,
                 assignment_model: AssignmentModel,
                 submodel: str,
                 mode_dest_calibration_path: Optional[str] = None,
                 municipality_calibration_path: Optional[str] = None,
                 long_dist_matrices_path: Optional[Path] = None,
                 freight_matrices_path: Optional[Path] = None):
        self.ass_model = cast(Union[MockAssignmentModel,EmmeAssignmentModel], assignment_model) #type checker hint
        self.zone_numbers: numpy.ndarray = self.ass_model.zone_numbers

        # Input data
        self.basematrices = MatrixData(base_matrices_path / submodel)
        self.long_dist_matrices = (MatrixData(long_dist_matrices_path)
            if long_dist_matrices_path is not None else None)
        self.freight_matrices = (MatrixData(freight_matrices_path)
            if freight_matrices_path is not None else None)
        cost_data: dict = json.loads(cost_data_path.read_text("utf-8"))
        self.car_dist_cost = cost_data["vehicle_km_cost"]
        self.car_time_cost = cost_data["vehicle_hour_cost"]
        self.transit_cost = {data.pop("id"): data for data
            in cost_data["transit_cost"].values()}
        if mode_dest_calibration_path is None:
            mode_dummies = {}
            dest_dummies = {}
        else:
            path = Path(mode_dest_calibration_path)
            calibration_data: dict = json.loads(path.read_text("utf-8"))
            mode_dummies = calibration_data["mode_choice_calibration"]
            dest_dummies = calibration_data["destination_choice_calibration"]
        extra_dummies = {**mode_dummies, **dest_dummies}
        if municipality_calibration_path is None:
            municip_calib = {}
        else:
            path = Path(municipality_calibration_path)
            municip_calib = pandas.read_csv(path, sep="\t",
                index_col=["generation", "attraction"]).to_dict("series")
        self._zone_datas = {
            model_area: ZoneData(
                zone_data_path, self.zone_numbers, submodel,
                model_area=model_area, municipality_calibration=municip_calib,
                extra_dummies=extra_dummies,
                car_dist_cost=self.car_dist_cost["car"]
            ) for model_area in ["domestic"]}

        # Output data
        self.resultdata = ResultsData(results_path)
        self.resultmatrices = MatrixData(results_path / "Matrices" / submodel)
        parameters_path = Path(__file__).parent / "parameters" / "demand"
        home_based_work_purposes = []
        home_based_leisure_purposes = []
        sec_dest_purposes = []
        other_work_purposes = []
        other_leisure_purposes = []
        purpose_names = []
        for file in parameters_path.glob("*.json"):
            specification = json.loads(file.read_text("utf-8"))
            for dummies in mode_dummies.values():
                for subarea in dummies:
                    for mode, coeff in dummies[subarea].items():
                        if mode in specification["mode_choice"]:
                            (specification["mode_choice"][mode]
                                          ["generation"][subarea]) = coeff
            for dummies in dest_dummies.values():
                for subarea in dummies:
                    for mode, coeff in dummies[subarea].items():
                        if mode in specification["destination_choice"]:
                            (specification["destination_choice"][mode]
                                          ["attraction"][subarea]) = coeff
            purpose = new_tour_purpose(
                specification, self._zone_datas, self.resultdata,
                cost_data["cost_changes"])
            required_time_periods = sorted(
                {tp for m in purpose.impedance_share.values() for tp in m})
            if required_time_periods == sorted(assignment_model.time_periods):
                purpose_names.append(purpose.name)
                if isinstance(purpose, SecDestPurpose):
                    sec_dest_purposes.append(purpose)
                elif purpose.orig == "home":
                    if param.assignment_classes[purpose.name] == "work":
                        home_based_work_purposes.append(purpose)
                    else:
                        home_based_leisure_purposes.append(purpose)
                else:
                    if param.assignment_classes[purpose.name] == "work":
                        other_work_purposes.append(purpose)
                    else:
                        other_leisure_purposes.append(purpose)
        if len(purpose_names) != len(set(purpose_names)):
            msg = f"Duplicate tour purposes in demand parameters."
            log.error(msg)
            raise ValueError(msg)
        self.dm = self._init_demand_model(
            home_based_work_purposes + other_work_purposes
            + home_based_leisure_purposes + other_leisure_purposes
            + sec_dest_purposes)
        self.travel_modes = {mode: True for purpose in self.dm.tour_purposes
            for mode in purpose.modes}  # Dict instead of set, to preserve order
        self.ass_classes = set()
        for mode in self.travel_modes.keys():
            self.ass_classes.add(param.mode_impedance[mode])
        self.external_purpose = ExternalPurpose(numpy.array(self.zone_numbers))
        self.mode_share: List[Dict[str,Any]] = []
        self.convergence = []

    def _init_demand_model(self, tour_purposes: List[TourPurpose]):
        return DemandModel(
            self._zone_datas["domestic"], self.resultdata, tour_purposes)

    def _add_internal_demand(self, previous_iter_impedance, is_last_iteration):
        """Produce mode-specific demand matrices.

        Add them for each time-period to container in departure time model.

        Parameters
        ----------
        previous_iter_impedance : dict
            key : str
                Time period (aht/pt/iht)
            value : dict
                key : str
                    Impedance type (time/cost/dist)
                value : dict
                    key : str
                        Assignment class (car_drv/transit/...)
                    value : numpy.ndarray
                        Impedance (float 2-d matrix)
        is_last_iteration : bool (optional)
            If this is the last iteration, 
            secondary destinations are calculated for all modes
        """
        log.info("Demand calculation started...")
        for purpose in self.dm.tour_purposes:
            if isinstance(purpose, SecDestPurpose):
                purpose_impedance = purpose.calc_prob(
                    previous_iter_impedance, is_last_iteration)
                purpose.generate_tours()
                if is_last_iteration:
                    for mode in purpose.model.dest_choice_param:
                        self._distribute_sec_dests(
                            purpose, mode, purpose_impedance)
                else:
                    self._distribute_sec_dests(
                        purpose, "car_drv", purpose_impedance)
            else:
                for mode_demand in purpose.calc_demand(
                        previous_iter_impedance, is_last_iteration):
                    self.dtm.add_demand(mode_demand)
        previous_iter_impedance.clear()
        log.info("Demand calculation completed")

    def _add_external_demand(self,
                             long_dist_matrices: MatrixData,
                             long_dist_classes: Iterable[str]):
        class_list = ", ".join(long_dist_classes)
        log.info(f"Get matrices for {class_list}...")
        zone_numbers = self.ass_model.zone_numbers
        matrices_to_add = {}
        with long_dist_matrices.open(
                "demand", "vrk", zone_numbers,
                self._zone_datas["domestic"].mapping, long_dist_classes) as mtx:
            for ass_class in long_dist_classes:
                demand = Demand(self.external_purpose, ass_class, mtx[ass_class])
                self.dtm.add_demand(demand)
                if ass_class in param.car_classes + param.local_transit_classes:
                    matrices_to_add[ass_class] = demand.matrix
            log.info(f"Demand imported from {long_dist_matrices.path}")
        if matrices_to_add:
            with self.resultmatrices.open(
                    "demand", "vrk", zone_numbers, m='w') as mtx:
                for ass_class in matrices_to_add:
                    mtx[ass_class] = matrices_to_add[ass_class]

    # possibly merge with init
    def assign_base_demand(self, 
            is_end_assignment: bool = False,
            is_car_end_assignment: bool = False,
            car_time_files: Optional[List[str]] = None) -> Dict[str, Dict[str, numpy.ndarray]]:
        """Assign base demand to network (before first iteration).

        Parameters
        ----------
        is_end_assignment : bool (optional)
            If base demand is assigned without demand calculations
        is_car_end_assignment : bool (optional)
            If base demand is assigned only for cars

        Returns
        -------
        dict
            key : str
                Assignment class (car/transit/bike/walk)
            value : dict
                key : str
                    Impedance type (time/cost/dist)
                value : numpy.ndarray
                    Impedance (float 2-d matrix)
        car_time_files : list (optional)
            List of paths, where car time data is stored.
            If set, traffic assignment is all-or-nothing with speeds stored
            in `#car_time_xxx`. Overrides `use_free_flow_speeds`.
            List can be empty, if car times are already stored on network.
        """
        # create attributes and background variables to network
        self.ass_model.prepare_network(
            self.car_dist_cost, self.car_time_cost, car_time_files)
        self.dtm = dt.DirectDepartureTimeModel(self.ass_model)

        self.ass_model.calc_transit_cost(self.transit_cost)
        ZoneData.beeline_dist = self.ass_model.beeline_dist
        if not isinstance(self.ass_model, MockAssignmentModel):
            with self.resultmatrices.open(
                    "beeline", "", self.ass_model.zone_numbers, m="w") as mtx:
                mtx["all"] = Purpose.distance
        for ap in self.ass_model.assignment_periods:
            tp = ap.name
            log.info(f"Initializing assignment for period {tp}...")
            if (is_end_assignment
                    or (not self.ass_model.use_free_flow_speeds
                        and car_time_files is None
                        and not isinstance(self.ass_model, MockAssignmentModel))):
                with self.basematrices.open(
                        "demand", tp, self.ass_model.zone_numbers,
                        transport_classes=ap.assignment_modes) as mtx:
                    for ass_class in ap.assignment_modes:
                        self.dtm.demand[tp][ass_class] = mtx[ass_class]
            if not is_car_end_assignment:
                ap.init_assign()
        if self.long_dist_matrices is not None:
            self.dtm.init_demand(param.long_dist_simple_classes)
            self._add_external_demand(
                self.long_dist_matrices, param.long_dist_simple_classes)
        if self.freight_matrices is not None:
            self.dtm.init_demand(param.truck_classes)
            self._add_external_demand(
                self.freight_matrices, param.truck_classes)

        # Perform traffic assignment and get result impedance,
        # for each time period
        impedance = {}
        for ap in self.ass_model.assignment_periods:
            tp = ap.name
            log.info(f"--- ASSIGNING PERIOD {tp.upper()} ---")
            ap.assign_trucks_init()
            impedance[tp] = (ap.end_assign(not is_car_end_assignment)
                             if is_end_assignment
                             else ap.assign(self.ass_classes))
            if is_end_assignment:
                if not isinstance(self.ass_model, MockAssignmentModel):
                    self._save_to_omx(impedance[tp], tp)
                impedance.clear()
        if is_end_assignment:
            self.ass_model.aggregate_results(self.resultdata)
            self.resultdata.flush()
        return impedance

    def run_iteration(self, previous_iter_impedance, iteration=None):
        """Calculate demand and assign to network.

        Parameters
        ----------
        previous_iter_impedance : dict
            key : str
                Assignment class (car/transit/bike/walk)
            value : dict
                key : str
                    Impedance type (time/cost/dist)
                value : numpy.ndarray
                    Impedance (float 2-d matrix)
        iteration : int or str (optional)
            Iteration number (0, 1, 2, ...) or "last"
            If this is the last iteration, 
            secondary destinations are calculated for all modes,
            congested assignment is performed,
            and matrix and assignment results are printed.
        Returns
        -------
        dict
            key : str
                Assignment class (car/transit/bike/walk)
            value : dict
                key : str
                    Impedance type (time/cost/dist)
                value : numpy.ndarray
                    Impedance (float 2-d matrix)
        """
        impedance = {}
        self.dtm.init_demand(self.ass_classes | {"van"})

        self.dm.calculate_car_ownership(previous_iter_impedance)

        # Calculate demand and add external demand
        self._add_internal_demand(previous_iter_impedance, iteration=="last")
        if (not self.ass_model.use_free_flow_speeds
                and not isinstance(self.ass_model, MockAssignmentModel)):
            matrices = (self.basematrices if self.long_dist_matrices is None
                else self.long_dist_matrices)
            self._add_external_demand(
                matrices, param.car_classes + param.local_transit_classes)

        # Add vans and save demand matrices
        zd = self._zone_datas["domestic"]
        for ap in self.ass_model.assignment_periods:
            self.dtm.add_vans(ap.name, zd.nr_zones)
            if (iteration=="last"
                    and not isinstance(self.ass_model, MockAssignmentModel)):
                self._save_demand_to_omx(ap)

        # Log mode shares
        is_in_submodel = zd.is_in_submodel
        idx = pandas.Series(False, self.zone_numbers)
        idx[is_in_submodel.index] = is_in_submodel
        tours, _ = self._get_mode_tours()
        sum_all = sum(tours.values())[idx].sum()
        mode_shares = {}
        for mode in tours:
            share = tours[mode][idx].sum() / sum_all
            mode_shares[mode] = share
            log.info(f"Mode shares ({iteration} iteration): {mode} : {round(100*share)} %")
        self.mode_share.append(mode_shares)

        if iteration == "last":
            self._export_model_results()
            self._export_accessibility()

        # Calculate convergence and empty result buffer
        gap = self.dtm.calc_gaps()
        log.info("Demand model convergence in iteration {} is {:1.5f}".format(
            iteration, gap["rel_gap"]))
        self.convergence.append(gap)
        self.resultdata._df_buffer["demand_convergence.txt"] = pandas.DataFrame(
            self.convergence)
        self.resultdata.flush()

        # Calculate and return traffic impedance
        for ap in self.ass_model.assignment_periods:
            tp = ap.name
            log.info(f"--- ASSIGNING PERIOD {tp.upper()} ---")
            impedance[tp] = (ap.end_assign() if iteration=="last"
                             else ap.assign(self.ass_classes))
            if iteration=="last":
                if not isinstance(self.ass_model, MockAssignmentModel):
                    self._save_to_omx(impedance[tp], tp)
                impedance.clear()
        if iteration=="last":
            self.ass_model.aggregate_results(self.resultdata)
            self.resultdata.flush()
        return impedance

    def _save_demand_to_omx(self, ap: AssignmentPeriod):
        zone_numbers = self.ass_model.zone_numbers
        tp = ap.name
        demand_sum_string = tp
        transport_classes = (param.car_classes + param.simple_transit_classes
            if self.ass_model.use_free_flow_speeds
            else ap.assignment_modes)
        with self.resultmatrices.open("demand", tp, zone_numbers, m='w') as mtx:
            for ass_class in transport_classes:
                demand = self.dtm.demand[tp][ass_class]
                if (self.ass_model.use_free_flow_speeds
                    and ass_class in param.intermodals):
                    for intermodal in param.intermodals[ass_class]:
                        demand += self.dtm.demand[tp][intermodal]
                mtx[ass_class] = demand
                demand_sum_string += "\t{:8.0f}".format(demand.sum())
        self.resultdata.print_line(demand_sum_string, "result_summary")
        log.info("Saved demand matrices for " + str(tp))

    def _save_to_omx(self, impedance, tp):
        zone_numbers = self.ass_model.zone_numbers
        for mtx_type in impedance:
            with self.resultmatrices.open(mtx_type, tp, zone_numbers, m='w') as mtx:
                for ass_class in impedance[mtx_type]:
                    mtx[ass_class] = impedance[mtx_type][ass_class]

    def _export_accessibility(self):
        for purpose in self.dm.tour_purposes:
            for logsum in purpose.model.accessibility.values():
                self.resultdata.print_data(logsum, f"accessibility.txt")
    
    def _export_model_results(self):
        self.resultdata.print_data(
            self._zone_datas["domestic"].zone_values, "zonedata_input.txt")
        gen_tours_purpose = {purpose.name: purpose.generated_tours_all
                             for purpose in self.dm.tour_purposes}
        self.resultdata.print_data(
            gen_tours_purpose, "zone_generation_by_purpose.txt")
        attr_tours_purpose = {purpose.name: purpose.attracted_tours_all
                              for purpose in self.dm.tour_purposes}
        self.resultdata.print_data(
            attr_tours_purpose, "zone_attraction_by_purpose.txt")
        gen_dist_purpose = {
            purpose.name: purpose.generated_dist_all / purpose.generated_tours_all
                              for purpose in self.dm.tour_purposes}
        self.resultdata.print_data(
            gen_dist_purpose, "zone_generation_dist_by_purpose.txt")
        attr_dist_purpose = {
            purpose.name: purpose.attracted_dist_all / purpose.attracted_tours_all
                              for purpose in self.dm.tour_purposes}
        self.resultdata.print_data(
            attr_dist_purpose, "zone_attraction_dist_by_purpose.txt")
        tours, dists = self._get_mode_tours()
        self.resultdata.print_data(tours, "zone_generation_by_mode.txt")
        self.resultdata.print_data(dists, "zone_generation_dist_by_mode.txt")
        tours, dists = self._get_mode_tours(generation=False)
        self.resultdata.print_data(tours, "zone_attraction_by_mode.txt")
        self.resultdata.print_data(dists, "zone_attraction_dist_by_mode.txt")
        for purpose in self.dm.tour_purposes:
            self.resultdata.print_concat(
                purpose.generation_mode_shares, "purpose_mode_shares.txt")
            self.resultdata.print_concat(
                purpose.tour_lengths, "tour_lengths.txt")
            for mapping in purpose.aggregates:
                self.resultdata.print_matrices(
                    purpose.aggregates[mapping],
                    f"aggregated_demand_{mapping}", purpose.name)
            for mode in purpose.within_zone_tours:
                self.resultdata.print_data(
                    purpose.within_zone_tours[mode], "within_zone_tours.txt")

    def _get_mode_tours(self, generation = True):
        tours: Dict[str, pandas.Series] = {}
        dists: Dict[str, pandas.Series] = {}
        idx = pandas.Index(self.zone_numbers, name="analysis_zone_id")
        for mode in self.travel_modes:
            demand = pandas.Series(0.0, idx, name=mode)
            dist = pandas.Series(0.0, idx, name=mode)
            for purpose in self.dm.tour_purposes:
                if mode in purpose.modes and purpose.dest != "source":
                    if generation:
                        bounds = (next(iter(purpose.sources)).bounds
                            if isinstance(purpose, SecDestPurpose)
                            else purpose.bounds)
                        demand[bounds] += purpose.generated_tours[mode]
                        dist[bounds] += purpose.generated_distance[mode]
                    else:
                        bounds = purpose.dest_interval
                        demand[bounds] += purpose.attracted_tours[mode]
                        dist[bounds] += purpose.attracted_distance[mode]
            tours[mode] = demand
            dists[mode] = dist / demand
        return tours, dists

    def _distribute_sec_dests(self, purpose, mode, impedance):
        threads = []
        demand = []
        nr_threads = param.performance_settings["number_of_processors"]
        if nr_threads == "max":
            nr_threads = multiprocessing.cpu_count()
        elif nr_threads <= 0:
            nr_threads = 1
        bounds = next(iter(purpose.sources)).bounds
        for i in range(nr_threads):
            # Take a range of origins, for which this thread
            # will calculate secondary destinations
            origs = range(i, bounds.stop - bounds.start, nr_threads)
            # Results will be saved in a temp dtm, to avoid memory clashes
            dtm = dt.DepartureTimeModel(
                self.ass_model.nr_zones, self.ass_model.time_periods, [mode])
            demand.append(dtm)
            thread = threading.Thread(
                target=self._distribute_tours,
                args=(dtm, purpose, mode, impedance, origs))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        for dtm in demand:
            for tp in dtm.demand:
                for ass_class in dtm.demand[tp]:
                    self.dtm.demand[tp][ass_class] += dtm.demand[tp][ass_class]

    def _distribute_tours(self, container, purpose, mode, impedance, origs):
        for orig in origs:
            demand = purpose.distribute_tours(mode, impedance[mode], orig)
            container.add_demand(demand)
