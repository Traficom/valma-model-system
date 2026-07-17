import numpy # type: ignore

import parameters.commodity as param


def fratar(prod, attr, trips, max_iter=10):
    """Perform fratar adjustment of matrix with production and attraction target.

    Parameters
    ----------
    prod : numpy/pandas array
        Production target
    attr : numpy/pandas array
        Attraction target
    trips : numpy array
        Seed trip matrix
    max_iter (optional) : int
        Maximum iterations, default is 10
    
    Returns
    -------
    pandas DataFrame 
        Fratared trip matrix
    """
    # Run 2D balancing
    for _ in range(max_iter):
        rowsum = trips.sum(axis=1)
        rowsum[rowsum == 0] = 1
        trips *= (prod / rowsum)[:, numpy.newaxis]
        colsum = trips.sum(axis=0)
        colsum[colsum == 0] = 1
        trips *= (attr / colsum)[numpy.newaxis, :]
    return trips

def calibrate(calib_base, production_base, production_forecast):
    """Calibrate a forecast according to calibrated base matrix.
    
    Parameters
    ----------
    calib_base : numpy matrix
        Calibrated base matrix
    production_base : numpy matrix
        Uncalibrated base matrix
    production_forecast : numpy matrix
        Uncalibrated forecast

    Return
    ------
    numpy matrix
        Calibrated forecast
    """
    b = calib_base
    n = production_base
    s = production_forecast
    threshold = param.vector_calibration_threshold
    n[n == 0] = 0.000001
    return numpy.where(s < threshold*n, s * b/n, s + threshold*(b - n))