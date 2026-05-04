from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, cast
import numpy # type: ignore
import pandas
import copy
from collections import defaultdict
from utils.calibrate import attempt_calibration

if TYPE_CHECKING:
    from datahandling.resultdata import ResultsData
    from datahandling.zonedata import ZoneData
    from datatypes.purpose import TourPurpose

import utils.log


def log(a: numpy.ndarray):
    with numpy.errstate(divide="ignore"):
        return numpy.log(a)

def divide(a, b):
    return numpy.divide(a, b, out=numpy.zeros_like(a), where=b!=0)

class LogitModel:
    """Generic logit model with mode/destination choice.

    Parameters
    ----------
    purpose : TourPurpose
        Tour purpose (type of tour)
    parameters : dict
        See `datatypes.purpose.new_tour_purpose()`
    generation_zone_data : ZoneData
        Data used for generation calculations
    attraction_zone_data : ZoneData
        Data used for attraction calculations
    resultdata : ResultData
        Writer object to result directory
    """

    def __init__(self, 
                 purpose: TourPurpose,
                 parameters: dict,
                 generation_zone_data: ZoneData,
                 attraction_zone_data: ZoneData,
                 resultdata: ResultsData):
        self.resultdata = resultdata
        self.purpose = purpose
        self.generation_zone_data = generation_zone_data
        self.attraction_zone_data = attraction_zone_data
        self.dest_choice_param: Dict[str, Dict[str, Any]] = parameters["destination_choice"]
        self.mode_choice_param: Optional[Dict[str, Dict[str, Any]]] = parameters["mode_choice"]
        self.distance_boundary = parameters["distance_boundaries"]

    def calc_mode_prob(self, impedance: Dict[str, numpy.ndarray]):
        expsum, mode_exps = self._calc_mode_utils(impedance)
        impedance.clear()
        prob = {mode: divide(mode_exps.pop(mode), expsum).T
            for mode in self.mode_choice_param}
        return prob, log(expsum)

    def _calc_alt_util(self, mode: str, utility: numpy.ndarray,
                       impedance: Dict[str, numpy.ndarray],
                       b: Dict[str, Dict[str, float]]):
        self._add_zone_util(utility, b["attraction"])
        self._add_impedance(utility, impedance, b["impedance"])
        if "transform" in b:
            b_transf = b["transform"]
            transimp = numpy.zeros_like(utility)
            self._add_zone_util(transimp, b_transf["attraction"])
            self._add_impedance(transimp, impedance, b_transf["impedance"])
            impedance["transform"] = transimp
        self._add_log_impedance(utility, impedance, b["log"])
        exps = numpy.exp(utility)
        dist = self.purpose.dist
        if mode != "logsum" and dist.shape == exps.shape:
            # If this is the lower level in nested model
            l, u = self.distance_boundary[mode]
            exps[(dist < l) | (dist >= u)] = 0
        return exps

    def _calc_mode_util(self, mode: str, impedance: Dict[str, numpy.ndarray],
                        dummy: Optional[str] = None):
        b = self.mode_choice_param[mode]
        utility = numpy.zeros_like(next(iter(impedance.values())))
        utility += b["constant"]
        if dummy in b["individual_dummy"]:
            utility += b["individual_dummy"][dummy]
        utility = self._add_zone_util(
            utility.T, b["generation"], generation=True).T
        exps = self._calc_alt_util(mode, utility, impedance, b)
        return exps

    def _calc_mode_utils(self, impedance: Dict[str, Dict[str, numpy.ndarray]],
                         dummy: Optional[str] = None):
        mode_exps: Dict[str, numpy.ndarray] = {}
        for mode in self.mode_choice_param:
            mode_exps[mode] = self._calc_mode_util(mode, impedance[mode], dummy)
        expsum: numpy.ndarray = sum(mode_exps.values())
        return expsum, mode_exps

    def _calc_dest_util(self, mode: str, impedance: dict) -> numpy.ndarray:
        b = self.dest_choice_param[mode]
        b["attraction"][f"municipality_calibration_{mode}"] = 1.0
        utility = numpy.zeros_like(next(iter(impedance.values())))
        impedance["attraction_size"] = self._add_zone_util(
            numpy.zeros_like(utility), b["attraction_size"])
        dest_exp = self._calc_alt_util(mode, utility, impedance, b)
        return dest_exp
    
    def _calc_sec_dest_util(self, mode, impedance, orig, dest):
        b = self.dest_choice_param[mode]
        utility = numpy.zeros_like(next(iter(impedance.values())))
        self._add_sec_zone_util(utility, b["attraction"], orig, dest)
        self._add_impedance(utility, impedance, b["impedance"])
        dest_exps = numpy.exp(utility)
        size = numpy.zeros_like(utility)
        self._add_sec_zone_util(size, b["attraction_size"])
        impedance["attraction_size"] = size
        self._add_log_impedance(dest_exps, impedance, b["log"])
        if mode != "logsum":
            l, u = self.distance_boundary[mode]
            dest_exps[(impedance["dist"] < l) | (impedance["dist"] >= u)] = 0
        return dest_exps

    def _add_impedance(self, utility, impedance, b):
        """Adds simple linear impedances to utility.
        
        Parameters
        ----------
        utility : ndarray
            Numpy array to which the impedances will be added
        impedance : dict
            A dictionary of time-averaged impedance matrices. Includes keys
            `time`, `cost`, and `dist` of which values are all ndarrays.
        b : dict
            The parameters for different impedance matrices.
        """
        for i in b:
            utility += b[i] * impedance[i]
        return utility

    def _add_log_impedance(self, utility, impedance, b):
        """Adds log transformations of impedance to utility.

        Parameters
        ----------
        exps : ndarray
            Numpy array to which the impedances will be multiplied
        impedance : dict
            A dictionary of time-averaged impedance matrices. Includes keys
            `time`, `cost`, and `dist` of which values are all ndarrays.
        b : dict
            The parameters for different impedance matrices
        """
        for i in b:
            imp = impedance[i] + 1 if b[i] < 0 else impedance[i]
            utility += b[i] * log(imp)
        return utility

    def _add_zone_util(self, utility, b, generation=False):
        """Adds simple linear zone terms to utility.
        
        Parameters
        ----------
        utility : ndarray
            Numpy array to which the impedances will be added
        b : dict
            The parameters for different zone data.
        generation : bool
            Whether the effect of the zone term is added only to the
            geographical area in which this model is used based on the
            `self.bounds` attribute of this class.
        """
        zdata = (self.generation_zone_data if generation
                 else self.attraction_zone_data)
        for i in b:
            utility += b[i] * numpy.asarray(zdata[i])
        return utility
    
    def _add_sec_zone_util(self, utility, b):
        for i in b:
            utility += b[i] * numpy.asarray(self.generation_zone_data[i])
        return utility

    def _add_log_zone_util(self, exps, b, generation=False):
        """Adds log transformations of zone data to utility.
        
        This is an optimized way of calculating log terms. Calculates
        zonedata1^b1 * ... * zonedataN^bN in the following equation:
        e^(linear_terms + b1*log(zonedata1) + ... + bN*log(zonedataN))
        = e^(linear_terms) * zonedata1^b1 * ... * zonedataN^bN

        Parameters
        ----------
        utility : ndarray
            Numpy array to which the impedances will be added
        b : dict
            The parameters for different zone data.
        generation : bool
            Whether the effect of the zone term is added only to the
            geographical area in which this model is used based on the
            `self.bounds` attribute of this class.
        """
        zdata = (self.generation_zone_data if generation
                 else self.attraction_zone_data)
        for i in b:
            exps *= numpy.power(
                numpy.asarray(zdata[i]) + 1, b[i])
        return exps


