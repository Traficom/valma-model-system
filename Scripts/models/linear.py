import numpy # type: ignore
import pandas
import math

class LinearModel(object):
    """Initialize a linear model.

    Parameters
    ----------
    zone_data : datahandling.ZoneData
        Object defining the input data of zones
    bounds : slice
        Defines the area on which the model is predicting to (usually the
        metropolitan area)
    resultdata : datahandling.ResultData
        Writer object for result directory
    """
    def __init__(self, zone_data, bounds, resultdata):
        self.zone_data = zone_data
        self.bounds = bounds
        self.resultdata = resultdata

    def _add_zone_terms(self, prediction, b, generation=False):
        zdata = self.zone_data
        for i in b:
            prediction += b[i] * zdata.get_data(i, self.bounds, generation)
        return prediction

    def _add_log_zone_terms(self, prediction, b, generation=False):
        zdata = self.zone_data
        for i in b:
            prediction += b[i] * numpy.log(zdata.get_data(
                i, self.bounds, generation))
        return prediction
