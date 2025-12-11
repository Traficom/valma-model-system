from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Tuple, Union, Optional, cast, Iterable
from collections import defaultdict
from pathlib import Path
import numpy
import pandas
from math import log10

import utils.log as log
from utils.print_links import geometries, Node, Link, Segment
import utils.sum_24h as sum24
import parameters.assignment as param
from assignment.abstract_assignment import AssignmentModel
from assignment.datatypes.emme_matrix import EmmeMatrix
import assignment.off_peak_period as periods
from assignment.freight_assignment import FreightAssignmentPeriod
if TYPE_CHECKING:
    from assignment.emme_bindings.emme_project import EmmeProject
    from datahandling.resultdata import ResultsData
    from inro.emme.database.scenario import Scenario # type: ignore
    from inro.emme.network.Network import Network # type: ignore


class EmmeAssignmentModel(AssignmentModel):
    """
    Emme assignment definition.

    Parameters
    ----------
    emme_context : assignment.emme_bindings.emme_project.EmmeProject
        Emme projekt to connect to this assignment
    first_scenario_id : int
        Id fo EMME scenario where network is stored and modified.
    submodel : str
        Name of regional submodel (or koko_suomi)
    separate_emme_scenarios : bool (optional)
        Whether four new scenarios will be created in EMME
        (with ids following directly after first scenario id)
        for storing time-period specific network results:
        day, morning rush hour, midday hour and afternoon rush hour.
    save_matrices : bool (optional)
        Whether matrices will be saved in Emme format for all time periods.
    use_free_flow_speeds : bool (optional)
        Whether traffic assignment is all-or-nothing with free-flow speeds.
    delete_extra_matrices : bool (optional)
        If True, only matrices needed for demand calculation will be
        returned from end assignment.
    delete_strat_files : bool (optional)
            If True, strategy files will be deleted immediately after usage.
    time_periods : dict (optional)
        key : str
            Time period names, default is aht, pt, iht
        value : str
            Name of `AssignmentPeriod` sub-class
    first_matrix_id : int (optional)
        Where to save matrices (if saved),
        300 matrix ids will be reserved, starting from first_matrix_id.
        Default is 100(-399).
    """
    def __init__(self, 
                 emme_context: EmmeProject,
                 first_scenario_id: int,
                 submodel: str,
                 separate_emme_scenarios: bool = False,
                 save_matrices: bool = False,
                 use_free_flow_speeds: bool = False,
                 delete_extra_matrices: bool = False,
                 delete_strat_files: bool = False,
                 time_periods: dict[str, str] = param.time_periods,
                 first_matrix_id: int = 100):
        self.submodel = submodel
        self.separate_emme_scenarios = separate_emme_scenarios
        self.save_matrices = save_matrices
        self.use_free_flow_speeds = use_free_flow_speeds
        self.transit_classes = (param.long_distance_transit_classes
            if self.use_free_flow_speeds else param.simple_transit_classes)
        self.simple_transit_classes = (param.long_dist_simple_classes
            if self.use_free_flow_speeds else param.simple_transit_classes)
        self.delete_extra_matrices = delete_extra_matrices
        self._delete_strat_files = delete_strat_files
        self.time_periods = time_periods
        EmmeMatrix.id_counter = first_matrix_id if save_matrices else 0
        self.emme_project = emme_context
        self.mod_scenario = self.emme_project.modeller.emmebank.scenario(
            first_scenario_id)
        if self.mod_scenario is None:
            raise ValueError(f"EMME project has no scenario {first_scenario_id}")

    def prepare_network(self, car_dist_unit_cost: Dict[str, float],
                        car_time_files: Optional[List[Path]] = None):
        """Create matrices, extra attributes and calc background variables.

        Parameters
        ----------
        dist_unit_cost : dict
            key : str
                Assignment class (car_work/truck/...)
            value : float
                Car cost per km in euros
        car_time_files : list (optional)
            List of paths, where car time data is stored.
            If set, traffic assignment is all-or-nothing with speeds stored
            in `#car_time_xxx`. Overrides `use_free_flow_speeds`.
            List can be empty, if car times are already stored on network.
        """
        if car_time_files is not None:
            for path in car_time_files:
                for file in path.rglob("netfield_links*"):
                    self.emme_project.import_network_fields(
                        file, field_separator="TAB",
                        revert_on_error=False, scenario=self.mod_scenario)
        self._add_bus_stops()
        self.emme_project.create_extra_attribute(
            "LINK", param.free_flow_time_attr, "free-flow car time",
            overwrite=True, scenario=self.mod_scenario)
        if self.separate_emme_scenarios:
            self.day_scenario = self.emme_project.copy_scenario(
                self.mod_scenario, self.mod_scenario.number + 1,
                self.mod_scenario.title + '_' + "vrk",
                overwrite=True, copy_paths=False, copy_strategies=False)
        else:
            self.day_scenario = self.mod_scenario
        self.assignment_periods: List[periods.AssignmentPeriod] = []
        for i, tp in enumerate(self.time_periods):
            if self.separate_emme_scenarios:
                scen_id = self.mod_scenario.number + i + 2
                self.emme_project.copy_scenario(
                    self.mod_scenario, scen_id,
                    self.mod_scenario.title + '_' + tp,
                    overwrite=True, copy_paths=False, copy_strategies=False)
            else:
                scen_id = self.mod_scenario.number
            self.assignment_periods.append(vars(periods)[self.time_periods[tp]](
                tp, scen_id, self.emme_project,
                separate_emme_scenarios=self.separate_emme_scenarios,
                use_stored_speeds=(car_time_files is not None),
                delete_extra_matrices=self.delete_extra_matrices,
                delete_strat_files=self._delete_strat_files))
        ass_classes = (param.car_classes + param.long_distance_transit_classes
            if self.use_free_flow_speeds else param.simple_transport_classes)
        ass_classes += ("bus",)
        self._create_attributes(
            self.day_scenario, ass_classes, self._extra, self._netfield)
        self._segment_results = self._create_transit_attributes(
            self.day_scenario, self._extra)
        for ap in self.assignment_periods:
            self._create_attributes(
                ap.emme_scenario, ass_classes, ap.extra, ap.netfield)
            self._create_transit_attributes(ap.emme_scenario, ap.extra)
            ap.prepare(
                car_dist_unit_cost, self.day_scenario, self.save_matrices)
            log.debug(
                f"Created extra attrs for scen {ap.emme_scenario}, {ap.name}")
        self._init_functions()
        #add ferry wait time
        self.emme_project.set_extra_function_parameters(el1=param.ferry_wait_attr)

    def prepare_freight_network(self, car_dist_unit_cost: Dict[str, float],
                                commodity_classes: List[str]):
        """Create matrices, extra attributes and calc background variables.

        Parameters
        ----------
        dist_unit_cost : dict
            key : str
                Assignment class (car_work/truck/...)
            value : float
                Car cost per km in euros
        commodity_classes : list of str
            Class names for which we want extra attributes
        """
        self.freight_network = FreightAssignmentPeriod(
            "vrk", self.mod_scenario.number, self.emme_project)
        self.assignment_periods = [self.freight_network]
        self.emme_project.create_extra_attribute(
            "LINK", param.free_flow_time_attr, "free-flow car time",
            overwrite=True, scenario=self.mod_scenario)
        self.emme_project.create_extra_attribute(
            "TRANSIT_LINE", param.terminal_cost_attr, "terminal cost",
            overwrite=True, scenario=self.mod_scenario)
        for ass_class in param.freight_modes.values():
            for attr in ass_class.values():
                self.emme_project.create_extra_attribute(
                    "TRANSIT_LINE", attr, "terminal cost",
                    overwrite=True, scenario=self.mod_scenario)
        for comm_class in commodity_classes:
            for ass_class in param.freight_modes:
                attr_name = (comm_class + ass_class)[:17]
                self.emme_project.create_extra_attribute(
                    "TRANSIT_SEGMENT", '@' + attr_name,
                    "commodity flow", overwrite=True,
                    scenario=self.mod_scenario)
                self.emme_project.create_extra_attribute(
                    "LINK", '@a_' + attr_name,
                    "commodity flow", overwrite=True,
                    scenario=self.mod_scenario)
                attr_name = (comm_class + "truck")[:17]
                self.emme_project.create_extra_attribute(
                        "LINK", '@' + attr_name,
                        "commodity flow", overwrite=True,
                        scenario=self.mod_scenario)
        self._create_attributes(
            self.mod_scenario,
            list(param.truck_classes) + list(param.freight_modes),
            self._extra, self._netfield)
        self.freight_network.prepare(car_dist_unit_cost, self.save_matrices)
        self._init_functions()
        self.emme_project.set_extra_function_parameters(el1=param.ferry_wait_attr)

    def _init_functions(self):
        for idx in param.volume_delay_funcs:
            try:
                self.emme_project.modeller.emmebank.delete_function(idx)
            except Exception:
                pass
            self.emme_project.modeller.emmebank.create_function(
                idx, param.volume_delay_funcs[idx])

    def init_assign(self):
        for ap in self.assignment_periods:
            ap.init_assign()

    @property
    def zone_numbers(self) -> List[int]:
        """List of all zone numbers. ???types"""
        return self.mod_scenario.zone_numbers

    @property
    def mapping(self) -> Dict[int, int]:
        """dict: Dictionary of zone numbers and corresponding indices."""
        mapping = {}
        for idx, zone in enumerate(self.zone_numbers):
            mapping[zone] = idx
        return mapping

    @property
    def nr_zones(self) -> int:
        """int: Number of zones in assignment model."""
        return len(self.zone_numbers)

    @property
    def beeline_dist(self):
        log.info("Get beeline distances from network centroids")
        network = self.mod_scenario.get_network()
        xy = 0.001 * numpy.array(
            [[node.x, node.y] for node in network.centroids()],
            dtype=numpy.float32)
        return numpy.sqrt(
            sum((xy[:, axis] - xy[:, axis, None])**2 for axis in (0, 1)))

    def aggregate_results(self,
                          resultdata: ResultsData,
                          mapping: pandas.Series):
        """Aggregate results to 24h and print vehicle kms.

        Parameters
        ----------
        resultdata : datahandling.resultdata.Resultdata
            Result data container to print to
        mapping : pandas.Series
            Mapping between municipality and county
        """
        car_times = pandas.DataFrame(
            {ap.netfield("car_time"): ap.get_car_times()
                for ap in self.assignment_periods})
        if not car_times.empty:
            car_times.index.names = ("i_node", "j_node")
            resultdata.print_data(
                car_times, f"netfield_links_{self.submodel}.txt")

        # Aggregate results to 24h
        for ap in self.assignment_periods:
            ap.transit_results_links_nodes()
        network = self.day_scenario.get_network()
        networks = {ap.name: ap.emme_scenario.get_network()
            for ap in self.assignment_periods}
        for res in param.segment_results:
            self._transit_segment_24h(
                network, networks, param.segment_results[res])
            if res != "transit_volumes":
                self._node_24h(network, networks, param.segment_results[res])
            log.info("Attribute {} aggregated to 24h (scenario {})".format(
                res, self.day_scenario.id))
        ass_classes = (param.car_classes + param.long_distance_transit_classes
            if self.use_free_flow_speeds else param.simple_transport_classes)
        ass_classes += ("bus", "aux_transit")
        self._link_24h(network, networks, ass_classes)
        self.day_scenario.publish_network(network)
        log.info("Link attributes aggregated to 24h (scenario {})".format(
            self.day_scenario.id))

        # Aggregate and print transit vehicle kms
        transit_modes = [veh.description for veh in network.transit_vehicles()]
        miles = {miletype: pandas.Series(0.0, transit_modes)
            for miletype in ("dist", "time")}
        for ap in self.assignment_periods:
            volume_factor = param.volume_factors["bus"][ap.name]
            time_attr = ap.extra(param.uncongested_transit_time)
            for line in networks.pop(ap.name).transit_lines():
                mode = line.vehicle.description
                headway = line[ap.netfield("hdw")]
                if 0 < headway < 990:
                    departures = 60 / headway / volume_factor
                    for segment in line.segments():
                        miles["dist"][mode] += departures * segment.link.length
                        miles["time"][mode] += departures * segment[time_attr]
        resultdata.print_data(miles, "transit_kms.txt")

        # Aggregate and print vehicle kms and link lengths
        kms = dict.fromkeys(ass_classes, 0.0)
        vdfs = {param.roadclasses[linktype].volume_delay_func
            for linktype in param.roadclasses}
        vdfs.add(0) # Links with car traffic prohibited
        vdf_kms = pandas.concat(
            {ass_class: pandas.Series(0.0, vdfs, name="veh_km")
                for ass_class in ass_classes},
            names=["class", "v/d-func"])
        areas = mapping.drop_duplicates()
        area_kms = {ass_class: pandas.Series(0.0, areas)
            for ass_class in ass_classes}
        vdf_area_kms = {vdf: pandas.Series(0.0, areas) for vdf in vdfs}
        #The following line only works well in Python 3.7+
        linktypes = (list(dict.fromkeys(param.roadtypes.values()))
                     + list(dict.fromkeys(param.railtypes.values())))
        linklengths = pandas.Series(0.0, linktypes, name="length")
        soft_modes = param.transit_classes + ("bike",)
        faulty_kela_code_nodes = set()
        for link in network.links():
            if link.i_node[param.subarea_attr] == 2:
                linktype = link.type % 100
                if linktype in param.roadclasses:
                    vdf = param.roadclasses[linktype].volume_delay_func
                elif linktype in param.custom_roadtypes:
                    vdf = linktype - 90
                else:
                    vdf = 0
                municipality = link.i_node[param.municipality_attr]
                try:
                    area = mapping[municipality]
                except KeyError:
                    faulty_kela_code_nodes.add(municipality)
                    area = None
                for ass_class in ass_classes:
                    veh_kms = link[self._extra(ass_class)] * link.length
                    kms[ass_class] += veh_kms
                    try:
                        vdf_kms[ass_class][vdf] += veh_kms
                    except KeyError:
                        pass
                    try:
                        area_kms[ass_class][area] += veh_kms
                    except KeyError:
                        pass
                    if ass_class not in soft_modes:
                        try:
                            vdf_area_kms[vdf][area] += veh_kms
                        except KeyError:
                            pass
                if vdf == 0 and linktype in param.railtypes:
                    linklengths[param.railtypes[linktype]] += link.length
                else:
                    linklengths[param.roadtypes[vdf]] += link.length / 2
        if faulty_kela_code_nodes:
            s = ("County not found for #municipality when aggregating link data: "
                 + ", ".join(faulty_kela_code_nodes))
            log.warn(s)
        resultdata.print_line("\nVehicle kilometres", "result_summary")
        resultdata.print_concat(vdf_kms, "vehicle_kms_vdfs.txt")
        for ass_class in ass_classes:
            resultdata.print_line(
                "{}:\t{:1.0f}".format(ass_class, kms[ass_class]),
                "result_summary")
        resultdata.print_data(area_kms, "vehicle_kms_county.txt")
        resultdata.print_data(vdf_area_kms, "vehicle_kms_vdfs_county.txt")
        resultdata.print_data(linklengths, "link_lengths.txt")

        # Print mode boardings per municipality
        boardings = defaultdict(lambda: defaultdict(float))
        modes = self.assignment_periods[0].assignment_modes
        attrs = [modes[transit_class].segment_results["total_boardings"]
            for transit_class in self.transit_classes]
        for line in network.transit_lines():
            mode = line.mode.id
            for seg in line.segments():
                municipality = seg.i_node[param.municipality_attr]
                for tc in attrs:
                    boardings[mode][municipality] += seg[tc]
        resultdata.print_data(
            pandas.DataFrame.from_dict(boardings), "municipality_boardings.txt")

        # Aggregate and print numbers of stations
        stations = pandas.Series(0, param.station_ids, name="number")
        for node in network.regular_nodes():
            for mode in param.station_ids:
                if (node.data2 == param.station_ids[mode]
                        and node[self._extra("transit_won_boa")] > 0):
                    stations[mode] += 1
                    break
        resultdata.print_data(stations, "transit_stations.txt")

        # Export link, node and segnment extra attributes to GeoPackage file
        fname = "assignment_results.gpkg"
        for geom_type, objects in (
                (Node, network.nodes()),
                (Link, network.links()),
                (Segment, network.transit_segments())):
            attrs = [attr.name for attr in self.day_scenario.extra_attributes()
                if attr.type == geom_type.name]
            attrs += [attr.name for attr in self.day_scenario.network_fields()
                if attr.type == geom_type.name and attr.atype == "REAL"]
            attrs += geom_type.attrs
            resultdata.print_gpkg(
                *geometries(attrs, objects, geom_type), fname, geom_type.name)
        log.info(f"EMME extra attributes exported to file {fname}")

    def calc_transit_cost(self, fares: pandas.DataFrame):
        """Insert line costs.
        
        Parameters
        ----------
        fares : pandas.DataFrame
            Transit fare zone specification
        """
        if self.separate_emme_scenarios:
            for ap in self.assignment_periods:
                ap.calc_transit_cost(fares)
        else:
            self.assignment_periods[0].calc_transit_cost(fares)

    def _extra(self, attr: str) -> str:
        """Add prefix "@" and suffix "_vrk".

        Parameters
        ----------
        attr : str
            Attribute string to modify

        Returns
        -------
        str
            Modified string
        """
        return "@{}_{}".format(attr, "vrk")

    def _netfield(self, attr: str) -> str:
        """Add prefix "#" and suffix "_vrk".

        Parameters
        ----------
        attr : str
            Attribute string to modify

        Returns
        -------
        str
            Modified string
        """
        return "#{}_{}".format(attr, "vrk")

    def _add_bus_stops(self):
        network: Network = self.mod_scenario.get_network()
        for line in network.transit_lines():
            if line.mode.id in param.stop_codes:
                if not line[param.keep_stops_attr]:
                    is_stop_field = param.stop_codes[line.mode.id]
                    for segment in line.segments():
                        is_stop = segment.i_node[is_stop_field]
                        segment.allow_alightings = is_stop
                        segment.allow_boardings = is_stop
            try:
                dwell_time = param.bus_dwell_time[line.mode.id]
            except KeyError:
                pass
            else:
                for segment in line.segments():
                    if segment.dwell_time < 2:
                        # Unless a longer stop is scheduled,
                        # we set default dwell time for buses
                        segment.dwell_time = (dwell_time
                            if segment.allow_boardings else 0)
        self.mod_scenario.publish_network(network)

    def _create_attributes(self,
                           scenario: Any,
                           assignment_classes: List[str],
                           extra: Callable[[str], str],
                           netfield: Callable[[str], str]):
        """Create extra attributes needed in assignment.

        Parameters
        ----------
        scenario : inro.modeller.emmebank.scenario
            Emme scenario to create attributes for
        assignment_classes : list of str
            Names of assignment classes to create volume attributes for
        extra : function
            Small helper function which modifies string
            (e.g., self._extra)
        netfield : function
            Small helper function which modifies string
            (e.g., self._netfield)
        """
        if TYPE_CHECKING: scenario = cast(Scenario, scenario)
        for ass_class in assignment_classes:
            self.emme_project.create_extra_attribute(
                "LINK", extra(ass_class), ass_class + " volume",
                overwrite=True, scenario=scenario)
        self.emme_project.create_extra_attribute(
            "LINK", param.aux_car_time_attr, "walk time",
            overwrite=True, scenario=scenario)
        self.emme_project.create_extra_attribute(
            "LINK", extra("truck_time"), "truck time",
            overwrite=True, scenario=scenario)
        if scenario.network_field("LINK", netfield("hinta")) is not None:
            self.emme_project.create_extra_attribute(
                "LINK", extra("toll_cost"), "toll cost",
                overwrite=True, scenario=scenario)

    def _create_transit_attributes(self,
                                   scenario: Any,
                                   extra: Callable[[str], str],
            ) -> Tuple[Dict[str,Dict[str,str]], Dict[str, str]]:
        """Create extra attributes needed in assignment.

        Parameters
        ----------
        scenario : inro.modeller.emmebank.scenario
            Emme scenario to create attributes for
        extra : function
            Small helper function which modifies string
            (e.g., self._extra)

        """
        # Create link attributes
        self.emme_project.create_extra_attribute(
            "LINK", extra("aux_transit"), "aux transit volume",
            overwrite=True, scenario=scenario)
        self.emme_project.create_extra_attribute(
            "LINK", param.park_cost_attr_l, "terminal parking cost",
            overwrite=True, scenario=scenario)
        self.emme_project.create_extra_attribute(
            "LINK", param.aux_transit_time_attr, "walk time",
            overwrite=True, scenario=scenario)
        # Create transit line attributes
        self.emme_project.create_extra_attribute(
            "TRANSIT_LINE", param.board_fare_attr,
            "boarding fare attribute", overwrite=True, scenario=scenario)
        self.emme_project.create_extra_attribute(
            "TRANSIT_LINE", param.board_long_dist_attr,
            "boarding fare attribute", overwrite=True, scenario=scenario)
        for transit_class in param.transfer_penalty:
            self.emme_project.create_extra_attribute(
                "TRANSIT_LINE", param.boarding_penalty_attr + transit_class,
                "boarding pentalty attribute", overwrite=True,
                scenario=scenario)
        # Create transit segment attributes
        self.emme_project.create_extra_attribute(
            "TRANSIT_SEGMENT", param.dist_fare_attr,
            "distance fare attribute", overwrite=True, scenario=scenario)
        self.emme_project.create_extra_attribute(
            "TRANSIT_SEGMENT", param.extra_waiting_time["penalty"],
            "wait time st.dev.", overwrite=True, scenario=scenario)
        self.emme_project.create_extra_attribute(
            "TRANSIT_SEGMENT", extra(param.uncongested_transit_time),
            "uncongested transit time", overwrite=True, scenario=scenario)
        for result, attr_name in param.segment_results.items():
            self.emme_project.create_extra_attribute(
                "TRANSIT_SEGMENT", attr_name, result, overwrite=True,
                scenario=scenario)
        self.emme_project.create_extra_attribute(
            "LINK", param.park_ride_vol_attr, "park-and-ride car volume",
            overwrite=True, scenario=scenario)

    def calc_noise(self, mapping: pandas.Series) -> pandas.Series:
        """Calculate noise according to Road Traffic Noise Nordic 1996.

        Parameters
        ----------
        mapping : pandas.Series
            Mapping between municipality and county

        Returns
        -------
        pandas.Series
            Area (km2) of noise polluted zone, aggregated to area level
        """
        noise_areas = pandas.Series(
            0.0, mapping.drop_duplicates(), name="county")
        network = self.day_scenario.get_network()
        morning_network = self.assignment_periods[0].emme_scenario.get_network()
        for link in network.links():
            # Aggregate traffic
            light_modes = (
                self._extra("car_work"),
                self._extra("car_leisure"),
                self._extra("van"),
            )
            traffic = sum([link[mode] for mode in light_modes])
            rlink = link.reverse_link
            if rlink is None:
                reverse_traffic = 0
            else:
                reverse_traffic = sum([rlink[mode] for mode in light_modes])
            cross_traffic = (param.years_average_day_factor
                             * param.share_7_22_of_day
                             * (traffic+reverse_traffic))
            heavy = (link[self._extra("truck")]
                     + link[self._extra("trailer_truck")])
            traffic = max(traffic, 0.01)
            heavy_share = heavy / (traffic+heavy)

            # Calculate speed
            link = morning_network.link(link.i_node, link.j_node)
            car_time_attr = self.assignment_periods[0].netfield("car_time")
            rlink = link.reverse_link
            if reverse_traffic > 0:
                speed = (60 * 2 * link.length
                         / (link[car_time_attr]+rlink[car_time_attr]))
            else:
                try:
                    speed = (0.3*(60*link.length/link[car_time_attr])
                             + 0.7*link.data2)
                except ZeroDivisionError:
                    speed = link.data2
            speed = max(speed, 50.0)

            # Calculate start noise
            if speed <= 90:
                heavy_correction = (10*log10((1-heavy_share)
                                    + 500*heavy_share/speed))
            else:
                heavy_correction = (10*log10((1-heavy_share)
                                    + 5.6*heavy_share*(90/speed)**3))
            start_noise = ((68 + 30*log10(speed/50)
                           + 10*log10(cross_traffic/15/1000)
                           + heavy_correction)
                if cross_traffic > 0 else 0)
            if start_noise < 0:
                log.warn(f"Negative noise level for link {link.id}")
                start_noise = 0

            # Calculate noise zone width
            func = param.noise_zone_width
            for interval in func:
                if interval[0] <= start_noise < interval[1]:
                    zone_width = func[interval](start_noise - interval[0])
                    break

            # Calculate noise zone area and aggregate to area level
            try:
                area = mapping[link.i_node[param.municipality_attr]]
            except KeyError:
                area = None
            if area in noise_areas:
                noise_areas[area] += 0.001 * zone_width * link.length
        return noise_areas

    def _link_24h(self, network: Network, networks: Dict[str, Network],
                  attrs: Iterable[str]):
        """ 
        Sums and expands link volumes to 24h.

        Parameters
        ----------
        network : inro.emme.network.Network.Network
            Day network
        networks : dict
            key : str
                Time period
            value : inro.emme.network.Network.Network
                Time-period networks
        attrs : list of str
            List of attributes corresponding to assignment class volumes
        """
        attrs = {attr: attr for attr in attrs}
        extras = {ap.name: {attr: ap.extra(attrs[attr]) for attr in attrs}
            for ap in self.assignment_periods}
        extra = {attr: self._extra(attrs[attr]) for attr in attrs}
        # save link volumes to result network
        for link in network.links():
            sum24.sum_24h(link, networks, extras, extra, sum24.get_link)
        return network

    def _node_24h(self, network: Network, networks: Dict[str, Network],
                  attr: str):
        """ 
        Sums and expands node attributes to 24h.

        Parameters
        ----------
        network : inro.emme.network.Network.Network
            Day network
        networks : dict
            key : str
                Time period
            value : inro.emme.network.Network.Network
                Time-period networks
        attr : str
            Attribute name that is usually in param.segment_results
        """
        attrs = {transit_class: f"node_{transit_class}_{attr[1:]}"
            for transit_class in self.simple_transit_classes}
        netfields = self._netfields(attrs)
        # save node volumes to result network
        for node in network.nodes():
            sum24.sum_24h(node, networks, *netfields, sum24.get_node)
        return network

    def _transit_segment_24h(self, network: Network,
                             networks: Dict[str, Network], attr: str):
        """ 
        Sums and expands transit attributes to 24h.

        Parameters
        ----------
        network : inro.emme.network.Network.Network
            Day network
        networks : dict
            key : str
                Time period
            value : inro.emme.network.Network.Network
                Time-period networks
        attr : str
            Attribute name that is usually in param.segment_results
        """
        attrs = {transit_class: transit_class + '_' + attr[1:]
            for transit_class in self.simple_transit_classes}
        netfields = self._netfields(attrs)
        # save segment volumes to result network
        for segment in network.transit_segments():
            sum24.sum_24h(segment, networks, *netfields, sum24.get_segment)
        return network

    def _netfields(self, attrs: Dict[str, str]):
        extras = {ap.name: {attr: ap.netfield(attrs[attr]) for attr in attrs}
            for ap in self.assignment_periods}
        extra = {attr: self._netfield(attrs[attr]) for attr in attrs}
        return extras, extra
