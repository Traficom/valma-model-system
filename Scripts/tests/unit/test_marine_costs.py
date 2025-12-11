#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
import json
import numpy
import unittest
import openmatrix as omx

from utils.freight_costs import calc_cost

TEST_PATH = Path(__file__).parent.parent / "test_data"
TEST_DATA_PATH = TEST_PATH / "Scenario_input_data"
TEST_MATRICES = TEST_PATH / "Scenario_input_data" / "Matrices" / "uusimaa"

class MarineCostTest(unittest.TestCase):

    def test_marine_cost(self):
        purpose_name = "kemiat"
        modes = ["truck", "freight_train", "ship"]

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
                "container_ship": {
                    "dist": numpy.full((3,2), numpy.inf, dtype="float32"),
                    "frequency": numpy.full((3,2), numpy.inf, dtype="float32")
                },
                "roro_vessel": {
                    "dist": numpy.full((3,2), numpy.inf, dtype="float32"),
                    "frequency": numpy.full((3,2), numpy.inf, dtype="float32")
                }
            }
        }
        impedance["ship"]["container_ship"]["dist"][1][1] = 532
        impedance["ship"]["container_ship"]["frequency"][1][1] = 38
        impedance["ship"]["roro_vessel"]["dist"][0][0] = 126
        impedance["ship"]["roro_vessel"]["frequency"][0][0] = 162
        origs = {"FIHMN": 19401, "FIHNK": 4102, "FIHEL": 524}
        dests = {"EETLL": 50107, "SESTO": 50127}

        costs = {mode: {"cost": calc_cost(mode, costdata["freight"][purpose_name], 
                                          impedance[mode], "foreign",
                                          origs, dests)}
                for mode in modes}
        container_imp_not_inf = (~numpy.isinf(impedance["ship"]["container_ship"]["dist"]))
        roro_imp_not_inf = (~numpy.isinf(impedance["ship"]["roro_vessel"]["dist"]))
        self.assert_costs(costs, container_imp_not_inf, roro_imp_not_inf)

    def assert_costs(self, costs, container_mask, roro_mask):
        container = costs["ship"]["cost"]["container_ship"]
        roro = costs["ship"]["cost"]["roro_vessel"]

        self.assertTrue(numpy.array_equal(numpy.isfinite(container["cost"]), 
                                          container_mask))
        self.assertTrue(numpy.array_equal(numpy.isfinite(roro["cost"]), 
                                          roro_mask))
        self.assertEqual(container["cost"][1][1], numpy.float32(27.31294))
        self.assertEqual(roro["cost"][0][0], numpy.float32(26.27858))
        self.assertEqual(container["draught"][1][1], 8)
        self.assertEqual(roro["draught"][0][0], 5)
