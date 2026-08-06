#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import numpy
import unittest
import openmatrix as omx
from copy import deepcopy

import parameters.assignment as param
from datahandling.resultdata import ResultsData
from datahandling.zonedata import FreightZoneData
from datatypes.commodity import create_commodities
from utils.freight_utils import (
    update_diagonal_cost, write_vehicle_summary,
    write_domestic_leg_summary,
)
from tests.integration.test_data_handling import (
    TEST_DATA_PATH,
    RESULTS_PATH,
    COSTDATA_PATH,
    BASE_MATRICES_PATH,
    INTERNAL_ZONES,
    EXTERNAL_ZONES
)
from parameters.zone import clusters

TEST_MATRICES = RESULTS_PATH / "Matrices" / "koko_suomi"
TEST_ZONE_DATA_PATH = TEST_DATA_PATH / "Scenario_input_data" / "freight_zonedata.gpkg"
TRADE_DEMAND_PATH = BASE_MATRICES_PATH / "koko_suomi" / "trade_demand.omx"
PARAMETERS_PATH = TEST_DATA_PATH.parent.parent / "parameters" / "freight"
ZONE_NUMBERS = INTERNAL_ZONES + EXTERNAL_ZONES


class FreightModelTest(unittest.TestCase):

    def test_freight_model(self):
        zonedata = FreightZoneData(
            TEST_ZONE_DATA_PATH, numpy.array(ZONE_NUMBERS), "koko_suomi")
        resultdata = ResultsData(RESULTS_PATH)
        with open(COSTDATA_PATH) as file:
            costdata = json.load(file)
        
        time_impedance = omx.open_file(TEST_MATRICES / "freight_time.omx", "r")
        dist_impedance = omx.open_file(TEST_MATRICES / "freight_dist.omx", "r")
        cost_impedance = omx.open_file(TEST_MATRICES / "freight_cost.omx", "r")
        impedance = {
            "truck": {
                "cost": numpy.array(cost_impedance["truck"]),
                "dist": numpy.array(dist_impedance["truck"]),
            },
            "freight_train": {
                "time": numpy.array(time_impedance["freight_train"]),
                "dist": numpy.array(dist_impedance["freight_train"]),
                "aux_cost": numpy.array(cost_impedance["freight_train_aux"]),
                "aux_dist": numpy.array(dist_impedance["freight_train_aux"]),
            },
            "ship": {
                "time": numpy.array(time_impedance["ship"]),
                "dist": numpy.array(dist_impedance["ship"]),
                "aux_cost": numpy.array(cost_impedance["ship_aux"]),
                "aux_dist": numpy.array(dist_impedance["ship_aux"]),
                "canal_cost": numpy.zeros([len(ZONE_NUMBERS), len(ZONE_NUMBERS)])
            }
        }
        impedance["semi_trailer"] = deepcopy(impedance["truck"])
        impedance["trailer_truck"] = deepcopy(impedance["truck"])
        impedance = update_diagonal_cost(impedance)

        # Run test foreign trade choice model
        trade_demand, foreign_purposes, fin_borders = self.run_trade_route_choice(
            zonedata, resultdata, costdata, impedance)
        for mtx_type in impedance.keys():
            for ass_class, mtx in impedance[mtx_type].items():
                impedance[mtx_type][ass_class] = mtx[:zonedata.nr_zones, :zonedata.nr_zones]
        commodities = create_commodities(
            PARAMETERS_PATH / "domestic", zonedata, resultdata,
            costdata["freight"])
        self.assertEqual(len(commodities), 2)

        total_demand = {mode : numpy.zeros_like(impedance["truck"]["cost"])
                        for mode in param.truck_classes}
        iterations = 1
        mapping = {zone: idx for idx, zone in enumerate(zonedata.zone_numbers)}
        
        # Run test domestic demand model
        for commodity in commodities.values():
            demand = commodity.calc_traffic(impedance)
            demand_trade = commodity.calc_trade_mode_share(demand, trade_demand, fin_borders)
            costs = commodity.get_costs(impedance)
            self._assert_calc_demand_results(demand, costs)
            
            # Calculate test vehicles
            aux_demand = {
                mode: numpy.ones_like(impedance["truck"]["cost"])
                for mode in demand if mode != "truck"
            }
            ton_demand = demand["truck"] + sum(aux_demand.values())
            vehicles = {
                model_type: {mode : numpy.zeros_like(impedance["truck"]["cost"])
                             for mode in param.truck_classes}
                for model_type in ("domestic", "foreign")
            }
            for mode in param.truck_classes:
                vehicles["domestic"][mode] += commodity.calc_vehicles(ton_demand, mode)
                for foreign_purpose in demand_trade:
                    vehicles["foreign"][mode] += foreign_purposes[foreign_purpose].calc_vehicles(
                        demand_trade[foreign_purpose]["truck"], mode)
                total_demand[mode] += vehicles["domestic"][mode] + vehicles["foreign"][mode]
            self._assert_calc_vehicle_results(vehicles, commodity.name)
            commodity.write_summary(demand, aux_demand, impedance)
            commodity.write_zone_summary(demand)
            write_domestic_leg_summary(demand_trade, impedance, resultdata)
            
            # Calculate test logistics demand
            if commodity.route_params and iterations > 0:
                demand_truck, per_route = commodity.run_logistics_module(
                    demand["truck"], impedance, iterations)
                self.assertTrue(numpy.isfinite(demand_truck).all())
                self.assertTrue((demand_truck >= 0).all())
                self.assertTrue(demand_truck.shape == (zonedata.nr_zones, zonedata.nr_zones))

                detour_total = numpy.sum(per_route[:-1])
                direct_total = per_route[-1]
                if commodity.name == "kemlaa":
                    self.assertAlmostEqual(detour_total, 19.52376, places=3)
                    self.assertAlmostEqual(direct_total, 12913.464, places=3)
                elif commodity.name == "kummuo":
                    self.assertAlmostEqual(detour_total, 26.133245, places=3)
                    self.assertAlmostEqual(direct_total, 15725.467, places=3)

        write_vehicle_summary(total_demand, impedance, resultdata)
        resultdata.flush()


    def run_trade_route_choice(self, zonedata, resultdata, costdata, impedance):
        marine_modes = ("container_ship", "roro_vessel")
        fin_border = {"FIHKO": 4102, "FIHMN": 19401}
        cluster_border = {"EETLL": 50107, "SESTO": 50127}

        commodities = create_commodities(
            PARAMETERS_PATH / "foreign", zonedata, resultdata,
            costdata["freight"])
        del commodities["kummuo_export"]
        del commodities["kummuo_import"]
        self.assertEqual(len(commodities), 2)

        ship_imps = {
            mode: {
                imp: numpy.full((len(fin_border), len(fin_border)), 
                                numpy.inf, dtype="float32")
                for imp in ("dist", "frequency")}
            for mode in marine_modes
        }
        ship_imps["container_ship"]["dist"][1][1] = 532
        ship_imps["container_ship"]["frequency"][1][1] = 38
        ship_imps["roro_vessel"]["dist"][0][0] = 126
        ship_imps["roro_vessel"]["frequency"][0][0] = 162
        marine_attr = (ship_imps, fin_border, cluster_border)
        network_clusters = set(ZONE_NUMBERS) & set(clusters.values())
        network_clusters = {key: value for key, value in clusters.items() 
                            if value in network_clusters}

        trade_demand = {}
        for purpose in commodities.values():
            demand = purpose.run_trade_route_module(
                impedance, *marine_attr, TRADE_DEMAND_PATH)
            trade_demand[purpose.name] = demand
        resultdata.flush()
        return trade_demand, commodities, list(fin_border.values())

    def _assert_calc_demand_results(self, demand, costs):
        for mode in demand:
            self.assertTrue(numpy.isfinite(demand[mode]).all())
            if mode == param.truck_classes[0]:
                self.assertTrue(numpy.isfinite(costs[mode]["cost"]).all())
            else:
                self.assertTrue(numpy.isfinite(costs[mode]["cost"]).any())

    def _assert_calc_vehicle_results(self, vehicles, purpose_name):
        dom_vehicles = vehicles["domestic"]
        for_vehicles = vehicles["foreign"] 
        if purpose_name == "kemlaa":
            self.assertAlmostEqual(numpy.sum(dom_vehicles["truck"]), 2.1024585, places=3)
            self.assertAlmostEqual(numpy.sum(for_vehicles["truck"]), 0.032649778, places=3)
            self.assertAlmostEqual(numpy.sum(dom_vehicles["semi_trailer"]), 1.2102093, places=3)
            self.assertAlmostEqual(numpy.sum(for_vehicles["semi_trailer"]), 0.05011665, places=3)
            self.assertAlmostEqual(numpy.sum(dom_vehicles["trailer_truck"]), 1.0011706, places=3)
            self.assertAlmostEqual(numpy.sum(for_vehicles["trailer_truck"]), 0.031095028, places=3)
        elif purpose_name == "kummuo":
            self.assertAlmostEqual(numpy.sum(dom_vehicles["truck"]), 2.5046012, places=3)
            self.assertAlmostEqual(numpy.sum(for_vehicles["truck"]), 0.0, places=3)
            self.assertAlmostEqual(numpy.sum(dom_vehicles["semi_trailer"]), 1.4416891, places=3)
            self.assertAlmostEqual(numpy.sum(for_vehicles["semi_trailer"]), 0.0, places=3)
            self.assertAlmostEqual(numpy.sum(dom_vehicles["trailer_truck"]), 1.1926672, places=3)
            self.assertAlmostEqual(numpy.sum(for_vehicles["trailer_truck"]), 0.0, places=3)