class ModeDestModel(LogitModel):
    """Nested logit model with mode choice in upper level.

    Uses logsums from destination choice model as utility
    in mode choice model.

         choice
        /     \\
      m1        m2
     / \\      / \\
    d1   d2   d1   d2

    Parameters
    ----------
    purpose : TourPurpose
        Tour purpose (type of tour)
    parameters : dict
        See `datatypes.purpose.new_tour_purpose()`
    zone_data : ZoneData
        Data used for all demand calculations
    resultdata : ResultData
        Writer object to result directory
    """
    def __init__(self, *args, **kwargs):
        LogitModel.__init__(self, *args, **kwargs)
        try:
            b = self.dest_choice_param["car"]["impedance"]["cost"]
        except KeyError:
            # School tours do not have a constant cost parameter
            # Use value of time conversion from CBA guidelines instead
            b = -0.46738697
        try:
            # Convert utility into euros
            money_utility = 1 / b
        except TypeError:
            # Separate sub-region parameters
            money_utility = 1 / b[0]
        money_utility /= next(iter(self.mode_choice_param.values()))["log"]["logsum"]
        self.money_utility: float = money_utility

    def calc_soft_mode_exps(self, impedance: dict):
        """Calculate utility exponentials for walk and bike.

        The exponentials will be used for mode choice at a later stage.

        Parameters
        ----------
        impedance : dict
            Mode (bike/walk) : dict
                Type (time/cost/dist) : numpy 2-d matrix
                    Impedances
        """
        self.soft_mode_exps, _, _, = self._calc_exps(impedance)

    def calc_soft_mode_prob(self, impedance: dict) -> dict:
        """Calculate matrix of walk and bike choice probabilities.

        Parameters
        ----------
        impedance : dict
            Mode (bike/walk) : dict
                Type (time/cost/dist) : numpy 2-d matrix
                    Impedances

        Returns
        -------
        dict
            Mode (bike/walk) : numpy 2-d matrix
                Choice probabilities
        """
        probs = {}
        for mode in list(impedance):
            dest_exps = self._calc_dest_util(mode, impedance.pop(mode))
            try:
                expsum = dest_exps.sum(1)
            except ValueError:
                expsum = dest_exps.sum()
            dest_prob = divide(dest_exps.T, expsum)
            probs[mode] = sum(self.soft_mode_probs[mode]) * dest_prob
        return probs

    def calc_prob(self, impedance: dict, calc_accessibility=False) -> dict:
        """Calculate matrix of choice probabilities.

        First calculates basic probabilities. Then inserts individual
        dummy variables by calling `calc_individual_prob()`.

        If model for non-home-based tours has individual dummy variables
        representing parent tour mode choice, None will be returned,
        because it requires parent tour demand to be calculated first.
        In this case, `calc_prob_again` will be called later.

        Parameters
        ----------
        impedance : dict
            Mode (car/transit/bike/walk) : dict
                Type (time/cost/dist) : numpy 2-d matrix
                    Impedances
        calc_accessibility : bool (optional)
            Whether to calclulate and store accessibility indicators

        Returns
        -------
        dict
            Mode (car/transit/bike/walk) : numpy 2-d matrix
                Choice probabilities
        """
        mode_exps, mode_expsum, dest_exps, dest_expsums = self._calc_utils(
            impedance)
        if calc_accessibility:
            self._calc_accessibility(mode_exps, mode_expsum)
        mode_probs = self._calc_mode_prob(mode_exps, mode_expsum)
        if mode_probs is None:
            self._stashed_exps += [dest_exps, dest_expsums]
            return None
        else:
            try:
                self.soft_mode_probs = {
                    mode: mode_probs[mode] for mode in self.soft_mode_exps}
            except AttributeError:
                pass
            return self._calc_prob(mode_probs, dest_exps, dest_expsums)

    def calc_prob_again(self) -> dict:
        """Return matrix of choice probabilities.

        First recovers basic probabilities. Then inserts individual
        dummy variables by calling `calc_individual_prob()`.

        Returns
        -------
        dict
            Mode (car/transit/bike/walk) : numpy 2-d matrix
                Choice probabilities
        """
        mode_exps, mode_expsum, dest_exps, dest_expsums = self._stashed_exps
        del self._stashed_exps
        mode_probs = self._calc_mode_prob(mode_exps, mode_expsum)
        try:
            self.soft_mode_probs = {
                mode: mode_probs[mode] for mode in self.soft_mode_exps}
        except AttributeError:
            pass
        return self._calc_prob(mode_probs, dest_exps, dest_expsums)

    def _calc_individual_prob(self, mod_modes: list[str], dummy: str,
                              mode_exps: Dict[str, numpy.ndarray]):
        """Calculate utilities with individual dummies included.

        Parameters
        ----------
        mod_modes : str
            The modes for which the utility will be modified
        dummy : str
            The name of the individual dummy
        mode_exps : dict
            key : str
                Mode
            value : numpy.ndarray
                Utility exponentials to modify
        Returns
        -------
        dict
            key : str
                Mode
            value : numpy.ndarray
                Modified utility exponentials
        """
        mode_exps2 = copy.deepcopy(mode_exps)
        for mod_mode in mod_modes:
            b = self.mode_choice_param[mod_mode]["individual_dummy"][dummy]
            mode_exps2[mod_mode] *= numpy.exp(b)
        return mode_exps2

    def _calc_utils(self,
                    impedance: Dict[str, Dict[str, Dict[str, numpy.ndarray]]]):
        mode_exps, dest_exps, dest_expsums = self._calc_exps(impedance)
        try:
            for mode in self.soft_mode_exps:
                mode_exps[mode] = self.soft_mode_exps[mode]
        except AttributeError:
            pass
        mode_expsum: numpy.ndarray = sum(mode_exps.values())
        logsum = pandas.Series(
            log(mode_expsum), self.purpose.orig_zone_numbers,
            name=self.purpose.name)
        self.generation_zone_data._values[self.purpose.name] = logsum
        return mode_exps, mode_expsum, dest_exps, dest_expsums

    def _calc_exps(self,
                   impedance: Dict[str, Dict[str, Dict[str, numpy.ndarray]]]):
        dest_expsums: Dict[str, numpy.ndarray] = {}
        dest_exps: Dict[str, numpy.ndarray] = {}
        mode_exps: Dict[str, numpy.ndarray] = {}
        for mode in list(impedance):
            dest_exps[mode] = self._calc_dest_util(mode, impedance.pop(mode))
            try:
                expsum = dest_exps[mode].sum(1)
            except ValueError:
                expsum = dest_exps[mode].sum()
            dest_expsums[mode] = {"logsum": expsum}
            label = self.purpose.name + "_" + mode
            logsum = pandas.Series(
                log(expsum), self.purpose.orig_zone_numbers, name=label)
            self.generation_zone_data._values[label] = logsum
            mode_exps[mode] = self._calc_mode_util(mode, dest_expsums[mode])
        return mode_exps, dest_exps, dest_expsums

    def _calc_mode_prob(self, mode_exps: Dict[str, numpy.ndarray],
                        mode_expsum: numpy.ndarray,
                        ) -> Dict[str, numpy.ndarray]:
        dummies: defaultdict[str, list] = defaultdict(list)
        for mode in self.mode_choice_param:
            if mode not in mode_exps:
                msg = f"Mode {mode} missing from {self.purpose.name} impedance"
                raise KeyError(msg)
            for i in self.mode_choice_param[mode]["individual_dummy"]:
                dummies[i].append(mode)
        mode_probs: defaultdict[str, list] = defaultdict(list)
        no_dummy_share = 1.0
        for dummy, modes in dummies.items():
            try:
                dummy_share = numpy.asarray(self.generation_zone_data[dummy])
            except KeyError:
                self._stashed_exps = [mode_exps, mode_expsum]
                return None
            no_dummy_share -= dummy_share
            mode_exps2 = self._calc_individual_prob(modes, dummy, mode_exps)
            mode_expsum2 = sum(mode_exps2.values())
            for mode2 in mode_exps2:
                mode_probs[mode2].append(
                    dummy_share * divide(mode_exps2[mode2], mode_expsum2))
        for mode in self.mode_choice_param:
            mode_probs[mode].append(
                no_dummy_share * divide(mode_exps[mode], mode_expsum))
        return mode_probs

    def _calc_prob(self, mode_probs: Dict[str, numpy.ndarray],
                   dest_exps: Dict[str, numpy.ndarray],
                   dest_expsums: Dict[str, numpy.ndarray]
                   ) -> Dict[str, numpy.ndarray]:
        prob = {}
        for mode in dest_expsums:
            dest_exp = dest_exps.pop(mode).T
            dest_expsum = dest_expsums[mode]["logsum"]
            dest_prob = divide(dest_exp, dest_expsum)
            prob[mode] = sum(mode_probs[mode]) * dest_prob
        return prob

    def _calc_accessibility(self, mode_exps: Dict[str, numpy.ndarray],
                            mode_expsum: numpy.ndarray):
        """Calculate logsum-based accessibility measures.

        Individual dummy variables are not included.
        """
        self.accessibility: Dict[str, pandas.Series] = {}
        self.accessibility["all"] = self.generation_zone_data[self.purpose.name]
        sustainable_expsum = numpy.zeros_like(mode_expsum)
        car_expsum = numpy.zeros_like(mode_expsum)
        for mode in self.mode_choice_param:
            logsum = self.generation_zone_data[f"{self.purpose.name}_{mode}"]
            self.accessibility[mode] = logsum
            if "car" in mode:
                car_expsum += mode_exps[mode]
            else:
                sustainable_expsum += mode_exps[mode]
        label = f"{self.purpose.name}_sustainable"
        logsum_sustainable = pandas.Series(
            log(sustainable_expsum), self.purpose.orig_zone_numbers, name=label)
        self.generation_zone_data._values[label] = logsum_sustainable
        self.accessibility["sustainable"] = logsum_sustainable
        self.accessibility["car"] = pandas.Series(
            log(car_expsum), self.purpose.orig_zone_numbers,
            name=f"{self.purpose.name}_car")
        for key in ["all", "sustainable", "car"]:
            scaled_access = self.money_utility * self.accessibility[key]
            name = f"{scaled_access.name}_scaled"
            scaled_access.rename(name, inplace=True)
            self.accessibility[name] = scaled_access


