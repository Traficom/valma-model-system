import numpy
from typing import Dict, Iterable
import utils.log as log
from parameters.marine_ship import port_draught_limit, ship_draught_speed


def calc_cost(mode: str, unit_costs: Dict[str, Dict],
              impedance: Dict[str, numpy.ndarray], model_category: str):
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
            return get_domestic_ship_cost(unit_costs, impedance, model_category)
        case _:
            msg = f"Unknown mode {mode}"
            log.error(msg)
            raise ValueError(msg)

def calc_road_cost(unit_costs: Dict[str, Dict],
                   impedance: Dict[str, numpy.ndarray],
                   model_category: str) -> numpy.ndarray:
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
                   model_category: str) -> numpy.ndarray:
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
                   model_category: str):
    """Calculates ship mode specific cost parts
    
    Parameters
    ----------
    unit_costs : Dict[str, float]
        unit cost name : unit cost value
    impedance : Dict[str, numpy.ndarray]
        Type (time/dist/canal_cost) : numpy 2d matrix
    model_category : str
        'domestic' or 'foreign'
    
    Returns
    -------
    ship_cost : numpy.ndarray
        impedance type cost : numpy 2d matrix
    """
    ship_cost = (impedance["time"] * unit_costs["time"]
                 + impedance["dist"] * unit_costs["dist"]
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

def get_foreign_ship_cost(unit_costs: Dict[str, dict],
                          impedance: Dict[str, dict],
                          model_category: str,
                          fin_ports: Iterable[str],
                          is_export: bool):
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
    fin_ports : iterable of str
        Finland border id (FIHEL/FISKV...) : str
    is_export : bool
        True if export, False if import

    Returns
    -------
    dict
        Marine ship type (general_cargo/container ship...) : matrix
            Mtx type (cost/mode/draught) : numpy.ndarray
    """
    inf_mtx = numpy.full_like(
        next(iter(impedance.values()))["frequency"], numpy.inf)
    ship_info = {}
    for mode in unit_costs["ship"].keys():
        if mode == "domestic_vessel":
            continue
        ship_info[mode] = {
            "cost": inf_mtx.copy(),
            "draught": inf_mtx.copy(),
            "frequency": impedance[mode]["frequency"]
        }
        draught_limits = port_draught_limit[mode]
        for draught in map(int, unit_costs["ship"][mode]):
            impedance[mode]["time"] = (impedance[mode]["dist"] 
                                       / ship_draught_speed[mode][draught]
                                       * 60)
            cost = calc_ship_cost(unit_costs["ship"][mode][f"{draught}"],
                                  impedance[mode], model_category)
            port_draughts = numpy.array(
                [draught_limits.get(port, numpy.inf) for port in fin_ports])
            too_shallow_ports = draught > port_draughts
            if is_export:
                cost[too_shallow_ports, :] = numpy.inf
            else:
                cost[:, too_shallow_ports] = numpy.inf
            is_cheaper = cost < ship_info[mode]["cost"]
            ship_info[mode]["cost"][is_cheaper] = cost[is_cheaper]
            ship_info[mode]["draught"][is_cheaper] = draught
    return ship_info
