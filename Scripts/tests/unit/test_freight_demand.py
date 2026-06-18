#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import json
import numpy
import unittest
import openmatrix as omx

import parameters.assignment as param
from datahandling.resultdata import ResultsData
from datahandling.zonedata import FreightZoneData
from utils.freight_utils import (
    create_purposes, write_leg2_summary, write_purpose_summary, 
    write_zone_summary, write_vehicle_summary, write_domestic_leg_summary
)
from tests.integration.test_data_handling import (
    TEST_DATA_PATH,
    RESULTS_PATH,
    COSTDATA_PATH,
    BASE_MATRICES_PATH,
)

TEST_MATRICES = RESULTS_PATH / "Matrices" / "koko_suomi"
TEST_ZONE_DATA_PATH = TEST_DATA_PATH / "Scenario_input_data" / "freight_zonedata.gpkg"
TRADE_DEMAND_PATH = BASE_MATRICES_PATH / "koko_suomi" / "trade_demand.omx"
PARAMETERS_PATH = TEST_DATA_PATH.parent.parent / "parameters" / "freight"
ZONE_NUMBERS = [202, 1344, 1755, 2037, 2129, 2224, 2333, 2413, 2519, 2621,
                2707, 2814, 2918, 3000, 3003, 3203, 3302, 3416, 3639, 3705,
                3800, 4013, 4102, 4202, 7043, 8284, 12614, 17278, 19401, 23678,
                50107, 50127, 50201, 50205]


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
        impedance["semi_trailer"] = impedance["truck"]
        impedance["trailer_truck"] = impedance["truck"]

        # Run test foreign trade choice model
        trade_demand, foreign_purposes, fin_borders = self.run_trade_route_choice(
            zonedata, resultdata, costdata, impedance)
        for mtx_type in impedance.keys():
            for ass_class, mtx in impedance[mtx_type].items():
                impedance[mtx_type][ass_class] = mtx[:zonedata.nr_zones, :zonedata.nr_zones]
        purposes = create_purposes(PARAMETERS_PATH / "domestic", zonedata, 
                                   resultdata, costdata["freight"])
        self.assertEqual(len(purposes), 2)

        total_demand = {mode : numpy.zeros_like(impedance["truck"]["cost"])
                        for mode in param.truck_classes}
        iterations = 1
        mapping = {zone: idx for idx, zone in enumerate(zonedata.zone_numbers)}
        
        # Run test domestic demand model
        for purpose in purposes.values():
            demand = purpose.calc_traffic(impedance)
            demand_trade = purpose.calc_trade_mode_share(demand, trade_demand, fin_borders)
            costs = purpose.get_costs(impedance)
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
                vehicles["domestic"][mode] += purpose.calc_vehicles(ton_demand, mode)
                for foreign_purpose in demand_trade:
                    vehicles["foreign"][mode] += foreign_purposes[foreign_purpose].calc_vehicles(
                        demand_trade[foreign_purpose]["truck"], mode)
                total_demand[mode] += vehicles["domestic"][mode] + vehicles["foreign"][mode]
            self._assert_calc_vehicle_results(vehicles, purpose.name)
            write_purpose_summary(purpose, demand, aux_demand, impedance, resultdata)
            write_zone_summary(purpose.name, zonedata.zone_numbers, demand, resultdata)
            write_domestic_leg_summary(demand_trade, impedance, resultdata)
            
            # Calculate test logistics demand
            if purpose.route_params and iterations > 0:
                demand_truck, per_route = purpose.run_logistics_module(demand["truck"],
                                                                       impedance, mapping, 
                                                                       iterations)
                self.assertTrue(numpy.isfinite(demand_truck).all())
                self.assertTrue((demand_truck >= 0).all())
                self.assertTrue(demand_truck.shape == (zonedata.nr_zones, zonedata.nr_zones))

                detour_total = numpy.sum(per_route[:-1])
                direct_total = per_route[-1]
                if purpose.name == "kemlaa":
                    self.assertAlmostEqual(detour_total, 50.635654, places=3)
                    self.assertAlmostEqual(direct_total, 12883.39, places=3)
                elif purpose.name == "kummuo":
                    self.assertAlmostEqual(detour_total, 81.766624, places=3)
                    self.assertAlmostEqual(direct_total, 15670.479, places=3)

        write_vehicle_summary(total_demand, impedance, resultdata)
        resultdata.flush()


    def run_trade_route_choice(self, zonedata, resultdata, costdata, impedance):
        marine_modes = ("container_ship", "roro_vessel")
        fin_border = {"FIHKO": 4102, "FIHMN": 19401}
        cluster_border = {"EETLL": 50107, "SESTO": 50127}

        purposes = create_purposes(PARAMETERS_PATH / "foreign", zonedata, 
                                   resultdata, costdata["freight"])
        del purposes["kummuo_export"]
        del purposes["kummuo_import"]
        self.assertEqual(len(purposes), 2)

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

        trade_demand = {}
        for purpose in purposes.values():
            demand = purpose.run_trade_route_module(
                impedance, *marine_attr, TRADE_DEMAND_PATH)
            write_leg2_summary(purpose, demand, marine_modes, 
                               fin_border, cluster_border, resultdata)
            trade_demand[purpose.name] = demand
        resultdata.flush()
        return trade_demand, purposes, list(fin_border.values())

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
