#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import json
import numpy
import unittest
import openmatrix as omx

from datahandling.resultdata import ResultsData
from datahandling.zonedata import FreightZoneData
from datatypes.commodity import create_commodities
from parameters.marine_ship import leg_names
from tests.integration.test_data_handling import (
    TEST_DATA_PATH,
    RESULTS_PATH,
    COSTDATA_PATH,
)
from tests.unit.test_freight_demand import (
    TEST_MATRICES,
    TEST_ZONE_DATA_PATH,
    TRADE_DEMAND_PATH,
    PARAMETERS_PATH,
    ZONE_NUMBERS,
)


class TradeRouteChoiceTest(unittest.TestCase):
    
    def test_route_choice(self): 
        truck_name = "truck"
        train_name = "freight_train"
        marine_modes = ("container_ship", "roro_vessel")
        fin_border = {"FIHKO": 4102, "FIHMN": 19401}
        cluster_border = {"EETLL": 50107, "SESTO": 50127}

        zonedata = FreightZoneData(
            TEST_ZONE_DATA_PATH, numpy.array(ZONE_NUMBERS), "koko_suomi")
        resultdata = ResultsData(RESULTS_PATH)
        with open(COSTDATA_PATH) as file:
            costdata = json.load(file)
        commodities = create_commodities(
            PARAMETERS_PATH / "foreign", zonedata, resultdata,
            costdata["freight"])
        del commodities["kummuo_export"]
        del commodities["kummuo_import"]
        self.assertEqual(len(commodities), 2)

        time_impedance = omx.open_file(TEST_MATRICES / "freight_time.omx", "r")
        dist_impedance = omx.open_file(TEST_MATRICES / "freight_dist.omx", "r")
        cost_impedance = omx.open_file(TEST_MATRICES / "freight_cost.omx", "r")
        impedance = {
            truck_name: {
                "cost": numpy.array(cost_impedance[truck_name]),
                "dist": numpy.array(dist_impedance[truck_name]),
            },
            train_name: {
                "time": numpy.array(time_impedance[train_name]),
                "dist": numpy.array(dist_impedance[train_name]),
                "aux_cost": numpy.array(cost_impedance[f"{train_name}_aux"]),
                "aux_dist": numpy.array(dist_impedance[f"{train_name}_aux"]),
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
        for commodity in commodities.values():
            split_impedances = commodity.form_impedance_legs(impedance, *marine_attr)
            self._assert_leg_impedances(commodity.name, split_impedances,
                                        truck_name, marine_modes)
            
            demand = commodity.run_trade_route_module(
                impedance, *marine_attr, TRADE_DEMAND_PATH)
            self._assert_leg_demand(commodity.name, demand)

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
            truck_leg1_cols = numpy.array((6.469845, 16.014633), dtype=numpy.float32)
            self.assertAlmostEqual(numpy.sum(leg_one["truck"]), 22.484474, places=3)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_one["truck"], axis=0), truck_leg1_cols)

            truck_leg2_cols = numpy.array((0.0, 0.0), dtype=numpy.float32)
            truck_leg2_row = numpy.array((0.0, 0.0), dtype=numpy.float32)
            container_leg2_cols = numpy.array((0, 16.014633), dtype=numpy.float32)
            roro_leg2_cols = numpy.array((6.4698453, 0), dtype=numpy.float32)
            self.assertAlmostEqual(numpy.sum(leg_two["truck"]), 0.0)
            self.assertAlmostEqual(numpy.sum(leg_two["container_ship"]), 16.014631, places=3)
            self.assertAlmostEqual(numpy.sum(leg_two["roro_vessel"]), 6.4698453, places=3)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["truck"], axis=0), truck_leg2_cols)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["truck"], axis=1), truck_leg2_row)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["container_ship"], axis=0), container_leg2_cols)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["roro_vessel"], axis=0), roro_leg2_cols)

            truck_leg3_cols = numpy.array((9.165112, 13.319365), dtype=numpy.float32)
            self.assertAlmostEqual(numpy.sum(leg_three["truck"]), 22.484474, places=3)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_three["truck"], axis=0), truck_leg3_cols)
            
        elif name == "kemlaa_import":
            truck_leg1_row = numpy.array((203.28796, 231.84688), dtype=numpy.float32)
            self.assertAlmostEqual(numpy.sum(leg_one["truck"]), 435.13483, places=3)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_one["truck"], axis=1), truck_leg1_row)

            truck_leg2_cols = numpy.array((0.0, 0.0), dtype=numpy.float32)
            truck_leg2_row = numpy.array((0.0, 0.0), dtype=numpy.float32)
            container_leg2_row = numpy.array((0, 7.178417), dtype=numpy.float32)
            roro_leg2_row = numpy.array((427.95648, 0), dtype=numpy.float32)
            self.assertAlmostEqual(numpy.sum(leg_two["truck"]), 0.0)
            self.assertAlmostEqual(numpy.sum(leg_two["container_ship"]), 7.178417, places=3)
            self.assertAlmostEqual(numpy.sum(leg_two["roro_vessel"]), 427.95648, places=3)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["truck"], axis=0), truck_leg2_cols)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["truck"], axis=1), truck_leg2_row)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["container_ship"], axis=1), container_leg2_row)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_two["roro_vessel"], axis=1), roro_leg2_row)
            
            truck_leg3_cols = numpy.array((427.95642, 7.178417), dtype=numpy.float32)
            self.assertAlmostEqual(numpy.sum(leg_three["truck"]), 435.13483, places=3)
            numpy.testing.assert_array_almost_equal(
                numpy.sum(leg_three["truck"], axis=1), truck_leg3_cols)
