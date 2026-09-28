
from pathlib import Path
import numpy

TEST_DATA_PATH = Path(__file__).parent.parent / "test_data"
RESULTS_PATH = TEST_DATA_PATH / "Results" / "test"
ZONEDATA_PATH = TEST_DATA_PATH / "Scenario_input_data" / "zonedata_test.gpkg"
COSTDATA_PATH = TEST_DATA_PATH / "Scenario_input_data" / "costdata.json"
MODE_DEST_CALIBRATION_FILE = TEST_DATA_PATH / "Scenario_input_data" / "mode_dest_calibration.json"
MUNICIPALITY_CALIBRATION_FILE = TEST_DATA_PATH / "Scenario_input_data" / "municipality_calibration.txt"
BASE_MATRICES_PATH = TEST_DATA_PATH / "Scenario_input_data" / "demand_matrices"
LOS_MATRIX_FOLDER = RESULTS_PATH / "los_matrices"
INTERNAL_ZONES = [
    213, 1344, 1753, 2037, 2129, 2224, 2333, 2413, 2519, 2621, 2707, 2814,
    2918, 3000, 3003, 3203, 3302, 3416, 3639, 3705, 3800, 4013, 4102, 4202]
EXTERNAL_ZONES = [7043, 8279, 12643, 17279, 19419, 23678, 50107, 50127, 60021,60031]
ZONE_INDEXES = numpy.array(INTERNAL_ZONES + EXTERNAL_ZONES)
