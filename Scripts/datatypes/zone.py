import numpy
import pandas
from typing import Union, Dict


class ZoneAggregations:
    """Object containing different zone mappings which can be used for
	aggregating data.
    """

    def __init__(self, mappings: pandas.DataFrame):
        """Initialize mappings.

        Parameters
        ----------
        mapping : pandas.Dataframe
            Zone numbers as index and different zone mappings as columns
        """
        self.mappings = mappings

    def averages(self,
                 array: pandas.Series,
                 weights: pandas.Series,
                 area_type: str) -> pandas.Series:
        """Get weighted area averages.

        Parameters
        ----------
        array : pandas.Series
            Array to average over areas
        weights : pandas.Series
            Array of weights
        area_type : str
            Name of the mapping to use for aggregation

        Returns
        -------
        pandas.Series
            Aggregated array
        """
        agg = array.groupby(self.mappings[area_type]).agg(avg, weights=weights)
        agg["all"] = avg(array, weights)
        return agg

    def aggregate_mtx(self,
                      matrix: pandas.DataFrame,
                      area_type: str) -> pandas.DataFrame:
        """Aggregate (tour demand) matrix to larger areas.

        Parameters
        ----------
        matrix : pandas.DataFrame
            Disaggregated matrix with zone indices and columns
        area_type : str
            Name of the mapping to use for aggregation

        Returns
        -------
        pandas.DataFrame
            Matrix aggregated to the selected mapping
        """
        return self.aggregate_array(
            self.aggregate_array(matrix, area_type).T, area_type).T

    def aggregate_array(self,
                        array: Union[pandas.Series, pandas.DataFrame],
                        area_type: str) -> Union[pandas.Series, pandas.DataFrame]:
        """Aggregate (tour demand) array to larger areas.

        Parameters
        ----------
        array : pandas.Series
            Disaggregated array with zone indices
        area_type : str
            Name of the mapping to use for aggregation

        Returns
        -------
        pandas.Series
            Array aggregated to the selected mapping
        """
        return array.groupby(self.mappings[area_type]).agg("sum")


class Zone:
    counter = 0

    def __init__(self, number: int, aggregations: ZoneAggregations):
        self.number = number
        self.index = Zone.counter
        Zone.counter += 1
        self.county = aggregations.mappings["county"][number]
        self.municipality = aggregations.mappings["municipality"][number]

class WeightedAverage:

    def __init__(self, weights: pandas.Series):
        self._weights = weights


    def avg(self, data: pandas.Series) -> float:
        try:
            return numpy.average(data, weights=self._weights[data.index])
        except ZeroDivisionError:
            return 0.0
