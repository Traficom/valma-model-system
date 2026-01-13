from argparse import ArgumentParser
import sys
from pathlib import Path
import numpy
import json
from pandas import DataFrame

import utils.log as log
import utils.config
import parameters.assignment as param
from datahandling.zonedata import FreightZoneData
from datahandling.resultdata import ResultsData
from assignment.emme_assignment import EmmeAssignmentModel
from assignment.emme_bindings.emme_project import EmmeProject
from datahandling.matrixdata import MatrixData
from datatypes.purpose import FreightPurpose

from utils.freight_utils import create_purposes, StoreDemand
from datahandling.traversaldata import transform_traversal_data
from parameters.commodity import commodity_conversion


def main(args):
    # Connect to emme project, set zonedata and other path variables
    zonedata_path = Path(args.forecast_data_path)
    cost_data_path = Path(args.cost_data_path)
    results_path = Path(args.results_path, args.scenario_name)
    emme_project_path = Path(args.emme_path)
    parameters_path = Path(__file__).parent / "parameters" / "freight"
    save_matrices = True if args.specify_commodity_names else False
    ep = EmmeProject(emme_project_path)
    ep.try_open_db("koko_suomi")
    ep.start()
    ass_model = EmmeAssignmentModel(ep,
                                    first_scenario_id=args.first_scenario_id,
                                    submodel="freight",
                                    save_matrices=save_matrices,
                                    first_matrix_id=args.first_matrix_id)
    zonedata = FreightZoneData(zonedata_path, ass_model.zone_numbers, "koko_suomi")
    resultdata = ResultsData(results_path)
    resultmatrices = MatrixData(results_path / "Matrices" / "koko_suomi")
    costdata = json.loads(cost_data_path.read_text("utf-8"))
    
    # Set purposes and fetch impedances
    purposes = create_purposes(parameters_path / "foreign", zonedata, 
                               resultdata, costdata["freight"])
    purposes_to_assign = [purpose for purpose in list(commodity_conversion)
                          if purpose in args.specify_commodity_names]
    ass_model.prepare_freight_network(costdata["car_cost"], purposes_to_assign)
    store_demand = StoreDemand(ass_model.freight_network, resultmatrices, 
                               zonedata.all_zone_numbers, zonedata.zone_numbers)
    impedance = ass_model.freight_network.assign()
    impedance[param.marine_ships_name] = {}
    
    # Run foreign trade route choice
    # Export for now. Export/import logic will be introduced later
    is_export = True
    ship_imps, origs, dests = ass_model.freight_network.read_ship_impedances(is_export)
    for purpose in purposes.values():
        log.info(f"Calculating route for foreign purpose: {purpose.name}")
        impedance[param.marine_ships_name] = ship_imps
        split_impedances = purpose.get_split_impedances(impedance, origs, dests, is_export)
    del impedance[param.marine_ships_name]

    # prepare domestic model by splicing impedances and initializing final demand matrix 
    for ass_class in list(impedance):
        for mtx_type, mtx in impedance[ass_class].items():
            impedance[ass_class][mtx_type] = mtx[:zonedata.nr_zones, :zonedata.nr_zones]
    total_demand = {mode: numpy.zeros([zonedata.nr_zones, zonedata.nr_zones], dtype="float32")
                    for mode in param.truck_classes}
    
    purposes = create_purposes(parameters_path / "domestic", zonedata, 
                               resultdata, costdata["freight"])
    # Run domestic demand calculation
    for purpose in purposes.values():
        log.info(f"Calculating demand for domestic purpose: {purpose.name}")
        demand = purpose.calc_traffic(impedance)
        if hasattr(purpose, "logistics_module") and args.logistics_iterations > 0:
            demand["truck"], _ = purpose.run_logistics_module(demand["truck"], impedance, 
                                                              ass_model.mapping, 
                                                              args.logistics_iterations)
        for mode in demand:
            omx_filename = ("freight_demand_tons" if purpose.name 
                            in args.specify_commodity_names else "")
            store_demand.store(mode, demand[mode], omx_filename, purpose.name)
        if purpose.name in args.specify_commodity_names:
            ass_model.freight_network.save_network_volumes(purpose.name)
        ass_model.freight_network.output_traversal_matrix(set(demand), resultdata.path)
        aux_demand = transform_traversal_data(resultdata.path, zonedata.zone_numbers)
        for mode in param.truck_classes:
            ton_demand = demand["truck"] + sum(aux_demand.values())
            total_demand[mode] += purpose.calc_vehicles(ton_demand, mode)
        write_purpose_summary(purpose, demand, aux_demand, impedance, resultdata)
        write_zone_summary(purpose.name, zonedata.zone_numbers, demand, resultdata)
    write_vehicle_summary(total_demand, impedance, resultdata)
    resultdata.flush()
    
    log.info("Starting end assigment")
    for ass_class in total_demand:
        store_demand.store(ass_class, total_demand[ass_class], "freight_demand")
    ass_model.freight_network._assign_trucks()
    log.info("Simulation ready.")

