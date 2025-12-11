from __future__ import annotations
import numpy # type: ignore

from parameters.departure_time import demand_share
from parameters.zone import purpose_areas


class ExternalPurpose:
    """External traffic purpose.

    Parameters
    ----------
    zone_numbers : numpy.ndarray
        Zone numbers from assignment model
    """

    def __init__(self, zone_numbers: numpy.ndarray):
        self.name = "external"
        self.demand_share = demand_share["external"]
        bounds = slice(*zone_numbers.searchsorted(purpose_areas["all"]))
        self.bounds = bounds
        self.dest_interval = bounds
