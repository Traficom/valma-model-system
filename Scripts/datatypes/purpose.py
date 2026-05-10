from __future__ import annotations
from typing import Dict, Iterator, Optional, List, cast
from copy import copy
from collections import defaultdict
import numpy # type: ignore
import pandas
from datahandling.resultdata import ResultsData
from datahandling.zonedata import ZoneData
from datahandling.matrixdata import MatrixData, read_omx_item
import utils.log as log
import parameters.zone as param
import models.logit as logit
from parameters.assignment import (
    assignment_classes,
    intermodals,
    mixed_mode_classes,
    mode_impedance
)
import parameters.cost as cost
import models.generation as generation
from datatypes.demand import Demand
from demand.foreign_external import ForeignExternalModel
from datatypes.histogram import TourLengthHistogram
from utils.freight_costs import calc_cost, get_foreign_ship_cost
from utils.calibrate import attempt_calibration
from models.logistics import (LogisticsModule, TradeRouteModule,
                              run_logistics_model, run_trade_model)
from parameters.marine_ship import leg_names


class Purpose:
    """Generic container class without methods.
    
    Sets the purpose zone bounds.

    Parameters
    ----------
    specification : dict
        "name" : str
            Tour purpose name
        "orig" : str
            Origin of the tours
        "dest" : str
            Destination of the tours
        "area" : str
            Model area
        "impedance_share" : dict
            Impedance shares
    zone_datas : Dict
        key : str
            Model area (domestic/foreign)
        val : ZoneData
            Data used for all demand calculations
    resultdata : ResultsData (optional)
        Writer object to result directory
    mtx_adjustment : dict (optional)
        Dict of matrix adjustments for testing elasticities
    """

    def __init__(self, 
                 specification: Dict[str,Optional[str]],
                 zone_datas: Dict[str, ZoneData],
                 resultdata: Optional[ResultsData] = None,
                 mtx_adjustment: Optional[Dict] = None):
        self.name = specification["name"]
        self.orig = specification["orig"]
        self.dest = specification["dest"]
        self.generation_area = specification["generation_area"]
        self.attraction_area = specification["attraction_area"]
        self.impedance_share = specification["impedance_share"]
        self.demand_share = specification["demand_share"]
        self.generation_zone_data = zone_datas[self.generation_area]
        self.attraction_zone_data = zone_datas[self.attraction_area]
        zone_numbers = self.generation_zone_data.all_zone_numbers
        self.bounds = slice(*zone_numbers.searchsorted(
            param.purpose_areas[self.generation_area]))
        self.dest_interval = slice(*zone_numbers.searchsorted(
            param.purpose_areas[self.attraction_area]))
        if self.name == "hb_abroad_other":
            self.dest_interval = slice(*zone_numbers.searchsorted(
                param.purpose_areas["external"]))
        self.resultdata = resultdata
        self.mtx_adjustment = mtx_adjustment
        self.generated_tours: Dict[str, numpy.array] = {}
        self.generated_distance: Dict[str, numpy.array] = {}
        self.attracted_tours: Dict[str, numpy.array] = {}
        self.attracted_distance: Dict[str, numpy.array] = {}

    @property
    def orig_zone_numbers(self):
        return self.generation_zone_data.zone_numbers

    @property
    def dest_zone_numbers(self):
        return self.attraction_zone_data.zone_numbers
    
    def transform_impedance(self, impedance):
        """Perform transformation from time period dependent matrices
        to aggregate impedance matrices for specific travel purpose.

        Parameters
        ----------
        impedance: dict
            key : str
                Time period (aht/pt/iht)
            value : dict
                key : str
                    Impedance type (time/cost/dist)
                value : dict
                    key : str
                        Assignment class (car/transit/...)
                    value : numpy.ndarray
                        Impedance (float 2-d matrix)

        Return
        ------
        dict
            key : str
                Mode (car/transit/bike/walk)
            value : dict
                key : str
                    Type (time/cost/dist)
                value : numpy 2-d matrix
                    Impedance (float 2-d matrix)
        """
        rows = self.bounds
        cols = self.dest_interval
        day_imp = defaultdict(lambda: defaultdict(float))
        for mode in self.impedance_share:
            share_sum = 0
            ass_class = mode_impedance[mode]
            for time_period in self.impedance_share[mode]:
                for mtx_type in impedance[time_period]:
                    if ass_class in impedance[time_period][mtx_type]:
                        imp = impedance[time_period][mtx_type][ass_class]
                        share = self.impedance_share[mode][time_period]
                        share_sum += sum(share)
                        day_imp[mode][mtx_type] += share[0] * imp[rows, cols]
                        day_imp[mode][mtx_type] += share[1] * imp[cols, rows].T
            if mode in day_imp and abs(share_sum/len(day_imp[mode]) - 2) > 0.001:
                raise ValueError(f"False impedance shares: {self.name} : {mode}")
        day_imp = {mode: dict(day_imp[mode]) for mode in day_imp}
        # Apply cost change to validate model elasticities
        if self.mtx_adjustment is not None:
            for t in self.mtx_adjustment:
                for m in self.mtx_adjustment[t]:
                    p = self.mtx_adjustment[t][m]
                    try:
                        # If `t` is one word (e.g., "time"),
                        # `los_component` is also that word.
                        # Then the calculation breaks down to
                        # `day_imp[m][t] *= p`, where `p` is the relative
                        # adjustment parameter.
                        # If t is "inv_time" for instance,
                        # `los_component` becomes "time".
                        los_component = t.split('_')[-1]
                        day_imp[m][los_component] += (p-1) * day_imp[m][t]
                        msg = (f"Purpose {self.name}: "
                            + f"Added {round(100*(p-1))} % to {t} : {m}.")
                        log.warn(msg)
                    except KeyError:
                        pass
        # Apply discounts and transformations to LOS matrices
        for mode in day_imp:
            for mtx_type in day_imp[mode]:
                if mtx_type == "cost":
                    try:
                        day_imp[mode][mtx_type] *= cost.cost_discount[self.name][mode]
                    except KeyError:
                        pass
                if mtx_type == "time" and "car" in mode and not self.name == "hb_abroad_other":
                    day_imp[mode][mtx_type] += self.attraction_zone_data["avg_park_time"].values
                if mtx_type == "cost" and "car" in mode and not self.name == "hb_abroad_other":
                    try:
                        day_imp[mode][mtx_type] += (cost.activity_time[self.name] *
                                                    cost.share_paying[self.name] *
                                                    self.attraction_zone_data["avg_park_cost"].values)
                    except KeyError:
                        pass
                if mtx_type == "cost" and mode == "car_drv":
                    try:
                        day_imp[mode][mtx_type] *= (1 - cost.sharing_factor[self.name] *
                                                    (cost.car_drv_occupancy[self.name] - 1) /
                                                    cost.car_drv_occupancy[self.name])
                    except KeyError:
                        pass
                if mtx_type == "cost" and mode == "car_pax":
                    try:
                        day_imp[mode][mtx_type] *= (cost.sharing_factor[self.name] /
                                                    cost.car_pax_occupancy[self.name])
                    except KeyError:
                        pass
            if "vrk" in self.impedance_share[mode] and mode != "walk":
                vot = cost.value_of_time[mode_impedance[mode]]
                day_imp[mode]["gen_cost"] = (day_imp[mode].pop("cost")
                                             + vot*day_imp[mode].pop("time")/60)
                log.info(f"Generalized cost calculated for {self.name} {mode}.")
            if mode in mixed_mode_classes:
                day_imp[mode]["park_cost"] = (day_imp[mode]["park_cost"]
                                              * cost.tour_duration[mode][self.name]
                                              / cost.tour_duration[mode]["avg"])
        return day_imp

