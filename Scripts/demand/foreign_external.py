from __future__ import annotations
from typing import TYPE_CHECKING
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
                 zone_data_base: ZoneData, 
                 zone_data_forecast: ZoneData, 
                 base_demand: MatrixData):
        self.zdata_b = zone_data_base
        self.zdata_f = zone_data_forecast
        self.base_demand = base_demand
        spec = { # TODO: Nää pitää ehkä speksata jostain kunnolla, että toimii oikein.
            "name": "foreign_external",
            "orig": None,
            "dest": None,
            "generation_area": "domestic",
            "attraction_area": "foreign",
            "impedance_share": None,
            "demand_share": demand_share["foreign_external"]
        }
        self.purpose = Purpose(spec, zone_data_base)

    def calc_foreign_external_traffic(self, mode: str) -> Demand:
        """Calculate foreign external passenger traffic matrix.

        Return
        ------
        datatypes.demand.Demand
            Foreign external passenger demand matrix for whole day
        """
        zone_data_base = self.zdata_b.get_foreign_external_data()
        zone_data_forecast = self.zdata_f.get_foreign_external_data()
        production_base: numpy.ndarray = self._generate_trips(zone_data_base, mode)
        production_forecast: numpy.ndarray = self._generate_trips(zone_data_forecast, mode)
        zone_numbers = self.zdata_b.zone_numbers
        # NOTE: Tässä oletetaaan, että base_demand -matriisi on symmetrinen, muuten fratar ei toimi oikein.
        with self.base_demand.open("ext_foreign_passenger", "vrk", list(zone_numbers)) as mtx:
            # Remove zero values
            base_mtx = mtx[mode].clip(0.000001, None)
        production = calibrate(
            base_mtx.sum(1), production_base, production_forecast)
        mtx = pandas.DataFrame(base_mtx, zone_numbers, zone_numbers)

        # NOTE: Tässä on tiputettu se HELMET-mallissa suuntautumismuutos-hommeli pois, koska nää on kiertomatkoja by defalult ja kohdemaissa ei oo aluejakoa

        # Matrix balancing
        demand = fratar(production, mtx)
        
        return Demand(self.purpose, mode, demand.values)

    def _generate_trips(self, 
                        zone_data: pandas.DataFrame, 
                        mode: str) -> numpy.ndarray:
        b = pandas.Series(param.tour_generation[mode])
        return (b * zone_data).sum(1) + 0.001