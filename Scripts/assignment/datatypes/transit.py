from __future__ import annotations
from typing import TYPE_CHECKING, Dict

import parameters.assignment as param
from assignment.datatypes.assignment_mode import AssignmentMode
from assignment.datatypes.journey_level import JourneyLevel
if TYPE_CHECKING:
    from assignment.assignment_period import AssignmentPeriod
    from assignment.emme_bindings.mock_project import Scenario


class TransitMode(AssignmentMode):
    def __init__(self, name: str, assignment_period: AssignmentPeriod,
                 day_scenario: Scenario, save_matrices: bool = False,
                 save_extra_matrices: bool = False):
        """Initialize transit mode.

        Parameters
        ----------
        name : str
            Mode name
        assignment_period : AssignmentPeriod
            Assignment period to link to the mode
        day_scenario : Scenario
            EMME scenario linked to whole-day time period
        save_matrices : bool (optional)
            Whether matrices will be saved in Emme format for all time periods
        save_extra_matrices : bool (optional)
            Whether extra LOS-component matrices will be saved in Emme format
        """
        AssignmentMode.__init__(self, name, assignment_period, save_matrices)
        self.vot_inv = param.vot_inv[param.vot_classes[self.name]]
        self._create_matrices()

        # Create extra attributes
        self.segment_results: Dict[str, str] = {}
        self.node_results: Dict[str, str] = {}
        for scenario, tp in (
                (day_scenario, "vrk"), (self.emme_scenario, self.time_period)):
            for res, attr in param.segment_results.items():
                attr_name = f"#{self.name}_{attr[1:]}_{tp}"
                self.segment_results[res] = attr_name
                self.emme_project.create_network_field(
                    "TRANSIT_SEGMENT", "REAL", attr_name, f"{self.name} {res}",
                    overwrite=True, scenario=scenario)
                if res != "transit_volumes":
                    attr_name = f"#node_{self.name}_{attr[1:]}_{tp}"
                    self.node_results[res] = attr_name
                    self.emme_project.create_network_field(
                        "NODE", "REAL", attr_name, f"{self.name} {res}",
                        overwrite=True, scenario=scenario)

        # Specify
        no_penalty = dict.fromkeys(["at_nodes", "on_lines", "on_segments"])
        no_penalty["global"] = {
            "penalty": 0,
            "perception_factor": 1,
        }
        modes = (param.local_transit_modes + param.aux_modes
                 + param.long_dist_transit_modes[self.name])
        num_proc = "number_of_processors"
        self.transit_spec = {
            "type": "EXTENDED_TRANSIT_ASSIGNMENT",
            "modes": modes,
            "demand": self.demand.id,
            "waiting_time": {
                "headway_fraction": 1,
                "effective_headways": param.effective_headway_attr,
                "spread_factor": 1,
                "perception_factor": 1,
            },
            "boarding_time": {
                "global": None,
                "at_nodes": None,
                "on_lines": {
                    "penalty": param.boarding_penalty_attr + self.name,
                    "perception_factor": 1
                },
                "on_segments": param.extra_waiting_time,
            },
            # Boarding cost is defined for each journey level separately,
            # so here we just set the default to zero.
            "boarding_cost": no_penalty,
            "in_vehicle_time": {
                "perception_factor": 1
            },
            "in_vehicle_cost": {
                "penalty": param.line_penalty_attr,
                "perception_factor": self.vot_inv,
            },
            "flow_distribution_at_origins": {
                "choices_at_origins": "OPTIMAL_STRATEGY",
            },
            "flow_distribution_at_regular_nodes_with_aux_transit_choices": {
                "choices_at_regular_nodes": "OPTIMAL_STRATEGY",
            },
            "flow_distribution_between_lines": {
                "consider_total_impedance": True,
            },
            "journey_levels": None,
            "performance_settings": {
                num_proc: param.performance_settings[num_proc],
            },
        }
        aux_transit_times = []
        aux_perception_factor = (param.aux_time_perception_factor
            if name in param.local_transit_classes
            else param.aux_time_perception_factor_long)
        for mode in param.aux_modes:
            aux_transit_times.append({
                "mode": mode,
                "cost": None,
                "cost_perception_factor": 1.0,
                "time": param.aux_transit_time_attr,
                "time_perception_factor": aux_perception_factor})
        self.transit_spec["aux_transit_by_mode"] = aux_transit_times
        self.ntw_results_spec = {
            "type": "EXTENDED_TRANSIT_NETWORK_RESULTS",
            "analyzed_demand": self.demand.id,
            "on_segments": param.segment_results,
        }
        is_park_and_ride = self._add_park_and_ride()
        self.transit_spec["journey_levels"] = [JourneyLevel(
                level, self.name, is_park_and_ride).spec
            for level in range(7)]
        result_specs = self._add_matrix_specs(modes)
        for matrix_subset, spec in zip(
                param.transit_impedance_matrices.values(), result_specs):
            for mtx_type, longer_name in matrix_subset.items():
                if save_extra_matrices or mtx_type in param.impedance_output:
                    mtx = self._create_matrix(mtx_type)
                    spec[longer_name] = mtx.id

    def _create_matrices(self):
        self.num_board = self._create_matrix("num_board")
        self.gen_cost = self._create_matrix("gen_cost")
        self.inv_cost = self._create_matrix("inv_cost")
        self.board_cost = self._create_matrix("board_cost")

    def _add_park_and_ride(self):
        return False

    def _add_matrix_specs(self, modes):
        subset = "by_mode_subset"
        self.transit_result_specs = [{
            "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
            "total_impedance": self.gen_cost.id,
            subset: {
                "modes": modes,
                "actual_in_vehicle_costs": self.inv_cost.id,
                "actual_total_boarding_costs": self.board_cost.id,
                "avg_boardings": self.num_board.id,
            },
        }]
        return [
            self.transit_result_specs[0],
            self.transit_result_specs[0][subset],
        ]

    def assign(self, add_volumes: bool):
        """Assign transit class.

        Parameters
        ----------
        add_volumes : bool
            Whether volumes should be added to existing link volumes.
        """
        self.init_matrices()
        self._set_link_parking_costs()
        self.emme_project.transit_assignment(
            specification=self.transit_spec, scenario=self.emme_scenario,
            add_volumes=add_volumes, save_strategies=True,
            class_name=self.name)
        for result_spec in self.transit_result_specs:
            self.emme_project.matrix_results(
                result_spec, scenario=self.emme_scenario,
                class_name=self.name)

    def _set_link_parking_costs(self):
        """Used in MixedMode for setting parking costs on links."""
        pass

    def get_matrices(self):
        transfer_penalty = (param.transfer_penalty[self.name]
                            * (self.num_board.data > 0)).astype("float32")
        cost = self.inv_cost.data + self.board_cost.data
        time = self.gen_cost.data - self.vot_inv*cost - transfer_penalty
        time[cost > 999999] = 999999
        mtxs = {"time": time, "cost": cost}
        for mtx_name in param.impedance_output:
            if mtx_name in self._matrices:
                mtxs[mtx_name] = self._matrices[mtx_name].data
        self._soft_release_matrices()
        return mtxs

    def calc_transit_network_results(self):
        self.emme_project.network_results(
            self.ntw_results_spec, scenario=self.emme_scenario,
            class_name=self.name)
        network = self.emme_scenario.get_network()
        for result, attr in param.segment_results.items():
            netfield = self.segment_results[result]
            for segment in network.transit_segments():
                segment[netfield] = segment[attr]
        self._save_link_results(network)
        self.emme_scenario.publish_network(network)

    def _save_link_results(self, network):
        """Used in MixedMode for saving park-and-ride volumes."""
        pass


