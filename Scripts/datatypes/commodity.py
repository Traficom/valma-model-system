from __future__ import annotations
from typing import List, Dict
from pathlib import Path
import json
import numpy # type: ignore
import pandas

from datatypes.purpose import Purpose
from datahandling.zonedata import FreightZoneData
from datahandling.resultdata import ResultsData
from datahandling.matrixdata import read_omx_item
import utils.log as log
import parameters.zone as param
from parameters.commodity import commodity_conversion
import models.logit as logit
from utils.freight_costs import calc_cost, get_foreign_ship_cost
from models.logistics import (LogisticsModule, TradeRouteModule,
                              run_logistics_model, run_trade_model)
from parameters.marine_ship import leg_names
from parameters.zone import clusters


def create_commodities(parameters_path: Path, zonedata: FreightZoneData,
                       resultdata: ResultsData, costdata: Dict[str, dict]):
    """Create instances of FreightPurpose for each model parameter json file
    in parameters path.

    Parameters
    ----------
    parameters_path : Path
        Path object folder containing model parameters
        json files
    zonedata : FreightZoneData
        freight zonedata container
    resultdata : ResultsData
        handler for result saving operations
    costdata : Dict[str, dict]
        Freight purpose : Freight mode
            Freight mode (truck/freight_train/ship) : mode
                Mode (truck/trailer_truck...) : unit cost name
                    unit cost name : unit cost value

    Returns
    -------
    dict[str, FreightPurpose]
        purpose name : FreightPurpose
    """
    purposes: Dict[str, FreightCommodity] = {}
    for file in parameters_path.rglob("*.json"):
        commodity_params = json.loads(file.read_text("utf-8"))
        commodity = commodity_params["name"].split("_")[0]
        purpose_cost = costdata.get(commodity_conversion[commodity])
        if not purpose_cost:
            log.warn(f"Aggregated commodity class '{commodity_conversion[commodity]}' "
                     f"for commodity '{commodity}' not found in costs json")
            continue
        zone_data = {parameters_path.stem: zonedata}
        if parameters_path.stem == "foreign":
            zone_data["domestic"] = zonedata
            purposes[commodity_params["name"]] = ForeignCommodity(
                commodity_params, zone_data, resultdata, purpose_cost)
        else:
            purposes[commodity_params["name"]] = DomesticCommodity(
                commodity_params, zone_data, resultdata, purpose_cost)
    return purposes


class FreightCommodity(Purpose):
    """Standard purpose for handling freight calculations.

    Parameters
    ----------
    specification : dict
        Model parameter specifications
    zone_data : Dict[str, FreightZoneData]
        Model area (domestic/foreign) : Data used for all demand calculations
    resultdata : ResultData
        Writer object to result directory
    costdata : Dict[str, dict]
        Freight mode (truck/freight_train/ship) : mode
            Mode (truck/trailer_truck...) : unit cost name
                unit cost name : unit cost value
    """
    def __init__(self, specification, zone_data, resultdata, costdata):
        Purpose.__init__(self, specification, zone_data, resultdata)
        self.costdata = costdata
        self.model_category = list(zone_data)[0]
        self.modes: List[str] = list(specification["mode_choice"])
        args = (self, specification, self.generation_zone_data,
                self.attraction_zone_data, resultdata)
        if specification["struct"] == "dest>mode":
            self.model = logit.DestModeModel(*args)
        elif specification["struct"] == "mode>dest":
            self.model = logit.ModeDestModel(*args)
        else:
            self.model = None
        self.route_params = specification.get("route_choice", None)
        self.is_export = {"export": True, "import": False}.get(
            specification["struct"])

        if (self.model is None and self.model_category == "domestic"
            or self.is_export is None and self.model_category == "foreign"):
            msg = f"Purpose {self.name} has invalid struct in specification"
            log.error(msg)
            raise ValueError(msg)
        elif self.route_params is None and self.model_category == "foreign":
            msg = f"Purpose {self.name} is missing route choice specification"
            log.error(msg)
            raise ValueError(msg)

    def get_costs(self, impedance: dict):
        """Fetch calculated costs for each mode in model's mode choice.

        Parameters
        ----------
        impedance : dict
            Mode (truck/train/...) : dict
                Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix

        Returns
        -------
        dict
            Mode (truck/freight_train/...) : cost : numpy.ndarray
        """
        costs = {mode: calc_cost(
                    mode, self.costdata, impedance[mode], self.model_category)
                 for mode in self.modes}
        for mode, mode_costs in costs.items():
            if not self.model or "aux_cost" not in self.model.mode_choice_param[mode]["impedance"]:
                mode_costs["cost"] += mode_costs.pop("aux_cost", 0)
        return costs

    def calc_vehicles(self, matrix: numpy.ndarray, ass_class: str):
        """Calculate vehicle matrix from ton matrix using ton-to-vehicles
        conversion values.

        Parameters
        ----------
        matrix : numpy.ndarray
            ton matrix
        ass_class : str
            truck assignment class

        Returns
        -------
        numpy.ndarray
            vehicle matrix
        """
        costdata = self.costdata["truck"][ass_class]
        vehicles = (matrix * costdata[f"{self.model_category}_distribution"]
                    / costdata["avg_load"] / 365)
        vehicles += vehicles.T * costdata["empty_share"]
        return vehicles


