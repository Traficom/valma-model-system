from argparse import ArgumentParser
import os
import sys
import json
from pathlib import Path
import numpy
from typing import List, Dict, Union

import utils.config
import utils.log as log
from utils.validate_network import validate
from assignment.mock_assignment import MockAssignmentModel
from datahandling.matrixdata import MatrixData
from datahandling.zonedata import GridData
import parameters.assignment as param
from valma_travel import BASE_ZONEDATA_FILE
from valma_travel import LOS_MATRIX_FOLDER


def main(args):
    emme_project_files: Union[str,List[str]] = args.emme_project_files
    first_scenario_ids: Union[int,List[int]] = args.first_scenario_ids
    zone_data_files: Union[str,List[str]] = args.zone_data_files
    zone_numbers: Dict[str, numpy.array] = {}
    # Get zone numbers from assignment model
    for i, emp_path in enumerate(emme_project_files):
        calc_long_dist_demand = args.long_dist_demand_forecast[i] == "calc"
        time_periods = ({"vrk": "WholeDayPeriod"} if calc_long_dist_demand
            else param.time_periods)
        if args.do_not_use_emme:
                mock_result_path = Path(
                    args.result_data_folder, args.scenario_name[i],
                    LOS_MATRIX_FOLDER, args.submodel[i])
                if not mock_result_path.exists():
                    msg = "Mock Results directory {} does not exist.".format(
                        mock_result_path)
                    log.error(msg)
                    raise NameError(msg)
                assignment_model = MockAssignmentModel(
                    MatrixData(mock_result_path), time_periods=time_periods)
                zone_numbers[args.submodel[i]] = assignment_model.zone_numbers
        else:
            if not os.path.isfile(emp_path):
                msg = ".emp project file not found in given '{}' location.".format(
                    emp_path)
                log.error(msg)
                raise ValueError(msg)
            import inro.emme.desktop.app as _app # type: ignore
            app = _app.start_dedicated(
                project=emp_path, visible=False, user_initials="HSL")
            data_expl = app.data_explorer()
            databases = data_expl.databases()
            if len(databases) > 1:
                for db in databases:
                    if db.title() == args.submodel[i]:
                        emmebank = db.core_emmebank
                        break
                else:
                    for db in databases:
                        if db.title() == "alueelliset_osamallit":
                            emmebank = db.core_emmebank
                            break
                    else:
                        emmebank = data_expl.active_database().core_emmebank
            else:
                emmebank = data_expl.active_database().core_emmebank
            scen = emmebank.scenario(first_scenario_ids[i])
            if scen is None:
                msg = "Project {} has no scenario {}".format(
                    emp_path, first_scenario_ids[i])
                log.error(msg)
                raise ValueError(msg)
            zone_numbers[args.submodel[i]] = scen.zone_numbers
    # Prepare ZoneData
    if not zone_data_files:
        msg = "Missing required argument 'zone-data-files'."
        log.error(msg)
        raise ValueError(msg)
    model_types = (args.model_types if args.model_types
        else ["passenger_transport" for _ in zone_data_files])
    for i, (model_type, data_path, submodel, scenario) in enumerate(zip(
            model_types, zone_data_files, args.submodel, args.scenario_name)):
            # Check forecasted zonedata
            if not os.path.exists(data_path):
                msg = "Data file '{}' does not exist.".format(data_path)
                log.error(msg)
                raise ValueError(msg)
            grid_data = GridData(Path(data_path), submodel, 
                                 zone_numbers[submodel], model_area="domestic")
            results_path = Path(args.result_data_folder, scenario)
            grid_data.export(Path(results_path / f"{submodel}.gpkg"))

    log.info(f"Successfully exported zonedata files { args.scenario_name}")


if __name__ == "__main__":
    # Initially read defaults from config file ("dev-config.json")
    # but allow override via command-line arguments
    config = utils.config.read_from_file()
    parser = ArgumentParser(epilog="HELMET model system entry point script.")
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
        "--model-types",
        type=str,
        nargs="+",
        help=("List of scenario model types "
              + "('passenger_transport'/'goods_transport'/...)")
    )
    parser.add_argument(
        "-l", "--long-dist-demand-forecast",
        type=str,
        nargs="+",
        required=True,
        help=("If 'calc', runs assigment with free-flow speed and "
              + "calculates demand for long-distance trips. "
              + "If 'base', takes long-distance trips from base matrices. "
              + "If path, takes long-distance trips from that path.")
    )
    parser.add_argument(
        "--do-not-use-emme",
        action="store_true",
        help="Using this flag runs with MockAssignmentModel instead of EmmeAssignmentModel, not requiring EMME.",
    )
    parser.add_argument(
        "--scenario-name",
        type=str,
        nargs="+",
        required=True,
        help="Name of VALMA scenario. Influences result folder name and log file name."),
    parser.add_argument(
        "--result-data-folder",
        type=str,
        help="Path to folder where result data is saved to."),
    # Scenarios' individual input
    parser.add_argument(
        "--submodel",
        type=str,
        nargs="+",
        required=True,
        help="Name of submodel, used for choosing appropriate zone mapping"),
    parser.add_argument(
        "--emme-project-files",
        type=str,
        nargs="+",
        required=True,
        help="List of filepaths to .emp EMME-project-files"),
    parser.add_argument(
        "--first-scenario-ids",
        type=int,
        nargs="+",
        required=True,
        help="List of first (biking) scenario IDs within EMME project (.emp)."),
    parser.add_argument(
        "--zone-data-files",
        type=str,
        nargs="+",
        required=True,
        help="List of paths to zone data files."),
    parser.set_defaults(
        **{key.lower(): val for key, val in config.items()})
    args = parser.parse_args()

    log.initialize(args)
    log.debug(utils.config.dump(vars(args)))

    if sys.version_info.major == 3:
        main(args)
    else:
        log.error("Python version not supported, must use version 3")
