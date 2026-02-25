from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Union, Iterable
import os
import sys
# Fiona will search for projection data when setting CRS
os.environ["PROJ_DATA"] = (sys.exec_prefix
                           + "\\Lib\\site-packages\\fiona\\proj_data")
import fiona
from fiona.crs import from_epsg
import pandas


class ResultsData:
    """
    Saves all result data to same folder.
    """
    def __init__(self, results_directory_path: Path):
        self.path = results_directory_path
        self.path.mkdir(parents=True, exist_ok=True)
        self._line_buffer: Dict[str, Any] = {}
        self._df_buffer: Dict[str, Any] = {}

    def flush(self):
        """Save to files and empty buffers."""
        for filename in self._line_buffer:
            self._line_buffer[filename].close()
        self._line_buffer = {}
        for filename in self._df_buffer:
            self._df_buffer[filename].to_csv(
                self.path / filename, sep='\t', float_format="%1.5f",
                header=True)
        self._df_buffer = {}

    def print_data(self,
                   data: Union[pandas.Series, pandas.DataFrame],
                   filename: str):
        """Save data to DataFrame buffer (printed to text file when flushing).

        Parameters
        ----------
        data : pandas.Series or pandas.DataFrame
            Data to add as new column(s) to DataFrame
        filename : str
            Name of file where data is pushed (can contain other data)
        """
        if filename not in self._df_buffer:
            self._df_buffer[filename] = pandas.DataFrame(data)
        else:
            self._df_buffer[filename] = self._df_buffer[filename].merge(
                data, "outer", left_index=True, right_index=True)

    def print_concat(self,
                     data: Union[pandas.Series, pandas.DataFrame],
                     filename: str):
        """Save data to Series buffer (printed to text file when flushing).

        Parameters
        ----------
        data : pandas.Series or pandas.DataFrame
            Data with multi index to add to Series or DataFrame
        filename : str
            Name of file where data is pushed (can contain other data)
        """
        if filename not in self._df_buffer:
            self._df_buffer[filename] = data
        else:
            self._df_buffer[filename] = pandas.concat(
                [self._df_buffer[filename], data])

    def print_line(self, line: str, filename: str):
        """Write text to line in file (closed when flushing).

        Parameters
        ----------
        line : str
            Row of text
        filename : str
            Name of file where text is pushed (can contain other text)
        """
        try:
            buffer = self._line_buffer[filename]
        except KeyError:
            buffer = open(self.path / "{}.txt".format(filename), 'w')
            self._line_buffer[filename] = buffer
        buffer.write(line + "\n")

    def print_matrices(self,
                       data: Dict[str, pandas.DataFrame],
                       filename: str,
                       description: str):
        """Save 2-d matrix data to buffer (printed to file when flushing).

        Saves matrix both in Excel format and as list in text file.

        Parameters
        ----------
        data : dict of pandas.DataFrame
            Data to add as a new sheets to WorkBook
        filename : str
            Name of file where data is pushed (without file extension)
        description : str
            Description of data
        """
        stacked_matrices = pandas.concat(
             {(description, key): df.stack() for key, df in data.items()},
            names=["purpose", "mode", "orig", "dest"])
        stacked_matrices.name = "nr_tours"
        self.print_concat(stacked_matrices, filename + ".txt")

    def print_gpkg(self,
                   records: Iterable[dict],
                   schema: dict,
                   filename: str,
                   layer: str):
        """Save data to layer in GeoPackage file in ETRS-TM35FIN projection.

        See fiona documentation on format of records and schema.
        """
        with fiona.open(
                self.path / filename, 'w', driver="GPKG", layer=layer,
                crs=from_epsg(3067), schema=schema) as colxn:
            colxn.writerecords(records)
