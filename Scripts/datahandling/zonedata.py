from __future__ import annotations
from typing import Any, List, Sequence, Union, Dict, Optional
from pathlib import Path
from collections import defaultdict
import numpy # type: ignore
import pandas
import fiona
import logging
import json

import parameters.zone as param
import utils.log as log
from datatypes.zone import Zone, ZoneAggregations, avg

def divide(a, b):
    return numpy.divide(a, b, out=numpy.zeros_like(a), where=b!=0)

class ZoneData:
    """Container for zone data read from input file.

    Parameters
    ----------
    data_path : Path
        File where scenario input data is found
    zone_numbers : list
        Zone numbers to compare with for validation
    zone_mapping : str
            Name of column where mapping between data zones (index)
            and assignment zones
    extra_dummies : dict
        key : str
            Name of aggregation level
        value : list
            Additional dummy variables to create
    car_dist_cost : float
        Car cost (eur) per km
    """
    def __init__(self, *args, **kwargs):
        self._init_data(*args, **kwargs)

    def _init_data(self, data_path: Path, zone_numbers: Sequence,
                 zone_mapping: str, data_type: str = "domestic_travel",
                 model_area: str = "domestic",
                 extra_dummies: Dict[str, Sequence[str]] = {},
                 car_dist_cost: Optional[float] = None):
        self._values = {}
        self.share = ShareChecker(self)
        all_zone_numbers = numpy.array(zone_numbers)
        self.all_zone_numbers = all_zone_numbers
        area = param.purpose_areas[model_area]
        self.zone_numbers = pandas.Index(
            all_zone_numbers[slice(*all_zone_numbers.searchsorted(area))],
            name="analysis_zone_id")
        Zone.counter = 0
        data, mapping = read_zonedata(
            data_path, self.zone_numbers, zone_mapping, data_type)
        self.mapping = mapping
        agg_keys = [key for key in data if "aggregate_results_" in key]
        aggs = data[agg_keys].rename(
            columns=lambda x : x.replace("aggregate_results_", ""))
        self.aggregations = ZoneAggregations(aggs)
        for col in data:
            if col not in agg_keys:
                if col.startswith("sh_"):
                    self.share[col] = data[col]
                else:
                    self[col] = data[col]
        self.zones = {number: Zone(number, self.aggregations)
            for number in self.zone_numbers}
        self.nr_zones = len(self.zone_numbers)
        self._add_transformations(data, extra_dummies, car_dist_cost)

    def _add_transformations(self,
                             data: pandas.DataFrame,
                             extra_dummies: Dict[str, Sequence[str]],
                             car_dist_cost: float):
        self["car_density"].clip(upper=1, inplace=True)
        self.share["share_female"] = pandas.Series(
            0.5, self.zone_numbers, dtype=numpy.float32)
        self.share["share_male"] = pandas.Series(
            0.5, self.zone_numbers, dtype=numpy.float32)

        # Convert household shares to population shares
        avg_hh_size = {
            "hh1": 1,
            "hh2": 2,
            "hh3": 4.13,  # Average size of 3+ households
        }
        hh_pop = sum(avg_hh_size[hh] * self[f"sh_{hh}"] for hh in avg_hh_size)
        for hh, avg_size in avg_hh_size.items():
            self.share[f"sh_pop_{hh}"] = divide(
                avg_size*self[f"sh_{hh}"], hh_pop)
            self[hh] = self[f"sh_pop_{hh}"] * self["population"] / avg_size
        self.share["sh_cars1_hh1"] = divide(self["sh_cars1_hh1"], hh_pop)
        self.share["sh_cars1_hh2"] = divide(
            (avg_hh_size["hh2"]*self["sh_cars1_hh2"]
             + avg_hh_size["hh3"]*self["sh_cars1_hh3"]),
            hh_pop)
        self.share["sh_cars2_hh2"] = divide(
            (avg_hh_size["hh2"]*self["sh_cars2_hh2"]
             + avg_hh_size["hh3"]*self["sh_cars2_hh3"]),
            hh_pop)
        self.share["sh_car"] = (self["sh_cars1_hh1"]
                                + self["sh_cars1_hh2"]
                                + self["sh_cars2_hh2"])
        self["pop_density"] = divide(data["population"], data["land_area"])
        self["log_pop_density"] = numpy.log(self["pop_density"]+1)

        # Create diagonal matrix
        self["within_zone"] = numpy.full((self.nr_zones, self.nr_zones), 0.0)
        self["within_zone"][numpy.diag_indices(self.nr_zones)] = 1.0
        # Two-way intrazonal distances from building distances
        self["dist"] = data["avg_building_distance"] * 2
        self["time"] = self["dist"] / (20/60) # 20 km/h
        self["cost"] = car_dist_cost * self["dist"]
        # Unavailability of intrazonal tours
        self["within_zone_inf"] = numpy.full((self.nr_zones, self.nr_zones), 0.0)
        self["within_zone_inf"][numpy.diag_indices(self.nr_zones)] = numpy.inf
        # Create matrix where value is True if origin and destination is in
        # same municipality
        municipalities = self.aggregations.mappings["municipality"].values
        within_municipality = municipalities[:, numpy.newaxis] == municipalities
        self["within_municipality"] = within_municipality
        self["outside_municipality"] = ~within_municipality
        dummies = {
            "subarea": {
                "Helsingin_kantakaupunki",
                "Tampereen_kantakaupunki",
            },
            "county": {
                "Lappi",
            },
            "municipality": {},
            "submodel": {},
        }
        for division_type in dummies:
            dummies[division_type].update(extra_dummies.get(division_type, []))
            for dummy in dummies[division_type]:
                self[dummy] = self.dummy(division_type, dummy)

    def dummy(self, division_type, name, bounds=slice(None)):
        dummy = self.aggregations.mappings[division_type][bounds] == name
        if not dummy.any():
            log.warn(f"Dummy variable {name} not found in {division_type}")
        return dummy

    @property
    def zone_values(self):
        return {key: val for key, val in self._values.items()
            if isinstance(val, pandas.Series)}

    def __getitem__(self, key):
        return self._values[key]

    def __setitem__(self, key: str, data: pandas.Series):
        try:
            if not numpy.isfinite(data).all():
                for (i, val) in data.items():
                    if not numpy.isfinite(val):
                        msg = "{} for zone {} is not a finite number".format(
                            key, i).capitalize()
                        log.error(msg)
                        raise ValueError(msg)
        except TypeError:
            for (i, val) in data.items():
                try:
                    float(val)
                except ValueError:
                    msg = "{} for zone {} is not a number".format(
                        key, i).capitalize()
                    log.error(msg)
                    raise TypeError(msg)
            msg = "{} could not be read".format(key).capitalize()
            log.error(msg)
            raise TypeError(msg)
        if (data < 0).any():
            for (i, val) in data.items():
                if val < 0:
                    msg = "{} ({}) for zone {} is negative".format(
                        key, val, i).capitalize()
                    log.error(msg)
                    raise ValueError(msg)
        self._values[key] = data.astype(numpy.float32)

    def zone_index(self, 
                   zone_number: int) -> int:
        """Get index of given zone number.

        Parameters
        ----------
        zone_number : int
            The zone number to look up
        
        Returns
        -------
        int
            Index of zone number
        """
        return self.zones[zone_number].index

    def get_data(self, key: str, bounds: slice, generation: bool=False) -> Union[pandas.Series, numpy.ndarray]:
        """Get data of correct shape for zones included in purpose.
        
        Parameters
        ----------
        key : str
            Key describing the data (e.g., "population")
        bounds : slice
            Slice that describes the lower and upper bounds of purpose
        generation : bool, optional
            If set to True, returns data only for zones in purpose,
            otherwise returns data for all zones
        
        Returns
        -------
        pandas Series or numpy 2-d matrix
        """
        try:
            val = self._values[key]
        except KeyError as err:
            keyl: List[str] = key.split('*')
            if (len(keyl) == 2):
                # If parameter is two-fold, they will be multiplied
                return (self.get_data(keyl[0], bounds, generation)
                        * self.get_data(keyl[1], bounds, generation))
            elif "beeline" in key:
                beeline, lower, upper, _ = key.split('_')
                mtx = self[beeline]
                return (mtx > int(lower)) & (mtx <= int(upper))[bounds, :]
            else:
                raise KeyError(err)
        if val.ndim == 1: # If not a compound (i.e., matrix)
            if generation:  # Return values for purpose zones
                return val[bounds].values
            else:  # Return values for all zones
                return val.values
        else:  # Return matrix (purpose zones -> all zones)
            return val[bounds, :]

    @property
    def is_in_submodel(self) -> pandas.Series:
        """Boolean mapping of zones, whether in proper sub-model area."""
        mapping = self.aggregations.mappings["submodel"]
        submodels = mapping.drop_duplicates()
        for submodel in submodels:
            if self.mapping.name == submodel.lower().replace('-', '_'):
                return mapping == submodel
        else:
            return pandas.Series(True, self.zone_numbers)


