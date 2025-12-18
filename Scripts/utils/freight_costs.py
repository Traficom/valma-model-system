import numpy
from typing import Dict
import utils.log as log
from parameters.marine_ship import port_draught_limit, ship_draught_speed


def calc_cost(mode: str, unit_costs: Dict[str, Dict],
              impedance: Dict[str, numpy.ndarray], model_category: str,
              origs: dict = None, dests: dict = None):
    """Calculate freight costs.

    Parameters
    ----------
    mode : str
        Freight mode (truck/freight_train/ship)
    unit_costs : Dict[str, Dict]
        Freight mode (truck/freight_train/ship) : mode
            Mode (truck/trailer_truck) : unit cost name
                unit cost name : unit cost value
    impedance : Dict[str, numpy.ndarray]
        Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix
    model_category : str
        purpose modelling category, within Finland as 'domestic, 
        outside Finland as 'foreign'
    origs : dict
        Origin border id (FIHEL/SESTO...) : str
            Centroid id : int
    dests : dict
        Destination border id (FIHEL/SESTO...) : str
            Centroid id : int

    Returns
    ----------
    road_cost : numpy.ndarray
        impedance type cost : numpy 2d matrix
    """
    match mode:
        case "truck":
            return calc_road_cost(unit_costs, impedance, model_category)
        case "freight_train":
            return calc_rail_cost(unit_costs, impedance, model_category)
        case "ship":
            if model_category == "domestic":
                return get_domestic_ship_cost(unit_costs, impedance, model_category)
            else:
                return get_foreign_ship_cost(unit_costs, impedance, 
                                             model_category, origs, dests)
        case _:
            msg = f"Unknown mode {mode}"
            log.error(msg)
            raise ValueError(msg)

def calc_road_cost(unit_costs: Dict[str, Dict],
                   impedance: Dict[str, numpy.ndarray],
                   model_category: str):
    """Calculate freight road costs.

    Parameters
    ----------
    unit_costs : Dict[str, Dict]
        Freight mode (truck/freight_train/ship) : mode
            Mode (truck/trailer_truck) : unit cost name
                unit cost name : unit cost value
    impedance : Dict[str, numpy.ndarray]
        Type (time/dist/toll_cost) : numpy 2d matrix
    model_category : str
        'domestic' or 'foreign'

    Returns
    ----------
    road_cost : numpy.ndarray
        impedance type cost : numpy 2d matrix
    """
    mode_cost = {}
    for mode, params in unit_costs["truck"].items():
        mode_cost[mode] = ((sum(impedance[k] * params[k] for k in impedance) 
                           + params["terminal_cost"])
                           * params[f"{model_category}_distribution"])
    return sum(mode_cost.values())

def calc_rail_cost(unit_costs: Dict[str, Dict],
                   impedance: Dict[str, numpy.ndarray],
                   model_category: str):
    """Calculate freight rail based costs.

    Parameters
    ----------
    unit_costs : Dict[str, Dict]
        Freight mode (truck/freight_train/ship) : mode
            Mode (electric_train/diesel_train) : unit cost name
                unit cost name : unit cost value
    impedance : Dict[str, numpy.ndarray]
        Type (time/dist/toll_cost) : numpy 2d matrix
    model_category : str
        'domestic' or 'foreign'

    Returns
    ----------
    rail_cost : numpy.ndarray
        impedance type cost : numpy 2d matrix
    """
    mode_cost = {}
    for mode, params in unit_costs["freight_train"].items():
        mode_cost[mode] = (impedance["time"] * params["time"]
                           + impedance["dist"] * params["dist"]
                           + params["terminal_cost"])
    rail_cost = mode_cost["diesel_train"]
    rail_aux_cost = get_aux_cost(unit_costs, impedance, model_category)
    return rail_cost + rail_aux_cost

def get_domestic_ship_cost(unit_costs: Dict[str, Dict],
                           impedance: Dict[str, numpy.ndarray],
                           model_category: str):
    """Fetch domestic freight ship based costs. 

    Parameters
    ----------
    unit_costs : Dict[str, Dict]
        Freight mode (truck/freight_train/ship) : mode
            Mode (domestic_vessel) : unit cost name
                unit cost name : unit cost value
    impedance : Dict[str, numpy.ndarray]
        Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix
    model_category : str
        'domestic' or 'foreign'

    Returns
    ----------
    ship_cost : numpy.ndarray
        impedance type cost : numpy 2d matrix
    """
    ship_params = unit_costs["ship"]["domestic_vessel"]
    ship_cost = calc_ship_cost(ship_params, impedance, model_category)
    ship_aux_cost = get_aux_cost(unit_costs, impedance, model_category)
    return ship_cost + ship_aux_cost

