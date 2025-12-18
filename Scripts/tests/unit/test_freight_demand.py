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
from utils.freight_utils import create_purposes

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
        purposes = create_purposes(PARAMETERS_PATH / "domestic", zonedata, 
                                   resultdata, costdata["freight"])
        self.assertGreaterEqual(len(purposes), 1)
        
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
        for mtx_type in impedance.keys():
            for ass_class, mtx in impedance[mtx_type].items():
                impedance[mtx_type][ass_class] = mtx[:zonedata.nr_zones, :zonedata.nr_zones]
        
        for purpose in purposes.values():
            demand = purpose.calc_traffic(impedance)
            costs = purpose.get_costs(impedance)
            for mode in demand:
                self.assertTrue(numpy.isfinite(demand[mode]).all())
                if mode == param.truck_classes[0]:
                    self.assertTrue(numpy.isfinite(costs[mode]["cost"]).all())
                else:
                    self.assertTrue(numpy.isfinite(costs[mode]["cost"]).any())
