from argparse import ArgumentParser
import sys
from pathlib import Path

import utils.config
import utils.log as log
from assignment.mock_assignment import MockAssignmentModel
from travel_iteration import ModelSystem
from datahandling.matrixdata import MatrixData


def main(args):
    base_matrices_path = Path(args.base_data_folder, "Matrices")
    zone_data_file = Path(args.zone_data_file)
    cost_data_file = Path(args.cost_data_file)
    result_data_folder = Path(args.result_data_folder, args.scenario_name)
    if not zone_data_file.is_file():
        raise NameError(
            "Forecast data file '{}' does not exist.".format(
                zone_data_file))

    # Choose and initialize the Traffic Assignment (supply)model
    log.info("Initializing MockAssignmentModel...")
    mock_result_path = result_data_folder / "Matrices" / args.submodel
    if not mock_result_path.is_dir():
        raise NameError(
            "Mock Results directory {} does not exist.".format(
            mock_result_path))
    ass_model = MockAssignmentModel(MatrixData(mock_result_path))
    
    # Initialize model system (wrapping Assignment-model,
    # and providing demand calculations as Python modules)
    # Read input matrices (.omx) and zonedata (.csv)
    log.info("Initializing matrices and models...")
    model_args = (zone_data_file, cost_data_file,
                  base_matrices_path, result_data_folder, ass_model, args.submodel)
    model = ModelSystem(*model_args)

    # Run  simulation for one iteration.
    impedance = model.assign_base_demand()
    model.run_car_ownership(impedance)
    log.info("Simulation ended.")


if __name__ == "__main__":
    # Initially read defaults from config file ("dev-config.json")
    # but allow override via command-line arguments
    config = utils.config.read_from_file()
    parser = ArgumentParser(epilog="VALMA travel model-system entry point script.")
    parser.add_argument(
        "--version",
        action="version",
        version="helmet " + str(config.VERSION))
    parser.add_argument(
        "--json",
        type=str,
        help="Read parameters from file, override command-line and dev-config.json arguments",
    )
    # Logging
    parser.add_argument(
        "--log-level",
        choices={"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
    )
    parser.add_argument(
        "--log-format",
        choices={"TEXT", "JSON"},
    )
    parser.add_argument(
        "--scenario-name",
        type=str,
        help="Name of HELMET scenario. Influences result folder name and log file name."),
    parser.add_argument(
        "--results-path",
        type=str,
        help="Path to folder where result data is saved to."),
    parser.add_argument(
        "--submodel",
        type=str,
        help="Name of submodel, used for choosing appropriate zone mapping"),
    parser.add_argument(
        "--baseline-data-path",
        type=str,
        help="Path to folder containing both baseline zonedata and -matrices (Given privately by project manager)"),
    parser.add_argument(
        "--forecast-data-path",
        type=str,
        help="Path to folder containing forecast zonedata"),
    parser.add_argument(
        "--cost-data-path",
        type=str,
        help="Path to file containing transport cost data"),
    parser.set_defaults(
        **{key.lower(): val for key, val in config.items()})
    args = parser.parse_args()
    args_dict = vars(args)
    if args.json is not None:
        config = utils.config.read_from_file(args.json)
        for key, val in config.items():
            args_dict[key.lower()] = val

    log.initialize(args)
    log.debug("lem_version=" + str(config.VERSION))
    log.debug('sys.version_info=' + str(sys.version_info[0]))
    log.debug('sys.path=' + str(sys.path))
    json_dump = utils.config.dump(args_dict)
    log.debug(json_dump)
    p = Path(args.result_data_folder, args.scenario_name, "runtime_params.json")
    with open(p, 'w') as file:
        file.write(json_dump)

    if sys.version_info.major == 3:
        main(args)
    else:
        log.error("Python version not supported, must use version 3")
