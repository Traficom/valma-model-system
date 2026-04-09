from __future__ import annotations
from typing import TYPE_CHECKING, Dict
import numpy # type: ignore
import pandas
if TYPE_CHECKING:
    from datahandling.matrixdata import MatrixData
    from datahandling.zonedata import ZoneData

import parameters.ext_tour_generation as param
from parameters.departure_time import demand_share
from utils.freight import fratar, calibrate
from datatypes.demand import Demand
from datatypes.purpose import Purpose


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
                 zone_data_base: Dict[str, ZoneData], 
                 zone_data_forecast: Dict[str, ZoneData], 
                 base_demand: MatrixData,
                 zone_numbers: numpy.ndarray):
        self.zdata_b = zone_data_base["domestic"]
        self.zdata_f = zone_data_forecast["domestic"]
        self.base_demand = base_demand
        self.zone_numbers_full = zone_numbers
        self.zone_numbers_zone_data = list(self.zdata_b.zone_numbers)

    def calc_foreign_external_traffic(self, mode: str) -> numpy.ndarray:
        """Calculate foreign external passenger traffic matrix.

        Return
        ------
        datatypes.demand.Demand
            Foreign external passenger demand matrix for whole day
        """
        zone_data_base = self.zdata_b.get_foreign_external_data()
        zone_data_forecast = self.zdata_f.get_foreign_external_data()
        production_base = self._generate_trips(zone_data_base, mode)
        production_forecast = self._generate_trips(zone_data_forecast, mode)

        # NOTE: Eli tässä input-matriisissa on kaikki sentroidit, mutta nollasta poikkeavia arvoja on vain lähtömaa-sijoittelualue - ulkomaan alueklusteri -pareilla.
        with self.base_demand.open(mtx_type="ext_foreign_passenger",
                                   time_period="vrk",
                                   zone_numbers=list(self.zone_numbers_full),
                                   transport_classes=[mode]) as mtx:
            mapping_full = mtx.mapping
            # Remove zero values
            base_mtx = mtx[mode].clip(0.000001, None)
            base_colsum = base_mtx.sum(1)
            # Add ones for missing zones in zonedata
            production_base_full = [1 if i not in self.zone_numbers_zone_data else production_base[i] for i in self.zone_numbers_full]
            production_forecast_full = [1 if i not in self.zone_numbers_zone_data else production_forecast[i] for i in self.zone_numbers_full]
        production = calibrate(
            base_colsum, production_base_full, production_forecast_full)
        mtx = pandas.DataFrame(base_mtx, self.zone_numbers_full, self.zone_numbers_full)

        # NOTE: Tässä on tiputettu se HELMET-mallissa suuntautumismuutos-hommeli pois, koska nää on kiertomatkoja by defalult ja kohdemaissa ei oo aluejakoa

        # Matrix balancing
        demand = fratar(production, mtx)
        
        return demand.to_numpy()

    def _generate_trips(self, 
                        zone_data: pandas.DataFrame, 
                        mode: str) -> numpy.ndarray:
        b = pandas.Series(param.tour_generation[mode])
        return (b * zone_data).sum(1) + 0.001