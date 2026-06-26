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

def write_vehicle_summary(demand: dict, impedance: dict, resultdata: ResultsData):
    """Write summary for truck classes and their mileage."""
    modes = list(demand)
    df = DataFrame(data={
        "Mode": modes,
        "Vehicle trips (day)": numpy.array([
            numpy.sum(demand[mode]) for mode in modes], dtype=numpy.int32),
        "Vehicle mileage (vkm/day)": numpy.array([
            numpy.sum(impedance[mode]["dist"]*demand[mode])
            for mode in modes], dtype=numpy.int64)
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
