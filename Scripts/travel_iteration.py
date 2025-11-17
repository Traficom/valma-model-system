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
from datatypes.person import Person
from datatypes.tour import Tour
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
                 base_zone_data_path: Path,
                 base_matrices_path: Path,
                 results_path: Path,
                 assignment_model: AssignmentModel,
                 submodel: str,
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
        self.car_dist_cost = cost_data["car_cost"]
        self.transit_cost = {data.pop("id"): data for data
            in cost_data["transit_cost"].values()}
        extra_dummies = cost_data.get("area_calibration", {})
        self._zone_datas = {
            model_area: ZoneData(
                zone_data_path, self.zone_numbers, submodel,
                model_area=model_area, extra_dummies=extra_dummies,
                car_dist_cost=self.car_dist_cost["car_work"]
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
        for file in parameters_path.rglob("*.json"):
            specification = json.loads(file.read_text("utf-8"))
            for dummies in extra_dummies.values():
                for subarea in dummies:
                    for mode, coeff in dummies[subarea].items():
                        if mode in specification["mode_choice"]:
                            (specification["mode_choice"][mode]
                                          ["generation"][subarea]) = coeff
            purpose = new_tour_purpose(
                specification, self._zone_datas, self.resultdata,
                cost_data["cost_changes"])
            required_time_periods = sorted(
                {tp for m in purpose.impedance_share.values() for tp in m})
            if required_time_periods == sorted(assignment_model.time_periods):
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
        self.dm = self._init_demand_model(
            home_based_work_purposes + other_work_purposes
            + home_based_leisure_purposes + other_leisure_purposes
            + sec_dest_purposes)
        self.travel_modes = {mode: True for purpose in self.dm.tour_purposes
            for mode in purpose.modes}  # Dict instead of set, to preserve order
        self.external_purpose = ExternalPurpose(numpy.array(self.zone_numbers))
        self.mode_share: List[Dict[str,Any]] = []
        self.convergence = []

    def _init_demand_model(self, tour_purposes: List[TourPurpose]):
        return DemandModel(
            self._zone_datas["domestic"], self.resultdata, tour_purposes,
            is_agent_model=False)

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
                        Assignment class (car_work/transit/...)
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
                        purpose, "car_leisure", purpose_impedance)
            else:
                if param.assignment_classes[purpose.name] == "leisure":
                    for tp_imp in previous_iter_impedance.values():
                        for imp in tp_imp.values():
                            for mode in ("car_work", "transit_work"):
                                imp.pop(mode, None)
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
        car_matrices = {}
        with long_dist_matrices.open(
                "demand", "vrk", zone_numbers,
                self._zone_datas["domestic"].mapping, long_dist_classes) as mtx:
            for ass_class in long_dist_classes:
                demand = Demand(self.external_purpose, ass_class, mtx[ass_class])
                self.dtm.add_demand(demand)
                if ass_class in param.car_classes:
                    car_matrices[ass_class] = demand.matrix
            log.info(f"Demand imported from {long_dist_matrices.path}")
        if car_matrices:
            with self.resultmatrices.open(
                    "demand", "vrk", zone_numbers, m='w') as mtx:
                for ass_class in car_matrices:
                    mtx[ass_class] = car_matrices[ass_class]

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
        self.ass_model.prepare_network(self.car_dist_cost, car_time_files)
        self.dtm = dt.DirectDepartureTimeModel(self.ass_model)

        self.ass_model.calc_transit_cost(self.transit_cost)
        Purpose.distance = self.ass_model.beeline_dist
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

        # Add beeline distance dummy
        zd = self._zone_datas["domestic"]
        idx = numpy.isin(self.zone_numbers, zd.zone_numbers)
        zd["beeline"] = Purpose.distance[numpy.ix_(idx, idx)]

        # Perform traffic assignment and get result impedance,
        # for each time period
        impedance = {}
        for ap in self.ass_model.assignment_periods:
            tp = ap.name
            log.info(f"--- ASSIGNING PERIOD {tp.upper()} ---")
            ap.assign_trucks_init()
            impedance[tp] = (ap.end_assign(not is_car_end_assignment)
                             if is_end_assignment
                             else ap.assign(self.travel_modes))
            if is_end_assignment:
                if not isinstance(self.ass_model, MockAssignmentModel):
                    self._save_to_omx(impedance[tp], tp)
                impedance.clear()
        if is_end_assignment:
            self.ass_model.aggregate_results(
                self.resultdata, zd.aggregations.municipality_mapping)
            self._calculate_noise_areas()
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
        self.dtm.init_demand({**self.travel_modes, "van": True})

        self.dm.calculate_car_ownership(previous_iter_impedance)

        # Calculate demand and add external demand
        self._add_internal_demand(previous_iter_impedance, iteration=="last")
        if (not self.ass_model.use_free_flow_speeds
                and not isinstance(self.ass_model, MockAssignmentModel)):
            car_matrices = (self.basematrices if self.long_dist_matrices is None
                else self.long_dist_matrices)
            self._add_external_demand(car_matrices, param.car_classes)

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
                             else ap.assign(self.travel_modes))
            if iteration=="last":
                if not isinstance(self.ass_model, MockAssignmentModel):
                    self._save_to_omx(impedance[tp], tp)
                impedance.clear()
        if iteration=="last":
            self.ass_model.aggregate_results(
                self.resultdata, zd.aggregations.municipality_mapping)
            self._calculate_noise_areas()
            self.resultdata.flush()
        return impedance

    def _save_demand_to_omx(self, ap: AssignmentPeriod):
        zone_numbers = self.ass_model.zone_numbers
        tp = ap.name
        demand_sum_string = tp
        transport_classes = (param.car_classes + param.long_dist_simple_classes
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

    def _calculate_noise_areas(self):
        if not self.ass_model.use_free_flow_speeds:
            data = {}
            zd = self._zone_datas["domestic"]
            data["area"] = self.ass_model.calc_noise(
                zd.aggregations.municipality_mapping)
            pop = zd.aggregations.aggregate_array(zd["population"], "county")
            conversion = pandas.Series(zone_param.pop_share_per_noise_area)
            data["population"] = conversion * data["area"] * pop
            self.resultdata.print_data(data, "noise_areas.txt")

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
        for mode in self.travel_modes:
            demand = pandas.Series(0.0, self.zone_numbers, name=mode)
            dist = pandas.Series(0.0, self.zone_numbers, name=mode)
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


class AgentModelSystem(ModelSystem):
    """Object keeping track of all sub-models and tasks in agent model system.

    Agents are added one-by-one to departure time model,
    where they are (so far) split in deterministic fractions.
    
    Parameters
    ----------
    zone_data_path : str
        Directory path where input data for forecast year are found
    base_zone_data_path : str
        Directory path where input data for base year are found
    base_matrices_path : str
        Directory path where base demand matrices are found
    results_path : str
        Directory path where to store results
    assignment_model : assignment.abstract_assignment.AssignmentModel
        Assignment model wrapper used in model runs,
        can be EmmeAssignmentModel or MockAssignmentModel
    name : str
        Name of scenario, used for results subfolder
    """

    def _init_demand_model(self, tour_purposes: List[TourPurpose]):
        log.info("Creating synthetic population")
        random.seed(zone_param.population_draw)
        return DemandModel(
            self._zone_datas["domestic"], self.resultdata, tour_purposes,
            is_agent_model=True)

    def _add_internal_demand(self, previous_iter_impedance, is_last_iteration):
        """Produce tours and add fractions of them
        for each time-period to container in departure time model.

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
                        Assignment class (car_work/transit/...)
                    value : numpy.ndarray
                        Impedance (float 2-d matrix)
        is_last_iteration : bool (optional)
            If this is the last iteration, 
            secondary destinations are calculated for all modes
        """
        log.info("Demand calculation started...")
        random.seed(None)
        self.dm.car_use_model.calc_basic_prob()
        for purpose in self.dm.tour_purposes:
            for mode_demand in purpose.calc_basic_prob(
                    previous_iter_impedance, is_last_iteration):
                # `demand` contains matrices only for non-agent purposes
                self.dtm.add_demand(mode_demand)
        tour_probs = self.dm.generate_tour_probs()
        log.info("Assigning mode and destination for {} agents ({} % of total population)".format(
            len(self.dm.population), int(zone_param.agent_demand_fraction*100)))
        purpose = self.dm.purpose_dict["hoo"]
        sec_dest_tours = {mode: [defaultdict(list) for _ in purpose.orig_zone_numbers]
            for mode in purpose.modes}
        # Add keys for work-tour-related modes (e.g., "car_work"),
        # which refer to the same demand containers as for leisure tours.
        # They are all assigned as leisure trips.
        work_tours = {mode.replace("leisure", "work"): sec_dest_tours[mode]
                      for mode in sec_dest_tours}
        sec_dest_tours.update(work_tours)
        car_users = pandas.Series(
            0, self.zone_numbers[self.dm.car_use_model.bounds])
        for person in self.dm.population:
            person.decide_car_use()
            car_users[person.zone.number] += person.is_car_user
            person.add_tours(self.dm.purpose_dict, tour_probs)
            for tour in person.tours:
                tour.choose_mode(person.is_car_user)
                tour.choose_destination(sec_dest_tours)
        for purpose in self.dm.tour_purposes:
            try:
                purpose.model.cumul_dest_prob.clear()
            except AttributeError:
                pass
        car_share = car_users / self.dm.zone_population
        car_share.name = "car_share"
        self.dm.car_use_model.print_results(car_share, self.dm.zone_population)
        log.info("Primary destinations assigned")
        purpose = self.dm.purpose_dict["hoo"]
        purpose_impedance = purpose.transform_impedance(
            previous_iter_impedance)
        nr_threads = param.performance_settings["number_of_processors"]
        if nr_threads == "max":
            nr_threads = multiprocessing.cpu_count()
        elif nr_threads <= 0:
            nr_threads = 1
        bounds = next(iter(purpose.sources)).bounds
        modes = purpose.modes if is_last_iteration else ["car_leisure"]
        for mode in modes:
            threads = []
            for i in range(nr_threads):
                origs = range(i, bounds.stop - bounds.start, nr_threads)
                thread = threading.Thread(
                    target=self._distribute_tours,
                    args=(
                        mode, origs, sec_dest_tours[mode],
                        purpose_impedance[mode]))
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join()
        if is_last_iteration:
            random.seed(zone_param.population_draw)
            self.dm.predict_income()
            random.seed(None)
            fname0 = "agents"
            fname1 = "tours"
            # print person and tour attr to files
            self.resultdata.print_line("\t".join(Person.attr), fname0)
            self.resultdata.print_line("\t".join(Tour.attr), fname1)
            for person in self.dm.population:
                person.calc_income()
                self.resultdata.print_line(str(person), fname0)
                for tour in person.tours:
                    tour.calc_cost(previous_iter_impedance)
                    self.resultdata.print_line(str(tour), fname1)
            log.info("Results printed to files {} and {}".format(
                fname0, fname1))
        previous_iter_impedance.clear()
        dtm = dt.DepartureTimeModel(
            self.ass_model.nr_zones, self.ass_model.time_periods,
            self.travel_modes)
        for person in self.dm.population:
            for tour in person.tours:
                dtm.add_demand(tour)
        for tp in dtm.demand:
            for ass_class in dtm.demand[tp]:
                self.dtm.demand[tp][ass_class] = dtm.demand[tp][ass_class]
        log.info("Demand calculation completed")

    def _distribute_tours(self, mode, origs, sec_dest_tours, impedance):
        sec_dest_purpose = self.dm.purpose_dict["hoo"]
        for orig in origs:
                dests = list(sec_dest_tours[orig])
                probs = sec_dest_purpose.calc_sec_dest_prob(
                    mode, impedance, orig, dests).cumsum(axis=0)
                for j, dest in enumerate(dests):
                    for tour in sec_dest_tours[orig][dest]:
                        tour.choose_secondary_destination(probs[:, j])
