from __future__ import annotations
from typing import Any, Dict, Union
import parameters.assignment as param


(
    NOT_BOARDED,
    PARKED,
    BOARDED_LOCAL,
    BOARDED_LONG_D,
    BOARDED_DEST,
    LEFT,
    FORBIDDEN,
) = range(7)
DESCRIPTION = [
    "Not boarded yet",
    "Parked",
    "Boarded local service",
    "Boarded long-distance service",
    "Boarded local service at destination",
    "Left transit system",
    "Forbidden",
]
DESTINATIONS_REACHABLE = {
    NOT_BOARDED: False,
    PARKED: False,
    BOARDED_LOCAL: True,
    BOARDED_LONG_D: True,
    BOARDED_DEST: True,
    LEFT: True,
    FORBIDDEN: False,
}


class JourneyLevel:
    """
    Journey level specification for transit assignment.

    Parameters
    ----------
    level : int
        Journey level: 0 - not boarded yet, 1 - parked,
        2 - boarded local service, 3 - boarded long-distance service,
        4 - boarded local service at destination,
        5 - left transit system, 6 - forbidden (virtual level)
    transit_class : str
        Name of transit class (transit_work/transit_leisure/...)
    park_and_ride : str or False (optional)
        Extra attribute name for park-and-ride aux volume if
        this is park-and-ride assignment, else False
    """
    def __init__(self, level: int, transit_class: str,
                 park_and_ride: Union[str, bool] = False):
        # Boarding transit modes allowed only on levels 0-4
        if level <= BOARDED_LOCAL:
            next = BOARDED_LOCAL
        elif level <= BOARDED_DEST:
            next = BOARDED_DEST
        else:
            next = FORBIDDEN
        local_transit_modes = [mode for mode in param.local_transit_modes
            if mode not in param.long_dist_transit_modes[transit_class]]
        transitions = [{
                "mode": mode,
                "next_journey_level": next,
            } for mode in local_transit_modes]
        next = BOARDED_LONG_D if level <= BOARDED_DEST else FORBIDDEN
        transitions += [{
                "mode": mode,
                "next_journey_level": next,
            } for mode in param.long_dist_transit_modes[transit_class]]
        if park_and_ride:
            if transit_class in param.car_access_classes:
                # Park-and-ride (car) mode allowed only on level 0.
                car = FORBIDDEN if level >= PARKED else NOT_BOARDED
                # If we want parking to be allowed only on specific links
                # (i.e., park-and-ride facilities), we should specify an
                # own mode for these links. For now, parking is allowed
                # on all links where walking to a stop is possible.
                walk = PARKED if level == NOT_BOARDED else level
            elif transit_class in param.car_egress_classes:
                # Transfer to park-and-ride (car) mode only allowed after first
                # boarding. If we want parking to be allowed only on specific
                # links, we should specify an own mode for these links.
                # For now, parking is allowed on all links where walking
                # from a stop is possible.
                car = LEFT if BOARDED_LOCAL < level < FORBIDDEN else FORBIDDEN
                walk = FORBIDDEN if level == LEFT else level
            transitions.append({
                "mode": param.park_and_ride_mode,
                "next_journey_level": car,
            })
        else:
            # Walk modes do not normally affect journey level transitions
            walk = level
        transitions += [{
                "mode": mode,
                "next_journey_level": walk,
            } for mode in param.aux_modes]
        self.spec = {
            "description": DESCRIPTION[level],
            "destinations_reachable": DESTINATIONS_REACHABLE[level],
            "transition_rules": transitions,
            "boarding_time": None,
            "boarding_cost": {
                "global": None,
                "at_nodes": None,
                "on_lines": {
                    "penalty": param.board_fare_attr,
                    "perception_factor": param.vot_inv[param.vot_classes[
                        transit_class]],
                },
                "on_segments": None,
            },
            "waiting_time": None,
        }
        if level in (BOARDED_LOCAL, BOARDED_DEST):
            # Free transfers within local transit
            (self.spec["boarding_cost"]
                      ["on_lines"]["penalty"]) =  param.board_long_dist_attr
        if (transit_class in param.long_distance_transit_classes
                and level == BOARDED_LOCAL):
            self.spec["destinations_reachable"] = False
