from __future__ import annotations
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Iterable
import openmatrix as omx # type: ignore
import numpy # type: ignore
import pandas
from contextlib import contextmanager
from tables.exceptions import NodeError

if TYPE_CHECKING:
    from datahandling.zonedata import BaseZoneData
import utils.log as log
import parameters.assignment as param


class MatrixData:
    def __init__(self, path: Path):
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def open(self,
             mtx_type: str,
             time_period: str,
             zone_numbers: Optional[numpy.ndarray] = None,
             mapping: Optional[pandas.Series] = None,
             transport_classes: Iterable[str] = param.simple_transport_classes,
             m: str = 'r'):
        file_name = self.path / (mtx_type + '_' + time_period + ".omx")
        mtxfile = MatrixFile(
            omx.open_file(file_name, m), zone_numbers, mapping,
            transport_classes)
        try:
            yield mtxfile
        finally:
            mtxfile.close()


class MatrixFile:
    def __init__(self,
                 omx_file: omx.File,
                 zone_numbers: numpy.ndarray,
                 mapping: pandas.Series,
                 transport_classes: Iterable[str]):
        self._file = omx_file
        self.missing_zones = []
        if mapping is not None:
            extra_mapping = pandas.Series(zone_numbers, zone_numbers)
            mapping = mapping.combine_first(extra_mapping).astype("int32")
            zone_numbers = mapping.index
        self._data_zone_mapping = mapping
        if zone_numbers is None:
            pass
        elif omx_file.mode == 'r':
            path = omx_file.filename
            mtx_numbers = self.zone_numbers
            if (numpy.diff(mtx_numbers) <= 0).any():
                msg = "Zone numbers not in strictly ascending order in file {}".format(
                    path)
                log.error(msg)
                raise IndexError(msg)
            if not numpy.array_equal(mtx_numbers, zone_numbers):
                for i in mtx_numbers:
                    if i not in zone_numbers:
                        msg = "Zone number {} from file {} not found in network".format(
                            i, path)
                        log.error(msg)
                        raise IndexError(msg)
                for i in zone_numbers:
                    if i not in mtx_numbers:
                        self.missing_zones.append(i)
                log.warn("Zone number(s) {} missing from file {}{}".format(
                             self.missing_zones, path,
                             ", adding zero row(s) and column(s)"))
                self.new_zone_numbers = zone_numbers
            ass_classes = self.matrix_list
            for ass_class in transport_classes:
                if ass_class not in ass_classes:
                    msg = "File {} does not contain {} matrix.".format(
                        path, ass_class)
                    log.error(msg)
                    raise IndexError(msg)
        else:
            self.mapping = zone_numbers
    
    def close(self):
        self._file.close()
    
    def __getitem__(self, mode: str):
        mtx = numpy.array(self._file[mode])
        nr_zones = len(self.zone_numbers)
        dim = (nr_zones, nr_zones)
        if mtx.shape != dim:
            msg = "Matrix {} in file {} has dimensions {}, should be {}".format(
                mode, self._file.filename, mtx.shape, dim)
            log.error(msg)
            raise IndexError(msg)
        if numpy.isnan(mtx).any():
            msg = "Matrix {} in file {} contains NA values".format(
                mode, self._file.filename)
            log.error(msg)
            raise ValueError(msg)
        if (mtx < 0).any():
            msg = "Matrix {} in file {} contains negative values".format(
                mode, self._file.filename)
            log.error(msg)
            raise ValueError(msg)
        mtx = pandas.DataFrame(mtx, self.zone_numbers, self.zone_numbers)
        if self.missing_zones:
            mtx = mtx.reindex(
                index=self.new_zone_numbers, columns=self.new_zone_numbers,
                fill_value=0)
        if self._data_zone_mapping is not None:
            for _ in range(2):
                mtx = mtx.groupby(self._data_zone_mapping).agg("sum").T
        return mtx.values

    def __setitem__(self, mode, data):
        try:
            self._file[mode] = data
        except NodeError:
            del self._file[mode]
            self._file[mode] = data

    @property
    def zone_numbers(self):
        return self._file.mapentries("zone_number")

    @property
    def mapping(self):
        return self._file.mapping("zone_number")

    @mapping.setter
    def mapping(self, zone_numbers):
        self._file.create_mapping("zone_number", zone_numbers, overwrite=True)

    @property
    def matrix_list(self):
        return self._file.list_matrices()