class DomesticCommodity(FreightCommodity):

    def calc_traffic(self, impedance: dict, iterations: int = 0):
        """Calculate freight traffic matrix.

        Parameters
        ----------
        impedance : dict
            Mode (truck/train/...) : dict
                Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix
        iterations : int (default: 0)
            Number of times logistics module is run

        Return
        ------
        dict
            Mode (truck/train/...) : calculated demand (numpy 2d matrix)
        """
        costs = self.get_costs(impedance)
        self.dist = costs[self.modes[0]]["cost"]
        nr_zones = self.attraction_zone_data.nr_zones
        probs = self.model.calc_prob(costs)
        generation = numpy.tile(
            self.generation_zone_data[f"gen_{self.name}"], (nr_zones, 1))
        demand = {mode: (probs.pop(mode) * generation).T for mode in self.modes}
        if self.route_params and iterations > 0:
            demand["truck"], _ = self.run_logistics_module(
                demand["truck"], impedance, iterations)
        return demand

    def run_logistics_module(self, demand_truck: numpy.ndarray,
                             impedance: numpy.ndarray,
                             iterations: int) -> tuple:
        """Run logistics module for truck demand within Finland.

        Parameters
        ----------
        demand_truck : numpy.ndarray
            Modelled truck demand for purpose
        impedance : dict
            Mode (truck/train/...) : dict
                Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix
        iterations : int
            Number of times logistics module is run

        Returns
        -------
        Tuple[np.ndarray]
            Routed truck demand, and totals for detoured and direct demand
        """
        zone_data = self.generation_zone_data
        try:
            lcs_areas = zone_data[f"lc_area_{self.name}"]
        except KeyError:
            lcs_areas = zone_data["lc_area"]
        lc_sizes = lcs_areas[lcs_areas > 0]
        zone_index_map = {
            zone: i for i, zone in enumerate(zone_data.all_zone_numbers)}
        lc_indices = numpy.array([zone_index_map.get(id, None)
                                for id in list(lc_sizes.index)])
        lc_sizes = lc_sizes.to_numpy()
        cost = self.get_costs(impedance)
        model = LogisticsModule(cost, self.route_params, lc_indices, lc_sizes)
        for i in range(1, iterations + 1):
            demand_truck, per_route = run_logistics_model(model, demand_truck, i)
        return demand_truck, per_route

    def calc_trade_mode_share(self, dom_demand: dict, trade_demand: dict,
                              fin_borders: list):
        """Calculate mode share of trade demand on its domestic leg
        among freight land mode alternatives.

        Parameters
        ----------
        dom_demand : dict
            Mode (truck/train/...) : domestic demand numpy 2d array
        trade_demand : dict
            Foreign purpose name : str
                Leg (one/two/three) : str
                    Mode (truck/container_ship...) : trade demand numpy 2d array
        fin_borders : list[int]
            Finnish border centroid ids

        Returns
        -------
        dict
            Foreign purpose name : str
                Mode (truck/freight_train) : trade demand domestic leg numpy 2d array
        """
        demand_sum = sum(dom_demand[mode] for mode in dom_demand
                         if mode in ["truck", "freight_train"])
        truck_share = numpy.zeros_like(demand_sum)
        numpy.divide(dom_demand["truck"], demand_sum, out=truck_share,
                     where=demand_sum > 0.0)
        train_share = numpy.ones_like(truck_share) - truck_share

        # Extracts trade purposes with same name as self.name
        # e.g. if self is kemlaa, extracts kemlaa_export and kemlaa_import
        purpose_trade_demand = {
            k: v for k, v in trade_demand.items()
            if k.startswith(f"{self.name}_")
        }

        dom_leg_demand = {}
        for purpose, demand in purpose_trade_demand.items():
            demand_full = pandas.DataFrame(
                0, index=self.orig_zone_numbers, columns=self.orig_zone_numbers,
                dtype=numpy.float32
            )
            if purpose.endswith("_export"):
                demand_full.loc[:, fin_borders] = demand["leg_one"]["truck"]
            else:
                demand_full.loc[fin_borders, :] = demand["leg_three"]["truck"]
            dom_leg_demand[purpose] = {"truck": demand_full.values * truck_share}
            train_demand = demand_full.values * train_share
            if numpy.sum(train_demand) > 0.0:
                dom_leg_demand[purpose]["freight_train"] = train_demand
        return dom_leg_demand

    def write_summary(self, demand: dict, aux_demand: dict,
                            impedance: dict):
        """Write purpose-mode specific summary as txt-file containing mode
        shares calculated from demand (tons), mode specific demand (tons),
        mode shares calculated from mileage, mode specific ton-mileage, 
        mode auxiliary ton-mileage and total eur-ton product.
        """
        modes = list(demand)
        mode_tons = numpy.array([numpy.sum(demand[mode])
                                for mode in modes], dtype=numpy.int32)
        mode_ton_dist = numpy.array([numpy.sum(demand[mode] * impedance[mode]["dist"])
                                    for mode in modes], dtype=numpy.int64)
        costs = {mode: numpy.nan_to_num(c["cost"], posinf=0)
                for mode, c in self.get_costs(impedance).items()}
        df = pandas.DataFrame(data={
            "Commodity": [self.name] * len(modes),
            "Mode": modes,
            "Mode share from tons (%)": numpy.round(mode_tons / mode_tons.sum(), 3),
            "Tons (t/annual)": mode_tons,
            "Mode share from mileage (%)": numpy.round(mode_ton_dist / mode_ton_dist.sum(), 3),
            "Ton mileage (tkm/annual)": mode_ton_dist,
            "Aux ton mileage (tkm/annual)": [
                int(numpy.sum(aux_demand[mode] * impedance[mode]["aux_dist"]))
                if mode != "truck" else 0 for mode in modes
            ],
            "Costs (eur-ton/annual)": [
                int(numpy.sum(costs[mode] * demand[mode]))
                for mode in modes
            ]
        })
        filename = "freight_purpose_summary.txt"
        self.resultdata.print_concat(df, filename)

    def write_zone_summary(self, demand: dict):
        """Write purpose and mode specific departing and arriving tons
        for each zone in zone mapping.
        """
        df = pandas.DataFrame(index=self.generation_zone_data.zone_numbers)
        for mode in demand:
            df[f"Departing_{self.name}_{mode}"] = numpy.sum(
                demand[mode], axis=1, dtype="int32")
            df[f"Arriving_{self.name}_{mode}"] = numpy.sum(
                demand[mode], axis=0, dtype="int32")
        filename = "freight_zone_summary.txt"
        self.resultdata.print_data(df, filename)


