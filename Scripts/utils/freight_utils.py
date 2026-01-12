import json
import numpy
from pathlib import Path
from typing import Dict

import utils.log as log
from datatypes.purpose import FreightPurpose
from datahandling.zonedata import FreightZoneData
from datahandling.resultdata import ResultsData
from parameters.commodity import commodity_conversion
from datahandling.matrixdata import MatrixData
from assignment.freight_assignment import FreightAssignmentPeriod
from models.logistics import DetourDistributionInference, process_logistics_inference

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
        commodity = commodity_params["name"]
        purpose_cost = costdata.get(commodity_conversion[commodity])
        if not purpose_cost:
            log.warn(f"Aggregated commodity class '{commodity_conversion[commodity]}' "
                     f"for commodity '{commodity}' not found in costs json")
            continue
        purposes[commodity] = FreightPurpose(commodity_params, 
                                             {parameters_path.stem: zonedata},
                                             resultdata, purpose_cost)
    return purposes

def run_logistics_module(purpose: FreightPurpose, demand_truck : numpy.ndarray,
                         impedance: numpy.ndarray, zonedata: FreightZoneData, 
                         zone_index_map: dict, iterations: int) -> numpy.ndarray:
    """Entry point for running logistics module for truck demand within Finland

    Parameters
    ----------
    purpose : FreightPurpose
        Freight purpose being modelled
    demand_truck : numpy.ndarray
        Modelled truck demand for purpose
     impedance : dict
        Mode (truck/train/...) : dict
            Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix
    zonedata : FreightZoneData
        Purpose zone data
    zone_index_map : dict 
        zone id number : index
    iterations : int
        Number of times logistics module is run

    Returns:
    -------
    np.ndarray
        Truck demand for purpose that is routed through logistic centers
    """
    try:
        lcs_areas = zonedata[f"lc_area_{purpose.name}"]
    except KeyError:
        lcs_areas = zonedata["lc_area"]
    lc_sizes = lcs_areas[lcs_areas > 0]
    lc_indices = numpy.array([zone_index_map.get(id, None) 
                            for id in list(lc_sizes.index)])
    lc_sizes = lc_sizes.to_numpy()
    cost = purpose.get_costs(impedance)["truck"]["cost"]
    logistics_module = DetourDistributionInference(cost_matrix=cost,
                                                   ddm_params=purpose.logistics_params,
                                                   lc_indices=lc_indices,
                                                   lc_sizes=lc_sizes)
    for _ in range(1, iterations + 1):
        demand_truck = process_logistics_inference(model=logistics_module,
                                                   n_zones=zonedata.nr_zones,
                                                   demand=demand_truck)
    return demand_truck


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
