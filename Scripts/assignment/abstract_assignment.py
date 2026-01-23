from __future__ import annotations
from abc import ABCMeta, abstractmethod
from typing import Any, Dict, List, Union
import numpy


class AssignmentModel:
    __metaclass__ = ABCMeta

    assignment_periods: List[Period]

    @property
    @abstractmethod
    def mapping(self) -> Dict[int,int]:
        """Dictionary of zone numbers and corresponding indices."""
        pass

    @property
    @abstractmethod
    def zone_numbers(self) -> List[int]:
        pass

    @property
    @abstractmethod
    def nr_zones(self) -> int:
        pass

    @abstractmethod
    def calc_transit_cost(self, fares):
        pass

    @abstractmethod
    def aggregate_results(self, resultdatawriter):
        pass

    @abstractmethod
    def prepare_network(self, car_dist_unit_cost=None, *args):
        pass

    @abstractmethod
    def init_assign(self):
        pass

class Period:
    __metaclass__ = ABCMeta

    name: str
    assignment_modes: List[str]

    @abstractmethod
    def assign_trucks_init(self):
        pass

    @abstractmethod
    def assign(self) -> Dict[str, Dict[str, numpy.ndarray]]:
        pass

    @abstractmethod
    def end_assign(self) -> Dict[str, Dict[str, numpy.ndarray]]:
        pass

    @abstractmethod
    def get_matrix(self, ass_class: str) -> numpy.ndarray:
        pass

    @abstractmethod
    def set_matrix(self,
                    ass_class: str,
                    matrix: numpy.ndarray):
        pass
