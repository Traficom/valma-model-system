import json
import numpy
from pathlib import Path
from typing import Dict
from pandas import DataFrame

import utils.log as log
from parameters.assignment import truck_classes
from datatypes.purpose import FreightPurpose
from datahandling.zonedata import FreightZoneData
from datahandling.resultdata import ResultsData
from parameters.commodity import commodity_conversion
from datahandling.matrixdata import MatrixData
from assignment.freight_assignment import FreightAssignmentPeriod

def create_purposes(parameters_path: Path, zonedata: FreightZoneData, 
                    resultdata: ResultsData, costdata: Dict[str, dict]) -> dict:
    """Creates instances of FreightPurpose class for each model parameter json file
    in parameters path.

    Parameters
    ----------
    parameters_path : Path
        Path object to estimation model type folder containing model parameter
        json files
    zonedata : FreightZoneData
        freight zonedata container
    resultdata : ResultsData
        handler for result saving operations 
    costdata : Dict[str, dict]
        Freight purpose : Freight mode
            Freight mode (truck/freight_train/ship) : mode
                Mode (truck/trailer_truck...) : unit cost name
                    unit cost name : unit cost value

    Returns
    -------
    dict[str, FreightPurpose]
        purpose name : FreightPurpose
    """
    purposes = {}
    for file in parameters_path.rglob("*.json"):
        commodity_params = json.loads(file.read_text("utf-8"))
        commodity = commodity_params["name"].split("_")[0]
        purpose_cost = costdata.get(commodity_conversion[commodity])
        if not purpose_cost:
            log.warn(f"Aggregated commodity class '{commodity_conversion[commodity]}' "
                     f"for commodity '{commodity}' not found in costs json")
            continue
        zone_data = {parameters_path.stem: zonedata}
        if parameters_path.stem == "foreign":
            zone_data["domestic"] = zonedata
        purposes[commodity_params["name"]] = FreightPurpose(commodity_params, 
                                                            zone_data, resultdata,
                                                            purpose_cost)
    return purposes

def update_diagonal_cost(impedance: dict) -> dict:
    """Updates diagonal (own zone) impedance values

    Parameters
    ----------
    impedance : dict
        Mode (truck/train/...) : dict
            Type (cost/time/dist...) : numpy 2d matrix
    
    Returns
    -------
    dict
        Mode (truck/train/...) : dict
            Type (cost/time/dist...) : numpy 2d matrix
    """
    for mode in impedance:
        if mode in truck_classes:
            diag_values = {
                imp_type: numpy.min(
                    numpy.where(impedance[mode][imp_type] > 0, 
                    impedance[mode][imp_type], numpy.inf), axis=1)
                for imp_type in ("cost", "dist")
            }
        else:
            diag_values = {mtx: numpy.inf for mtx in ("time", "aux_cost")}
        for imp_type in diag_values:
            numpy.fill_diagonal(impedance[mode][imp_type], diag_values[imp_type])
    return impedance

def write_trade_route_summary(purpose: FreightPurpose, demand: dict, 
                              _, fin_border_ids: dict, cluster_border_ids: dict,
                              resultdata: ResultsData, clusters: dict = None):
    """Write summary from routed trade demand matrix.
    Handles both 2nd leg and cluster_border summary outputs.
    """
    commodity, trade_type = purpose.name.split("_")
    cluster_border_indices = dict(enumerate(cluster_border_ids))
    match_clusters = purpose.is_export == bool(clusters)
    if clusters:
        key_indices = dict(enumerate(clusters))
        leg_name = "leg_three" if purpose.is_export else "leg_one"
        label = "Cluster"
        filename = "freight_cluster_border_summary.txt"
    else:
        key_indices = dict(enumerate(fin_border_ids))
        leg_name = "leg_two"
        label = "Finnish border"
        filename = "freight_leg2_summary.txt"
    df_data = [
        {
            "Commodity": commodity,
            "Type": trade_type,
            "Mode": mode,
            label: key_indices[col if match_clusters else row],
            "Foreign_border": cluster_border_indices[row if match_clusters else col],
            "Tons (t/annual)": mtx[row, col]
        }
        for mode, mtx in demand[leg_name].items()
        for row, col in zip(*numpy.nonzero(numpy.round(mtx, 5)))
    ]
    resultdata.print_concat(DataFrame(df_data), filename)

def write_domestic_leg_summary(demand_trade: dict, impedance: dict,
                               resultdata: ResultsData):
    """Write summary for trade demand's domestic leg including transported
    commodity, trade type (export/import), mode, tons and ton mileage.
    """
    rows = [
        {
            "Commodity": name,
            "Type": trade_type,
            "Mode": mode,
            "Tons (t/annual)": numpy.sum(demand_trade[purpose][mode], dtype=numpy.float32),
            "Ton mileage (tkm/annual)": numpy.sum(
                demand_trade[purpose][mode] * impedance[mode]["dist"], dtype=numpy.int64),
        }
        for purpose in demand_trade
        for name, trade_type in [purpose.split("_")]
        for mode in demand_trade[purpose]
    ]
    filename = "freight_domestic_leg_summary.txt"
    resultdata.print_concat(DataFrame(rows), filename)

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

class StoreDemand():
    """Handles demand dimension compatibility when storing demand matrices 
    into Emme and omx-files.
    """

    def __init__(self, 
                 freight_network: FreightAssignmentPeriod, 
                 resultmatrices: MatrixData, 
                 all_zone_numbers: numpy.ndarray, 
                 zone_numbers: numpy.ndarray):
        self.network = freight_network
        self.resultmatrices = resultmatrices
        self.all_zones = all_zone_numbers
        self.zones = zone_numbers

    def store(self, mode: str, demand: numpy.ndarray, 
              omx_filename: str = "", key_prefix: str = ""):
        """Stores demand matrices into Emme and as omx if user has given
        name for the .omx file. 

        Parameters
        ----------
        mode : str
            freight mode/assignment class
        demand : numpy.ndarray
            matrix that is set to Emme
        omx_filename : str, by default empty string
            optional name of an external .omx file for saving results
        key_prefix : str, by default empty string
            optional name prefix for matrix e.g. purpose name
        """
        emme_mtx = self.assess_dimensions(demand)
        self.network.set_matrix(mode, emme_mtx)
        if omx_filename:
            with self.resultmatrices.open(omx_filename, self.network.name, 
                                          self.all_zones, m="a") as mtx:
                keyname = f"{key_prefix}_{mode}" if key_prefix else mode
                mtx[keyname] = emme_mtx

    def assess_dimensions(self, demand: numpy.ndarray) -> numpy.ndarray:
        """Evaluates whether given demand matrix needs to be padded with zones 
        to maintain zone compatibility with scenario's Emme network.

        Parameters
        ----------
        demand : numpy.ndarray
            type demand matrix which is assessed before setting into Emme

        Returns
        -------
        numpy.ndarray
            demand with/without zone padding
        """
        fill_mtx = demand
        nr_all_zones = self.all_zones.size
        nr_zones = self.zones.size
        if demand.size != nr_all_zones**2:
            fill_mtx = numpy.zeros([nr_all_zones, nr_all_zones], dtype=numpy.float32)
            fill_mtx[:nr_zones, :nr_zones] = demand
        return fill_mtx