def new_tour_purpose(*args):
    """Create purpose for two-way tour or for secondary destination of tour.

    Parameters
    ----------
    specification : dict
        "name" : str
            Tour purpose name (hw/oo/hop/sop/...)
        "orig" : str
            Origin of the tours (home/source)
        "dest" : str
            Destination of the tours (work/other/source/...)
        "generation_area" : str
            Model area (domestic/foreign)
        "struct" : str
            Model structure (dest>mode/mode>dest)
        "impedance_share" : dict
            Impedance shares
        "impedance_transform" : dict
            Impedance transformations
        "destination_choice" : dict
            Destionation choice parameters
        "mode_choice" dict
            Mode choice parameters
    zone_data : ZoneData
        Data used for all demand calculations
    resultdata : ResultData
        Writer object for result directory
    mtx_adjustment : dict (optional)
        Dict of matrix adjustments for testing elasticities
    """
    specification = args[0]
    attempt_calibration(specification)
    if "sec_dest" in specification:
        purpose = SecDestPurpose(*args)
    elif specification["name"] == "hb_abroad_other":
        purpose = ForeignExternalPurpose(*args)
    elif (specification["dest"] == "source"
          or specification["name"] == "oop"):
        purpose = SimpleTourPurpose(*args)
    else:
        purpose = TourPurpose(*args)
    try:
        purpose.sources = specification["source"]
    except KeyError:
        pass
    return purpose


