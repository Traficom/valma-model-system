from __future__ import annotations
import numpy
import pandas
from collections import defaultdict
from typing import TYPE_CHECKING, Dict

from models.logit import GenerationLogit
from models.logit import divide
if TYPE_CHECKING:
    from datatypes.purpose import Purpose
    from datahandling.resultdata import ResultsData
    from datahandling.zonedata import ZoneData


class GenerationModel:
    """Container for tour vector.

    In the base class, tours are calculated directly in `add_tours()`.
    """

    def __init__(self, purpose: Purpose,
                 resultdata: ResultsData,
                 param: Dict[str, float]):
        """Initialize tour generation model.

        Parameters
        ----------
        purpose : datatypes.purpose.TourPurpose
            Travel purpose (hw/hs/ho/...)
        resultdata : datahandling.resultdata.ResultData
            Writer object for result directory
        param : dict
            key : str
                Zone variable name
            value : float
                Generation factor
        """
        self.resultdata = resultdata
        self.zone_data = purpose.attraction_zone_data
        self.purpose = purpose
        self.param = param

    def init_tours(self):
        """Initialize `tours` vector to 0."""
        self.tours = pandas.Series(
            0.0, self.purpose.orig_zone_numbers, dtype=numpy.float32)

    def add_tours(self):
        """Generate and add tours to zone vector."""
        shares = {
            "has_car": self.zone_data["sh_car"],
            "no_car": 1 - self.zone_data["sh_car"]
        }
        for car_availibility, b in self.param.items():
            tours = sum(b[i]*self.zone_data[i][self.purpose.bounds] for i in b)
            self.tours += shares[car_availibility] * tours

    def get_tours(self):
        """Get vector of tour numbers per zone.
        
        Returns
        -------
        numpy.ndarray
            Vector of tour numbers per zone
        """
        return self.tours.values

class LogitTourGeneration(GenerationModel):
    """For this sub-class, tours are created in `model.logit.TourCombinationModel`."""

    def __init__(self, 
                 purpose: Purpose,
                 parameters: dict,
                 zone_data: ZoneData, 
                 bounds: slice, 
                 resultdata: ResultsData):
        """Initialize tour generation model.

        Parameters
        ----------
        purpose : datatypes.purpose.TourPurpose
            Travel purpose (hw/hs/ho/...)
        resultdata : datahandling.resultdata.ResultData
            Writer object for result directory
        param : dict
            key : str
                Zone variable name
            value : float
                Generation factor
        """
        self.purpose = purpose
        self.zone_data = zone_data
        self.gen_model = GenerationLogit(parameters, zone_data, bounds, resultdata)

    def add_tours(self):
        prob = self.gen_model.calc_prob()
        for nr in range(2):
            # Each combination is a tuple of tours performed during a day
            nr_tours: pandas.Series = (nr * prob[str(nr)] * 
                                       self.zone_data["population"])
            self.tours += nr_tours

class TourCombinationGeneration(GenerationModel):
    """For this sub-class, tours are created in `model.logit.TourCombinationModel`."""

    def add_tours(self):
        pass


class NonHomeGeneration(GenerationModel):
    """For calculating numbers of non-home tours starting in each zone."""

    def add_tours(self):
        pass
    
    def get_tours(self):
        """Generate vector of tour numbers from attracted source tours.

        Assumes that home-based tours have been assigned destinations.
        
        Returns
        -------
        numpy.ndarray
            Vector of tour numbers per zone
        """
        mode_tours = defaultdict(float)
        for source in self.purpose.sources:
            b = self.param[source.name]
            for mode in source.attracted_tours:
                mode_tours[mode] += b * source.attracted_tours[mode]
        tours = sum(mode_tours.values())
        for mode in mode_tours:
            key = f"{self.purpose.name}_parent_{mode}_share"
            self.zone_data.share[key] = pandas.Series(
                divide(mode_tours[mode], tours), self.purpose.orig_zone_numbers)
        return tours


class SecDestGeneration(GenerationModel):
    """For calculating numbers of secondary-destination tours.

    Calculation is for each mode and origin-destination pair separately.
    """

    def init_tours(self):
        self.tours = dict.fromkeys(self.purpose.modes)
        for mode in self.tours:
            self.tours[mode] = 0
    
    def add_tours(self):
        pass

    def add_secondary_tours(self, demand, mode, purpose):
        """Generate matrix of tour numbers from attracted source tours."""
        mod_mode = mode.replace("work", "leisure")
        if mod_mode in self.purpose.modes:
            bounds = self.purpose.bounds
            metropolitan = next(iter(self.purpose.sources)).bounds
            self.tours[mod_mode] += (self.param[purpose.name][mode]
                                     * demand[metropolitan, bounds])
    
    def get_tours(self, mode):
        """Get vector of tour numbers per od pair.
        
        Returns
        -------
        numpy.ndarray
            Matrix of tour numbers per origin-destination pair
        """
        return self.tours[mode]