def write_purpose_summary(purpose: FreightPurpose, demand: dict, aux_demand: dict, 
                          impedance: dict, resultdata: ResultsData):
    """Write purpose-mode specific summary as txt-file containing mode shares 
    calculated from demand (tons), mode specific demand (tons), mode shares 
    calculated from mileage, mode specific ton-mileage, mode auxiliary ton-mileage
    and total eur-ton product.
    """
    modes = list(demand)
    mode_tons = [numpy.sum(demand[mode])+0.01 for mode in modes]
    shares_tons = [tons / sum(mode_tons) for tons in mode_tons]
    mode_ton_dist = [numpy.sum(demand[mode]*impedance[mode]["dist"])+0.01 for mode in modes]
    shares_mileage = [share / sum(mode_ton_dist) for share in mode_ton_dist]
    costs = {mode: c["cost"] for mode, c in purpose.get_costs(impedance).items()}
    for cost in costs.values():
        cost[cost == numpy.inf] = 0
    ton_costs = [numpy.sum(costs.pop(mode)*demand[mode]) for mode in modes]
    aux_ton_dist = [numpy.sum(aux_demand[mode]*impedance["truck"]["dist"]) 
                    if mode != "truck" else 0 for mode in modes]
    df = DataFrame(data={
        "Commodity": [purpose.name]*len(modes),
        "Mode": modes,
        "Mode share from tons (%)": [round(i, 3) for i in shares_tons],
        "Tons (t/annual)": [int(i) for i in mode_tons],
        "Mode share from mileage (%)": [round(i, 3) for i in shares_mileage],
        "Ton mileage (tkm/annual)": [int(i) for i in mode_ton_dist],
        "Aux ton mileage (tkm/annual)": [int(i) for i in aux_ton_dist],
        "Costs (eur-ton/annual)": [int(i) for i in ton_costs]
        })
    filename = "freight_purpose_summary.txt"
    resultdata.print_concat(df, filename)

def write_zone_summary(purpose_name: str, zone_numbers: list, 
                       demand: dict, resultdata: ResultsData):
    """Write purpose and mode specific departing and arriving tons for each zone
    in zone mapping.
    """
    df = DataFrame(index=zone_numbers)
    for mode in demand:
        df[f"Departing_{purpose_name}_{mode}"] = numpy.sum(demand[mode], axis=1, dtype="int32")
        df[f"Arriving_{purpose_name}_{mode}"] = numpy.sum(demand[mode], axis=0, dtype="int32")
    filename = "freight_zone_summary.txt"
    resultdata.print_data(df, filename)

def write_vehicle_summary(demand: dict, impedance: dict, resultdata: ResultsData):
    """Write summary for truck classes and their mileage."""
    modes = list(demand)
    vehicles_sum = [numpy.sum(demand[mode]) for mode in modes]
    mileage_sum = [numpy.sum(impedance[mode]["dist"]*demand[mode]) for mode in modes]
    df = DataFrame(data={
        "Mode": modes,
        "Vehicle trips (day)": [int(i) for i in vehicles_sum],
        "Vehicle mileage (vkm/day)": [int(i) for i in mileage_sum]
        })
    filename = "freight_vehicle_summary.txt"
    resultdata.print_data(df, filename)

if __name__ == "__main__":
    parser = ArgumentParser(epilog="VALMA freight model-system entry point script.")
    config = utils.config.read_from_file()
    
    parser.add_argument(
        "--log-level",
        choices={"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
    parser.add_argument(
        "--log-format",
        choices={"TEXT", "JSON"})
    parser.add_argument(
        "--scenario-name",
        type=str,
        help="Scenario name.")
    parser.add_argument(
        "--forecast-data-path",
        type=str,
        help="Path to file containing forecast zonedata.")
    parser.add_argument(
        "--cost-data-path",
        type=str,
        help="Path to file containing transport cost data.")
    parser.add_argument(
        "--results-path",
        type=str,
        help="Path to folder where result data is saved to.")
    parser.add_argument(
        "--emme-path",
        type=str,
        help="Filepath to .emp EMME-project-file.")
    parser.add_argument(
        "--first-scenario-id",
        type=int,
        help="First scenario ID within EMME project (.emp).")
    parser.add_argument(
        "--first-matrix-id",
        type=int,
        help="First matrix ID within EMME project (.emp).")
    parser.add_argument(
        "-d", "--del-strat-files",
        action="store_true",
        help="Using this flag deletes strategy files from Emme-project Database folder.")
    parser.add_argument(
        "--specify-commodity-names",
        nargs="*",
        choices=commodity_conversion,
        help="Commodity names in 29 classification. Assigned and saved as mtx.")
    parser.add_argument(
        "--trade-demand-data-path",
        type=str,
        help="Path to .omx file containing freight foreign trade demand.")

    parser.set_defaults(
        **{key.lower(): val for key, val in config.items()})
    args = parser.parse_args()
    log.initialize(args)
    if sys.version_info.major == 3:
        main(args)
    else:
        log.error("Python version not supported, must use version 3")