class TourPurpose(Purpose):
    """Standard two-way tour purpose.

    Parameters
    ----------
    specification : dict
        See `new_tour_purpose()`
    zone_datas : Dict
        key : str
            Model area (domestic/foreign)
        val : ZoneData
            Data used for all demand calculations
    resultdata : ResultData
        Writer object for result directory
    mtx_adjustment : dict (optional)
        Dict of matrix adjustments for testing elasticities
    """

    def __init__(self, specification, zone_datas, resultdata, mtx_adjustment):
        Purpose.__init__(
            self, specification, zone_datas, resultdata, mtx_adjustment)
        if (self.orig == "home" and 
            specification["gen_model"] == "rate"):
            self.gen_model = generation.GenerationModel(
                self, resultdata, specification["generation"])
        elif (self.orig == "source" and 
              specification["gen_model"] == "rate"):
            self.gen_model = generation.NonHomeGeneration(
                self, resultdata, specification["generation"])
        elif (self.orig == "home" and 
              specification["gen_model"] == "logit"):
            self.gen_model = generation.LogitTourGeneration(
                self, specification["generation"], self.generation_zone_data,
                self.bounds, resultdata)
        else:
            log.error(f"Tour generation model not defined for {self.name}")
        args = (self, specification, self.generation_zone_data,
                self.attraction_zone_data, resultdata)
        if specification["struct"] == "mode>dest":
            self.model = logit.ModeDestModel(*args)
        elif specification["struct"] == "dest>mode":
            self.model = logit.DestModeModel(*args)
        else:
            log.error(f"Unknown struct in {self.name} parameters.")
        for mode in self.impedance_share:
            if mode not in self.demand_share:
                self.demand_share[mode] = self.impedance_share[mode]
        self.modes = list(self.model.mode_choice_param)
        self.intermodals = {key: intermodals[key] for key in self.modes if key in intermodals}
        self.connection_models: Dict[str, logit.LogitModel] = {}
        if "access_mode_choice" in specification:
            for mode in self.intermodals:
                self.modes += self.intermodals[mode]
                new_spec = copy(specification)
                new_spec["mode_choice"] = new_spec["access_mode_choice"][mode]
                self.connection_models[mode] = logit.LogitModel(
                    self, new_spec, self.generation_zone_data,
                    self.attraction_zone_data, resultdata)
        self.histograms = {mode: TourLengthHistogram(self.name)
            for mode in self.modes}
        self.orig_mappings = self.generation_zone_data.result_aggs.mappings
        self.dest_mappings = self.attraction_zone_data.result_aggs.mappings
        self.aggregates = {name: {} for name in self.dest_mappings}
        self.within_zone_tours = {}
        self.sec_dest_purpose: SecDestPurpose = None

    @property
    def dist(self):
        return ZoneData.beeline_dist[self.bounds, self.dest_interval]
    
    @property
    def generated_tours_all(self):
        return pandas.Series(
            sum(self.generated_tours.values()), self.orig_zone_numbers)
    
    @property
    def generated_dist_all(self):
        return pandas.Series(
            sum(self.generated_distance.values()), self.orig_zone_numbers)
    
    @property
    def attracted_dist_all(self):
        return pandas.Series(
            sum(self.attracted_distance.values()), self.dest_zone_numbers)

    @property
    def attracted_tours_all(self):
        return pandas.Series(
            sum(self.attracted_tours.values()), self.dest_zone_numbers)
    
    @property
    def generation_mode_shares(self):
        idx = self.generation_zone_data.is_in_submodel
        shares = {mode: (self.generated_tours[mode][idx].sum()
                          / self.generated_tours_all[idx].sum())
            for mode in self.modes}
        return pandas.concat({self.name: pandas.Series(shares, name="mode_share")},
                             names=["purpose", "mode"])
    
    @property
    def tour_lengths(self):
        lengths = {mode: self.histograms[mode].histogram for mode in self.histograms}
        return pandas.concat(lengths, names=["mode", "purpose", "interval"])

    def init_sums(self):
        for name in self.aggregates:
            orig_agg = self.orig_mappings[name].drop_duplicates()
            dest_agg = self.dest_mappings[name].drop_duplicates()
            for mode in self.modes:
                self.aggregates[name][mode] = pandas.DataFrame(
                    0, orig_agg, dest_agg)
        for mode in self.modes:
            self.generated_tours[mode] = numpy.zeros_like(self.orig_zone_numbers)
            self.attracted_tours[mode] = numpy.zeros_like(self.dest_zone_numbers)
            self.histograms[mode].__init__(self.name)
            self.within_zone_tours[mode] = pandas.Series(
                0, self.dest_zone_numbers, name="{}_{}".format(self.name, mode))

    def calc_soft_mode_prob(self, impedance):
        """Calculate walk and bike utilities.

        Parameters
        ----------
        impedance : dict
            Time period (aht/pt/iht/it) : dict
                Type (time/dist) : dict
                    Mode (bike/walk) : numpy.ndarray
        """
        purpose_impedance = self.transform_impedance(impedance)
        self.model.calc_soft_mode_exps(purpose_impedance)

    def calc_prob(self, impedance, is_last_iteration):
        """Calculate mode and destination probabilities.
        
        Parameters
        ----------
        impedance : dict
            Time period (aht/pt/iht/it) : dict
                Type (time/cost/dist) : dict
                    Mode (car/transit/bike/...) : numpy.ndarray
        is_last_iteration : bool
            Whether to calclulate and store accessibility indicators

        Returns
        -------
        dict
            Mode (car/transit/bike/walk) : numpy 2-d matrix
                Choice probabilities
        """
        purpose_impedance = self.transform_impedance(impedance)

        #If the trip is long-distance, calculate unimodal/intermodal
        # probability split for each main mode
        if "vrk" in impedance:
            acc_splits = {}
            matrixdata = MatrixData(self.resultdata.path / "Matrices")
            with matrixdata.open(
                    f"logsum_{self.name}", "vrk", list(self.orig_zone_numbers), m='w'
                    ) as mtx:
                for main_mode, acc_modes in self.intermodals.items():
                    mode_impedance = {mode: purpose_impedance.pop(mode)
                        for mode in [main_mode] + acc_modes}
                    acc_splits[main_mode], logsum = self.split_connection_mode(
                        mode_impedance, main_mode)
                    purpose_impedance[main_mode] = {"logsum": logsum}
                    mtx[main_mode] = logsum

        # Calculate main mode probability after access mode probability
        # to have access mode logsum as variable
        prob = self.model.calc_prob(purpose_impedance, is_last_iteration)
        log.info(f"Mode and dest probabilities calculated for {self.name}")

        # If the trip is long-distance, calculate joint main mode/access
        # mode probability for each intermodal class in EMME assignment
        if "vrk" in impedance:
            for main_mode, split in acc_splits.items():
                main_prob = prob[main_mode]
                for acc_mode in split:
                    prob[acc_mode] = split[acc_mode] * main_prob
        return prob

    def split_connection_mode(self, impedance, pt_mode):
        if pt_mode == "airplane":
            impedance["airpl_taxi_acc"] = impedance["airpl_car_acc"]
        model = self.connection_models[pt_mode]
        prob, logsum = model.calc_mode_prob(impedance)
        if "airpl_taxi_acc" in prob:
            prob["airpl_car_acc"] += prob.pop("airpl_taxi_acc")
        return prob, logsum


    def calc_basic_prob(self, impedance, is_last_iteration):
        """Calculate mode and destination probabilities.

        Individual dummy variables are not included.
        In `SimpleTourPurpose`, this method is used for calculating demand,
        but here it returns an empty list.

        Parameters
        ----------
        impedance : dict
            Time period (aht/pt/iht/it) : dict
                Type (time/cost/dist) : dict
                    Mode (car/transit/bike/...) : numpy.ndarray

        Returns
        -------
        list
            Empty list
        """
        purpose_impedance = self.transform_impedance(impedance)
        self.model.calc_basic_prob(
            purpose_impedance, is_last_iteration and self.name[0] != 's')
        log.info(f"Mode and dest probabilities calculated for {self.name}")
        return []

    def calc_demand(
            self, impedance, is_last_iteration: bool) -> Iterator[Demand]:
        """Calculate purpose specific demand matrices.

        Parameters
        ----------
        impedance : dict
            Time period (aht/pt/iht/it) : dict
                Type (time/cost/dist) : dict
                    Mode (car/transit/bike/...) : numpy.ndarray
        is_last_iteration : bool
            Whether to calculate and store accessibility indicators

        Yields
        -------
        Demand
                Mode-specific demand matrix for whole day
        """
        self.gen_model.add_tours()
        prob = self.calc_prob(impedance, is_last_iteration)
        tours = self.gen_model.get_tours()
        orig_agg = self.generation_zone_data.result_aggs
        dest_agg = self.attraction_zone_data.result_aggs
        for mode in self.modes:
            mtx = (prob.pop(mode) * tours).T
            try:
                self.sec_dest_purpose.gen_model.add_secondary_tours(
                    mtx, mode, self)
            except AttributeError:
                pass
            self.attracted_tours[mode] = mtx.sum(0)
            self.generated_tours[mode] = mtx.sum(1)
            self.attracted_distance[mode] = (self.dist*mtx).sum(0)
            self.generated_distance[mode] = (self.dist*mtx).sum(1)
            self.histograms[mode].count_tour_dists(mtx, self.dist)
            for mapping in self.aggregates:
                df = pandas.DataFrame(
                    mtx, self.orig_zone_numbers, self.dest_zone_numbers)
                df = orig_agg.aggregate_array(df, mapping).T
                df = dest_agg.aggregate_array(df, mapping).T
                self.aggregates[mapping][mode] = df
            self.within_zone_tours[mode] = pandas.Series(
                numpy.diag(mtx), self.dest_zone_numbers,
                name="{}_{}".format(self.name, mode))
            if self.dest != "source":
                yield Demand(self, mode, mtx)
        log.info(f"Demand calculated for {self.name}")


