from __future__ import annotations
from typing import Any, List, Sequence, Union, Dict, Optional
from pathlib import Path
from collections import defaultdict
import numpy # type: ignore
import pandas
import fiona
import logging
import json
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

import parameters.zone as param
import utils.log as log
from datatypes.zone import Zone, ZoneAggregations, WeightedAverage
from models.logit import divide


class GridData:
    """Container for unaggregated grid data.
    Grid level data is used to calculate within zone distances.
    Grid is aggregated to zone level using "input_zone_id" as 
    grouping variable and rules from zone_variables.json. 

    Parameters
    ----------
    data_path : Path
        File containing grid-level input data
    submodel : str
        Name of column that maps each grid cell to an analysis zone
    data_type : str
        Data type used to select aggregation rules
    """

    def __init__(self, data_path: Path, submodel: str,
                zone_numbers: Sequence, model_area: str = "domestic",
                data_type: str = "domestic_travel"
                ):
        self.data, self.mapping, self.geometry, self.crs = _read_griddata(
            data_path, submodel)
        self.centroids = [geometry.centroid for geometry in self.geometry]
        self.submodel = submodel
        self.zone_mapping = self.data[submodel]
        self.data_type = data_type
        all_zone_numbers = numpy.asarray(zone_numbers, dtype=numpy.int64)
        self.all_zone_numbers = all_zone_numbers
        area = param.purpose_areas[model_area]
        self.zone_slice = slice(*all_zone_numbers.searchsorted(area))
        self.zone_numbers = pandas.Index(
            all_zone_numbers[self.zone_slice], name="analysis_zone_id")
        self.calc_intra_dist()

    def calc_intra_dist(self):
        """Calculate within-zone distances from grid-cell attraction.

        Distances are calculated in kilometres. 
        The resulting values are assigned to every grid cell.
        """
        log.info("Calculate intrazonal distances...")
        result = {
            "dist_walk": numpy.zeros(len(self.data)),
            "dist_bike": numpy.zeros(len(self.data)),
            "dist_car": numpy.zeros(len(self.data)),
        }
        sizes = numpy.clip(
            self.data["workplaces"].to_numpy(dtype=float)
            + self.data["population"].to_numpy(dtype=float),
            0,
            None,
        )
        population = self.data["population"].to_numpy(dtype=float)
        mapping = self.mapping.to_numpy()
        zone_rows = {
            zone: numpy.flatnonzero(mapping == zone)
            for zone in self.zone_numbers
        }

        for zone in self.zone_numbers:
            actual_rows = zone_rows[zone]
            origin_rows = actual_rows[population[actual_rows] > 0]
            destination_rows = actual_rows[sizes[actual_rows] > 0]
            if destination_rows.size > 300:
                sample_positions = numpy.linspace(
                    0, destination_rows.size - 1, 300, dtype=int)
                destination_rows = destination_rows[sample_positions]
            if not origin_rows.size or not destination_rows.size:
                continue
            origin_coordinates = self._coordinates(origin_rows)
            destination_coordinates = self._coordinates(destination_rows)
            distances = numpy.linalg.norm(
                origin_coordinates[:, numpy.newaxis, :]
                - destination_coordinates[numpy.newaxis, :, :],
                axis=2,
            ) / 1000
            destination_positions = numpy.searchsorted(
                destination_rows, origin_rows)
            valid_positions = destination_positions < destination_rows.size
            safe_positions = numpy.minimum(
                destination_positions, destination_rows.size - 1)
            valid_positions &= (
                destination_rows[safe_positions] == origin_rows)
            distances[
                numpy.flatnonzero(valid_positions),
                destination_positions[valid_positions],
            ] = 0.125

            zone_sizes = sizes[origin_rows]
            with numpy.errstate(divide="ignore", invalid="ignore"):
                log_zone_sizes = numpy.log(zone_sizes)[:, numpy.newaxis]
                mode_parameters = {
                    "dist_walk": (-0.8, 1.5),
                    "dist_bike": (-0.3, -0.5),
                    "dist_car": (-0.1, 0.0),
                }
                utilities = {
                    name: numpy.exp(
                        coefficient * distances
                        + intercept
                        + log_zone_sizes
                    )
                    for name, (coefficient, intercept)
                    in mode_parameters.items()
                }
                expsum = numpy.sum(list(utilities.values()), axis=0)

                origin_probability = population[origin_rows].copy()
                origin_probability /= origin_probability.sum()
                origin_probability[numpy.isnan(origin_probability)] = 1

                for name, utility in utilities.items():
                    probability = divide(utility, expsum)
                    destination_probability = probability.sum(axis=0)
                    distances_by_origin = numpy.sum(
                        divide(probability, destination_probability) * distances,
                        axis=1)
                    result[name][actual_rows] = numpy.sum(
                        distances_by_origin * origin_probability)

        for name, values in result.items():
            self[name] = pandas.Series(values, index=self.data.index)

    def _coordinates(self, rows):
        return numpy.array([
            (self.centroids[index].x, self.centroids[index].y)
            for index in rows
        ])

    def __getitem__(self, key: str):
        return self.data[key]

    def __setitem__(self, key: str, value):
        self.data[key] = value

    def aggregate(self,
                   car_dist_cost: Optional[float] = None,
                   electric_car_share: Optional[Dict] = None):
        zone_variables: dict = json.loads(
            (Path(__file__).parent / "zone_variables.json").read_text("utf-8")
        )[self.data_type]
        aggs = {}
        optional_agg = [
            key for key in self.data.columns if "aggregate_results_" in key]
        for func, cols in zone_variables.items():
            for col in cols:
                if not isinstance(col, dict):
                    aggs[col] = self._most_common if func == "first" else func
                    continue
                total = col["total"]
                aggs[total] = func
                wa = WeightedAverage(self.data[total])
                for share in col["shares"]:
                    aggs[share] = wa.avg
        for column in optional_agg:
            aggs[column] = self._most_common

        aggregated = self.data.groupby(self.submodel).agg(aggs)
        aggregated.index = aggregated.index.astype(numpy.int64)
        aggregated.index.name = "analysis_zone_id"
        zone_numbers = self.zone_numbers
        missing_zones = zone_numbers.difference(aggregated.index).tolist()
        extra_zones = aggregated.index.difference(zone_numbers).tolist()
        if missing_zones or extra_zones:
            msg = (
                f"Zone numbers did not match for zonedata: "
                f"missing={missing_zones}, extra={extra_zones}"
            )
            log.error(msg)
            raise IndexError(msg)
        aggregated = aggregated.reindex(zone_numbers)
        geometry = pandas.Series(self.geometry, index=self.data.index)
        self.aggregated_geometry = geometry.groupby(self.mapping).agg(unary_union)
        self.aggregated_geometry = self.aggregated_geometry.reindex(
            aggregated.index)
        zone_mapping = self.zone_mapping.reindex(aggregated.index)
        self._add_transformations(aggregated, car_dist_cost, electric_car_share)
        return aggregated, zone_mapping, self.zone_numbers

    @staticmethod
    def _most_common(values: pandas.Series):
        modes = values.mode(dropna=True)
        if modes.empty:
            return values.iloc[0]
        return modes.iloc[0]

    def export(self, path: Path):
        """Export aggregated grid data and geometries with Fiona."""
        data, _, _ = self.aggregate()
        schema = {
            "geometry": "Unknown",
            "properties": {
                column: self._fiona_type(data[column]) for column in data
            },
        }
        with fiona.open(
            path, "w", driver="GPKG", layer=path.stem,
            crs=self.crs, schema=schema) as destination:
            for zone, row in data.iterrows():
                properties = {
                    column: self._fiona_value(value)
                    for column, value in row.items()
                }
                destination.write({
                    "geometry": mapping(self.aggregated_geometry[zone]),
                    "properties": properties,
                })

        return path

    @staticmethod
    def _fiona_type(values: pandas.Series) -> str:
        if pandas.api.types.is_bool_dtype(values):
            return "bool"
        if pandas.api.types.is_integer_dtype(values):
            return "int"
        if pandas.api.types.is_float_dtype(values):
            return "float"
        return "str"

    @staticmethod
    def _fiona_value(value: Any):
        if pandas.isna(value):
            return None
        return value.item() if isinstance(value, numpy.generic) else value

    def _add_transformations(self,
                             data: pandas.DataFrame,
                             car_dist_cost: Optional[float],
                             electric_car_share: Optional[Dict]):
        data["time_car"] = 2 * 60 * data["dist_car"] / 20
        if car_dist_cost is not None:
            data["cost_car"] = 2 * car_dist_cost * data["dist_car"]
        if electric_car_share is not None:
            car_shares = pandas.DataFrame(electric_car_share).T.reindex(
                index=data["county"].values).fillna(
                    electric_car_share["default"])
            car_shares.index = data.index
            data["sh_bev"] = car_shares["bev"]
            data["sh_phev"] = car_shares["phev"]
            data["sh_icev"] = 1 - car_shares.sum(axis=1)

        avg_hh_size = {"hh1": 1, "hh2": 2, "hh3": 4.13}
        hh_pop = sum(avg_hh_size[hh] * data[f"sh_{hh}"]
                     for hh in avg_hh_size)
        households = 0
        for hh, avg_size in avg_hh_size.items():
            data[f"sh_pop_{hh}"] = divide(
                avg_size * data[f"sh_{hh}"], hh_pop)
            households += data[f"sh_pop_{hh}"] * data["population"] / avg_size
        data["households"] = households
        density_pop_wrk = divide(
            data["population"] + data["workplaces"], data["land_area"])
        data["avg_walk_time"] = round(0.047583 * numpy.sqrt(density_pop_wrk))
        data["avg_park_time"] = round(0.053891 * numpy.sqrt(density_pop_wrk))

