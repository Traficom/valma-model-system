#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import numpy
import pandas
import unittest
from datahandling.zonedata import ZoneData
from models.tour_combinations import TourCombinationModel
from tests.integration.test_data_handling import ZONEDATA_PATH


INTERNAL_ZONES = [202, 1344, 1755, 2037, 2129, 2224, 2333, 2413, 2519,
                  2621, 2707, 2814, 2918, 3000, 3003, 3203, 3302, 3416,
                  3639, 3705, 3800, 4013, 4102, 4202]
EXTERNAL_ZONES = [7043, 8284, 12614, 17278, 19401, 23678, 50107, 50127, 50201, 50205]
ZONE_INDEXES = numpy.array(INTERNAL_ZONES + EXTERNAL_ZONES)


class TourCombinationModelTest(unittest.TestCase):
    def test_generation(self):
        zi = numpy.array(INTERNAL_ZONES + EXTERNAL_ZONES)
        zd = ZoneData(ZONEDATA_PATH, zi, "uusimaa", car_dist_cost=0.12)
        zd._values["hb_edu_student"] = pandas.Series(0.0, INTERNAL_ZONES)
        model = TourCombinationModel(zd)
