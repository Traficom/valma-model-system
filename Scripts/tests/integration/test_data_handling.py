import unittest
import pandas
import os
import numpy

import utils.log as log
from datahandling.zonedata import GridData, ZoneData
from datahandling.matrixdata import MatrixData
import parameters.assignment as param
from tests.integration.test_arguments import (
    TEST_DATA_PATH,
    RESULTS_PATH,
    ZONEDATA_PATH,
    COSTDATA_PATH,
    MODE_DEST_CALIBRATION_FILE,
    MUNICIPALITY_CALIBRATION_FILE,
    BASE_MATRICES_PATH,
    INTERNAL_ZONES,
    EXTERNAL_ZONES,
    ZONE_INDEXES,
)

# Integration tests for validating that we can read the matrices from OMX
#  and CSV files correctly. Assumes that the matrix is fixed and the
# values don't change throughout the project.

class Config():
    log_format = None
    log_level = "DEBUG"
    scenario_name = "TEST"
    result_data_folder = TEST_DATA_PATH / "Results"

class MatrixDataTest(unittest.TestCase):

    def test_constructor(self):
        log.initialize(Config())
        m = MatrixData(RESULTS_PATH / "los_matrices" / "uusimaa")
        # Verify that the base folder exists
        self.assertTrue(os.path.isdir(m.path))

    def test_matrix_operations(self):
        log.initialize(Config())
        m = MatrixData(RESULTS_PATH / "los_matrices" / "uusimaa")
        MATRIX_TYPES = ["time"]
        for matrix_type in MATRIX_TYPES:
            print("validating matrix type", matrix_type)
            self._validate_matrix_operations(m, matrix_type)

    def _validate_matrix_operations(self, matrix_data: MatrixData,
                                    matrix_type: str):
        emme_scenarios = ["aht", "pt", "iht"]
        expanded_zones = numpy.insert(ZONE_INDEXES, 3, 8)
        expanded_internal = numpy.insert(INTERNAL_ZONES, 3, 8)
        mapping = pandas.Series(expanded_internal, expanded_internal)
        mapping[300] = 213
        for key in emme_scenarios:
            print("Opening matrix for time period", key)
            with matrix_data.open(
                matrix_type, key, expanded_zones, mapping, param.car_classes) as mtx:
                for ass_class in param.car_classes:
                    a = mtx[ass_class]


class ZoneDataTest(unittest.TestCase):

    def _get_freight_data_2016(self):
        zdata = ZoneData(ZONEDATA_PATH, ZONE_INDEXES)
        df = zdata.get_freight_data()
        self.assertIsNotNone(df)
        return df

    def test_csv_file_read(self):
        grid_data = GridData(ZONEDATA_PATH, "uusimaa", 
                             ZONE_INDEXES,  model_area="domestic")
        data = grid_data.aggregate()
        zone_data = ZoneData(data, "uusimaa", ZONE_INDEXES, 
                             "domestic", car_dist_cost=0.12, 
                             electric_car_share={"default": {"bev": 0.1, "phev": 0.2}})
        self.assertIsNotNone(zone_data["population"])
        self.assertIsNotNone(zone_data["workplaces"])
