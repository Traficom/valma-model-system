#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import numpy
import unittest
from assignment.departure_time import DepartureTimeModel


class DepartureTimeTest(unittest.TestCase):
    def test_mtx_add(self):
        class Period:
            def __init__(self, name):
                self.name = name
                self.assignment_modes = [
                    "car", "transit", "bike"]
        assignment_periods = [
            Period(name) for name in ("aht", "pt", "iht")]
        it = Period("it")
        it.assignment_modes = ["transit"]
        assignment_periods.append(it)
        dtm = DepartureTimeModel(8, assignment_periods)
        mtx = numpy.arange(9)
        mtx.shape = (3, 3)
        class Demand:
            pass
        class Purpose:
            pass
        dem = Demand()
        pur1 = Purpose()
        dem.purpose = pur1

        dem.purpose.name = "wb_other"
        dem.purpose.demand_share = {
            "car_drv": {
                "aht": [
                0.0595,
                0.01
                ],
                "pt": [
                    0.5898,
                    0.8011
                ],
                "iht": [
                    0.3508,
                    0.1889
                ]
            },
            "car_pax": {
                "aht": [
                    0.0595,
                    0.01
                ],
                "pt": [
                    0.5898,
                    0.8011
                ],
                "iht": [
                    0.3508,
                    0.1889
                ]
            },
            "transit": {
                "aht": [
                    0.0595,
                    0.01
                ],
                "pt": [
                    0.3173,
                    0.2154
                ],
                "iht": [
                    0.3508,
                    0.1889
                ],
                "it": [
                    0.2725,
                    0.5857
                ]
            },
            "bike": {
                "pt": [
                    1.0,
                    1.0
                ]
            },
            "walk": {
                "pt": [
                    1.0,
                    1.0
                ]
            }
        }
        dem.mode = "car_drv"
        dem.matrix = mtx
        dem.orig = 1
        dem.dest = None
        dem.position = (1, 0, 0)
        dtm.add_demand(dem)

        dem.purpose = Purpose()
        dem.purpose.name = "hb_work"
        dem.purpose.demand_share = {
            "transit": {
                "aht": [0.168710422485735, 0.0387468664988151],
                "pt": [0.0716348116654068, 0.0679842570835241],
                "iht": [0.0437554897467228, 0.108924099422715]
                },
            "bike": {
                "aht": [0.0259945209673068, 0.0164613914375604],
                "pt": [0.0692448058659033, 0.0449421010361262],
                "iht": [0.0131611231013582, 0.0411710936086695]
                },
        }
        dem.mode = "bike"
        dem.dest = 2
        dem.matrix = numpy.array([[3]])
        dem.position = (1, 2)
        dtm.add_demand(dem)

        dem.purpose = Purpose()
        dem.purpose.name = "hb_leisure"
        dem.purpose.demand_share = {
            "transit": {
                "aht": [0.168710422485735, 0.0387468664988151],
                "pt": [0.0716348116654068, 0.0679842570835241],
                "iht": [0.0437554897467228, 0.108924099422715],
                "it": [0.0716348116654068, 0.0679842570835241],
                },
            "bike": {
                "aht": [0.0259945209673068, 0.0164613914375604],
                "pt": [0.0692448058659033, 0.0449421010361262],
                "iht": [0.0131611231013582, 0.0411710936086695]
                },
        }
        dem.purpose.sec_dest_purpose = pur1
        dem.mode = "transit"
        dem.matrix = numpy.array([[3]])
        dem.position = (1, 2, 0)
        dtm.add_demand(dem)

        self.assertIsNotNone(dtm.demand)
        self.assertIs(type(dtm.demand["iht"]["car"]), numpy.ndarray)
        self.assertEquals(dtm.demand["pt"]["car"].ndim, 2)
        self.assertEquals(dtm.demand["aht"]["bike"].shape[1], 8)
        self.assertNotEquals(dtm.demand["iht"]["car"][0, 1], 0)
