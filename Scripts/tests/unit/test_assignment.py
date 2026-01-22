#!/usr/bin/env python2
# -*- coding: utf-8 -*-
import unittest
import numpy
import pandas
from pathlib import Path

from utils.validate_network import validate
from assignment.emme_bindings.mock_project import MockProject
from assignment.emme_assignment import EmmeAssignmentModel
from datahandling.resultdata import ResultsData
from tests.integration.test_data_handling import TEST_DATA_PATH, RESULTS_PATH


class EmmeAssignmentTest(unittest.TestCase):
    def setUp(self):
        self.context = MockProject()
        scenario_dir = TEST_DATA_PATH / "Network"
        self.scenario_id = 19
        self.context.import_scenario(scenario_dir, self.scenario_id, "test")
        self.dist_cost = {
            "car_work": 0.12,
            "car_leisure": 0.12,
            "trailer_truck": 0.5,
            "semi_trailer": 0.4,
            "truck": 0.3,
            "van": 0.2,
        }
        firstb_single = (2, 3, 5, 70, 0, 1.5)
        dist_single = (0.1, 0.2, 0.1, 0.3, 0.1, 0.2)
        self.fares = pandas.DataFrame(
            {i: {"firstb_single": firstb_single[i],
                 "dist_single": dist_single[i]}
             for i in range(0, len(firstb_single))})
        self.mapping = pandas.Series({
            "Helsinki": "Uusimaa",
            "Espoo": "Uusimaa",
            "Lohja": "Uusimaa",
            "Salo": "Varsinais-Suomi",
        })
        self.resultdata = ResultsData(RESULTS_PATH)

    def test_assignment(self):
        validate(
            self.context.modeller.emmebank.scenario(
                self.scenario_id).get_network())
        ass_model = EmmeAssignmentModel(
            self.context, self.scenario_id, "uusimaa")
        ass_model.prepare_network(self.dist_cost, car_time_files=[])
        ass_model.calc_transit_cost(self.fares)
        nr_zones = ass_model.nr_zones
        car_matrix = numpy.arange(nr_zones**2).reshape(nr_zones, nr_zones)
        demand = [
            "car_work",
            "car_leisure",
            "transit_work",
            "transit_leisure",
            "bike",
            "trailer_truck",
            "semi_trailer",
            "truck",
            "van",
        ]
        ass_model.init_assign()
        ass_model.beeline_dist
        for ap in ass_model.assignment_periods:
            for ass_class in demand:
                if ass_class in ap.assignment_modes:
                    ap.set_matrix(ass_class, car_matrix)
            ap.assign_trucks_init()
            imp = ap.assign(demand + ["car_pax"])
            for mtx_type in imp:
                for ass_class in imp[mtx_type]:
                    self.assertEqual(
                        imp[mtx_type][ass_class].dtype, numpy.float32)
            ap.end_assign()
        ass_model.aggregate_results(self.resultdata, self.mapping)
        ass_model.calc_noise(self.mapping)
        self.resultdata.flush()

    def test_long_dist_assignment(self):
        ass_model = EmmeAssignmentModel(
            self.context, self.scenario_id, "koko_suomi",
            use_free_flow_speeds=True, time_periods={"vrk": "WholeDayPeriod"})
        ass_model.prepare_network(self.dist_cost)
        ass_model.calc_transit_cost(self.fares)
        nr_zones = ass_model.nr_zones
        car_matrix = numpy.arange(nr_zones**2).reshape(nr_zones, nr_zones)
        demand = [
            "car_work",
            "car_leisure",
            "transit_work",
            "transit_leisure",
            "airplane",
            "pt_car_acc",
            "pt_taxi_acc",
            "airpl_car_acc",
        ]
        for ap in ass_model.assignment_periods:
            for ass_class in demand:
                ap.set_matrix(
                    ass_class, car_matrix)
            ap.assign_trucks_init()
            ap.assign(demand + ["car_pax"])
            ap.end_assign()
        ass_model.aggregate_results(self.resultdata, self.mapping)

    def test_freight_assignment(self):
        ass_model = EmmeAssignmentModel(
            self.context, self.scenario_id, "koko_suomi")
        ass_model.prepare_freight_network(self.dist_cost, ["c1", "c2"])
        ass_model.freight_network.assign()
        demand = numpy.full((ass_model.nr_zones, ass_model.nr_zones), 1.0)
        for mode in ["truck", "freight_train", "ship"]:
            ass_model.freight_network.set_matrix(mode, demand)
        ass_model.freight_network.save_network_volumes("c1")
        ass_model.freight_network.output_traversal_matrix({"freight_train", "ship"},
                                                          self.resultdata.path)
        ass_model.freight_network.read_ship_impedances(is_export=True)
        self.resultdata.flush()
