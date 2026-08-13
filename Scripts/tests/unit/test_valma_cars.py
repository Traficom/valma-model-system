import unittest

from tests.integration.test_data_handling import TEST_DATA_PATH, ZONEDATA_PATH
from valma_cars import main


class Args:
    zone_data_file = ZONEDATA_PATH
    scenario_name = "test"
    result_data_folder = TEST_DATA_PATH / "Results"
    submodel = "uusimaa"

class ValmaCarsTest(unittest.TestCase):

    def test_individual_car_ownership(self):
        main(Args())
