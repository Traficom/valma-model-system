from __future__ import annotations
from typing import TYPE_CHECKING, Dict
import numpy # type: ignore
import pandas
if TYPE_CHECKING:
    from datahandling.matrixdata import MatrixData
    from datahandling.zonedata import ZoneData
    from datatypes.purpose import Purpose

from parameters.departure_time import demand_share
from pathlib import Path
from utils.external import fratar, calibrate
import openmatrix as omx # type: ignore
from parameters.zone import purpose_areas


class ForeignExternalModel:
    """Foreign external passenger traffic model.
    Parameters
    ----------
    zone_data_base : datahandling.zonedata.ZoneData
        Zone data for base year
    zone_data_forecast : datahandling.zonedata.ZoneData
        Zone data for forecast year
    base_demand : datahandling.matrixdata.MatrixData
        Base demand matrices
    """

    def __init__(self,
                 purpose: Purpose, 
                 zone_data_base: Dict[str, ZoneData], 
                 zone_data_forecast: Dict[str, ZoneData], 
                 base_demand_path: Path,
                 zone_numbers: numpy.ndarray):
        self.purpose = purpose
        self.zdata_b = zone_data_base["domestic"]
        self.zdata_f = zone_data_forecast["domestic"]
        self.base_demand_path = base_demand_path
        self.zone_numbers = zone_numbers
        self.zone_numbers_zone_data = list(self.zdata_b.zone_numbers)

    def calc_foreign_external_traffic(self, mode: str) -> numpy.ndarray:
        """Calculate foreign external passenger traffic matrix.
        Return
        ------
        numpy.ndarray
            Foreign external passenger demand matrix for whole day
        """
        zone_data_base = self.zdata_b.get_foreign_external_data()
        zone_data_forecast = self.zdata_f.get_foreign_external_data()
        production_base = self._generate_trips(zone_data_base, mode)
        production_forecast = self._generate_trips(zone_data_forecast, mode)

        # NOTE: Eli tässä input-matriisissa on kaikki sentroidit, mutta nollasta poikkeavia arvoja on vain lähtömaa-sijoittelualue - ulkomaan alueklusteri -pareilla.
        with omx.open_file(self.base_demand_path, "r") as mtx:
            # Remove zero values
            base_mtx = numpy.array(mtx[mode]).clip(0.000001, None)
            base_colsum = base_mtx.sum(1)
        # Calibrate generation
        production = calibrate(
            base_colsum, production_base, production_forecast)
        
        # Get zone numbers for matrix construction
        all_zone_numbers = numpy.array(self.zone_numbers)
        domestic_zone_numbers = all_zone_numbers[(all_zone_numbers >= purpose_areas["domestic"][0]) & (all_zone_numbers <= purpose_areas["domestic"][1])]
        external_zone_numbers = all_zone_numbers[(all_zone_numbers >= purpose_areas["external"][0]) & (all_zone_numbers <= purpose_areas["external"][1])]

        # Construct matrix with correct zone numbers
        mtx = pandas.DataFrame(base_mtx, domestic_zone_numbers, external_zone_numbers)

        # NOTE: Tässä on tiputettu se HELMET-mallissa suuntautumismuutos-hommeli pois, koska nää on kiertomatkoja by defalult ja kohdemaissa ei oo aluejakoa

        # Matrix balancing
        demand = fratar(production, mtx)

        # Remove small values
        demand[demand < 0.0001] = 0

        return demand.to_numpy()

    def _generate_trips(self, 
                        zone_data: pandas.DataFrame, 
                        mode: str) -> numpy.ndarray:
        b = pandas.Series(self.purpose.tour_generation[mode])
        return (b * zone_data).sum(1) + 0.001