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
from tests.integration.test_arguments import RESULTS_PATH, ZONEDATA_PATH, INTERNAL_ZONES

class LogitModelTest(unittest.TestCase):
    def test_logit_calc(self):
        resultdata = ResultsData(RESULTS_PATH)
        class Purpose:
            pass
        pur = Purpose()
        zi = numpy.array(INTERNAL_ZONES)
        zd = ZoneData(
            ZONEDATA_PATH, zi, "uusimaa", car_dist_cost=0.12,
            electric_car_share={"default": {"bev": 0.1, "phev": 0.2}})
        for attr in ("sh_cars1_hh1", "sh_cars1_hh2", "sh_cars1_hh3",
                     "sh_cars2_hh2", "sh_cars2_hh3"):
            zd[attr] = pandas.Series(0.2, index=zd.zone_numbers)
        nr_zones = len(INTERNAL_ZONES)
        mtx = numpy.arange(nr_zones*nr_zones, dtype=numpy.float32)
        mtx.shape = (nr_zones, nr_zones)
        mtx[numpy.diag_indices(nr_zones)] = 0
        impedance = {
            "car_driver": {
                "time": mtx,
                "cost": mtx,
                "dist": mtx,
            },
            "car_passenger": {
                "time": mtx,
                "cost": mtx,
                "dist": mtx,
            },
            "transit": {
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
        pur.bounds = slice(0, nr_zones)
        pur.orig_zone_numbers = INTERNAL_ZONES
        pur.dist = mtx
        parameters_path = Path(__file__).parents[2] / "parameters" / "demand"
        for file in parameters_path.rglob("*.json"):
            parameters = json.loads(file.read_text("utf-8"))
            attempt_calibration(parameters)
            pur.name = parameters["name"]
            if parameters["name"] == "hb_work":
                args = (pur, parameters, zd, zd, resultdata)
                model = (DestModeModel(*args)
                    if parameters["struct"] == "dest>mode"
                    else ModeDestModel(*args))
                prob = model.calc_prob(impedance)
                if parameters["dest"] in ("work"):
                    for mode in ("car_driver", "transit", "bike", "walk"):
                        self._validate(prob[mode])
                else:
                    for mode in ("car_driver", "transit", "bike", "walk"):
                        self._validate(prob[mode])

    def _validate(self, prob):
        self.assertIs(type(prob), numpy.ndarray)
        self.assertEquals(prob.ndim, 2)
        self.assertNotEquals(prob[1, 0], 0)
        assert numpy.isfinite(prob).all()