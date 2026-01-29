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
        truck_name = "truck"
        train_name = "freight_train"
        marine_modes = ("container_ship", "roro_vessel")
        origs_exp = {"FIHMN": 19401, "FIHNK": 4102}
        dests_exp = {"EETLL": 50107, "SESTO": 50127}
        origs_imp = dests_exp.copy()
        dests_imp = origs_exp.copy()

        zonedata = FreightZoneData(TEST_DATA_PATH / "freight_zonedata.gpkg", 
                                   numpy.array(ZONE_NUMBERS), "koko_suomi")
        resultdata = ResultsData(RESULT_PATH)
        with open(TEST_DATA_PATH / "costdata.json") as file:
            costdata = json.load(file)
        purposes = create_purposes(PARAMETERS_PATH / "foreign", zonedata, 
                                   resultdata, costdata["freight"])
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
            },
            marine_ships_name: {
                mode: {imp: numpy.full((len(origs_exp), len(origs_exp)), numpy.inf, dtype="float32")
                                       for imp in ("dist", "frequency")}
                        for mode in marine_modes
            }
        }

        impedance[marine_ships_name]["container_ship"]["dist"][1][1] = 532
        impedance[marine_ships_name]["container_ship"]["frequency"][1][1] = 38
        impedance[marine_ships_name]["roro_vessel"]["dist"][0][0] = 126
        impedance[marine_ships_name]["roro_vessel"]["frequency"][0][0] = 162

        for purpose in purposes.values():
            if purpose.is_export:
                origs, dests = origs_exp, dests_exp
            else:
                origs, dests = origs_imp, dests_imp
            split_impedances = purpose.form_impedance_legs(impedance, origs, dests)
            self._assert_split_impedances(purpose.name, split_impedances, truck_name, 
                                          train_name, marine_modes)

    def _assert_split_impedances(self, name, split_impedances,
                                 truck_name, train_name, marine_modes):
        if name.split("_")[0] == "kemlaa":
            leg_one, leg_two, leg_three = "leg_one", "leg_two", "leg_three"
            self.assertEqual(len(split_impedances), 3)
            self.assertEqual([leg_one, leg_two, leg_three], 
                                list(split_impedances))
            self.assertTrue(all(mode in split_impedances[leg_two] for mode in marine_modes) 
                            and all(mode not in split_impedances[leg_one] for mode in marine_modes)
                            and all(mode not in split_impedances[leg_three] for mode in marine_modes))
            self.assertEqual(["cost", "draught", "frequency"], 
                             list(split_impedances[leg_two]["container_ship"]))
            self.assertTrue(numpy.all(numpy.isinf(split_impedances[leg_two][train_name]["cost"])))
            self.assertEqual(split_impedances[leg_two][truck_name]["cost"].shape, (2, 2))
            
            if name == "kemlaa_export":
                self.assertEqual(len(split_impedances[leg_one]), 2)
                self.assertEqual(split_impedances[leg_one][truck_name]["cost"].shape, (30, 2))
                self.assertEqual(split_impedances[leg_three][truck_name]["cost"].shape, (2, 2))
            elif name == "kemlaa_import":
                self.assertEqual(len(split_impedances[leg_one]), 1)
                self.assertEqual(split_impedances[leg_one][truck_name]["cost"].shape, (2, 2))
                self.assertEqual(split_impedances[leg_three][truck_name]["cost"].shape, (2, 30))
