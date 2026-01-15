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
from parameters.assignment import marine_ships_name


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
        is_export = True
        truck_name = "truck"
        train_name = "freight_train"
        origs = {"FIHMN": 19401, "FIHNK": 4102}
        dests = {"EETLL": 50107, "SESTO": 50127}

        zonedata = FreightZoneData(TEST_DATA_PATH / "freight_zonedata.gpkg", 
                                   numpy.array(ZONE_NUMBERS), "koko_suomi")
        resultdata = ResultsData(RESULT_PATH)
        with open(TEST_DATA_PATH / "costdata.json") as file:
            costdata = json.load(file)
        purposes = create_purposes(PARAMETERS_PATH / "foreign", zonedata, 
                                   resultdata, costdata["freight"])
        self.assertGreaterEqual(len(purposes), 1)

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
            },
            marine_ships_name: {
                "container_ship": {
                    "dist": numpy.full((len(origs), len(origs)), numpy.inf, dtype="float32"),
                    "frequency": numpy.full((len(dests), len(dests)), numpy.inf, dtype="float32")
                },
                "roro_vessel": {
                    "dist": numpy.full((len(origs), len(origs)), numpy.inf, dtype="float32"),
                    "frequency": numpy.full((len(dests), len(dests)), numpy.inf, dtype="float32")
                }
            }
        }

        impedance[marine_ships_name]["container_ship"]["dist"][1][1] = 532
        impedance[marine_ships_name]["container_ship"]["frequency"][1][1] = 38
        impedance[marine_ships_name]["roro_vessel"]["dist"][0][0] = 126
        impedance[marine_ships_name]["roro_vessel"]["frequency"][0][0] = 162

        for purpose in purposes.values():
            split_impedances = purpose.get_split_impedances(impedance, origs, 
                                                            dests, is_export)
            self._assert_split_impedances(purpose, split_impedances, 
                                          truck_name, train_name)


    def _assert_split_impedances(self, purpose, split_impedances,
                                 truck_name, train_name):
        if purpose.name == "kemlaa":
            self.assertEqual(len(split_impedances), 3)
            self.assertEqual(["split_one", "split_three", "split_two"], 
                                list(split_impedances))
            self.assertEqual(len(split_impedances["split_one"]), 2)
            self.assertTrue(marine_ships_name in split_impedances["split_two"] 
                            and (marine_ships_name not in split_impedances["split_one"]
                            and marine_ships_name not in split_impedances["split_three"]))
            
            self.assertEqual(split_impedances["split_one"][truck_name]["cost"].shape, (30, 2))
            self.assertEqual(split_impedances["split_two"][truck_name]["cost"].shape, (2, 2))
            self.assertEqual(["cost", "draught", "frequency"], 
                            list(split_impedances["split_two"][marine_ships_name]["container_ship"]))
            self.assertTrue(numpy.all(numpy.isinf(split_impedances["split_two"][train_name]["cost"])))
            self.assertEqual(split_impedances["split_three"][truck_name]["cost"].shape, (2, 2))