class SimpleTourPurpose(TourPurpose):
    """Purpose for simplified demand calculation, not part of agent model."""

    def calc_basic_prob(self, impedance, is_last_iteration) -> Iterator[Demand]:
        """Calculate purpose specific demand matrices.

        Yields
        -------
        Demand
                Mode-specific demand matrix for whole day
        """
        return self.calc_demand(impedance, is_last_iteration)


class SecDestPurpose(Purpose):
    """Purpose for secondary destination of tour.

    Parameters
    ----------
    specification : dict
        See `new_tour_purpose()`
    zone_data : ZoneData
        Data used for all demand calculations
    resultdata : ResultData
        Writer object to result directory
    mtx_adjustment : dict (optional)
        Dict of matrix adjustments for testing elasticities
    """

    def __init__(self, specification, zone_data, resultdata, mtx_adjustment):
        args = (self, specification, zone_data, resultdata)
        Purpose.__init__(*args, mtx_adjustment)
        self.gen_model = generation.SecDestGeneration(
            self, resultdata, specification["generation"])
        self.model = logit.SecDestModel(*args)
        self.modes = list(self.model.dest_choice_param)
        for mode in self.demand_share:
            self.demand_share[mode]["vrk"] = [[0.5, 0.5], [0.5, 0.5]]

    def _init_sums(self):
        for mode in self.model.dest_choice_param:
            self.generated_tours[mode] = numpy.zeros_like(self.orig_zone_numbers)
        for purpose in self.gen_model.param:
            for mode in self.gen_model.param[purpose]:
                self.attracted_tours[mode] = numpy.zeros_like(
                    self.attraction_zone_data.zone_numbers, float)

    def calc_basic_prob(self, *args):
        self._init_sums()

    def calc_prob(self, impedance, is_last_iteration):
        self.gen_model.init_tours()
        return self.transform_impedance(impedance)

    def generate_tours(self):
        """Generate the source tours without secondary destinations."""
        self.gen_model.init_tours()
        self.tours = {}
        self._init_sums()
        for mode in self.model.dest_choice_param:
            self.tours[mode] = self.gen_model.get_tours(mode)

    def distribute_tours(self, mode, impedance, orig, orig_offset=0):
        """Decide the secondary destinations for all tours (generated 
        earlier) starting from one specific zone.
        
        Parameters
        ----------
        mode : str
            Mode (car/transit/bike)
        impedance : dict
            Type (time/cost/dist) : numpy 2d matrix
        orig : int
            The relative zone index from which these tours origin
        orig_offset : int (optional)
            Absolute zone index of orig is orig_offset + orig

        Returns
        -------
        Demand
            Matrix of destination -> secondary_destination pairs
            The origin zone for all of these tours
        """
        generation = self.tours[mode][orig, :]
        # All o-d pairs below threshold are neglected,
        # total demand is increased for other pairs.
        dests = generation > param.secondary_destination_threshold
        if not dests.any():
            # If no o-d pairs have demand above threshold,
            # the sole destination with largest demand is picked
            dests = [generation.argmax()]
            generation.fill(0)
            generation[dests] = generation.sum()
        else:
            generation[dests] *= generation.sum() / generation[dests].sum()
            generation[~dests] = 0
        prob = self.calc_sec_dest_prob(mode, impedance, orig, dests)
        demand = numpy.zeros_like(impedance["time"])
        demand[dests, :] = (prob * generation[dests]).T
        self.attracted_tours[mode][self.bounds] += demand.sum(0)
        return Demand(self, mode, demand, orig_offset + orig)

    def calc_sec_dest_prob(self, mode, impedance, orig, dests):
        """Calculate secondary destination probabilites.
        
        For tours starting in specific zone and ending in some zones.
        
        Parameters
        ----------
        mode : str
            Mode (car/transit/bike)
        impedance : dict
            Type (time/cost/dist) : numpy 2d matrix
        orig : int
            Origin zone index
        dests : list or boolean array
            Destination zone indices

        Returns
        -------
        numpy.ndarray
            Probability matrix for chosing zones as secondary destination
        """
        dest_imp = {}
        for mtx_type in impedance:
            dest_imp[mtx_type] = (impedance[mtx_type][dests, :]
                                  + impedance[mtx_type][:, orig]
                                  - impedance[mtx_type][dests, orig][:, numpy.newaxis])
        return self.model.calc_prob(mode, dest_imp, orig, dests)

    def print_data(self):
        self.resultdata.print_data(
            pandas.Series(
                sum(self.attracted_tours.values()),
                self.dest_zone_numbers, name=self.name),
            "attraction.txt")