class DestModeModel(LogitModel):
    """Nested logit model with destination choice in upper level.

    Used only in peripheral non-home source model.
    Uses logsums from mode choice model as utility
    in destination choice model.

         choice
        /     \\
      d1        d2
     / \\      / \\
    m1   m2   m1   m2

    Parameters
    ----------
    purpose : TourPurpose
        Tour purpose (type of tour)
    parameters : dict
        See `datatypes.purpose.new_tour_purpose()`
    zone_data : ZoneData
        Data used for all demand calculations
    resultdata : ResultData
        Writer object to result directory
    """
    def calc_soft_mode_exps(self, impedance):
        return []

    def calc_soft_mode_prob(self, impedance):
        return []

    def calc_prob(self, impedance, calc_accessibility=False):
        """Calculate matrix of choice probabilities.
        
        Parameters
        ----------
        impedance : dict
            Mode (car/transit/bike/walk) : dict
                Type (time/cost/dist) : numpy 2-d matrix
                    Impedances
        
        Returns
        -------
        dict
            Mode (car/transit/bike/walk) : numpy 2-d matrix
                Choice probabilities
        """
        dummies: set[str] = set()
        for mode in self.mode_choice_param:
            for i in self.mode_choice_param[mode]["individual_dummy"]:
                dummies.add(i)
        no_dummy_share = 1.0
        prob = defaultdict(float)
        for dummy in dummies:
            dummy_share = numpy.asarray(self.generation_zone_data[dummy])
            no_dummy_share -= dummy_share
            tmp_prob = self._calc_prob(impedance, dummy)
            for mode in self.mode_choice_param:
                prob[mode] += dummy_share * tmp_prob.pop(mode)
        tmp_prob = self._calc_prob(impedance, store_logsum=True)
        for mode in self.mode_choice_param:
            prob[mode] += no_dummy_share * tmp_prob.pop(mode)
        return prob

    def _calc_prob(self, impedance: Dict[str, Dict[str, numpy.ndarray]],
                   dummy: Optional[str] = None, store_logsum: bool = False):
        mode_expsum, mode_exps = self._calc_mode_utils(impedance, dummy)
        dest_exps = self._calc_dest_util("logsum", {"logsum": mode_expsum})
        try:
            dest_expsum = dest_exps.sum(1)
        except ValueError:
            dest_expsum = dest_exps.sum()
        if store_logsum:
            logsum = pandas.Series(
                log(dest_expsum), self.purpose.orig_zone_numbers,
                name=self.purpose.name)
            self.accessibility = {"all": logsum}
            self.generation_zone_data._values[self.purpose.name] = logsum
        prob: Dict[str, numpy.ndarray] = {}
        dest_prob = divide(dest_exps.T, dest_expsum)
        for mode in self.mode_choice_param:
            mode_prob = divide(mode_exps.pop(mode), mode_expsum).T
            prob[mode] = mode_prob * dest_prob
        return prob

    def calc_basic_prob(self, impedance):
        mode_expsum, _ = self._calc_mode_utils(impedance)
        dest_exps = self._calc_dest_util("logsum", {"logsum": mode_expsum})
        cumsum = dest_exps.T.cumsum(axis=0)
        self.cumul_dest_prob = cumsum / cumsum[-1]