class MixedMode(TransitMode):
    def __init__(self, name: str, assignment_period: AssignmentPeriod,
                 day_scenario: Scenario, dist_unit_cost: float,
                 save_matrices: bool = False, save_extra_matrices: bool = False):
        TransitMode.__init__(
            self, name, assignment_period, day_scenario, save_matrices,
            save_extra_matrices)
        self.dist_unit_cost = dist_unit_cost

    def _create_matrices(self):
        TransitMode._create_matrices(self)
        self.car_time = self._create_matrix("car_time")
        self.car_dist = self._create_matrix("car_dist")
        self.loc_time = self._create_matrix("loc_time")
        self.aux_time = self._create_matrix("aux_time")
        self.park_cost = self._create_matrix("park_cost")

    def _add_park_and_ride(self):
        aux_perception_factor = (param.aux_time_perception_factor_long
            if 'l' in self.transit_spec["modes"]
            else param.aux_time_perception_factor_car)
        aux_transit_times = self.transit_spec["aux_transit_by_mode"]
        aux_transit_times.append({
            "mode": param.park_and_ride_mode,
            "time": param.aux_car_time_attr,
            "time_perception_factor": aux_perception_factor,
        })
        if "taxi" not in self.name:
            for mode_cost in aux_transit_times:
                mode_cost["cost"] = param.park_cost_attr_l
                mode_cost["cost_perception_factor"] = self.vot_inv
        self.park_ride_results = f"#park_and_ride_vol_{self.name}"
        self.emme_project.create_network_field(
            "LINK", "REAL", self.park_ride_results, self.name,
            overwrite=True, scenario=self.emme_scenario)
        self.transit_spec["modes"].append(param.park_and_ride_mode)
        self.ntw_results_spec["on_links"] = {
            "aux_transit_volumes_by_mode": [{
                "mode": param.park_and_ride_mode,
                "volume": param.park_ride_vol_attr,
            }],
        }
        return True

    def _add_matrix_specs(self, modes):
        local_transit_modes = [mode for mode in param.local_transit_modes
            if mode not in param.long_dist_transit_modes[self.name]]
        specs = [
            {
                "modes": local_transit_modes + param.aux_modes,
                "perceived_aux_transit_times": self.aux_time.id,
                "perceived_in_vehicle_times": self.loc_time.id,
            },
            {
                "modes": [param.park_and_ride_mode],
                "distance": self.car_dist.id,
                "actual_aux_transit_times": self.car_time.id,
            },
            {
                "modes": [param.park_and_ride_mode] + param.aux_modes,
                "actual_aux_transit_costs": self.park_cost.id,
            },
        ]
        result_specs: list = TransitMode._add_matrix_specs(self, modes)
        result_specs += specs
        self.transit_result_specs += [{
            "type": "EXTENDED_TRANSIT_MATRIX_RESULTS",
            "by_mode_subset": spec,
        } for spec in specs]
        return result_specs

    def _set_link_parking_costs(self):
        network = self.emme_scenario.get_network()
        avg_days = param.tour_duration[self.name]["avg"]
        for node in network.nodes():
            parking_cost = node[param.park_cost_attr_n]
            if parking_cost > 0:
                parking_cost *= 0.5 * avg_days
                if self.name in param.car_access_classes:
                    parking_links = node.incoming_links()
                    other_links = node.outgoing_links()
                else:
                    other_links = node.incoming_links()
                    parking_links = node.outgoing_links()
                for link in parking_links:
                    link[param.park_cost_attr_l] = parking_cost
                for link in other_links:
                    link[param.park_cost_attr_l] = 0
        self.emme_scenario.publish_network(network)

    def get_matrices(self):
        car_cost = self.dist_unit_cost * self.car_dist.data
        mtxs = TransitMode.get_matrices(self)
        mtxs["cost"] += car_cost
        mtxs["transfer_time"] = self.loc_time.data + self.aux_time.data
        return mtxs

    def _save_link_results(self, network):
        for link in network.links():
            link[self.park_ride_results] = link[param.park_ride_vol_attr]
