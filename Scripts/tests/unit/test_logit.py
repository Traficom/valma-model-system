#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import numpy
import pandas
import unittest
import json
from pathlib import Path

from datahandling.zonedata import ZoneData
from models.logit import ModeDestModel, DestModeModel
from datatypes.purpose import attempt_calibration
from datahandling.resultdata import ResultsData
from tests.integration.test_data_handling import RESULTS_PATH, ZONEDATA_PATH


INTERNAL_ZONES = [202, 1344, 1755, 2037, 2129, 2224, 2333, 2413, 2519,
                  2621, 2707, 2814, 2918, 3000, 3003, 3203, 3302, 3416,
                  3639, 3705, 3800, 4013, 4102, 4202]
EXTERNAL_ZONES = [7043, 8284, 12614, 17278, 19401, 23678, 50107, 50127, 50201, 50205]
ZONE_INDEXES = numpy.array(INTERNAL_ZONES + EXTERNAL_ZONES)


class LogitModelTest(unittest.TestCase):
    def test_logit_calc(self):
        resultdata = ResultsData(RESULTS_PATH)
        class Purpose:
            pass
        pur = Purpose()
        zi = numpy.array(INTERNAL_ZONES + EXTERNAL_ZONES)
        zd = ZoneData(ZONEDATA_PATH, zi, "uusimaa", car_dist_cost=0.12)
        mtx = numpy.arange(720, dtype=numpy.float32)
        mtx.shape = (24, 30)
        mtx[numpy.diag_indices(24)] = 0
        impedance = {
            "car_work": {
                "time": mtx,
                "cost": mtx,
                "dist": mtx,
            },
            "car_leisure": {
                "time": mtx,
                "cost": mtx,
                "dist": mtx,
            },
            "car_pax": {
                "time": mtx,
                "cost": mtx,
                "dist": mtx,
            },
            "transit_work": {
                "time": mtx,
                "cost": mtx,
                "dist": mtx,
            },
            "transit_leisure": {
                "time": mtx,
                "cost": mtx,
                "dist": mtx,
            },
            "bike": {
                "dist": mtx,
            },
            "walk": {
                "dist": mtx,
            },
        }
        pur.bounds = slice(0, 24)
        pur.orig_zone_numbers = INTERNAL_ZONES
        pur.dist = mtx
        parameters_path = Path(__file__).parents[2] / "parameters" / "demand"
        for file in parameters_path.rglob("*.json"):
            parameters = json.loads(file.read_text("utf-8"))
            attempt_calibration(parameters)
            pur.name = parameters["name"]
            if parameters["name"] == "hb_work":
                args = (pur, parameters, zd, resultdata)
                model = (DestModeModel(*args)
                    if parameters["struct"] == "dest>mode"
                    else ModeDestModel(*args))
                prob = model.calc_prob(impedance)
                if parameters["dest"] in ("work"):
                    for mode in ("car_work", "transit_work", "bike", "walk"):
                        self._validate(prob[mode])
                else:
                    for mode in ("car_leisure", "transit_leisure", "bike", "walk"):
                        self._validate(prob[mode])

    def _validate(self, prob):
        self.assertIs(type(prob), numpy.ndarray)
        self.assertEquals(prob.ndim, 2)
        self.assertEquals(prob.shape[1], 24)
        self.assertNotEquals(prob[1, 0], 0)
        assert numpy.isfinite(prob).all()