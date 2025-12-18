from __future__ import annotations
from typing import TYPE_CHECKING, Dict
import numpy

import utils.log as log
if TYPE_CHECKING:
    from assignment.emme_bindings.emme_project import EmmeProject


class EmmeMatrix:
    """Container for EMME matrix.

    To actually create the EMME matrix (which is a file),
    `init` method must be called.
    Disk storage can be released by calling `release`.
    After release, `init` must be called again to be able to set the matrix.
    """

    id_counter = 0

    def __init__(self, name: str, description: str, emme_project: EmmeProject,
                 scenario_id: int, default_value: float = 99999):
        """Initialize container.

        Parameters
        ----------
        name : str
            Short name (e.g., "time")
        description : str
            Long name used in EMME (e.g., "time_transit_work_aht")
        emme_project : assignment.emme_bindings.emme_project.EmmeProject
            Emme project connected to this assignment
        scenario_id : int
            Id of EMME scenario
        default_value : float (optional)
            Can be set to a number, otherwise it is 99999
        """
        EmmeMatrix.id_counter +=1
        self._id = EmmeMatrix.id_counter
        self.name = name
        self.description = description
        self.default_value = default_value
        self._emme_project = emme_project
        self._scenario_id = scenario_id

    @property
    def id(self):
        return f"mf{self._id}"

    def init(self):
        """Create (overwrite if exists) matrix in EMME and set to default."""
        emmebank = self._emme_project.modeller.emmebank
        if emmebank.matrix(self.id) is not None:
            emmebank.delete_matrix(self.id)
        self._emme_project.create_matrix(
            self.id, self.description, self.description, self.default_value)

    def set(self, matrix: numpy.ndarray):
        if numpy.isnan(matrix).any():
            msg = ("NAs in demand matrix "
                   + "would cause infinite loop in Emme assignment.")
            log.error(msg)
            raise ValueError(msg)
        else:
            (self._emme_project.modeller.emmebank.matrix(self.id)
             .set_numpy_data(matrix, scenario_id=self._scenario_id))

    @property
    def data(self) -> numpy.ndarray:
        try:
            return (self._emme_project.modeller.emmebank.matrix(self.id)
                    .get_numpy_data(scenario_id=self._scenario_id))
        except AttributeError:
            raise AttributeError(f"Matrix {self.description} not found")

    @property
    def item(self):
        return {self.name: self.data}

    def release(self):
        """Remove matrix from EMME if not `PermanentEmmeMatrix.`"""
        self._emme_project.modeller.emmebank.delete_matrix(self.id)

    def hard_release(self):
        """Remove matrix from EMME (without exceptions)."""
        emmebank = self._emme_project.modeller.emmebank
        if emmebank.matrix(self.id) is not None:
            emmebank.delete_matrix(self.id)


class PermanentEmmeMatrix(EmmeMatrix):
    """Container for EMME matrix.

    This immediately creates the EMME matrix (which is a file).
    It will exist through the whole model run, and calling `release`
    will not affect that.
    """
    def __init__(self, *args, **kwargs):
        EmmeMatrix.__init__(self, *args, **kwargs)
        EmmeMatrix.init(self)

    def init(self):
        pass

    def release(self):
        pass
