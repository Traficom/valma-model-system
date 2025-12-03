from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Tuple, List, cast
import numpy # type: ignore
import pandas
if TYPE_CHECKING:
    from datahandling.resultdata import ResultsData
    from datahandling.zonedata import ZoneData
    from datatypes.purpose import TourPurpose
from datatypes.person import Person

import utils.log as log
import parameters.zone as param
from parameters.tour_combinations import tour_combination_area
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
    is_agent_model : bool (optional)
        Whether the model is used for agent-based simulation
    """
    
    def __init__(self, 
                 zone_data: ZoneData, 
                 resultdata: ResultsData,
                 tour_purposes: List[TourPurpose],
                 is_agent_model: bool=False):
        self.resultdata = resultdata
        self.zone_data = zone_data
        self.tour_purposes = tour_purposes
        self.purpose_dict = {purpose.name: purpose for purpose in tour_purposes}
        self._use_tour_combination_model = False
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
        bounds = param.purpose_areas[tour_combination_area]
        self.bounds = slice(*zone_data.all_zone_numbers.searchsorted(
            [bounds[0], bounds[-1]]))
        self.car_ownership_models = {
            hh_size: GenerationLogit(
                car_ownership[hh_size], zone_data, self.bounds, self.resultdata)
            for hh_size in car_ownership}
    
        # Income models used only in agent modelling
        self._income_models = [
            linear.IncomeModel(
                self.zone_data, self.bounds,
                self.resultdata, param.age_groups, is_helsinki=False),
            linear.IncomeModel(
                self.zone_data, self.bounds,
                self.resultdata, param.age_groups, is_helsinki=True),
        ]
        if is_agent_model:
            self.create_population()

    def _age_strings(self):
        for age_group in param.age_groups:
            yield "age_{}_{}".format(*age_group)

    def create_population(self):
        """Create population for agent-based simulation.

        Store list of `Person` instances in `self.population`.
        """
        numpy.random.seed(param.population_draw)
        self.population = []
        zone_numbers = self.zone_data.zone_numbers[self.bounds]
        self.zone_population = pandas.Series(0, zone_numbers)
        # Group -1 is under-7-year-olds
        age_range = numpy.arange(-1, len(param.age_groups))
        for zone_number in zone_numbers:
            weights = [self.zone_data[f"share_{age}"][zone_number]
                for age in self._age_strings()]
            # Append under-7 weight
            weights = [max(1 - sum(weights), 0)] + weights
            if sum(weights) > 1:
                if sum(weights) > 1.005:
                    msg = "Sum of age group shares for zone {} is {}".format(
                        zone_number, sum(weights))
                    log.error(msg)
                    raise ValueError(msg)
                else:
                    weights = numpy.array(weights)
                    rebalance = 1 / sum(weights)
                    weights = rebalance * weights
            zone_pop = int(round(self.zone_data["population"][zone_number]
                                 * param.agent_demand_fraction))
            zone = self.zone_data.zones[zone_number]
            incmod = self._income_models[zone.municipality == "Helsinki"]
            for _ in range(zone_pop):
                i = numpy.random.choice(a=age_range, p=weights)
                if i != -1:
                    self.population.append(Person(
                        zone, param.age_groups[i], self.tour_generation_model,
                        self.car_use_model, incmod))
                    self.zone_population[zone_number] += 1
        numpy.random.seed(None)

    def predict_income(self):
        for model in self._income_models:
            model.predict()

    def generate_tours(self):
        """Generate vector of tours for each tour purpose.

        Not used in agent-based simulation.
        Result is stored in `purpose.gen_model.tours`.
        """
        for purpose in self.tour_purposes:
            purpose.gen_model.init_tours()
            purpose.gen_model.add_tours() 
        log.info("Tours generated.")

    def generate_tour_probs(self) -> Dict[Tuple[int,int], numpy.ndarray]:
        """Generate matrices of cumulative tour combination probabilities.

        Used in agent-based simulation.

        Returns
        -------
        dict
            Age (age_7-17/...) : tuple
                Is car user (False/True) : numpy.array
                    Matrix with cumulative tour combination probabilities
                    for all zones
        """
        probs = {}
        for age in self._age_strings():
            probs[age] = [self._get_probs(age, is_car_user)
                for is_car_user in (False, True)]
        return probs

    def _get_probs(self, age: str, is_car_user: bool) -> pandas.DataFrame:
        probs = self.tour_generation_model.calc_prob(
            age, is_car_user, self.bounds)
        return pandas.DataFrame(probs).to_numpy().cumsum(axis=1)
    
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
        # The following shares of the population have own dummies in
        # mode-choice models.
        # They represent shares of the population living
        # in households with given number of cars and *adults*.
        zd.share["sh_cars1_hh1"] = zd["sh_pop_hh1_lic1"]*prob["hh1_lic1"]["1"]
        zd.share["sh_cars1_hh2"] = (zd["sh_pop_hh2_lic1"]*prob["hh2_lic1"]["1"]
                                    + zd["sh_pop_hh2_lic2"]*prob["hh2_lic2"]["1"])
        zd.share["sh_cars2_hh2"] = zd["sh_pop_hh2_lic2"]*prob["hh2_lic2"]["2"]
        zd.share["sh_car"] = (zd["sh_cars1_hh1"]
                              + zd["sh_cars1_hh2"]
                              + zd["sh_cars2_hh2"])
        result = {"cars": numpy.zeros_like(zd["population"])}
        for n_cars in range(3):
            result[f"sh_cars{n_cars}"] = numpy.zeros_like(zd["population"])
            for hh_type in prob:
                pop_hh_type = zd[f"sh_{hh_type}"] * zd["households"]
                if str(n_cars) in prob[hh_type]:
                    hh_car = prob[hh_type][str(n_cars)] * pop_hh_type
                    result["cars"] += hh_car * n_cars
                    national_share = sum(hh_car) / sum(pop_hh_type)
                    self.resultdata.print_line(
                        f"{hh_type},cars{n_cars},{national_share}", "car_ownership")
                    result[f"sh_cars{n_cars}"] += (prob[hh_type][str(n_cars)]
                                                   * zd[f"sh_{hh_type}"])
        self.resultdata.print_data(result, "zone_car_ownership.txt")
        log.info("New car-ownership values calculated.")