class FreightZoneData(ZoneData):
    """Container for freight zone data read from input file.

    Parameters
    ----------
    data_path : Path
        File where scenario input data is found
    zone_numbers : list
        Zone numbers to compare with for validation
    zone_mapping : str
            Name of column where mapping between data zones (index)
            and assignment zones
    """
    def __init__(self, *args, **kwargs):
        ZoneData._init_data(self, *args, **kwargs, data_type="freight")

    def _add_transformations(self, *args, **kwargs):
        pass


class ShareChecker:
    def __init__(self, data):
        self.data = data

    def __setitem__(self, key, data):
        if (data > 1.02).any():
            for (i, val) in data.items():
                if val > 1.02:
                    msg = "{} ({}) for zone {} is larger than one".format(
                        key, val, i).capitalize()
                    log.error(msg)
                    raise ValueError(msg)
        self.data[key] = data


def read_zonedata(path: Path,
                  zone_numbers: numpy.ndarray,
                  zone_mapping_name: str,
                  data_type: str = "trips"):
    """Read zone data from space-separated file.

    Parameters
    ----------
    path : Path
        Path to the .gpkg file
    zone_numbers : ndarray
        Zone numbers to compare with for validation
    zone_mapping_name : str
        Name of column where mapping between data zones (index)
        and assignment zones
    data_type : str (optional)
        Type of data to read (trips or freight)

    Returns
    -------
    pandas.DataFrame
        Zone data
    pandas.Series
        Mapping between zones in zone-data file and in network
    """
    if not path.exists():
        msg = f"Path {path} not found."
        raise NameError(msg)
    logging.getLogger("fiona").setLevel(logging.ERROR)
    if len(fiona.listlayers(path)) > 1:
        msg = f"Multiple layers found in file {path}"
        log.error(msg)
        raise TypeError(msg)
    with fiona.open(path, ignore_geometry=True) as colxn:
        data = pandas.DataFrame(
            [record["properties"] for record in colxn],
            columns=list(colxn.schema["properties"]))
    data.set_index("input_zone_id", inplace=True)
    if data.index.hasnans:
        msg = "Row with only spaces or tabs in file {}".format(path)
        log.error(msg)
        raise IndexError(msg)
    if data.index.has_duplicates:
        raise IndexError("Index in file {} has duplicates".format(path))
    if not data.index.is_monotonic_increasing:
        data.sort_index(inplace=True)
        log.warn("File {} is not sorted in ascending order".format(path))
    zone_mapping = data[zone_mapping_name]
    zone_variables: dict = json.loads(
        (Path(__file__).parent / "zone_variables.json").read_text("utf-8")
    )[data_type]
    aggs = {}
    shares: Dict[str, Dict[str, List[str]]] = {}
    for func, cols in zone_variables.items():
        for col in cols:
            try:
                total = col["total"]
                shares[total] = defaultdict(list)
            except TypeError:
                aggs[col] = func
            else:
                aggs[total] = func
                for share in col["shares"]:
                    aggs[share] = lambda x: avg(x, weights=data[total])
                    shares[total][share.split('_')[1]].append(share)
    data = data.groupby(zone_mapping_name).agg(aggs)
    data.index = data.index.astype(int)
    data.index.name = "analysis_zone_id"
    data = data.loc[zone_numbers[0]:zone_numbers[-1]]
    if data.index.size != zone_numbers.size or (data.index != zone_numbers).any():
        for i in data.index:
            if int(i) not in zone_numbers:
                msg = (f"Zone number {i} from mapping {zone_mapping_name} "
                       + f"in file {path} not found in network")
                log.error(msg)
                raise IndexError(msg)
        for i in zone_numbers:
            if i not in data.index:
                msg = (f"Zone number {i} not found in mapping "
                       + f"{zone_mapping_name} in file {path}")
                log.error(msg)
                raise IndexError(msg)
        msg = "Zone numbers did not match for file {}".format(path)
        log.error(msg)
        raise IndexError(msg)
    for total in shares:
        for share_type, type_shares in shares[total].items():
            for share in type_shares:
                data[share.replace("sh_", "")] = data[share] * data[total]
            if len(type_shares[0].split('_')) == 4:
                # Example: Sum sh_age_7_17 .. sh_age_65_99 in sh_age_7_99
                total_interval = "sh_{}_{}_{}".format(
                    share_type, type_shares[0].split('_')[2],
                    type_shares[-1].split('_')[3])
            else:
                total_interval = f"sh_{share_type}_all"
            data[total_interval] = data[type_shares].sum(axis="columns")
    return data, zone_mapping
