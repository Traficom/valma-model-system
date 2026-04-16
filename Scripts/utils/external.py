import numpy # type: ignore

import parameters.commodity as param


def fratar(target_vect, trips, max_iter=10):
    """Perform fratar adjustment of matrix with production target.

    Parameters
    ----------
    target_vect : numpy/pandas array
        Production target
    trips : pandas DataFrame
        Seed trip matrix
    max_iter (optional) : int
        Maximum iterations, default is 10
    
    Returns
    -------
    pandas DataFrame 
        Fratared trip matrix
    """
    # Run 2D balancing
    # Assumes only production target vector is given, and the other is constructed such that target totals match
    prod_target = target_vect
    attr_share = trips.sum(axis=0) / trips.values.sum()
    attr_target = attr_share * prod_target.sum()
    for _ in range(0, max_iter):
        colsum = trips.sum("columns")
        colsum[colsum == 0] = 1
        trips = trips.mul(prod_target/colsum, "index")
        rowsum = trips.sum("index")
        rowsum[rowsum == 0] = 1
        trips = trips.mul(attr_target/rowsum, "columns")
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

    debug = numpy.where(s < threshold*n, s * b/n, s + threshold*(b - n))


    return numpy.where(s < threshold*n, s * b/n, s + threshold*(b - n))
