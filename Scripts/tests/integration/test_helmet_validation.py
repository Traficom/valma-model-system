import unittest

from validate_inputfiles import main
import utils.log as log
from tests.integration.test_data_handling import (
    TEST_DATA_PATH, ZONEDATA_PATH, COSTDATA_PATH)


class Args:
    log_format = None
    log_level = "DEBUG"
    model_types = ["passenger_transport"]
    end_assignment_only = False
    base_data_folder = TEST_DATA_PATH / "Scenario_input_data"
    emme_paths = [ZONEDATA_PATH / "2016.cco"]
    first_scenario_ids = ["test"]
    zone_data_file = [ZONEDATA_PATH]
    cost_data_file = [COSTDATA_PATH]
    result_data_folder = TEST_DATA_PATH / "Results"
    scenario_name = ["test"]
    do_not_use_emme = True
    long_dist_demand_forecast = ["base"]
    freight_matrix_paths = ["none"]
    submodel = ["uusimaa"]


class ValdidationTest(unittest.TestCase):

    def test_validation(self):
        print("Testing input file validation..")
        log.initialize(Args())
        main(Args())