class ZoneData:
    """Container for analysis zone data. 
    Uses instance of GridData as input.

    Parameters
    ----------
    data_path : Path
        File where scenario input data is found
    zone_numbers : list
        Zone numbers to compare with for validation
    municipality_calibration : dict
        key : str
            Transport mode (car/bike/...)
        value : pandas.Series
            Municipality-pair calibration factors
    extra_dummies : dict
        key : str
            Name of aggregation level
        value : list
            Additional dummy variables to create
    car_dist_cost : float
        Car cost (eur) per km
    electric_car_share : dict
        key : str
            County name or "default"
        value : dict
            key : str
                Electric car type (bev/phev)
            value : float
                Share of electric cars of that type
    ----------
    """
    beeline_dist: numpy.ndarray

    def __init__(self, *args, **kwargs):
        self._init_data(*args, **kwargs)

    def _init_data(self, data, mapping, zone_numbers, model_area,
                 municipality_calibration: Dict[str, pandas.Series] = {},
                 extra_dummies: Dict[str, Sequence[str]] = {}):
        self._values = {}
        self.share = ShareChecker(self)
        Zone.counter = 0
        self.mapping = mapping
        all_zone_numbers = numpy.array(zone_numbers)
        self.all_zone_numbers = all_zone_numbers
        area = param.purpose_areas[model_area]
        self.zone_slice = slice(*all_zone_numbers.searchsorted(area))
        self.zone_numbers = pandas.Index(
            all_zone_numbers[self.zone_slice], name="analysis_zone_id")
        demand_aggs = ["municipality", "county", "submodel", "calibration_area", "pt_authority"]
        result_aggs = demand_aggs + [key for key in data if "aggregate_results_" in key]
        source_shares = [
            column for column in data
            if column.startswith("sh_") and not column.startswith((
                "sh_pop_", "sh_hh_", "sh_bev", "sh_phev", "sh_icev"))
            and not column.endswith("_all")]
        for share in source_shares:
            data[share.replace("sh_", "", 1)] = data[share] * data["population"]
        share_groups = defaultdict(list)
        for share in source_shares:
            share_parts = share.split("_")
            share_groups[share_parts[1]].append(share)
        for share_type, type_shares in share_groups.items():
            if len(type_shares[0].split("_")) == 4:
                total_interval = "sh_{}_{}_{}".format(
                    share_type, type_shares[0].split("_")[2],
                    type_shares[-1].split("_")[3])
            else:
                total_interval = f"sh_{share_type}_all"
            data[total_interval] = data[type_shares].sum(axis="columns")
        self.demand_aggs = ZoneAggregations(data[demand_aggs])
        self.result_aggs = ZoneAggregations(data[result_aggs])
        for col in data:
            if col not in demand_aggs + result_aggs:
                if col.startswith("sh_"):
                    self.share[col] = data[col]
                else:
                    self[col] = data[col]
        self.zones = {number: Zone(number, self.demand_aggs)
            for number in self.zone_numbers}
        self.nr_zones = len(self.zone_numbers)
        self._municip_calib = municipality_calibration
        dummies = {
            "zone": {},
            "municipality": {},
            "county": {"Lappi"},
            "submodel": {},
            "calibration_area": {},
            "pt_authority": {"HSL", "Oulu", "Tampere", "Turku"}
        }
        for division_type in dummies:
            dummies[division_type].update(extra_dummies.get(division_type, []))
            for dummy in dummies[division_type]:
                self[dummy] = self.dummy(division_type, dummy)
        self["density_pop_wrk"] = divide(
            data["population"] + data["workplaces"], data["land_area"])
        pop_density = divide(data["population"], data["land_area"])
        self["sqrt_pop_density"] = numpy.sqrt(pop_density)
        self._calc_household_shares(share="sh")
        self._calc_household_shares(share="sh_pop")

    def _calc_household_shares(self, share: str = "sh"):
        """Calculate household adult, childen and license shares.

        Parameters
        ----------
        share : str
            Whether to calculate household ("sh") or population ("sh_pop")
            shares
        """
        # Calculate household adult number share
        avg_two_adult_share = {
            "hh2": 0.926,
            "hh3": 0.949,
        }
        singles_no_children = self[f"{share}_hh1"]
        singles_children = sum(
            (1-avg_two_adult_share[hh]) * self[f"{share}_{hh}"]
            for hh in avg_two_adult_share)
        couples_no_children = avg_two_adult_share["hh2"] * self[f"{share}_hh2"]
        couples_children = avg_two_adult_share["hh3"] * self[f"{share}_hh3"]
        couples = couples_no_children + couples_children
        singles = singles_no_children + singles_children

        # Simple combinatorial household license share calculations assuming
        # no correlation between license distribution in population and
        # household size.
        # They represent
        # - shares of households ("sh") or
        # - shares of population living in households ("sh_pop"),
        # with given number of *adults* and licenses.
        sh_lic = self["sh_adult_license"]
        self.share[f"{share}_hh1_lic1"] = sh_lic * singles
        self.share[f"{share}_hh2_lic1"] = 2 * sh_lic * (1-sh_lic) * couples
        self.share[f"{share}_hh2_lic2"] = sh_lic**2 * couples

        if share == "sh_pop":
            # Share of population in 1-adult households that
            # have / do not have children
            self.share["sh_hh_1_adult_children"] = divide(
                singles_children, singles)
            self.share["sh_hh_1_adult_no_children"] = divide(
                singles_no_children, singles)
            # Share of population in 2-adult households that
            # have / do not have children
            self.share["sh_hh_2_adults_children"] = divide(
                couples_children, couples)
            self.share["sh_hh_2_adults_no_children"] = divide(
                couples_no_children, couples)

    def dummy(self, division_type, name, bounds=slice(None)):
        if division_type == "zone":
            dummy = pandas.Series(
                self.zone_numbers == int(name), self.zone_numbers)
        else:
            dummy = self.demand_aggs.mappings[division_type][bounds] == name
        if not dummy.any():
            log.warn(f"Dummy variable {name} not found in {division_type}")
        return dummy

    @property
    def zone_values(self):
        return {key: val for key, val in self._values.items()
            if isinstance(val, pandas.Series)}

    def __setitem__(self, key: str, data: pandas.Series):
        if numpy.isscalar(data):
            data = pandas.Series(data, index=self.zone_numbers)
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
    
    def get_foreign_external_data(self) -> pandas.DataFrame:
        """Get zone data for foreign external passenger traffic calculation.
        Returns
        -------
        pandas DataFrame
            Zone data for foreign external passenger traffic calculation
        """
        variables = (
            "population",
        )
        data = {k: self._values[k] for k in variables}
        return pandas.DataFrame(data)

    def __getitem__(self, key: str) -> Union[pandas.Series, numpy.ndarray]:
        try:
            return self._values[key]
        except KeyError as err:
            keyl: List[str] = key.split('*')
            mun_idx = self.demand_aggs.mappings["municipality"].to_numpy()
            if (len(keyl) == 2):
                # If parameter is two-fold, they will be multiplied
                return numpy.asarray(self[keyl[0]]) * numpy.asarray(self[keyl[1]])
            elif "within_zone" in key:
                mtx = numpy.zeros(
                    (self.nr_zones, self.nr_zones), dtype=numpy.float32)
                numpy.fill_diagonal(mtx, numpy.inf if "inf" in key else 1.0)
                return mtx
            elif key == "within_municipality":
                # Create matrix with True if origin and destination
                # is in same municipality
                return mun_idx[:, numpy.newaxis] == mun_idx
            elif key == "outside_municipality":
                return mun_idx[:, numpy.newaxis] != mun_idx
            elif "beeline" in key:
                mtx = self.beeline_dist[self.zone_slice, self.zone_slice]
                try:  # If key contains km interval (e.g., "beeline_10_100_km")
                    _, lower, upper, _ = key.split('_')
                except ValueError:
                    return mtx
                else:
                    return (mtx > int(lower)) & (mtx <= int(upper))
            elif "municipality_calibration" in key:
                try:
                    # Try to find mode-specific calibration matrix
                    calib = self._municip_calib[key.split('_')[-1]]
                except KeyError:
                    return 0
                else:
                    return calib.unstack("attraction").reindex(
                        index=mun_idx, columns=mun_idx, fill_value=0.0
                    ).to_numpy(numpy.float32)
            else:
                raise KeyError(err)

    @property
    def is_in_submodel(self) -> pandas.Series:
        """Boolean mapping of zones, whether in proper sub-model area."""
        mapping = self.demand_aggs.mappings["submodel"]
        submodels = mapping.drop_duplicates()
        for submodel in submodels:
            if submodel is None:
                continue
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


