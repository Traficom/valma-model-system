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
from assignment.mock_assignment import MockAssignmentModel
from datahandling.matrixdata import MatrixData

TEST_PATH = Path(__file__).parent.parent / "test_data"
TEST_DATA_PATH = TEST_PATH / "Scenario_input_data"
TEST_MATRICES = TEST_PATH / "Scenario_input_data" / "Matrices" / "uusimaa"
RESULT_PATH = TEST_PATH / "Results"
PARAMETERS_PATH = TEST_PATH.parent.parent / "parameters" / "freight"
ZONE_NUMBERS = [202, 1344, 1755, 2037, 2129, 2224, 2333, 2413, 2519, 2621,
                2707, 2814, 2918, 3000, 3003, 3203, 3302, 3416, 3639, 3705,
                3800, 4013, 4102, 4202, 7043, 8284, 12614, 17278, 19401, 23678,
                50107, 50127, 50201, 50205]


class LogisticsModelTest(unittest.TestCase):

    def test_logistics_model(self):      
        zonedata = FreightZoneData(
            TEST_DATA_PATH / "freight_zonedata.gpkg", numpy.array(ZONE_NUMBERS),
            "koko_suomi")
        resultdata = ResultsData(RESULT_PATH)
        with open(TEST_DATA_PATH / "costdata.json") as file:
            costdata = json.load(file)
        purposes = create_purposes(PARAMETERS_PATH / "domestic", zonedata, 
                                   resultdata, costdata["freight"])
        
        mapping = {}
        for idx, zone in enumerate(zonedata.zone_numbers):
            mapping[zone] = idx
        
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
        
        iterations = 1
        for purpose in purposes.values():
            demand = purpose.calc_traffic(impedance)
            if hasattr(purpose, "logistics_module") and iterations > 0:
                demand_truck, per_route = purpose.run_logistics_module(demand["truck"],
                                                                       impedance, mapping, 
                                                                       iterations)
                self.assertTrue(numpy.isfinite(demand_truck).all())
                self.assertTrue((demand_truck >= 0).all())
                self.assertTrue(demand_truck.shape == (zonedata.nr_zones, zonedata.nr_zones))

                detour_total = numpy.sum(per_route[:-1])
                direct_total = per_route[-1]
                if purpose.name == "kemlaa":
                    self.assertAlmostEqual(detour_total, 12.948977, places=3)
                    self.assertAlmostEqual(direct_total, 12956.025, places=3)
                elif purpose.name == "kummuo":
                    self.assertAlmostEqual(detour_total, 54.282013, places=3)
                    self.assertAlmostEqual(direct_total, 15736.507, places=3)
