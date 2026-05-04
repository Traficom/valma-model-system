import numpy
from typing import Dict
from parameters.zone import print_od_pairs

import utils.log as log
from datahandling.resultdata import ResultsData

def validate_assignment(impedance, tp, ass_classes, zone_numbers, resultdata: ResultsData):
    """Print LOS data and speed statistics.

    Parameters
    ----------
    impedance : dict
        Nested dictionary containing impedance matrices with structure:
        impedance[mtx_type][ass_class] where mtx_type is "time", "cost" or "dist".
    tp : str
        Time period identifier ("aht", "pt", "iht")
    ass_classes : list
        List of assignment class names (["car", "transit"])
    zone_numbers : numpy.ndarray
        Array mapping matrix indices to zone numbers
    resultdata : ResultsData
        Output data handler for writing LOS validation results

    """
    for mtx_type in impedance:
        for ass_class in impedance[mtx_type]:
            zone_to_idx = {zone: idx for idx, zone in enumerate(zone_numbers)}
            for od_pair, (z0, z1) in print_od_pairs.items():
                try:
                    idx0 = zone_to_idx[z0]
                    idx1 = zone_to_idx[z1]
                except KeyError:
                    continue
                los = int(impedance[mtx_type][ass_class][idx0, idx1])
                if "time" in mtx_type:
                    los = round(los / 60, 1)
                    unit = "h"
                elif "cost" in mtx_type:
                    unit = "eur"
                elif "dist" in mtx_type:
                    unit = "km"
                else:
                    unit = ""
                txt = f"{od_pair}\t{tp}\t{ass_class}\t{mtx_type}\t{los}\t{unit}"
                resultdata.print_line(txt, "los_validation")
            
    for ass_class in ass_classes:
        try:
            dist = impedance["dist"][ass_class]
            time = impedance["time"][ass_class]/60
            mask = time != 0
            mtx = dist[mask] / time[mask]
            v = [round(numpy.quantile(mtx, q)) for q in [0.00, 0.50, 1.00]]
            log.debug(f"{tp} {ass_class} (min, median, max) {v[0]} - {v[1]} - {v[2]}")
        except KeyError:
            pass