def _read_griddata(path: Path, submodel: str):
    if not path.exists():
        msg = f"Path {path} not found."
        raise NameError(msg)
    logging.getLogger("fiona").setLevel(logging.ERROR)
    if len(fiona.listlayers(path)) > 1:
        msg = f"Multiple layers found in file {path}"
        log.error(msg)
        raise TypeError(msg)
    with fiona.open(path, ignore_geometry=False) as colxn:
        records = list(colxn)
        data = pandas.DataFrame(
            [record["properties"] for record in records],
            columns=list(colxn.schema["properties"]))
        geometries = [shape(record["geometry"]) for record in records]
        crs = colxn.crs
    if "grid_id" not in data:
        raise IndexError(f"Grid data file {path} lacks grid_id")
    data.set_index("grid_id", inplace=True)
    if data.index.hasnans:
        msg = "Row with only spaces or tabs in file {}".format(path)
        log.error(msg)
        raise IndexError(msg)
    if data.index.has_duplicates:
        raise IndexError("Index in file {} has duplicates".format(path))
    if not data.index.is_monotonic_increasing:
        order = numpy.argsort(data.index.to_numpy())
        data = data.iloc[order]
        geometries = [geometries[index] for index in order]
        log.warn("File {} is not sorted in ascending order".format(path))
    return data, data[submodel], geometries, crs


