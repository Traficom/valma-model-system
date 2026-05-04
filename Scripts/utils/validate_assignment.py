import numpy
from typing import Dict
from parameters.zone import print_od_pairs

import utils.log as log
from datahandling.resultdata import ResultsData

def log_avg_speed(mtx1: numpy.ndarray,
                     mtx2: numpy.ndarray,
                     mode: str,
                     tp: str):
    """Perform array division where division by zero is skipped.

    Log descriptives min, median, max.
    """
    mask = mtx2 != 0
    mtx = mtx1[mask] / mtx2[mask]
    v = [round(numpy.quantile(mtx, q)) for q in [0.00, 0.50, 1.00]]
    log.debug(f"{tp} {mode} (min, median, max) {v[0]} - {v[1]} - {v[2]}")

def output_od_los(impedance: numpy.ndarray,
                  zone_numbers: numpy.ndarray,
                  mtx_type: str,
                  mode: str,
                  tp: str,
                  resultdata: ResultsData):
    """Write LOS between OD pairs.

    Parameters
    ----------
    impedance : numpy.ndarray
        Level-of-service matrix
    zone_numbers : numpy.ndarray
        Array mapping matrix indices to zone numbers
    mtx_type : str
        Type (time/cost/dist/...)
    mode : str
        Assignment class (car/transit/...)
    tp : str
        Time period
    resultdata : ResultsData
        Output data handler
    """
    zone_to_idx = {zone: idx for idx, zone in enumerate(zone_numbers)}
    for od_pair, (z0, z1) in print_od_pairs.items():
        try:
            idx0 = zone_to_idx[z0]
            idx1 = zone_to_idx[z1]
        except KeyError:
            continue
        los = int(impedance[idx0, idx1])
        if "time" in mtx_type:
            los = round(los / 60, 1)
            unit = "h"
        elif "cost" in mtx_type:
            unit = "eur"
        elif "dist" in mtx_type:
            unit = "km"
        else:
            unit = ""
        txt = f"{od_pair}\t{tp}\t{mode}\t{mtx_type}\t{los}\t{unit}"
        resultdata.print_line(txt, "los_validation")
