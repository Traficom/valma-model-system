"""The valma_bike_and_walk hooks in ModelSystem, with the package stubbed.

The package's own routing is tested in valma_bike_and_walk; this checks that
the model system asks for its LOS, uses it everywhere, and hands it the right
demand files.
"""
import unittest
from unittest import mock

import numpy

import utils.log as log
from travel_iteration import ModelSystem
from assignment.mock_assignment import MockAssignmentModel
from datahandling.matrixdata import MatrixData
from tests.integration.test_arguments import (
    TEST_DATA_PATH,
    RESULTS_PATH,
    ZONEDATA_PATH,
    COSTDATA_PATH,
    LOS_MATRIX_FOLDER,
    BASE_MATRICES_PATH,
    MODE_DEST_CALIBRATION_FILE,
    MUNICIPALITY_CALIBRATION_FILE
)

try:
    from valma_bike_and_walk import valma as bike_and_walk
except ImportError:
    bike_and_walk = None


class Config():
    log_format = None
    log_level = "DEBUG"
    scenario_name = "TEST"
    result_data_folder = TEST_DATA_PATH / "Results"

INTRAZONAL_KM = 0.25


def fake_skims(setup, zone_numbers, baseline):
    """Half of every baseline value, and a routed intrazonal distance."""
    result = {}
    for mtx_type, mode_mtx in baseline.items():
        for mode, mtx in mode_mtx.items():
            ours = numpy.array(mtx, dtype=numpy.float32) * 0.5
            numpy.fill_diagonal(ours, INTRAZONAL_KM)
            result.setdefault(mtx_type, {})[mode] = ours
    return result


@unittest.skipIf(bike_and_walk is None, "valma_bike_and_walk not installed")
class BikeAndWalkTest(unittest.TestCase):

    def _model(self):
        log.initialize(Config())
        ass_model = MockAssignmentModel(MatrixData(
            RESULTS_PATH / LOS_MATRIX_FOLDER / "uusimaa"))
        model = ModelSystem(
            ZONEDATA_PATH, COSTDATA_PATH, BASE_MATRICES_PATH, RESULTS_PATH,
            ass_model, "uusimaa", MODE_DEST_CALIBRATION_FILE,
            MUNICIPALITY_CALIBRATION_FILE,
            bike_and_walk_config=TEST_DATA_PATH / "bike_and_walk")
        return model, ass_model

    def test_walk_and_bike_los_come_from_valma_bike_and_walk(self):
        with mock.patch.object(bike_and_walk, "skims",
                               side_effect=fake_skims) as skims:
            model, ass_model = self._model()
            impedance = model.assign_base_demand()

            setup = skims.call_args.args[0]
            self.assertEqual(setup.zone_data_file, ZONEDATA_PATH)
            self.assertEqual(setup.submodel, "uusimaa")
            self.assertEqual(setup.output_dir, RESULTS_PATH / "bike_and_walk")
            numpy.testing.assert_array_equal(
                skims.call_args.args[1], ass_model.zone_numbers)

            # Each period's own walk and bike LOS, replaced by ours.
            pt = ass_model.assignment_periods[1]
            self.assertEqual(pt.name, "pt")
            emme = pt.get_soft_mode_impedances()
            for mtx_type in ("time", "dist"):
                for mode in ("walk", "bike"):
                    if mode not in emme[mtx_type]:
                        continue
                    numpy.testing.assert_array_equal(
                        impedance["pt"][mtx_type][mode],
                        fake_skims(None, None, emme)[mtx_type][mode])

            car_share_before = 0.40937976247880853  # test_models.py
            impedance = model.run_iteration(impedance)
            # The demand model saw the shorter walks and rides ...
            self.assertLess(model.mode_share[0]["car_driver"],
                            car_share_before)
            # ... and the next iteration gets them again.
            numpy.testing.assert_array_equal(
                numpy.diag(impedance["pt"]["dist"]["walk"]), INTRAZONAL_KM)

    def test_demand_files_go_to_valma_bike_and_walk(self):
        with mock.patch.object(bike_and_walk, "assign") as assign:
            model, _ = self._model()
            model._assign_bike_and_walk(model.basematrices)

        demand = assign.call_args.args[1]
        folder = BASE_MATRICES_PATH / "uusimaa"
        self.assertEqual(demand, {
            tp: folder / f"demand_{tp}.omx"
            for tp in ("aht", "pt", "iht", "it")})


if __name__ == "__main__":
    unittest.main()
