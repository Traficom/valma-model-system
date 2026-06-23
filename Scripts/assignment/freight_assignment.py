from typing import Dict, Tuple
from pathlib import Path
import numpy
from collections import defaultdict

import utils.log as log
import parameters.assignment as param
from parameters.zone import finland_border_points, cluster_border_points
from assignment.assignment_period import AssignmentPeriod
from assignment.datatypes.freight_specification import FreightMode


class FreightAssignmentPeriod(AssignmentPeriod):
    def __init__(self, *args, **kwargs):
        AssignmentPeriod.__init__(self, *args, **kwargs)
        for criteria in self.stopping_criteria.values():
                criteria["max_iterations"] = 0

    def prepare(self, dist_unit_cost: Dict[str, float],
                time_unit_cost: Dict[str, float], save_matrices: bool):
        self._prepare_cars(dist_unit_cost, time_unit_cost, save_matrices)
        network = self.emme_scenario.get_network()
        for line in network.transit_lines():
            mode = line.mode.id
            for cost_attrs in param.freight_modes.values():
                if mode in cost_attrs:
                    cost = param.freight_terminal_cost[mode]
                    line[param.terminal_cost_attr] = cost
                    line[cost_attrs[mode]] = cost
                    break
        self.emme_scenario.publish_network(network)
        self.assignment_modes.update({ass_class: FreightMode(
                ass_class, self, save_matrices)
            for ass_class in param.freight_modes})

    def assign(self):
        self._set_car_vdfs(use_free_flow_speeds=True)
        self._init_truck_times()
        self._assign_trucks()
        self._set_freight_vdfs()
        self._assign_freight()
        mtxs = {tc: self.assignment_modes[tc].get_matrices()
                for tc in param.truck_classes + tuple(param.freight_modes)}
        impedance_types = ("time", "dist", "aux_time", "aux_dist",
                           "toll_cost", "canal_cost")
        impedance = {mode: {mtx_type: mtxs[mode][mtx_type]
                            for mtx_type in impedance_types if mtx_type in mtxs[mode]}
                    for mode in mtxs}
        return impedance

    def save_network_volumes(self, commodity_class: str):
        """Save commodity-specific volumes in segment attribute.

        Parameters
        ----------
        commodity_class : str
            Commodity class name
        """
        for ass_class in param.freight_modes:
            spec = self.assignment_modes[ass_class].ntw_results_spec
            self.emme_project.network_results(
                spec, self.emme_scenario, ass_class)
            seg_attr = "#" + commodity_class + ass_class
            self.emme_project.create_network_field(
                    "TRANSIT_SEGMENT", "REAL", seg_attr, "commodity flow",
                    overwrite=True, scenario=self.emme_scenario)
            link_attr = "#aux_" + commodity_class + ass_class
            self.emme_project.create_network_field(
                    "LINK", "REAL", link_attr, "aux commodity flow",
                    overwrite=True, scenario=self.emme_scenario)
            network = self.emme_scenario.get_network()
            for segment in network.transit_segments():
                segment[seg_attr] = segment[param.commodity_flow_attr]
            for link in network.links():
                link[link_attr] = link[param.aux_commodity_flow_attr]
            self.emme_scenario.publish_network(network)
        for spec in self._car_spec.truck_specs():
            spec["stopping_criteria"] = self.stopping_criteria["coarse"]
            self.emme_project.car_assignment(spec, self.emme_scenario)
        link_attr = "#" + commodity_class + "truck"
        self.emme_project.create_network_field(
            "LINK", "REAL", link_attr, "truck commodity flow",
            overwrite=True, scenario=self.emme_scenario)
        network = self.emme_scenario.get_network()
        for link in network.links():
                link[link_attr] = link["@truck"]
        self.emme_scenario.publish_network(network)
        for tc in param.truck_classes:
            self.assignment_modes[tc].get_matrices()

    def output_traversal_matrix(self, demand_modes: set, output_path: Path):
        """Save commodity class specific auxiliary tons for freight modes.
        Result file indicates amount of transported tons with auxiliary 
        mode between gate pair.

        Parameters
        ----------
        demand_modes : set
            commodity specific demand modes
        output_path : Path
            Path where traversal matrices are saved
        """
        spec = {
            "type": "EXTENDED_TRANSIT_TRAVERSAL_ANALYSIS",
            "portion_of_path": "COMPLETE",
            "gates_by_trip_component": {
                "aux_transit": param.freight_gate_attr,
            },
        }
        for ass_class in set(param.freight_modes) & demand_modes:
            output_file = output_path / f"{ass_class}.txt"
            spec["analyzed_demand"] = self.assignment_modes[ass_class].demand.id
            self.emme_project.traversal_analysis(
                spec, output_file, append_to_output_file=False,
                scenario=self.emme_scenario, class_name=ass_class)

    def _set_freight_vdfs(self):
        network = self.emme_scenario.get_network()
        for segment in network.transit_segments():
            if segment.data1 > 0:
                segment.transit_time_func = 6
            else:
                segment.transit_time_func = 7
        self.emme_scenario.publish_network(network)

    def _assign_freight(self):
        network = self.emme_scenario.get_network()
        truck_mode = network.mode(param.assignment_modes["truck"])
        park_and_ride_mode = network.mode(param.park_and_ride_mode)
        extra_cost_attr = param.background_traffic_attr.replace("ul", "data")
        for link in network.links():
            if truck_mode in link.modes:
                link.modes |= {park_and_ride_mode}
            else:
                link.modes -= {park_and_ride_mode}
            link[extra_cost_attr] = link[param.extra_freight_cost_attr]
        self.emme_scenario.publish_network(network)
        for i, ass_class in enumerate(param.freight_modes):
            spec = self.assignment_modes[ass_class]
            spec.init_matrices()
            self.emme_project.transit_assignment(
                specification=spec.spec, scenario=self.emme_scenario,
                add_volumes=i, save_strategies=True, class_name=ass_class)
            self.emme_project.matrix_results(
                spec.result_spec, scenario=self.emme_scenario,
                class_name=ass_class)
            self.emme_project.matrix_results(
                spec.local_result_spec, scenario=self.emme_scenario,
                class_name=ass_class)
        log.info("Freight assignment performed for scenario {}".format(
            self.emme_scenario.id))

    def read_ship_impedances(self, is_export: bool) -> Tuple[dict, dict, dict]:
        """Create impedance matrices for freight ships using transit line
        attribute data.

        Parameters
        ----------
        is_export : bool
            Whether data should be fetched for export (True) or import (False)

        Returns
        -------
        dict
            Mode (container_ship/general_cargo...) : attribute
                Type (dist/frequency) : numpy.ndarray
        dict
            Finland border id (FIHEL/FISKV...) : str
                Centroid id : int
        dict
            Foreign border id (AEJEA/SESTO...) : str
                Centroid id : int
        """
        fin_borders = self._filter_border_points(finland_border_points)
        cluster_borders = self._filter_border_points(cluster_border_points)
        fin_mapping = {pid: idx for idx, pid in enumerate(fin_borders)}
        cluster_mapping = {pid: idx for idx, pid in enumerate(cluster_borders)}
        mappings = ((fin_mapping, cluster_mapping) if is_export
                    else (cluster_mapping, fin_mapping))

        transit_lines = self._get_marine_transit_lines(is_export)

        ship_impedances = {}
        for marine_ship, modes in param.freight_marine_modes.items():
            ship_impedances[marine_ship] = {}
            ship_mode = next(iter(modes))
            for key, attr in param.ship_attrs.items():
                ship_impedances[marine_ship][key] = self._line_data_to_matrix(
                    transit_lines[ship_mode], attr, *mappings)
        return ship_impedances, fin_borders, cluster_borders

    def _filter_border_points(self, border_data: dict) -> Dict[str, int]:
        """Filter out border centroids that don't exist in scenario's network.

        Parameters
        ----------
        border_data : dict
            key : str
                Border id (FIHEL/SESTO...)
            value : dict
                key : str
                    Attribute type (name/id)
                value : str | int
                    Attribute value

        Returns
        -------
        dict
            key : str
                Border id (FIHEL/SESTO...)
            value : int
                Centroid id
        """
        zone_numbers = self.emme_scenario.zone_numbers
        port_ids = {pid: border_data[pid]["id"] for pid in border_data
                    if border_data[pid]["id"] in zone_numbers}
        return port_ids

    def _get_marine_transit_lines(self, is_export: bool) -> dict:
        """Fetch list of marine transit lines.

        Parameters
        ----------
        is_export : bool
            Fetch export specific transit lines. Else import specific
        
        Returns
        -------
        dict
            marine mode : str
                marine ship mode
            transit lines : list
                Emme Transit line objects
        """
        mode_transit_lines = defaultdict(list)
        ship_modes = {mode for nesting in param.freight_marine_modes.values() 
                      for mode in nesting}
        for line in self.emme_scenario.get_network().transit_lines():
            # Marine transit line id in format port-port_shiptype
            if line.mode.id not in ship_modes or not line.id[0:2].isalpha():
                continue
            starts_in_fi = line.id[0:2] == "FI"
            if ((starts_in_fi and is_export) or (not starts_in_fi and not is_export)):
                mode_transit_lines[line.mode.id].append(line)
        return mode_transit_lines

    def _line_data_to_matrix(self, transit_lines: list, attribute: str,
                             orig_mapping: Dict[str, int],
                             dest_mapping: Dict[str, int]) -> numpy.ndarray:
        """Create inf matrix and insert attribute values into origin and
        destination indices of the matrix. OD pairs without trade route will 
        retain their inf attribute value.

        Parameters
        ----------
        transit_lines : list[Transit line]
            Emme transit line objects
        attribute : str
            Name of attribute
        orig_mapping : dict
            key : str
                Border id (FIHEL/SESTO...)
            value : int
                Index number (0, 1, 2, ...)
        dest_mapping : dict
            key : str
                Border id (FIHEL/SESTO...)
            value : int
                Index number (0, 1, 2, ...)

        Returns
        -------
        numpy.ndarray
            Impedance matrix with index inserted transit line attribute data
        """
        attr = attribute.replace("ut", "data")
        impedance_matrix = numpy.full(
            (len(orig_mapping), len(dest_mapping)), numpy.inf, dtype="float32")
        for line in transit_lines:
            # Marine transit line id in format port-port_shiptype
            o, d = str(line).split("_")[0].split("-")
            if o in orig_mapping and d in dest_mapping:
                impedance_matrix[orig_mapping[o], dest_mapping[d]] = line[attr]
        return impedance_matrix
