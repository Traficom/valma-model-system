from __future__ import annotations
from typing import Any, Dict, Generator
import parameters.assignment as param
from assignment.datatypes.car import CarMode

class CarSpecification:

    def __init__(self, modes: Dict[str, CarMode]):
        """
        Car assignment specification.

        Parameters
        ----------
        modes : dict
            key : str
                    Assignment class (car/transit/...)
            value : CarMode
                Assignment mode to add to specification
        """
        self._modes = modes
        self._spec = {
            "type": "SOLA_TRAFFIC_ASSIGNMENT",
            "background_traffic": {
                "link_component": param.background_traffic_attr,
                "add_transit_vehicles": False,
            },
            "performance_settings": param.performance_settings,
            "stopping_criteria": None, # This is defined later
        }

    def light_spec(self) -> Dict[str, Any]:
        """Return light vehicle assignment specification."""
        specs = []
        for mode in param.car_and_van_classes:
            if mode in self._modes:
                self._modes[mode].init_matrices()
                specs.append(self._modes[mode].spec)
        self._spec["classes"] = specs
        return self._spec

    def separate_light_specs(self) -> Generator[Dict[str, Any]]:
        """Yield light vehicle assignment specifications.

        Can be used for assigning car modes sequentially,
        without congestion.
        """
        for mode in param.car_and_van_classes:
            if mode in self._modes:
                self._modes[mode].init_matrices()
                self._spec["classes"] = [self._modes[mode].spec]
                yield self._spec

    def truck_specs(self) -> Generator[Dict[str, Any]]:
        """Yield truck assignment specifications."""
        for mode in param.truck_classes:
            self._modes[mode].init_matrices()
            self._spec["classes"] = [self._modes[mode].spec]
            yield self._spec
