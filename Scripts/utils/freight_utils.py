import json
import numpy
from pathlib import Path
from typing import Dict
from pandas import DataFrame

import utils.log as log
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


def write_leg2_summary(purpose: FreightPurpose, demand: dict, 
                       _, fin_border_ids: dict, cluster_border_ids: dict,
                       resultdata: ResultsData):
    """Write summary for leg two of trade routes, including commodity, type, mode,
    border crossings, and tons for non-zero demand pairs.
    """
    commodity, trade_type = purpose.name.split("_")
    fin_border_indices = {i: key for i, key in enumerate(fin_border_ids)}
    cluster_border_indices = {i: key for i, key in enumerate(cluster_border_ids)}
    df_data = []
    for mode in demand["leg_two"]:
        mtx = numpy.round(demand["leg_two"][mode], 5)
        nonzero_indices = numpy.nonzero(mtx)
        for i, j in zip(nonzero_indices[0], nonzero_indices[1]):
            tons = mtx[i, j]
            fin_border_idx = i if purpose.is_export else j
            foreign_border_idx = j if purpose.is_export else i
            fin_border = fin_border_indices[fin_border_idx]
            foreign_border = cluster_border_indices[foreign_border_idx]
            df_data.append({
                "Commodity": commodity,
                "Type": trade_type,
                "Mode": mode,
                "Finnish border": fin_border,
                "Foreign border": foreign_border,
                "Tons (t/annual)": tons
            })
    filename = "leg2_summary.txt"
    resultdata.print_concat(DataFrame(df_data), filename)

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
