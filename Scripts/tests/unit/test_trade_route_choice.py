#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import json
import numpy
import unittest
import openmatrix as omx

from datahandling.resultdata import ResultsData
from datahandling.zonedata import FreightZoneData
from utils.freight_utils import create_purposes
from parameters.marine_ship import leg_names

TEST_PATH = Path(__file__).parent.parent / "test_data"
TEST_DATA_PATH = TEST_PATH / "Scenario_input_data"
TEST_MATRICES = TEST_PATH / "Scenario_input_data" / "Matrices" / "uusimaa"
RESULT_PATH = TEST_PATH / "Results"
PARAMETERS_PATH = TEST_PATH.parent.parent / "parameters" / "freight"
ZONE_NUMBERS = [202, 1344, 1755, 2037, 2129, 2224, 2333, 2413, 2519, 2621,
                2707, 2814, 2918, 3000, 3003, 3203, 3302, 3416, 3639, 3705,
                3800, 4013, 4102, 4202, 7043, 8284, 12614, 17278, 19401, 23678,
                50107, 50127, 50201, 50205]


class TradeRouteChoiceTest(unittest.TestCase):
    
    def test_route_choice(self): 
        truck_name = "truck"
        train_name = "freight_train"
        marine_modes = ("container_ship", "roro_vessel")
        fin_border = {"FIHMN": 19401, "FIHKO": 4102}
        cluster_border = {"EETLL": 50107, "SESTO": 50127}

        zonedata = FreightZoneData(TEST_DATA_PATH / "freight_zonedata.gpkg", 
                                   numpy.array(ZONE_NUMBERS), "koko_suomi")
        resultdata = ResultsData(RESULT_PATH)
        trade_demand_path = Path(TEST_MATRICES / "trade_demand.omx")
        with open(TEST_DATA_PATH / "costdata.json") as file:
            costdata = json.load(file)
        purposes = create_purposes(PARAMETERS_PATH / "foreign", zonedata, 
                                   resultdata, costdata["freight"])
        del purposes["kummuo_export"]
        del purposes["kummuo_import"]
        self.assertEqual(len(purposes), 2)

        with open(TEST_DATA_PATH / "costdata.json") as file:
            costdata = json.load(file)
        time_impedance = omx.open_file(TEST_MATRICES / "freight_time.omx", "r")
        dist_impedance = omx.open_file(TEST_MATRICES / "freight_dist.omx", "r")
        toll_impedance = omx.open_file(TEST_MATRICES / "freight_dist.omx", "r")
        impedance = {
            truck_name: {
                "time": numpy.array(time_impedance[truck_name]),
                "dist": numpy.array(dist_impedance[truck_name]),
                "toll_cost": numpy.array(toll_impedance[truck_name])
            },
            train_name: {
                "time": numpy.array(time_impedance[train_name]),
                "dist": numpy.array(dist_impedance[train_name]),
                "aux_time": numpy.array(time_impedance[f"{train_name}_aux"]),
                "aux_dist": numpy.array(dist_impedance[f"{train_name}_aux"]),
                "toll_cost": numpy.array(toll_impedance[train_name])
            }
        }

        ship_imps = {
            mode: {
                imp: numpy.full((len(fin_border), len(fin_border)), numpy.inf, dtype="float32")
                for imp in ("dist", "frequency")}
            for mode in marine_modes
        }
        ship_imps["container_ship"]["dist"][1][1] = 532
        ship_imps["container_ship"]["frequency"][1][1] = 38
        ship_imps["roro_vessel"]["dist"][0][0] = 126
        ship_imps["roro_vessel"]["frequency"][0][0] = 162

        marine_attr = (ship_imps, fin_border, cluster_border)
        for purpose in purposes.values():
            split_impedances = purpose.form_impedance_legs(impedance, *marine_attr)
            self._assert_leg_impedances(purpose.name, split_impedances, 
                                        truck_name, marine_modes)
            
            demand = purpose.run_trade_route_module(impedance, *marine_attr, trade_demand_path)
            self._assert_leg_demand(purpose.name, demand)

    def _assert_leg_impedances(self, name, split_impedances, truck_name, marine_modes):
        if name.split("_")[0] == "kemlaa":
            leg_one, leg_two, leg_three = leg_names
            self.assertEqual(len(split_impedances), 3)
            self.assertEqual([leg_one, leg_two, leg_three], 
                                list(split_impedances))
            self.assertTrue(all(mode in split_impedances[leg_two] for mode in marine_modes) 
                            and all(mode not in split_impedances[leg_one] for mode in marine_modes)
                            and all(mode not in split_impedances[leg_three] for mode in marine_modes))
            self.assertEqual(["cost", "draught", "frequency"], 
                             list(split_impedances[leg_two]["container_ship"]))
            self.assertEqual(split_impedances[leg_two][truck_name]["cost"].shape, (2, 2))
            
            if name == "kemlaa_export":
                self.assertEqual(len(split_impedances[leg_one]), 1)
                self.assertEqual(split_impedances[leg_one][truck_name]["cost"].shape, (30, 2))
                self.assertEqual(split_impedances[leg_three][truck_name]["cost"].shape, (2, 2))
            elif name == "kemlaa_import":
                self.assertEqual(len(split_impedances[leg_one]), 1)
                self.assertEqual(split_impedances[leg_one][truck_name]["cost"].shape, (2, 2))
                self.assertEqual(split_impedances[leg_three][truck_name]["cost"].shape, (2, 30))

    def _assert_leg_demand(self, name, demand):
        leg_one, leg_two, leg_three = [demand[leg_name] for leg_name in leg_names]
        self.assertEqual(len(leg_one), 1)
        self.assertEqual(len(leg_two), 3)
        self.assertEqual(len(leg_three), 1)
        if name == "kemlaa_export":
            truck_leg1_cols = numpy.array((8.169347, 14.315129), dtype=numpy.float32)
            self.assertAlmostEqual(numpy.sum(leg_one["truck"]), 22.484474, places=3)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_one["truck"], axis=0), truck_leg1_cols)

            truck_leg2_cols = numpy.array((4.003486, 4.003484), dtype=numpy.float32)
            truck_leg2_row = numpy.array((4.0034847, 4.0034847), dtype=numpy.float32)
            container_leg2_cols = numpy.array((0, 10.3116455), dtype=numpy.float32)
            roro_leg2_cols = numpy.array((4.1658616, 0), dtype=numpy.float32)
            self.assertAlmostEqual(numpy.sum(leg_two["truck"]), 8.006969, places=3)
            self.assertAlmostEqual(numpy.sum(leg_two["container_ship"]), 10.3116455, places=3)
            self.assertAlmostEqual(numpy.sum(leg_two["roro_vessel"]), 4.1658616, places=3)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["truck"], axis=0), truck_leg2_cols)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["truck"], axis=1), truck_leg2_row)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["container_ship"], axis=0), container_leg2_cols)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["roro_vessel"], axis=0), roro_leg2_cols)

            truck_leg3_cols = numpy.array((9.165112, 13.319366), dtype=numpy.float32)
            self.assertAlmostEqual(numpy.sum(leg_three["truck"]), 22.484474, places=3)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_three["truck"], axis=0), truck_leg3_cols)
            
        elif name == "kemlaa_import":
            truck_leg1_row = numpy.array((203.28798, 231.84685), dtype=numpy.float32)
            self.assertAlmostEqual(numpy.sum(leg_one["truck"]), 435.13483, places=3)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_one["truck"], axis=1), truck_leg1_row)

            truck_leg2_cols = numpy.array((34.18222, 32.160725), dtype=numpy.float32)
            truck_leg2_row = numpy.array((33.581642, 32.761303), dtype=numpy.float32)
            container_leg2_row = numpy.array((0, 61.939617), dtype=numpy.float32)
            roro_leg2_row = numpy.array((306.85233, 0), dtype=numpy.float32)
            self.assertAlmostEqual(numpy.sum(leg_two["truck"]), 66.34295, places=3)
            self.assertAlmostEqual(numpy.sum(leg_two["container_ship"]), 61.939617, places=3)
            self.assertAlmostEqual(numpy.sum(leg_two["roro_vessel"]), 306.85233, places=3)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["truck"], axis=0), truck_leg2_cols)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["truck"], axis=1), truck_leg2_row)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["container_ship"], axis=1), container_leg2_row)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["roro_vessel"], axis=1), roro_leg2_row)
            
            truck_leg3_cols = numpy.array((341.03445, 94.10034), dtype=numpy.float32)
            self.assertAlmostEqual(numpy.sum(leg_three["truck"]), 435.13483, places=3)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_three["truck"], axis=1), truck_leg3_cols)
