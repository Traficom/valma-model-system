from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Tuple, List, cast
import numpy # type: ignore
import pandas
if TYPE_CHECKING:
    from datahandling.resultdata import ResultsData
    from datahandling.zonedata import ZoneData
    from datatypes.purpose import TourPurpose

import utils.log as log
import parameters.zone as param
from datatypes.purpose import SecDestPurpose
from models import linear
from models.logit import GenerationLogit
from parameters.car import car_ownership



class DemandModel:
    """Container for private tour purposes and models.

    Parameters
    ----------
    zone_data : ZoneData
        Data used for all demand calculations
    resultdata : ResultData
        Writer object to result directory
    tour_purposes : list of TourPurpose and SecDestPurpose instances
        Tour purposes
    """
    
    def __init__(self, 
                 zone_data: ZoneData, 
                 resultdata: ResultsData,
                 tour_purposes: List[TourPurpose]):
        self.resultdata = resultdata
        self.zone_data = zone_data
        self.tour_purposes = tour_purposes
        self.purpose_dict = {purpose.name: purpose for purpose in tour_purposes}
        for purpose in tour_purposes:
            try:
                sources = purpose.sources
            except AttributeError:
                pass
            else:
                purpose.sources = [self.purpose_dict[source] for source in sources]
                if isinstance(purpose, SecDestPurpose):
                    for source in purpose.sources:
                        source.sec_dest_purpose = purpose
        bounds = param.purpose_areas["domestic"]
        self.bounds = slice(*zone_data.all_zone_numbers.searchsorted(
            [bounds[0], bounds[-1]]))
        self.car_ownership_models = {
            hh_size: GenerationLogit(
                car_ownership[hh_size], zone_data, self.bounds, self.resultdata)
            for hh_size in car_ownership}
    
    def calculate_car_ownership(self, impedance):
        try:
            acc_purpose = self.purpose_dict["hb_leisure"]
        except KeyError:
            log.info("Car ownership not calculated, take from zone data")
            return
        log.info("Calc car ownership based on hb_leisure accessibility...")
        purpose_impedance = acc_purpose.transform_impedance(impedance)
        acc_purpose.model.calc_prob(purpose_impedance, calc_accessibility=True)
        zd = self.zone_data
        prob = {hh_size: model.calc_prob()
            for hh_size, model in self.car_ownership_models.items()}
        zd.share["sh_cars1_hh1"] = zd["sh_pop_hh1"]*prob["hh1"]["1"]
        zd.share["sh_cars1_hh2"] = (zd["sh_pop_hh2"]*prob["hh2"]["1"]
                                    + zd["sh_pop_hh3"]*prob["hh3"]["1"])
        zd.share["sh_cars2_hh2"] = (zd["sh_pop_hh2"]*prob["hh2"]["2"]
                                    + zd["sh_pop_hh3"]*prob["hh3"]["2"])
        zd.share["sh_car"] = (zd["sh_cars1_hh1"]
                              + zd["sh_cars1_hh2"]
                              + zd["sh_cars2_hh2"])
        result = {"cars": numpy.zeros_like(zd["population"])}
        for n_cars in range(3):
            result[f"sh_cars{n_cars}"] = numpy.zeros_like(zd["population"])
            for hh_size in prob:
                if str(n_cars) in prob[hh_size]:
                    hh_car = prob[hh_size][str(n_cars)] * zd[hh_size]
                    result["cars"] += hh_car * n_cars
                    national_share = sum(hh_car) / sum(zd[hh_size])
                    self.resultdata.print_line(
                        f"{hh_size},cars{n_cars},{national_share}", "car_ownership")
                    result[f"sh_cars{n_cars}"] += prob[hh_size][str(n_cars)] * zd[f"sh_{hh_size}"]                
        self.resultdata.print_data(result, "zone_car_ownership.txt")
        log.info("New car-ownership values calculated.")