class ForeignCommodity(FreightCommodity):

    def form_impedance_legs(self, impedance: dict,
                            ship_imps: dict,
                            fin_border_ids: dict,
                            cluster_border_ids: dict) -> dict:
        """Form impedance matrices for the three legs of foreign trade
        route choice model.

        Parameters
        ----------
        impedance : dict
            Mode (truck/train/...) : dict
                Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix
        ship_imps : dict
            Mode (container_ship/general_cargo...) : attribute
                Type (dist/frequency) : numpy.ndarray
        fin_border_ids : dict
            Finland border id (FIHEL/FISKV...) : str
                Centroid id : int
        cluster_border_ids : dict
            Foreign border id (AEJEA/SESTO...) : str
                Centroid id : int

        Returns
        -------
        dict
            Name of a leg (leg_one/...) : dict
                Mode (truck/train/marine ships) : dict
                    Type (cost/frequency/draught) : mask indexed numpy 2d matrix
        """
        fin_port_zones = numpy.array(
            list(fin_border_ids.values()), dtype=numpy.int32)
        cluster_port_zones = numpy.array(
            list(cluster_border_ids.values()), dtype=numpy.int32)
        all_zones = self.generation_zone_data.all_zone_numbers
        fin_borders = numpy.isin(all_zones, fin_port_zones)
        cluster_borders = numpy.isin(all_zones, cluster_port_zones)
        fin_zones = numpy.isin(all_zones, numpy.union1d(self.orig_zone_numbers,
                                                        fin_port_zones))
        cluster_zones = ~fin_zones & ~cluster_borders

        masks = (fin_zones, fin_borders, cluster_borders, cluster_zones)
        if not self.is_export:
            masks = masks[::-1]

        costs = self.get_costs(impedance)
        impedance_legs = {l: {} for l in leg_names}
        for i, imp_leg in enumerate(impedance_legs.values()):
            imp_leg["truck"] = {imp_type: mtx[numpy.ix_(masks[i], masks[i+1])]
                                for imp_type, mtx in costs["truck"].items()}
        ship_costs = get_foreign_ship_cost(
            self.costdata, ship_imps, self.model_category, fin_border_ids,
            self.is_export)
        impedance_legs["leg_two"].update(ship_costs)

        # Retain leg two truck cost only for designated land border pairs
        mask = pandas.DataFrame(
            True, index=fin_port_zones, columns=cluster_port_zones)
        for fin_border, cluster_border in param.land_border_pairs.values():
            if fin_border in fin_port_zones and cluster_border in cluster_port_zones:
                mask.at[fin_border, cluster_border] = False
        if not self.is_export:
            mask = mask.T
        impedance_legs["leg_two"]["truck"]["cost"][mask.to_numpy()] = numpy.inf
        return impedance_legs

    def run_trade_route_module(self, impedance: dict,
                               ship_imps: dict,
                               fin_border_ids: dict,
                               cluster_border_ids: dict,
                               trade_demand_path):
        """Run foreign trade route choice module.

        Parameters
        ----------
        impedance : dict
            Mode (truck/train/...) : dict
                Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix
        ship_imps : dict
            Mode (container_ship/general_cargo...) : attribute
                Type (dist/frequency) : numpy.ndarray
        fin_border_ids : dict
            Finland border id (FIHEL/FISKV...) : str
                Centroid id : int
        cluster_border_ids : dict
            Foreign border id (AEJEA/SESTO...) : str
                Centroid id : int
        trade_demand_path : Path
            argument path to trade demand omx-file

        Returns
        -------
        dict
            Leg name (one/two/three) : Mode
                Name (truck/container_ship...) : numpy 2d array
        """
        impedance_legs = self.form_impedance_legs(
            impedance, ship_imps, fin_border_ids, cluster_border_ids)
        demand, trade_mappings = read_omx_item(trade_demand_path, self.name)

        mapping_name = (self.generation_zone_data.mapping.name if self.is_export
                        else self.attraction_zone_data.mapping.name)
        if mapping_name == "municipality_center":
            df = pandas.DataFrame(demand, trade_mappings["finland_zone_number"])
            demand = df.groupby(self.generation_zone_data.mapping).sum().to_numpy()
        demand = demand.T if not self.is_export else demand

        # Finland border control point key - zone index
        border_indices = {key: idx for idx, key in enumerate(fin_border_ids)}
        route_model = TradeRouteModule(impedance_legs, self.route_params,
                                       border_indices, self.is_export)
        trade_demand = run_trade_model(route_model, demand)
        self.write_trade_route_summary(
            trade_demand, fin_border_ids, cluster_border_ids)
        self.write_trade_route_summary(
            trade_demand, fin_border_ids, cluster_border_ids, clusters)
        return trade_demand

    def write_trade_route_summary(self,
                                  demand: dict,
                                  fin_border_ids: dict,
                                  cluster_border_ids: dict,
                                  clusters: dict = None):
        """Write summary from routed trade demand matrix.
        Handles both 2nd leg and cluster_border summary outputs.
        """
        commodity, trade_type = self.name.split("_")
        cluster_border_indices = dict(enumerate(cluster_border_ids))
        match_clusters = self.is_export == bool(clusters)
        if clusters:
            key_indices = dict(enumerate(clusters))
            leg_name = "leg_three" if self.is_export else "leg_one"
            label = "Cluster"
            filename = "freight_cluster_border_summary.txt"
        else:
            key_indices = dict(enumerate(fin_border_ids))
            leg_name = "leg_two"
            label = "Finnish border"
            filename = "freight_leg2_summary.txt"
        df_data = [
            {
                "Commodity": commodity,
                "Type": trade_type,
                "Mode": mode,
                label: key_indices[col if match_clusters else row],
                "Foreign_border": cluster_border_indices[row if match_clusters else col],
                "Tons (t/annual)": mtx[row, col]
            }
            for mode, mtx in demand[leg_name].items()
            for row, col in zip(*numpy.nonzero(numpy.round(mtx, 5)))
        ]
        self.resultdata.print_concat(pandas.DataFrame(df_data), filename)
