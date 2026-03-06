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
                    "icev", "transit", "bike"]
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
                "aht":[
                    [0.0113538534294527, 0.0483356330299955],
                    [0.000783876140666748, 0.0782437896466509]
                ],
                "pt":[
                    [0.0415688948149155, 0.0275008865700513],
                    [0.0249338403352452, 0.0218610155562793]
                ],
                "iht": [
                    [0.126631086164843, 0.0254942149131846],
                    [0.103874241247952, 0.0253360698120264]
                ]
            },
            "transit": {
                "aht": [
                    [0.007848433131924, 0.0318369625680414],
                    [0.00148575955291745, 0.0800841531842564]
                ],
                "pt": [
                    [0.0392336062771297, 0.0251341675086098],
                    [0.0191847672424449, 0.0215475457292278]
                ],
                "iht": [
                    [0.191259463404029, 0.0367695909665859],
                    [0.0872373132287834, 0.0165925719765324]
                ],
                "it": [
                    [0.0392336062771297, 0.0251341675086098],
                    [0.0191847672424449, 0.0215475457292278]
                ],
            },
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
        self.assertIs(type(dtm.demand["iht"]["icev"]), numpy.ndarray)
        self.assertEquals(dtm.demand["pt"]["icev"].ndim, 2)
        self.assertEquals(dtm.demand["aht"]["bike"].shape[1], 8)
        self.assertNotEquals(dtm.demand["iht"]["icev"][0, 1], 0)