def calc_ship_cost(unit_costs: Dict[str, float], 
                   impedance: Dict[str, numpy.ndarray],
                   model_category: str,
                   draught_mask: numpy.ndarray = 1):
    """Calculates ship mode specific cost parts
    
    Parameters
    ----------
    unit_costs : Dict[str, float]
        unit cost name : unit cost value
    impedance : Dict[str, numpy.ndarray]
        Type (time/dist/canal_cost) : numpy 2d matrix
    model_category : str
        'domestic' or 'foreign'
    draught_mask : numpy.ndarray, Optional
        marine ship eligibility to traverse at specific draught. By default 1
    
    Returns
    -------
    ship_cost : numpy.ndarray
        impedance type cost : numpy 2d matrix
    """
    ship_cost = (impedance["time"] * unit_costs["time"] * draught_mask
                 + impedance["dist"] * unit_costs["dist"] * draught_mask
                 + unit_costs["terminal_cost"])
    if model_category == "domestic":
        ship_cost += impedance["canal_cost"] * unit_costs["canal_cost"]
    return ship_cost

def get_aux_cost(unit_costs: Dict[str, Dict],
                 impedance: Dict[str, numpy.ndarray],
                 model_category: str):
    """Checks whether auxiliary mode distance is over twice as long
    as main mode distance or if main mode mode has not been used 
    at all. In such cases, assigns inf for said OD pairs.
    Otherwise calculates actual auxiliary cost.

    Parameters
    ----------
    unit_costs : Dict[str, Dict]
        Freight mode (truck/freight_train/ship)
    impedance : Dict[str, numpy.ndarray]
        Type (time/dist/toll_cost) : numpy 2d matrix
    model_category : str
        'domestic' or 'foreign'

    Returns
    ----------
    auxiliary road cost : numpy.ndarray
        impedance type cost : numpy 2d matrix
    """
    impedance_aux = {
        "dist": impedance["aux_dist"],
        "time": impedance["aux_time"],
        "toll_cost": impedance["toll_cost"]
    }
    aux_cost = numpy.where(
        (impedance["aux_dist"] > (impedance["dist"]*2))
        | (impedance["dist"] == 0),
        numpy.inf,
        calc_road_cost(unit_costs, impedance_aux, model_category))
    return aux_cost

def get_foreign_ship_cost(unit_costs: Dict[str, dict], impedance: Dict[str, dict], 
                          model_category: str, origs: dict, dests: dict):
    """Fetch smallest general cost for each marine ship in unit costs.
    
    Parameters
    ----------
    unit_costs : Dict[str, dict]
        Freight mode (truck/freight_train/ship) : mode
            Mode (general_cargo/container_ship...) : draught
                draught (4/5/8...) : unit cost name
                    unit cost name : unit cost value
    impedance : Dict[str, dict]
        Sub ship mode (general_cargo/container_ship...) : attribute
            Type (dist) : numpy 2d matrix
    model_category : str
        purpose estimation category, domestic or foreign
    origs : dict
        Origin border id (FIHEL/SESTO...) : str
            Centroid id : int
    dests : dict
        Destination border id (FIHEL/SESTO...) : str
            Centroid id : int

    Returns
    -------
    dict
        Marine ship type (general_cargo/container ship...) : matrix
            Mtx type (cost/mode/draught) : numpy.ndarray
    """
    inf_mtx = numpy.full((len(origs), len(dests)), numpy.inf, dtype="float32")
    ship_info = {}
    for mode in unit_costs["ship"].keys():
        if mode == "domestic_vessel":
            continue
        ship_info[mode] = {
            "cost": inf_mtx.copy(),
            "draught": inf_mtx.copy()
        }
        for draught in map(int, unit_costs["ship"][mode]):
            impedance[mode]["time"] = (impedance[mode]["dist"] 
                                       / ship_draught_speed[mode][draught]
                                       * 60)
            mask = evaluate_port_draught(draught, port_draught_limit[mode], 
                                         origs, dests)
            cost = calc_ship_cost(unit_costs["ship"][mode][f"{draught}"], 
                                  impedance[mode], model_category, 
                                  draught_mask=mask)
            mask = cost < ship_info[mode]["cost"]
            ship_info[mode]["cost"][mask] = cost[mask]
            ship_info[mode]["draught"][mask] = draught
    return ship_info

def evaluate_port_draught(draught: int, port_draught: dict, 
                          ext_origin: dict, ext_dest: dict) -> bool:
    """Evaluates whether a ship type can enter to a Finnish port within draught 
    restrictions. Uses ext zones to deduce whether evaluation should be done
    for origin or destination zones. Result matrix contains 1 for enable to 
    enter and np.inf for unable to enter.

    Parameters
    ----------
    ship_draught : int
        draught (4/5/8...) for marine ship type in unit costs
    port_draught : dict[str, int]
        Finnish port name id (FIHEL/FISKV...) : draught limit
    ext_origin : dict
        External origin name id (FIHEL/EETLL...) : emme centroid id
    ext_dest : dict
        External destination name id (FIHEL/EETLL...) : emme centroid id

    Returns
    -------
    numpy.ndarray
        Mask (1/np.inf)
    """
    mask = numpy.ones((len(ext_origin), len(ext_dest)))
    for index, port in enumerate(ext_origin):
        if port in port_draught and draught > port_draught[port]:
            mask[index, :] = numpy.inf
    for index, port in enumerate(ext_dest):
        if port in port_draught and draught > port_draught[port]:
            mask[:, index] = numpy.inf
    return mask