class FreightPurpose(Purpose):
    """Standard purpose for handling freight calculations.

    Parameters
    ----------
    specification : dict
        Model parameter specifications
    zone_data : Dict[str, FreightZoneData]
        Model area (domestic/foreign) : Data used for all demand calculations
    resultdata : ResultData
        Writer object to result directory
    costdata : Dict[str, dict]
        Freight mode (truck/freight_train/ship) : mode
            Mode (truck/trailer_truck...) : unit cost name
                unit cost name : unit cost value
    """
    def __init__(self, specification, zone_data, resultdata, costdata):
        Purpose.__init__(self, specification, zone_data, resultdata)
        self.costdata = costdata
        self.model_category = list(zone_data)[0]
        self.modes: List[str] = list(specification["mode_choice"])
        args = (self, specification, self.generation_zone_data,
                self.attraction_zone_data, resultdata)
        if specification["struct"] == "dest>mode":
            self.model = logit.DestModeModel(*args)
        elif specification["struct"] == "mode>dest":
            self.model = logit.ModeDestModel(*args)
        else:
            self.model = None
        self.route_params = specification.get("route_choice", None)
        self.is_export = {"export": True, "import": False}.get(specification["struct"])

        if (self.model is None and self.model_category == "domestic"
            or self.is_export is None and self.model_category == "foreign"):
            msg = f"Purpose {self.name} has invalid struct in specification"
            log.error(msg)
            raise ValueError(msg)
        
        elif self.route_params is None and self.model_category == "foreign":
            msg = f"Purpose {self.name} is missing route choice specification"
            log.error(msg)
            raise ValueError(msg)

    def calc_traffic(self, impedance: dict):                                                                                    
        """Calculate freight traffic matrix.

        Parameters
        ----------
        impedance : dict
            Mode (truck/train/...) : dict
                Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix

        Return
        ------
        dict
            Mode (truck/train/...) : calculated demand (numpy 2d matrix)
        """
        costs = self.get_costs(impedance)
        self.dist = costs["truck"]["cost"]
        nr_zones = self.attraction_zone_data.nr_zones
        probs = self.model.calc_prob(costs)
        generation = numpy.tile(self.generation_zone_data[f"gen_{self.name}"], (nr_zones, 1))
        demand = {mode: (probs.pop(mode) * generation).T for mode in self.modes}
        return demand

    def form_impedance_legs(self, impedance: dict,
                            ship_imps: dict,
                            fin_border_ids: dict,
                            cluster_border_ids: dict) -> dict:
        """Forms impedance matrices for the three legs of foreign trade 
        route choice model. 

        Parameters
        ----------
        impedance : dict
            Mode (truck/train/...) : dict
                Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix
        ship_imps : dict
            Mode (container_ship/general_cargo...) : attribute
                Type (dist/frequency) : numpy.ndarray
        fin_border_ids : dict
            Finland border id (FIHEL/FISKV...) : str
                Centroid id : int
        cluster_border_ids : dict
            Foreign border id (AEJEA/SESTO...) : str
                Centroid id : int

        Returns
        -------
        dict
            Name of a leg (leg_one/...) : dict
                Mode (truck/train/marine ships) : dict
                    Type (cost/frequency/draught) : mask indexed numpy 2d matrix
        """
        fin_port_zones = numpy.array(
            list(fin_border_ids.values()), dtype=numpy.int32)
        cluster_port_zones = numpy.array(
            list(cluster_border_ids.values()), dtype=numpy.int32)
        all_zones = self.generation_zone_data.all_zone_numbers
        fin_borders = numpy.isin(all_zones, fin_port_zones)
        cluster_borders = numpy.isin(all_zones, cluster_port_zones)
        fin_zones = numpy.isin(all_zones, numpy.union1d(self.orig_zone_numbers, 
                                                        fin_port_zones))
        cluster_zones = ~fin_zones & ~cluster_borders
        
        masks = (fin_zones, fin_borders, cluster_borders, cluster_zones)
        if not self.is_export:
            masks = masks[::-1]

        costs = self.get_costs(impedance)
        impedance_legs = {l: {} for l in leg_names}
        for i, imp_leg in enumerate(impedance_legs.values()):
            imp_leg["truck"] = {imp_type: mtx[numpy.ix_(masks[i], masks[i+1])]
                                for imp_type, mtx in costs["truck"].items()}
        ship_costs = get_foreign_ship_cost(
            self.costdata, ship_imps, self.model_category, fin_border_ids,
            self.is_export)
        impedance_legs["leg_two"].update(ship_costs)

        # Retain leg two truck cost only for designated land border pairs
        mask = pandas.DataFrame(True, index=fin_port_zones, columns=cluster_port_zones)
        for fin_border, cluster_border in param.land_border_pairs.values():
            if fin_border in fin_port_zones and cluster_border in cluster_port_zones:
                mask.at[fin_border, cluster_border] = False
        if not self.is_export:
            mask = mask.T
        impedance_legs["leg_two"]["truck"]["cost"][mask.to_numpy()] = numpy.inf
        return impedance_legs

    def get_costs(self, impedance: dict):
        """Fetches calculated costs for each mode in model's mode choice.

        Parameters
        ----------
        impedance : dict 
            Mode (truck/train/...) : dict
                Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix

        Returns
        -------
        dict
            Mode (truck/freight_train/...) : cost : numpy.ndarray
        """
        return {mode: {"cost": calc_cost(mode, self.costdata, impedance[mode],
                                         self.model_category)}
                for mode in self.modes}

    def calc_vehicles(self, matrix: numpy.ndarray, ass_class: str):
        """Calculate vehicle matrix from ton matrix using ton-to-vehicles 
        conversion values.

        Parameters
        ----------
        matrix : numpy.ndarray
            ton matrix
        ass_class : str
            truck assignment class

        Returns
        -------
        numpy.ndarray
            vehicle matrix
        """
        costdata = self.costdata["truck"][ass_class]
        vehicles = (matrix * costdata[f"{self.model_category}_distribution"] 
                    / costdata["avg_load"] / 365)
        vehicles += vehicles.T * costdata["empty_share"]
        return vehicles

    def calc_trade_mode_share(self, dom_demand: dict, trade_demand: dict,
                              fin_borders: list):
        """Calculate mode share of trade demand on its domestic leg 
        among freight land mode alternatives.

        Parameters
        ----------
        dom_demand : dict
            Mode (truck/train/...) : domestic demand numpy 2d array
        trade_demand : dict
            Foreign purpose name : str
                Leg (one/two/three) : str
                    Mode (truck/container_ship...) : trade demand numpy 2d array
        fin_borders : list[int]
            Finnish border centroid ids

        Returns
        -------
        dict
            Foreign purpose name : str
                Mode (truck/freight_train) : trade demand domestic leg numpy 2d array
        """
        demand_sum = sum(dom_demand[mode] for mode in dom_demand
                         if mode in ["truck", "freight_train"])
        truck_share = numpy.zeros_like(demand_sum)
        numpy.divide(dom_demand["truck"], demand_sum, out=truck_share,
                     where=demand_sum > 0.0)
        train_share = numpy.ones_like(truck_share) - truck_share
        
        # Extracts trade purposes with same name as self.name
        # e.g. if self is kemlaa, extracts kemlaa_export and kemlaa_import
        purpose_trade_demand = {
            k: v for k, v in trade_demand.items()
            if k.startswith(f"{self.name}_")
        }
        
        dom_leg_demand = {}
        for purpose in purpose_trade_demand:
            demand_full = pandas.DataFrame(
                0, index=self.orig_zone_numbers, columns=self.orig_zone_numbers,
                dtype=numpy.float32
            )
            if purpose.endswith("_export"):
                demand_full.loc[:, fin_borders] = purpose_trade_demand[purpose]["leg_one"]["truck"]
            else:
                demand_full.loc[fin_borders, :] = purpose_trade_demand[purpose]["leg_three"]["truck"]
            dom_leg_demand[purpose] = {"truck": demand_full.values * truck_share}
            train_demand = demand_full.values * train_share
            if numpy.sum(train_demand) > 0.0:
                dom_leg_demand[purpose]["freight_train"] = train_demand
        return dom_leg_demand

    def run_logistics_module(self, demand_truck: numpy.ndarray, impedance: numpy.ndarray, 
                             zone_index_map: dict, iterations: int) -> tuple:
        """Entry point for running logistics module for truck demand within Finland

        Parameters
        ----------
        demand_truck : numpy.ndarray
            Modelled truck demand for purpose
        impedance : dict
            Mode (truck/train/...) : dict
                Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix
        zone_index_map : dict 
            zone id number : index
        iterations : int
            Number of times logistics module is run

        Returns
        -------
        Tuple[np.ndarray]
            Routed truck demand, and totals for detoured and direct demand
        """
        try:
            lcs_areas = self.generation_zone_data[f"lc_area_{self.name}"]
        except KeyError:
            lcs_areas = self.generation_zone_data["lc_area"]
        lc_sizes = lcs_areas[lcs_areas > 0]
        lc_indices = numpy.array([zone_index_map.get(id, None) 
                                for id in list(lc_sizes.index)])
        lc_sizes = lc_sizes.to_numpy()
        cost = self.get_costs(impedance)
        model = LogisticsModule(cost, self.route_params, lc_indices, lc_sizes)
        for i in range(1, iterations + 1):
            demand_truck, per_route = run_logistics_model(model, demand_truck, i)
        return demand_truck, per_route

    def run_trade_route_module(self, impedance: dict,
                               ship_imps: dict,
                               fin_border_ids: dict,
                               cluster_border_ids: dict,
                               trade_demand_path):
        """Entry point for running foreign trade route choice module. 
        
        Parameters
        ----------
        impedance : dict
            Mode (truck/train/...) : dict
                Type (time/dist/toll_cost/canal_cost) : numpy 2d matrix
        ship_imps : dict
            Mode (container_ship/general_cargo...) : attribute
                Type (dist/frequency) : numpy.ndarray
        fin_border_ids : dict
            Finland border id (FIHEL/FISKV...) : str
                Centroid id : int
        cluster_border_ids : dict
            Foreign border id (AEJEA/SESTO...) : str
                Centroid id : int
        trade_demand_path : Path
            argument path to trade demand omx-file

        Returns
        -------
        dict
            Leg name (one/two/three) : Mode
                Name (truck/container_ship...) : numpy 2d array
        """
        impedance_legs = self.form_impedance_legs(
            impedance, ship_imps, fin_border_ids, cluster_border_ids)
        demand, trade_mappings = read_omx_item(trade_demand_path, self.name)

        mapping_name = (self.generation_zone_data.mapping.name if self.is_export 
                        else self.attraction_zone_data.mapping.name)
        if mapping_name == "municipality_center":
            df = pandas.DataFrame(demand, trade_mappings["finland_zone_number"])
            demand = df.groupby(self.generation_zone_data.mapping).sum().to_numpy()
        demand = demand.T if not self.is_export else demand

        # Finland border control point key - zone index
        border_indices = {key: idx for idx, key in enumerate(fin_border_ids)}
        route_model = TradeRouteModule(impedance_legs, self.route_params, 
                                       border_indices, self.is_export)
        trade_demand = run_trade_model(route_model, demand)
        return trade_demand
    
