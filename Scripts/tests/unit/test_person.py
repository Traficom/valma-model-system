#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import numpy
import unittest
from datatypes.person import Person


class PersonTest(unittest.TestCase):
    def test_add_tours(self):
        class ZoneData:
                def zone_index(self, zonenumber):
                    try:
                        return zonenumber - 100
                    except TypeError:
                        raise KeyError()
        class GenMod:
            zone_data = ZoneData()
            tour_combinations = [("hb_work",), ("hb_work", "hb_other"), ("hb_work", "hb_work")]
            param = {
                "hb_work": 0.3,
                "hb_other": 0.7,
            }
        class Purpose:
            zone_data = ZoneData()
            gen_model = GenMod()
            modes = ["car", "transit"]
            def __init__(self, name):
                self.name = name
        class Zone:
            number = 101
            index = 0
        p = Person(Zone(), (18, 29), GenMod(), ZoneData())
        purposes = {
            "hb_work": Purpose("hb_work"),
            "hb_other": Purpose("hb_other"),
            "wb_business": Purpose("wb_business"),
            "wb_other": Purpose("wb_other"),
            "ob_other": Purpose("ob_other"),
        }
        data = numpy.array([
            [0.3, 0.6, 1.0],
            [0.3, 0.6, 1.0],
            [0.3, 0.6, 1.0],
            [0.3, 0.6, 1.0],
        ])
        probs = {"age_18_29": data}
        p.add_tours(purposes, probs)
        p.add_tours(purposes, probs)
