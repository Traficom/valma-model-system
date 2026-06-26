from argparse import ArgumentParser
import sys
from pathlib import Path
import numpy
import json

import utils.log as log
import utils.config
import parameters.assignment as param
from datahandling.zonedata import FreightZoneData
from datahandling.resultdata import ResultsData
from assignment.emme_assignment import EmmeAssignmentModel
from assignment.emme_bindings.emme_project import EmmeProject
from datahandling.matrixdata import MatrixData
from datatypes.freight_purpose import (
    DomesticFreightPurpose, ForeignFreightPurpose, create_purposes)
from utils.freight_utils import (
    StoreDemand, update_diagonal_cost,
    write_domestic_leg_summary, write_purpose_summary, 
    write_zone_summary, write_vehicle_summary
)
from datahandling.traversaldata import transform_traversal_data
from parameters.commodity import commodity_conversion
from parameters.zone import clusters


def main(args):
    # Connect to emme project, set zonedata and other path variables
    zone_data_file = Path(args.zone_data_file)
    cost_data_file = Path(args.cost_data_file)
    result_data_folder = Path(args.result_data_folder, args.scenario_name)
    emme_project_path = Path(args.emme_project_file)
    parameters_path = Path(__file__).parent / "parameters" / "freight"
    trade_demand_file = Path(args.trade_demand_file)
    save_matrices = True if args.specify_commodity_names else False
    ep = EmmeProject(emme_project_path)
    ep.try_open_db("koko_suomi")
    ep.start()
    ass_model = EmmeAssignmentModel(ep,
                                    first_scenario_id=args.first_scenario_id,
                                    submodel="freight",
                                    save_matrices=save_matrices,
                                    first_matrix_id=args.first_matrix_id)
    zonedata = FreightZoneData(zone_data_file, ass_model.zone_numbers, "koko_suomi")
    resultdata = ResultsData(result_data_folder)
    resultmatrices = MatrixData(result_data_folder / "Matrices" / "koko_suomi")
    costdata = json.loads(cost_data_file.read_text("utf-8"))
    
    # Set foreign purposes and fetch impedances
    foreign_purposes: dict[str, ForeignFreightPurpose] = create_purposes(
        parameters_path / "foreign", zonedata, resultdata, costdata["freight"])
    purposes_to_assign = [purpose for purpose in list(commodity_conversion)
                          if purpose in args.specify_commodity_names]
    ass_model.prepare_freight_network(
        costdata["vehicle_km_cost"], costdata["vehicle_hour_cost"],
        purposes_to_assign)
    store_demand = StoreDemand(ass_model.freight_network, resultmatrices, 
                               zonedata.all_zone_numbers, zonedata.zone_numbers)
    impedance = ass_model.freight_network.assign()
    impedance = update_diagonal_cost(impedance)

    log.info("Reads marine ship impedances from network")
    trade_demand = {}
    marine_export = ass_model.freight_network.read_ship_impedances(True)
    marine_import = ass_model.freight_network.read_ship_impedances(False)
    for purpose in foreign_purposes.values():
        log.info(f"Calculating trade route for purpose: {purpose.name}")
        marine_data = marine_export if purpose.is_export else marine_import
        demand = purpose.run_trade_route_module(
            impedance, *marine_data, trade_demand_file)
        trade_demand[purpose.name] = demand
    resultdata.flush()
    fin_border_ids = list(marine_export[1].values())
    marine_export, marine_import = None, None

    # Prepare domestic model by splicing impedances and initializing final demand matrix 
    for ass_class in list(impedance):
        for mtx_type, mtx in impedance[ass_class].items():
            impedance[ass_class][mtx_type] = mtx[:zonedata.nr_zones, :zonedata.nr_zones]
    total_demand = {mode: numpy.zeros([zonedata.nr_zones, zonedata.nr_zones], dtype="float32")
                    for mode in param.truck_classes}
    
    purposes: dict[str, DomesticFreightPurpose] = create_purposes(
        parameters_path / "domestic", zonedata, resultdata, costdata["freight"])
    # Run domestic demand calculation
    for purpose in purposes.values():
        log.info(f"Calculating demand for purpose: {purpose.name}")
        demand = purpose.calc_traffic(impedance, args.logistics_iterations)
        for mode in demand:
            omx_filename = ("freight_demand_tons" if purpose.name 
                            in args.specify_commodity_names else "")
            store_demand.store(mode, demand[mode], omx_filename, purpose.name)
        if purpose.name in args.specify_commodity_names:
            ass_model.freight_network.save_network_volumes(purpose.name)
        
        if "truck" in demand:
            # Calc aux tons and transform tons to vehicles
            ass_model.freight_network.output_traversal_matrix(set(demand), resultdata.path)
            aux_demand = transform_traversal_data(resultdata.path, zonedata.zone_numbers)
            domestic_tons = demand["truck"] + sum(aux_demand.values())
            dom_leg_tons = purpose.calc_trade_mode_share(
                demand, trade_demand, fin_border_ids)
            for mode in param.truck_classes:
                total_demand[mode] += purpose.calc_vehicles(domestic_tons, mode)
                for foreign_purpose in dom_leg_tons:
                    total_demand[mode] += foreign_purposes[foreign_purpose].calc_vehicles(
                        dom_leg_tons[foreign_purpose]["truck"], mode)
            write_domestic_leg_summary(dom_leg_tons, impedance, resultdata)
        purpose.write_summary(demand, aux_demand, impedance)
        purpose.write_zone_summary(demand)
    write_vehicle_summary(total_demand, impedance, resultdata)
    resultdata.flush()
    
    log.info("Starting end assigment")
    for ass_class in total_demand:
        store_demand.store(ass_class, total_demand[ass_class], "freight_demand")
    ass_model.freight_network._assign_trucks()
    log.info("Simulation ready.")


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
        "--zone-data-file",
        type=str,
        help="Path to file containing forecast zonedata.")
    parser.add_argument(
        "--cost-data-file",
        type=str,
        help="Path to file containing transport cost data.")
    parser.add_argument(
        "--result-data-folder",
        type=str,
        help="Path to folder where result data is saved to.")
    parser.add_argument(
        "--emme-project-file",
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
        help="Specify commodity names to be assigned and saved as matrix.")
    parser.add_argument(
        "--trade-demand-file",
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