class ForeignExternalPurpose(TourPurpose):
    """External two-way tour purpose.

    Parameters
    ----------
        See `new_tour_purpose()`
    zone_datas : Dict
        key : str
            Model area (domestic/foreign)
        val : ZoneData
            Data used for all demand calculations
    resultdata : ResultData
        Writer object for result directory
    mtx_adjustment : dict (optional)
        Dict of matrix adjustments for testing elasticities
    basematrices_path : Path
        Path to base matrices for calculating foreign external demand
    """

    def __init__(self, specification, zone_datas, resultdata, mtx_adjustment, basematrices_path):
        attempt_calibration(specification)
        TourPurpose.__init__(
            self, specification, zone_datas, resultdata, mtx_adjustment)
        self.tour_generation = specification["tour_generation"]
        self._zone_datas = zone_datas
        self.basematrices_path = basematrices_path
        self.fem = ForeignExternalModel(
            self, self._zone_datas, self._zone_datas, self.basematrices_path, self.generation_zone_data.all_zone_numbers)
    
    def calc_demand(
            self, impedance, is_last_iteration: bool) -> Iterator[Demand]:
        """Calculate purpose specific demand matrices.

        Parameters
        ----------
        impedance : dict
            Time period (aht/pt/iht/it) : dict
                Type (time/cost/dist) : dict
                    Mode (car/transit/bike/...) : numpy.ndarray
        is_last_iteration : bool
            Whether to calculate and store accessibility indicators

        Yields
        -------
        Demand
                Mode-specific demand matrix for whole day
        """
        for main_mode in self.intermodals:
            foreign_ext_mtx = self.fem.calc_foreign_external_traffic(main_mode)
            # Calculate probabilities for all access mode of the main mode
            access_mode_probs = self.calc_prob(impedance)[main_mode]
            # Access mode demand
            for access_mode in access_mode_probs:
                access_probs = access_mode_probs[access_mode].T
                access_mode_mtx = foreign_ext_mtx * access_probs
                yield Demand(self, access_mode, access_mode_mtx)
            log.info(f"Demand calculated for {self.name}")
    
    def calc_prob(self, impedance):
        """Calculate mode and destination probabilities.
        
        Parameters
        ----------
        impedance : dict
            Time period (aht/pt/iht/it) : dict
                Type (time/cost/dist) : dict
                    Mode (car/transit/bike/...) : numpy.ndarray
        is_last_iteration : bool
            Whether to calclulate and store accessibility indicators

        Returns
        -------
        dict
            Mode (car/transit/bike/walk) : numpy 2-d matrix
                Choice probabilities
        """
        purpose_impedance = self.transform_impedance(impedance)

        #If the trip is long-distance, calculate unimodal/intermodal
        # probability split for each main mode
        if "vrk" in impedance:
            acc_splits = {}
            matrixdata = MatrixData(self.resultdata.path / "Matrices")
            with matrixdata.open(
                    f"logsum_{self.name}", "vrk", list(self.orig_zone_numbers), m='w'
                    ) as mtx:
                for main_mode, acc_modes in self.intermodals.items():
                    mode_impedance = {mode: purpose_impedance.pop(mode)
                        for mode in [main_mode] + acc_modes}
                    acc_splits[main_mode], logsum = self.split_connection_mode(
                        mode_impedance, main_mode)
                    purpose_impedance[main_mode] = {"logsum": logsum}
                    mtx[main_mode] = logsum
        return acc_splits