def read_zonedata(path: Path,
                  zone_numbers: numpy.ndarray):
    """Read zone data from space-separated file.

    Parameters
    ----------
    path : Path
        Path to the .gpkg file
    zone_numbers : ndarray
        Zone numbers to compare with for validation

    Returns
    -------
    pandas.DataFrame
        Zone data
    """
    if not path.exists():
        raise NameError(f"Path {path} not found.")
    if path.suffix.lower() == ".csv":
        data = pandas.read_csv(path)
    else:
        logging.getLogger("fiona").setLevel(logging.ERROR)
        if len(fiona.listlayers(path)) > 1:
            raise TypeError(f"Multiple layers found in file {path}")
        with fiona.open(path, ignore_geometry=True) as colxn:
            data = pandas.DataFrame(
                [record["properties"] for record in colxn],
                columns=list(colxn.schema["properties"]))
    index_name = "analysis_zone_id"
    if index_name not in data:
        if "input_zone_id" not in data:
            raise IndexError(
                f"Aggregated zonedata file {path} lacks analysis_zone_id")
        index_name = "input_zone_id"
    data.set_index(index_name, inplace=True)
    data.index = data.index.astype(int)
    data.index.name = "analysis_zone_id"
    requested_zones = pandas.Index(zone_numbers)
    available_zones = data.index.intersection(requested_zones)
    missing_zones = [zone for zone in requested_zones if zone not in data.index]
    if missing_zones:
        raise IndexError(
            f"Zone numbers did not match for file {path}: "
            f"missing {missing_zones}")
    data = data.loc[available_zones].reindex(zone_numbers)
    data = data.loc[zone_numbers]
    return data
