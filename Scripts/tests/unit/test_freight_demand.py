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

TEST_PATH = Path(__file__).parent.parent / "test_data"
TEST_DATA_PATH = TEST_PATH / "Scenario_input_data"
TEST_MATRICES = TEST_PATH / "Scenario_input_data" / "Matrices" / "uusimaa"
RESULT_PATH = TEST_PATH / "Results"
PARAMETERS_PATH = TEST_PATH.parent.parent / "parameters" / "freight"
ZONE_NUMBERS = [202, 1344, 1755, 2037, 2129, 2224, 2333, 2413, 2519, 2621,
                2707, 2814, 2918, 3000, 3003, 3203, 3302, 3416, 3639, 3705,
                3800, 4013, 4102, 4202, 7043, 8284, 12614, 17278, 19401, 23678,
                50107, 50127, 50201, 50205]


class FreightModelTest(unittest.TestCase):

    def test_freight_model(self):
        zonedata = FreightZoneData(
            TEST_DATA_PATH / "freight_zonedata.gpkg", numpy.array(ZONE_NUMBERS),
            "koko_suomi")
        resultdata = ResultsData(RESULT_PATH)
        with open(TEST_DATA_PATH / "costdata.json") as file:
            costdata = json.load(file)
        
        time_impedance = omx.open_file(TEST_MATRICES / "freight_time.omx", "r")
        dist_impedance = omx.open_file(TEST_MATRICES / "freight_dist.omx", "r")
        toll_impedance = omx.open_file(TEST_MATRICES / "freight_dist.omx", "r")
        impedance = {
            "truck": {
                "time": numpy.array(time_impedance["truck"]),
                "dist": numpy.array(dist_impedance["truck"]),
                "toll_cost": numpy.array(toll_impedance["truck"])
            },
            "freight_train": {
                "time": numpy.array(time_impedance["freight_train"]),
                "dist": numpy.array(dist_impedance["freight_train"]),
                "aux_time": numpy.array(time_impedance["freight_train_aux"]),
                "aux_dist": numpy.array(dist_impedance["freight_train_aux"]),
                "toll_cost": numpy.array(toll_impedance["freight_train"])
            },
            "ship": {
                "time": numpy.array(time_impedance["ship"]),
                "dist": numpy.array(dist_impedance["ship"]),
                "aux_time": numpy.array(time_impedance["ship_aux"]),
                "aux_dist": numpy.array(dist_impedance["ship_aux"]),
                "toll_cost": numpy.array(toll_impedance["ship"]),
                "canal_cost": numpy.zeros([len(ZONE_NUMBERS), len(ZONE_NUMBERS)])
            }
        }
        impedance["semi_trailer"] = impedance["truck"]
        impedance["trailer_truck"] = impedance["truck"]

        trade_demand, fin_borders = self.run_trade_route_choice(zonedata, resultdata, 
                                                                costdata, impedance)
        for mtx_type in impedance.keys():
            for ass_class, mtx in impedance[mtx_type].items():
                impedance[mtx_type][ass_class] = mtx[:zonedata.nr_zones, :zonedata.nr_zones]
        purposes = create_purposes(PARAMETERS_PATH / "domestic", zonedata, 
                                   resultdata, costdata["freight"])
        self.assertEqual(len(purposes), 2)

        total_demand = {mode: numpy.zeros_like(impedance["truck"]["time"])
                        for mode in param.truck_classes}
        for purpose in purposes.values():
            demand = purpose.calc_traffic(impedance)
            demand_trade = purpose.calc_trade_mode_share(demand, trade_demand, fin_borders)
            costs = purpose.get_costs(impedance)
            self._assert_calc_demand_results(demand, costs)
            aux_demand = {
                mode: numpy.ones_like(impedance["truck"]["time"])
                for mode in demand if mode != "truck"
            }
            for mode in param.truck_classes:
                ton_demand = demand["truck"] + sum(aux_demand.values())
                total_demand[mode] += purpose.calc_vehicles(ton_demand, mode)
            write_purpose_summary(purpose, demand, aux_demand, impedance, resultdata)
            write_zone_summary(purpose.name, zonedata.zone_numbers, demand, resultdata)
            write_domestic_leg_summary(demand_trade, impedance, resultdata)
        write_vehicle_summary(total_demand, impedance, resultdata)
        resultdata.flush()


    def run_trade_route_choice(self, zonedata, resultdata, costdata, impedance):
        marine_modes = ("container_ship", "roro_vessel")
        fin_border = {"FIHKO": 4102, "FIHMN": 19401}
        cluster_border = {"EETLL": 50107, "SESTO": 50127}
        trade_demand_path = Path(TEST_MATRICES / "trade_demand.omx")

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
                impedance, *marine_attr, trade_demand_path)
            write_leg2_summary(purpose, demand, marine_modes, 
                               fin_border, cluster_border, resultdata)
            trade_demand[purpose.name] = demand
        resultdata.flush()
        return trade_demand, list(fin_border.values())

    def _assert_calc_demand_results(self, demand, costs):
        for mode in demand:
            self.assertTrue(numpy.isfinite(demand[mode]).all())
            if mode == param.truck_classes[0]:
                self.assertTrue(numpy.isfinite(costs[mode]["cost"]).all())
            else:
                self.assertTrue(numpy.isfinite(costs[mode]["cost"]).any())
