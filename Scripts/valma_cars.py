from argparse import ArgumentParser
import sys
from pathlib import Path

import fiona
import pandas

from datahandling.resultdata import ResultsData
from datahandling.zonedata import ZoneData
from demand.trips import DemandModel
import utils.config
import utils.log as log


def main(args):
    zone_data_file = Path(args.zone_data_file)
    result_data_folder = Path(args.result_data_folder, args.scenario_name)
    if not zone_data_file.is_file():
        raise NameError(
            "Forecast data file '{}' does not exist.".format(
                zone_data_file))

    # Read zone numbers
    if len(fiona.listlayers(zone_data_file)) > 1:
            msg = f"Multiple layers found in file {zone_data_file}"
            log.error(msg)
            raise TypeError(msg)
    with fiona.open(zone_data_file, ignore_geometry=True) as colxn:
        data = pandas.DataFrame(
            [record["properties"] for record in colxn],
            columns=list(colxn.schema["properties"]))

    zonedata = ZoneData(
        zone_data_file, data["input_zone_id"], args.submodel,
        car_dist_cost=0.12,
        electric_car_share={"default": {"bev": 0.05, "phev": 0.05}})
    resultdata = ResultsData(result_data_folder)
    dm = DemandModel(zonedata, resultdata, [])

    # Run  simulation for one iteration.
    dm.calculate_individual_car_ownership()
    resultdata.flush()
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
        help="Name of HELMET scenario. Influences result folder name and log file name.")
    parser.add_argument(
        "--results-path",
        type=str,
        help="Path to folder where result data is saved to.")
    parser.add_argument(
        "--submodel",
        type=str,
        help="Name of submodel, used for choosing appropriate zone mapping")
    parser.add_argument(
            "--zone-data-file",
            type=str,
            help="Path to folder containing forecast zonedata")
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