class SecDestModel(LogitModel):
    """Logit model for secondary destination choice.

    Attaches secondary destinations to tours with already calculated
    modes and destinations.

    Parameters
    ----------
    zone_data : ZoneData
        Data used for all demand calculations
    purpose : TourPurpose
        Tour purpose (type of tour)
    resultdata : ResultData
        Writer object to result directory
    """

    def calc_prob(self, mode, impedance, origin, destination=None):
        """Calculate matrix of choice probabilities.
        
        Parameters
        ----------
        mode : str
            Mode (car/transit/bike)
        impedance : dict
            Type (time/cost/dist) : numpy 2d matrix
                Impedances
        origin: int
            Origin zone index
        destination: int or ndarray (optional)
            Destination zone index or boolean array (if calculation for 
            all primary destinations is performed in parallel)
        
        Returns
        -------
        numpy 2-d matrix
                Choice probabilities
        """
        dest_exps = self._calc_sec_dest_util(mode, impedance, origin, destination)
        return dest_exps.T / dest_exps.sum(1)


class GenerationLogit(LogitModel):
    """Logit model with generation count response.

    Parameters
    ----------
    zone_data : ZoneData
        Data used for all demand calculations
    bounds : slice
        Zone bounds
    age_groups : list
        tuple
            int
                Age intervals
    resultdata : ResultData
        Writer object to result directory
    """

    def __init__(self, 
                 parameters: dict,
                 zone_data: ZoneData, 
                 bounds: slice, 
                 resultdata: ResultsData):
        self.resultdata = resultdata
        self.generation_zone_data = zone_data
        self.bounds = bounds
        attempt_calibration(parameters)
        self.param = parameters

    def calc_basic_prob(self) -> Dict[int, numpy.ndarray]:
        prob = {}
        self.exps = {}
        nr_expsum = 0
        # First calc probabilites without individual dummies
        for nr in self.param:
            b = self.param[nr]
            utility = numpy.zeros(self.bounds.stop, dtype=numpy.float32)
            utility += b["constant"]
            utility = self._add_zone_util(utility, b["generation"], True)
            self.exps[nr] = numpy.minimum(numpy.exp(utility), 99999)
            nr_expsum += self.exps[nr]
        for nr in self.param:
            prob[nr] = divide(self.exps[nr], nr_expsum)
        return prob


    def calc_prob(self) -> Dict[int, numpy.ndarray]:
        """Calculate tour generation probabilities with individual dummies included.

        Returns
        -------
        dict
            key : int
                Number of cars in household / Number of tours per day 
            value : numpy.ndarray
                Choice probabilities
        """
        self.calc_basic_prob()
        prob = {}
        for nr in self.param:
            prob[nr] = numpy.zeros(self.bounds.stop, dtype=numpy.float32)
        # Calculate probability with individual dummies and combine
        for dummy in self.param["0"]["individual_dummy"]:
            nr_exp = {}
            nr_expsum = numpy.zeros(self.bounds.stop, dtype=numpy.float32)
            for nr in self.param:
                b = self.param[nr]["individual_dummy"][dummy]
                nr_exp[nr] = self.exps[nr] * numpy.exp(b)
                nr_expsum += nr_exp[nr]
            for nr in self.param:
                ind_prob = nr_exp[nr] / nr_expsum
                dummy_share = numpy.asarray(self.generation_zone_data[dummy])
                with_dummy = dummy_share * ind_prob
                prob[nr] += with_dummy
        return prob
