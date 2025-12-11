#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import logging
import numpy
import pandas

import parameters.assignment as param
import utils.log as log
import assignment.emme_assignment as ass
from datahandling.matrixdata import MatrixData
from datahandling.resultdata import ResultsData
from tests.integration.test_data_handling import (
    TEST_DATA_PATH,
)
from datahandling.traversaldata import transform_traversal_data
try:
    from assignment.emme_bindings.emme_project import EmmeProject
    import inro.emme.desktop.app as _app
    import inro.emme.database.emmebank as _eb
    emme_available = True
except ImportError:
    emme_available = False
except RuntimeError as ex:
    print(f'Unable to start Emme. Emme assignment tests disabled. ({ex})')
    emme_available = False

class EmmeAssignmentTest:
    """Create small EMME test network and test assignments.

    On first run, create new EMME project and database files.
    """
    def __init__(self):
        logging.basicConfig(format='%(asctime)s %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S',
                            level=logging.INFO)
        project_dir = TEST_DATA_PATH / "Results"
        log.info(str(project_dir))
        project_name = "test_assignment"
        db_dir = project_dir / project_name / "Database"
        try:
            project_path = _app.create_project(project_dir, project_name)
            db_dir.mkdir(parents=True, exist_ok=True)
        except FileExistsError:
            project_path = project_dir / project_name / (project_name + ".emp")
        emme_context = EmmeProject(project_path)
        dim = {
            "scalar_matrices": 100,
            "origin_matrices": 100,
            "destination_matrices": 100,
            "full_matrices": 9999,
            "scenarios": 5,
            "centroids": 35,
            "regular_nodes": 2000,
            "links": 6000,
            "turn_entries": 100,
            "transit_vehicles": 35,
            "transit_lines": 40,
            "transit_segments": 850,
            "extra_attribute_values": 1300000,
            "functions": 99,
            "operators": 5000,
            "sola_analyses": 240,
        }
        scenario_num = 19
        try:
            eb = _eb.create(db_dir / "emmebank", dim)
        except RuntimeError:
            pass
        else:
            eb.create_scenario(scenario_num)
            emmebank_path = eb.path
            eb.dispose()
            emme_context.add_db(emmebank_path, "test")
        emme_context.start()
        emme_context.import_scenario(
            project_dir.parent / "Network", scenario_num, "test",
            overwrite=True)
        self.ass_model = ass.EmmeAssignmentModel(
             emme_context, scenario_num, "uusimaa")
        self.long_dist_model = ass.EmmeAssignmentModel(
            emme_context, scenario_num, "koko_suomi",
            use_free_flow_speeds=True, time_periods={"vrk": "WholeDayPeriod"})
        self.dist_cost = {
            "car_work": 0.12,
            "car_leisure": 0.12,
            "trailer_truck": 0.5,
            "semi_trailer": 0.4,
            "truck": 0.3,
            "van": 0.2,
        }
        self.resultdata = ResultsData(TEST_DATA_PATH / "Results" / "assignment")
    
    def test_assignment(self):
        self.ass_model.prepare_network(self.dist_cost)
        nr_zones = self.ass_model.nr_zones
        car_matrix = numpy.full((nr_zones, nr_zones), 10.0)
        demand = {
            "car_work": car_matrix,
            "car_leisure": car_matrix,
            "transit_work": car_matrix,
            "transit_leisure": car_matrix,
            "bike": car_matrix,
            "trailer_truck": car_matrix,
            "semi_trailer": car_matrix,
            "truck": car_matrix,
            "van": car_matrix,
        }
        travel_cost = {}
        self.test_transit_cost()
        self.ass_model.init_assign()
        for ap in self.ass_model.assignment_periods:
            for ass_class in demand:
                if ass_class in ap.assignment_modes:
                    ap.set_matrix(ass_class, car_matrix)
            travel_cost[ap.name] = ap.end_assign()
        mapping = pandas.Series({
            "Helsinki": "Uusimaa",
            "Espoo": "Uusimaa",
            "Vantaa": "Uusimaa",
            "Kauniainen": "Uusimaa",
            "Hyvinkaa": "Uusimaa",
            "Lohja": "Uusimaa",
            "Hameenlinna": "Kanta-Hame",
            "Tampere": "Pirkanmaa",
            "Turku": "Varsinais-Suomi",
            "Jyvaskyla": "Keski-Suomi",
            "Kotka": "Kymenlaakso",
            "Lahti": "Paijat-Hame"
        })
        self.ass_model.aggregate_results(self.resultdata, mapping)
        self.ass_model.calc_noise(mapping)
        self.resultdata.flush()
        costs_files = MatrixData(
            TEST_DATA_PATH / "Results" / "assignment" / "Matrices")
        for time_period in travel_cost:
            for mtx_type in travel_cost[time_period]:
                zone_numbers = self.ass_model.zone_numbers
                with costs_files.open(mtx_type, time_period, zone_numbers, m='w') as mtx:
                    for ass_class in travel_cost[time_period][mtx_type]:
                        cost_data = travel_cost[time_period][mtx_type][ass_class]
                        mtx[ass_class] = cost_data

    def test_park_and_ride(self):
        self.long_dist_model.prepare_network(self.dist_cost)
        nr_zones = self.ass_model.nr_zones
        car_matrix = numpy.full((nr_zones, nr_zones), 10.0)
        ass_classes = [
            "car_work",
            "car_leisure",
            "train",
            "coach",
            "airplane",
            "train_car_acc",
            "train_taxi_acc",
            "coach_car_acc",
            "airpl_car_acc",
            "train_car_egr",
            "train_taxi_egr",
            "coach_car_egr",
            "airpl_car_egr",
        ]
        demand = {ass_class: car_matrix for ass_class in ass_classes}
        for ap in self.long_dist_model.assignment_periods:
            for ass_class in demand:
                ap.set_matrix(ass_class, car_matrix)
            ap.init_assign()
            ap.assign_trucks_init()
            travel_cost = ap.end_assign()
            costs_files = MatrixData(
                TEST_DATA_PATH / "Results" / "assignment" / "Matrices")
            for mtx_type in travel_cost:
                zone_numbers = self.ass_model.zone_numbers
                with costs_files.open(mtx_type, ap.name, zone_numbers, m='w') as mtx:
                    for ass_class in travel_cost[mtx_type]:
                        cost_data = travel_cost[mtx_type][ass_class]
                        mtx[ass_class] = cost_data
            ap.transit_results_links_nodes()

    def test_transit_cost(self):
        firstb_single = (2, 3, 5, 70, 0, 1.5)
        dist_single = (0.1, 0.2, 0.1, 0.3, 0.1, 0.2)
        fares = pandas.DataFrame(
            {i: {"firstb_single": firstb_single[i],
                 "dist_single": dist_single[i]}
             for i in range(0, len(firstb_single))})
        self.ass_model.calc_transit_cost(fares)

    def test_freight_assignment(self):
        purposes = ["marita", "kalevi"]
        self.ass_model.prepare_freight_network(self.dist_cost, purposes)
        temp_impedance = self.ass_model.freight_network.assign()
        nr_zones = self.ass_model.nr_zones
        freight_modes = ["truck", "freight_train", "ship"]
        demand = {mode: numpy.full((nr_zones, nr_zones), 10.0) for mode in freight_modes}
        truck_loads = (2, 4, 5)
        truck_loads = dict(zip(param.truck_classes, truck_loads))
        total_demand = {mode: numpy.full((nr_zones, nr_zones), 0.0)
                    for mode in param.truck_classes}
        for purpose in purposes:
            for mode in freight_modes:
                self.ass_model.freight_network.set_matrix(mode, demand[mode])
            self.ass_model.freight_network.save_network_volumes(purpose)
            self.ass_model.freight_network.output_traversal_matrix(
                set(demand), self.resultdata.path)
            aux_demand = transform_traversal_data(
                self.resultdata.path, self.ass_model.zone_numbers)
            demand["truck"] += sum(aux_demand.values())
            for mode in param.truck_classes:
                total_demand[mode] += demand["truck"] / truck_loads[mode]
        for ass_class in total_demand:
            self.ass_model.freight_network.set_matrix(ass_class, total_demand[ass_class])
        self.ass_model.freight_network._assign_trucks()

if emme_available:
    em = EmmeAssignmentTest()
    em.test_assignment()
    em.test_park_and_ride()
    em.test_freight_assignment()
