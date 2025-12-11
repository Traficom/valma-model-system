from __future__ import annotations
import numpy # type: ignore
import pandas # type: ignore
import copy
import json
from pathlib import Path

from typing import TYPE_CHECKING, Dict, Union, Iterable, Optional
import utils.log as log
from utils.validate_assignment import divide_matrices, output_od_los
import parameters.assignment as param
from assignment.datatypes.assignment_mode import AssignmentMode, BikeMode, WalkMode
from assignment.datatypes.car import CarMode, TruckMode
from assignment.datatypes.car_specification import CarSpecification
from assignment.datatypes.transit import TransitMode, MixedMode
from assignment.abstract_assignment import Period
if TYPE_CHECKING:
    from assignment.emme_bindings.emme_project import EmmeProject
    from emme_context.modeller.emmebank import Scenario # type: ignore


class AssignmentPeriod(Period):
    """
    EMME assignment period definition.

    This typically represents an hour of the day, which may or may not
    have a dedicated EMME scenario. In case it does not have its own
    EMME scenario, assignment results are stored only in extra attributes.
    """
    def __init__(self, name: str, emme_scenario: int,
                 emme_context: EmmeProject,
                 separate_emme_scenarios: bool = False,
                 use_stored_speeds: bool = False,
                 delete_extra_matrices: bool = False,
                 delete_strat_files: bool = False):
        """
        Initialize assignment period.

        Parameters
        ----------
        name : str
            Time period name (aht/pt/iht)
        emme_scenario : int
            EMME scenario linked to the time period
        emme_context : assignment.emme_bindings.emme_project.EmmeProject
            Emme project to connect to this assignment
        separate_emme_scenarios : bool (optional)
            Whether separate scenarios have been created in EMME
            for storing time-period specific network results.
        use_stored_speeds : bool (optional)
            Whether traffic assignment is all-or-nothing with speeds stored
            in `#car_time_xxx`. Overrides `use_free_flow_speeds` if this is
            also set to `True`.
        delete_extra_matrices : bool (optional)
            If True, only matrices needed for demand calculation will be
            returned from end assignment.
        delete_strat_files : bool (optional)
            If True, strategy files will be deleted immediately after usage.
        """
        self.name = name
        self.emme_scenario: Scenario = emme_context.modeller.emmebank.scenario(
            emme_scenario)
        self.emme_project = emme_context
        self._separate_emme_scenarios = separate_emme_scenarios
        self._delete_strat_files = delete_strat_files
        self.use_stored_speeds = use_stored_speeds
        self.stopping_criteria = copy.deepcopy(
            param.stopping_criteria)
        if use_stored_speeds:
            for criteria in self.stopping_criteria.values():
                criteria["max_iterations"] = 0
        self._end_assignment_classes = set(param.private_classes
                                           + param.local_transit_classes
            if delete_extra_matrices else param.simple_transport_classes)
        self.assignment_modes: Dict[str, AssignmentMode] = {}

    def extra(self, attr: str) -> str:
        """Add prefix "@" and time-period suffix.

        Parameters
        ----------
        attr : str
            Attribute string to modify

        Returns
        -------
        str
            Modified string
        """
        return "@{}_{}".format(attr, self.name)

    def netfield(self, attr: str) -> str:
        """Add prefix "#" and time-period suffix.

        Parameters
        ----------
        attr : str
            Attribute string to modify

        Returns
        -------
        str
            Modified string
        """
        return "#{}_{}".format(attr, self.name)

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
            Whether matrices will be saved in Emme format for all time periods
        """
        self._prepare_cars(dist_unit_cost, save_matrices)
        self._prepare_walk_and_bike(save_matrices=False)
        self._prepare_transit(day_scenario, save_matrices, save_matrices)

    def _prepare_cars(self, dist_unit_cost: Dict[str, float],
                      save_matrices: bool,
                      car_classes: Iterable[str] = param.car_and_van_classes,
                      truck_classes: Iterable[str] = param.truck_classes):
        include_toll_cost = self.emme_scenario.network_field(
            "LINK", self.netfield("hinta")) is not None
        car_modes = {mode: CarMode(
                mode, self, dist_unit_cost[mode], include_toll_cost,
                save_matrices)
            for mode in car_classes}
        truck_modes = {mode: TruckMode(
                mode, self, dist_unit_cost[mode], include_toll_cost,
                save_matrices)
            for mode in truck_classes}
        modes = {**car_modes, **truck_modes}
        if include_toll_cost:
            self._calc_road_cost(modes.values())
        self.assignment_modes.update(modes)
        self._car_spec = CarSpecification(modes)

    def _prepare_walk_and_bike(self, save_matrices: bool):
        self.bike_mode = BikeMode("bike", self, save_matrices)
        self.walk_mode = WalkMode("walk", self, save_matrices)
        self.assignment_modes.update({
            "bike": self.bike_mode,
            "walk": self.walk_mode,
        })

    def _prepare_transit(
            self, day_scenario: int, save_standard_matrices: bool,
            save_extra_matrices: bool,
            transit_classes: Iterable[str] = param.simple_transit_classes,
            mixed_classes: Iterable[str] = [],
            dist_unit_cost: Optional[float] = None):
        transit_modes = {mode: TransitMode(
                mode, self, day_scenario, save_standard_matrices,
                save_extra_matrices)
            for mode in transit_classes}
        self.assignment_modes.update(transit_modes)
        mixed_modes = {mode: MixedMode(
                mode, self, day_scenario, dist_unit_cost,
                save_standard_matrices, save_extra_matrices)
            for mode in mixed_classes}
        self.assignment_modes.update(mixed_modes)
        self._calc_boarding_penalties()
        self._set_transit_vdfs()
        self._set_walk_time()
        self._long_distance_trips_assigned = False

    def init_assign(self):
        return []

    def get_soft_mode_impedances(self):
        """Get travel impedance matrices for walk and bike.

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (walk/bike) : numpy 2-d matrix
        """
        return []

    def assign_trucks_init(self):
        self._set_car_vdfs(use_free_flow_speeds=True)
        self._init_truck_times()
        self._assign_trucks()
        self._calc_background_traffic(include_trucks=True)
        self._set_car_vdfs()

    def assign(self, *args) -> Dict[str, Dict[str, numpy.ndarray]]:
        """Assign cars and transit for one time period.

        Get travel impedance matrices for one time period from assignment.

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (car_work/transit/...) : numpy 2-d matrix
        """
        if not self._separate_emme_scenarios:
            self._calc_background_traffic(include_trucks=True)
        self._assign_cars(self.stopping_criteria["coarse"])
        self._assign_transit(delete_strat_files=self._delete_strat_files)
        mtxs = self._get_impedances(
            param.car_classes + param.local_transit_classes)
        self._check_congestion()
        del mtxs["dist"]
        del mtxs["toll_cost"]
        return mtxs

    def end_assign(self,
                   assign_transit=True) -> Dict[str, Dict[str, numpy.ndarray]]:
        """Assign bikes, cars, trucks and transit for one time period.

        Get travel impedance matrices for one time period from assignment.

        Parameters
        ----------
        assign_transit : bool (optional)
            Whether to assign transit (default: true)

        Returns
        -------
        dict
            Type (time/cost/dist) : dict
                Assignment class (car_work/transit/...) : numpy 2-d matrix
        """
        self._set_bike_vdfs()
        self._assign_bikes()
        self._set_car_vdfs()
        if not self._separate_emme_scenarios:
            self._calc_background_traffic(include_trucks=True)
        self._assign_cars(self.stopping_criteria["fine"])
        self._set_car_vdfs(use_free_flow_speeds=True)
        self._assign_trucks()
        if assign_transit:
            self._assign_transit(
                param.simple_transit_classes, calc_network_results=True,
                delete_strat_files=self._delete_strat_files)
            self._calc_transit_link_results()
        else:
            self._end_assignment_classes -= set(param.transit_classes)
        mtxs = self._get_impedances(self._end_assignment_classes)
        self._check_congestion()
        for tc in self.assignment_modes:
            self.assignment_modes[tc].release_matrices()
        return mtxs

    def _get_impedances(self, assignment_classes: Iterable[str]):
        mtxs = {tc: self.assignment_modes[tc].get_matrices()
            for tc in assignment_classes if tc != "car_pax"}
        for mode in mtxs:
            try:
                divide_matrices(
                    mtxs[mode]["dist"], mtxs[mode]["time"]/60,
                    f"OD speed (km/h) {mode}")
            except KeyError:
                pass
            for mtx_type, mtx in mtxs[mode].items():
                output_od_los(mtx, self.mapping, mtx_type, mode)
                if numpy.any(mtx > 1e10):
                    log.warn(f"Matrix with infinite values: {mtx_type} {mode}")
        impedance = {mtx_type: {mode: mtxs[mode][mtx_type]
                for mode in mtxs if mtx_type in mtxs[mode]}
            for mtx_type in param.impedance_output}
        return impedance

    def _check_congestion(self):
        for car_class in param.car_classes:
            mode: CarMode = self.assignment_modes[car_class]
            log.debug(f"Maximum {self.name} {car_class} link congestion "
                      + f"is {mode.max_congestion:.0%} of free flow time")
            if mode.max_congestion == 0:
                log.warn(f"No car congestion in time period {self.name}!")

    @property
    def mapping(self) -> Dict[int, int]:
        """Dictionary of zone numbers and corresponding indices."""
        mapping = {}
        for idx, zone in enumerate(self.emme_scenario.zone_numbers):
            mapping[zone] = idx
        return mapping

    def calc_transit_cost(self, fares: pandas.DataFrame):
        """Insert line costs.
        
        Parameters
        ----------
        fares : pandas.DataFrame
            Transit fare zone specification
        """
        network = self.emme_scenario.get_network()
        penalty_attr = param.line_penalty_attr.replace("us", "data")
        op_attr = param.line_operator_attr.replace("ut", "data")
        long_dist_transit_modes = list({mode for mode_set
            in param.long_dist_transit_modes.values() for mode in mode_set})
        transit_modes = long_dist_transit_modes + param.local_transit_modes
        for mode in long_dist_transit_modes:
            if network.mode(mode) is None:
                raise AttributeError(f"Long-dist mode {mode} does not exist.")
        for line in network.transit_lines():
            if line.mode.id in transit_modes:
                fare = fares[line[op_attr]]
                for segment in line.segments():
                    segment[param.dist_fare_attr] = (fare["dist_single"]
                                                    * segment.link.length)
                    segment[penalty_attr] = segment[param.dist_fare_attr]
                line[param.board_fare_attr] = fare["firstb_single"]
                line[param.board_long_dist_attr] = (line[param.board_fare_attr]
                    if line.mode.id in long_dist_transit_modes else 0)
        self.emme_scenario.publish_network(network)

    def transit_results_links_nodes(self):
        """
        Calculate and sum transit results to link and nodes.
        """
        network = self.emme_scenario.get_network()
        for tc in param.transit_classes:
            if tc in self.assignment_modes:
                link_attr = self.extra(tc)
                mode: TransitMode = self.assignment_modes[tc]
                for result, attr_name in mode.segment_results.items():
                    if result == "transit_volumes":
                        for segment in network.transit_segments():
                            if segment.link is not None:
                                segment.link[link_attr] += segment[attr_name]
                    else:
                        nodeattr = mode.node_results[result]
                        for segment in network.transit_segments():
                            segment.i_node[nodeattr] += segment[attr_name]
        self.emme_scenario.publish_network(network)

    def get_car_times(self) -> Dict[str, float]:
        """Get dict of link car travel times for links within sub-model.

        Returns
        -------
        dict
            key : str
                Link id
            value : float
                Link car travel time
        """
        time_attr = self.netfield("car_time")
        network = self.emme_scenario.get_network()
        return {(link.i_node.id, link.j_node.id): link[time_attr]
            for link in network.links()
            if link.i_node[param.subarea_attr] == 2 and link[time_attr] > 0}

    def _set_car_vdfs(self, use_free_flow_speeds: bool = False):
        log.info("Sets car functions for scenario {}".format(
            self.emme_scenario.id))
        emmebank = self.emme_project.modeller.emmebank
        # Function 90 is used for free-flow speeds on external links
        emmebank.function("fd90").expression = param.volume_delay_funcs["fd90"]
        network = self.emme_scenario.get_network()
        car_time_attr = self.netfield("car_time")
        main_mode = network.mode(param.main_mode)
        car_modes = {
            network.mode(param.assignment_modes["car_work"]),
            network.mode(param.assignment_modes["truck"])
        }
        park_and_ride_mode = network.mode(param.park_and_ride_mode)
        car_time_zero = []
        for link in network.links():
            linktype = link.type % 100
            if link.type > 80 and linktype in param.roadclasses:
                # Car link with standard attributes
                roadclass = param.roadclasses[linktype]
                if link.volume_delay_func != 90:
                    if ((self.use_stored_speeds or use_free_flow_speeds)
                        and roadclass.type != "connector"):
                        link.volume_delay_func = 91
                    else:
                        link.volume_delay_func = roadclass.volume_delay_func
                link.data1 = roadclass.lane_capacity
                link.data2 = roadclass.free_flow_speed
                link[param.free_flow_time_attr] = (60 * link.length
                                                   / roadclass.free_flow_speed)
            elif linktype in param.custom_roadtypes:
                # Custom car link
                if link.volume_delay_func != 90:
                    if self.use_stored_speeds or use_free_flow_speeds:
                        link.volume_delay_func = 91
                    else:
                        link.volume_delay_func = linktype - 90
                link[param.free_flow_time_attr] = (60 * link.length
                                                   / link.data2)
                for linktype in param.roadclasses:
                    roadclass = param.roadclasses[linktype]
                    if (link.volume_delay_func == roadclass.volume_delay_func
                            and link.data2 > roadclass.free_flow_speed-1):
                        # Find the most appropriate road class
                        break
            else:
                # Link with no car traffic
                link.volume_delay_func = 0
            if link["#buslane"]:
                if (link.num_lanes == 3
                        and roadclass.num_lanes == ">=3"):
                    roadclass = param.roadclasses[linktype - 1]
                    link.data1 = roadclass.lane_capacity
                if link.volume_delay_func not in (90, 91):
                    link.volume_delay_func += 5
            if self.use_stored_speeds and link.volume_delay_func == 91:
                if car_modes & link.modes:
                    car_time = link[car_time_attr]
                    if 0 < car_time < 1440:
                        link.data2 = (link.length / car_time) * 60
                    elif car_time == 0:
                        car_time_zero.append(link.id)
                    else:
                        msg = f"Car travel time on link {link.id} is {car_time}"
                        log.error(msg)
                        raise ValueError(msg)
            if car_modes & link.modes:
                link.modes |= {main_mode, park_and_ride_mode}
            else:
                link.modes -= {main_mode, park_and_ride_mode}
        self.emme_scenario.publish_network(network)
        if car_time_zero and not use_free_flow_speeds:
            if len(car_time_zero) < 50000:
                links = ", ".join(car_time_zero)
                log.warn(
                    f"Car_time attribute on links {links} "
                     + "is zero. Free flow speed used on these links.")
            else:
                msg = "No car times on links. Demand calculation not reliable!"
                log.error(msg)
                raise ValueError(msg)

    def _set_transit_vdfs(self):
        log.info("Sets transit functions for scenario {}".format(
            self.emme_scenario.id))
        network = self.emme_scenario.get_network()
        transit_modesets = {modes[0]: {network.mode(m) for m in modes[1]}
            for modes in param.transit_delay_funcs}
        for link in network.links():
            try:
                next(link.segments())
            except StopIteration:
                # Skip the else clause if no transit segments on link
                pass
            else:
                for modeset in param.transit_delay_funcs:
                    # Check that intersection is not empty,
                    # hence that mode is active on link
                    if transit_modesets[modeset[0]] & link.modes:
                        funcs = param.transit_delay_funcs[modeset]
                        if modeset[0] == "bus":
                            if link["#buslane"]:
                                func = funcs["buslane"]
                            else:
                                func = funcs["no_buslane"]
                        else:
                            func = funcs[self.name]
                        break
                else:
                    msg = f"No transit time function for modes on link {link.id}"
                    log.error(msg)
                    raise ValueError(msg)
                for segment in link.segments():
                    segment.transit_time_func = func
        self.emme_scenario.publish_network(network)

    def _init_truck_times(self):
        """Set truck_time attribute to free-flow travel time.

        Later car assignment will calculate congested truck time,
        but for now we calculate free flow time with max speed 90 km/h.
        """
        network = self.emme_scenario.get_network()
        truck_time_attr = self.extra("truck_time")
        for link in network.links():
            try:
                link[truck_time_attr] = link.length * 60 / min(link.data2, 90)
            except ZeroDivisionError:
                link[truck_time_attr] = 0
        self.emme_scenario.publish_network(network)

    def _set_bike_vdfs(self):
        log.info("Sets bike functions for scenario {}".format(
            self.emme_scenario.id))
        emmebank = self.emme_project.modeller.emmebank
        emmebank.function("fd90").expression = param.volume_delay_funcs["fd98"]
        network = self.emme_scenario.get_network()
        main_mode = network.mode(param.main_mode)
        bike_mode = network.mode(param.bike_mode)
        for link in network.links():
            if link.volume_delay_func != 90:
                link.volume_delay_func = 98
            if bike_mode in link.modes:
                link.modes |= {main_mode}
            elif main_mode in link.modes:
                link.modes -= {main_mode}
        self.emme_scenario.publish_network(network)

    def set_matrix(self,
                    ass_class: str,
                    matrix: numpy.ndarray):
        self.assignment_modes[ass_class].demand.set(matrix)

    def get_matrix(self, ass_class: str) -> numpy.ndarray:
        """Get demand matrix with type pair (e.g., demand, car_work).
        Parameters
        ----------
        ass_class : str
            Assignment class (car_work/transit_leisure/truck/...)

        Return
        ------
        numpy 2-d matrix
            Matrix of the specified type
        """
        return self.assignment_modes[ass_class].demand.data

    def _calc_background_traffic(self, include_trucks: bool = False):
        """Calculate background traffic (buses)."""
        network = self.emme_scenario.get_network()
        # emme api has name "data3" for ul3
        background_traffic = param.background_traffic_attr.replace(
            "ul", "data")
        # calc @bus and data3
        heavy = [self.extra(ass_class) for ass_class in param.truck_classes]
        for link in network.links():
            if link.type > 100: # If car or bus link
                freq = 0
                for segment in link.segments():
                    segment_hdw = segment.line[self.netfield("hdw")]
                    if 0 < segment_hdw < 900:
                        freq += 60 / segment_hdw
                link[self.extra("bus")] = freq
                link[background_traffic] = 0 if link["#buslane"] else freq
                if include_trucks:
                    for ass_class in heavy:
                        link[background_traffic] += link[ass_class]
        self.emme_scenario.publish_network(network)

    def _set_walk_time(self):
        """Set walk or ferry time to data3"""
        network = self.emme_scenario.get_network()
        walk_time = param.aux_transit_time_attr
        for link in network.links():
            linktype = link.type % 100
            if linktype == 44:
                ferry_travel_time = link.length / link.data2 * 60
                link[walk_time] = link[param.ferry_wait_attr] + ferry_travel_time
            else:
                link[walk_time] = link.length / param.walk_speed * 60
        self.emme_scenario.publish_network(network)

    def _calc_road_cost(self, modes: Iterable[CarMode]):
        """Calculate road charges and driving costs for one scenario.

        Parameters
        ----------
        modes : Iterable
            List of car and truck modes for which to calculate link cost
        """
        log.info("Calculates road charges for time period {}...".format(self.name))
        network = self.emme_scenario.get_network()
        for link in network.links():
            toll_cost = link.length * link[self.netfield("hinta")]
            link[self.extra("toll_cost")] = toll_cost
            for mode in modes:
                dist_cost = mode.dist_unit_cost * link.length
                link[mode.link_cost_attr] = toll_cost + dist_cost
        self.emme_scenario.publish_network(network)

    def _calc_boarding_penalties(self, extra_penalty: int = 0):
        """Calculate boarding penalties for transit assignment."""
        # Definition of line specific boarding penalties
        network = self.emme_scenario.get_network()
        missing_penalties = set()
        penalty_attr = param.boarding_penalty_attr
        for line in network.transit_lines():
            try:
                penalty = self.boarding_penalty[line.mode.id] + extra_penalty
            except KeyError:
                penalty = extra_penalty
                missing_penalties.add(line.mode.id)
            for transit_class, transfer_pen in param.transfer_penalty.items():
                line[penalty_attr + transit_class] = penalty + transfer_pen
        if missing_penalties:
            missing_penalties_str: str = ", ".join(missing_penalties)
            log.warn("No boarding penalty found for transit modes " + missing_penalties_str)
        self.emme_scenario.publish_network(network)

    @property
    def boarding_penalty(self):
        return param.boarding_penalty

    def _assign_cars(self, 
                     stopping_criteria: Dict[str, Union[int, float]]):
        """Perform car_work traffic assignment for one scenario."""
        log.info("Car assignment started...")
        if self.use_stored_speeds:
            for car_spec in self._car_spec.separate_light_specs():
                car_spec["stopping_criteria"] = stopping_criteria
                self.emme_project.car_assignment(car_spec, self.emme_scenario)
        else:
            car_spec = self._car_spec.light_spec()
            car_spec["stopping_criteria"] = stopping_criteria
            assign_report = self.emme_project.car_assignment(
                car_spec, self.emme_scenario)
            log.info("Stopping criteria: {}, iteration {} / {}".format(
                assign_report["stopping_criterion"],
                len(assign_report["iterations"]),
                stopping_criteria["max_iterations"]))
            if assign_report["stopping_criterion"] == "MAX_ITERATIONS":
                log.warn("Car assignment not fully converged.")
        network = self.emme_scenario.get_network()
        if not self.use_stored_speeds:
            time_attr = self.netfield("car_time")
            for link in network.links():
                link[time_attr] = link.auto_time
        truck_time_attr = self.extra("truck_time")
        for link in network.links():
            link[param.aux_car_time_attr] = link.auto_time
            # Truck speed limited to 90 km/h
            link[truck_time_attr] = max(link.auto_time, link.length * 0.67)
        self.emme_scenario.publish_network(network)
        log.info("Car assignment performed for scenario {}".format(
            self.emme_scenario.id))

    def _assign_trucks(self):
        stopping_criteria = copy.deepcopy(param.stopping_criteria["coarse"])
        stopping_criteria["max_iterations"] = 0
        for truck_spec in self._car_spec.truck_specs():
            truck_spec["stopping_criteria"] = stopping_criteria
            self.emme_project.car_assignment(
                truck_spec, self.emme_scenario)
        log.info("Truck assignment performed for scenario {}".format(
            self.emme_scenario.id))

    def _assign_bikes(self):
        """Perform bike traffic assignment for one scenario."""
        self.bike_mode.init_matrices()
        scen = self.emme_scenario
        log.info("Bike assignment started...")
        self.emme_project.car_assignment(
            specification=self.bike_mode.spec, scenario=scen)
        log.info("Bike assignment performed for scenario " + str(scen.id))

    def _calc_extra_wait_time(self):
        """Calculate extra waiting time for one scenario."""
        network = self.emme_scenario.get_network()
        log.info("Calculates effective headways "
                 + "and cumulative travel times for scenario "
                 + str(self.emme_scenario.id))
        long_dist_transit_modes = list({mode for mode_set
            in param.long_dist_transit_modes.values() for mode in mode_set})
        transit_modes = long_dist_transit_modes + param.local_transit_modes
        headway_attr = self.netfield("hdw")
        effective_hdw_attr = param.effective_headway_attr.replace(
            "ut", "data")
        delay_attr = param.transit_delay_attr.replace("us", "data")
        for line in network.transit_lines():
            if line.mode.id in transit_modes:
                func = (param.effective_headway
                    if line.mode.id in param.local_transit_modes
                    else param.effective_headway_ld)
                hdw = line[headway_attr]
                for interval in func:
                    if interval[0] <= hdw < interval[1]:
                        effective_hdw = func[interval](hdw - interval[0])
                        break
                line[effective_hdw_attr] = effective_hdw
                cumulative_length = 0
                cumulative_time = 0
                cumulative_speed = 0
                headway_sd = 0
                for segment in line.segments():
                    if segment.dwell_time >= 2:
                        # Time-point stops reset headway deviation
                        cumulative_length = 0
                        cumulative_time = 0
                    cumulative_length += segment.link.length
                    # Travel time for buses in mixed traffic
                    if segment.transit_time_func == 1:
                        cumulative_time += (segment.link.auto_time
                                            + segment.dwell_time)
                    # Travel time for buses on bus lanes
                    if segment.transit_time_func == 2:
                        cumulative_time += (segment.link.length
                                            / segment.link.data2
                                            * 60
                                            + segment.dwell_time)
                    # Travel time for rail
                    if segment.transit_time_func == 6:
                        cumulative_time += (segment[delay_attr]
                                            + segment.dwell_time)
                    if cumulative_time > 0:
                        cumulative_speed = (cumulative_length
                                            / cumulative_time
                                            * 60)
                    # Headway standard deviation for buses and trams
                    if line.mode.id in param.headway_sd_func:
                        b = param.headway_sd_func[line.mode.id]
                        headway_sd = (b["asc"]
                                    + b["ctime"]*cumulative_time
                                    + b["cspeed"]*cumulative_speed)
                    # Estimated waiting time addition caused by headway dev
                    segment["@wait_time_dev"] = (headway_sd**2
                                                / (2.0*line[effective_hdw_attr]))
        self.emme_scenario.publish_network(network)

    def _assign_transit(self, transit_classes=param.local_transit_classes,
                        calc_network_results=False, delete_strat_files=False):
        """Perform transit assignment for one scenario."""
        self._calc_extra_wait_time()
        log.info("Transit assignment started...")
        for i, transit_class in enumerate(transit_classes):
            tc: TransitMode = self.assignment_modes[transit_class]
            tc.assign(i)
            if calc_network_results:
                tc.calc_transit_network_results()
            if delete_strat_files:
                self._strategy_paths[transit_class].unlink(missing_ok=True)
            log.info(f"Transit class {transit_class} assigned")

    def _calc_transit_link_results(self):
        volax_attr = self.extra("aux_transit")
        network = self.emme_scenario.get_network()
        for link in network.links():
            link[volax_attr] = link.aux_transit_volume
        time_attr = self.extra(param.uncongested_transit_time)
        for segment in network.transit_segments():
            segment[time_attr] = segment.transit_time
        self.emme_scenario.publish_network(network)

    @property
    def _strategy_paths(self) -> Dict[str, Path]:
        db_path = (Path(self.emme_project.modeller.emmebank.path).parent
                   / f"STRATS_s{self.emme_scenario.id}")
        with open(db_path / "config", "r") as f:
            config = json.load(f)
        return {strat["name"]: db_path / strat["path"]
            for strat in config["strat_files"]}
