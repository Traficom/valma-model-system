from pathlib import Path
import parameters.assignment as param
import numpy
from typing import Dict

def transform_traversal_data(result_path: Path, zones: list) -> Dict[str, numpy.ndarray]:
    """Processes freight model specific traversal files containing information 
    on amount of transported tons between gate pair as auxiliary demand.

    Parameters
    ----------
    result_path : Path
        result path where traversal files are located
    zones : list
        zones in network

    Returns
    ----------
    dict
        freight transit mode : numpy.ndarray
    """
    aux_tons = {}
    for ass_class in param.freight_modes:
        file = result_path / f"{ass_class}.txt"
        if file.exists():
            aux_tons[ass_class] = read_traversal_file(file, numpy.array(zones))
            file.unlink()
    return aux_tons

def read_traversal_file(file: Path, zones: numpy.ndarray):
    """Creates assingment class specific traversal file where
    index based cell values are inserted.

    Parameters
    ----------
    file : Path
        path of assignment class specific traversal file
    zones : numpy.ndarray
        zones in network

    Returns
    ----------
    numpy matrix
        ass class specific traversal matrix
    """
    traversal_matrix = numpy.zeros([len(zones), len(zones)], dtype=numpy.float32)
    with open(file) as f:
        lines = f.readlines()
        for line in lines:
            data = line.split()
            try:
                int(data[0])
            except ValueError:
                continue
            row_index = numpy.searchsorted(zones, numpy.int32(data[0]))
            col_index = numpy.searchsorted(zones, numpy.int32(data[1]))
            try:
                cell_value = numpy.float32(data[2])
            except ValueError:
                cell_value = parse_cell_value(data[2])
            traversal_matrix[row_index, col_index] += cell_value
    return traversal_matrix

def parse_cell_value(cell: str):
    """Parses engineering notation based auxiliary tons for
    a given matrix cell of a traversal file. Unit mapping is based
    on Emme's engineering notation syntax.

    Parameters
    ----------
    cell : str
        cell as a string to parse

    Returns
    ----------
    float32
        parsed cell value 
    """
    units = {
        "p": 10 ** -12,
        "n": 10 ** -9,
        "u": 10 ** -6,
        "m": 10 ** -3,
        ".": 1,
        "k": 10 ** 3,
        "M": 10 ** 6,
        "G": 10 ** 9,
        "T": 10 ** 12,
    }
    for i, char in enumerate(cell):
        if char in units.keys():
            value = f"{cell[:i]}.{cell[i+1:]}"
            return numpy.float32(value) * units[char]
