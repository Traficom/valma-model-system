import os
from pathlib import Path
import json
import subprocess


def read_from_file(path=Path(__file__).parent.parent / "dev-config.json"):
    """Read config parameters from json file.

    Parameters
    ----------
    path : Path (optional)
        Path where json file is found (default: Scripts/dev-config.json)

    Returns
    -------
    Config
        Config object with parameters set from file
    """
    with open(path, 'r', encoding='utf-8') as file:
        config = json.load(file)
    return create_config(config)


def dump(args_dict: dict) -> str:
    """Dump config parameters to json.

    Parameters
    ----------
    args_dict : dict
        Parameters from argument parsing

    Returns
    -------
    str
        JSON dump that can be read by `create_config()`
    """
    args_dump = {key.upper(): val for key, val in args_dict.items()
        if not (isinstance(val, bool) or val is None)}
    args_dump["OPTIONAL_FLAGS"] = [key.upper() for key, val in args_dict.items()
        if val is True]
    args_dump["LOG_FORMAT"] = "TEXT"
    return json.dumps(args_dump, indent=4)


def create_config(config: dict):
    """Container for config parameters.

    The parameters are object variables with CAPS_LOCK,
    which means they should not be modified.
    For clarity the normally used parameters are explicitly initialized
    (to None). However, during `Config` initialization, these variables are
    read from a dictionary and hence strictly speaking modified once.

    Parameters
    ----------
    config : dict
        key : str
            Parameter name (e.g., HELMET_VERSION)
        value : str/bool/int/float
            Parameter value
    """
    c = Config()
    c.update({
        "LEM_VERSION": None,
        "JSON": None,
        "SCENARIO_NAME": None,
        "ITERATIONS": None,
        "MAX_GAP": None,
        "REL_GAP": None,
        "LOG_LEVEL": None,
        "LOG_FORMAT": None,
        "BASELINE_DATA_PATH": None,
        "FORECAST_DATA_PATH": None,
        "COST_DATA_PATH": None,
        "RESULTS_PATH": None,
        "SUBMODEL": None,
        "EMME_PATH": None,
        "FIRST_SCENARIO_ID": None,
        "FIRST_MATRIX_ID": None,
        "END_ASSIGNMENT_ONLY": False,
        "CAR_END_ASSIGNMENT_ONLY": False,
        "LONG_DIST_DEMAND_FORECAST": None,
        "FREIGHT_MATRIX_PATH": None,
        "STORED_SPEED_ASSIGNMENT": None,
        "RUN_AGENT_SIMULATION": False,
        "DO_NOT_USE_EMME": False,
        "SEPARATE_EMME_SCENARIOS": False,
        "SAVE_EMME_MATRICES": False,
        "DEL_STRAT_FILES": False,
        "USE_FIXED_TRANSIT_COST": False,
        "DELETE_EXTRA_MATRICES": False,
        "SPECIFY_COMMODITY_NAMES": []
    })
    for key in config.pop("OPTIONAL_FLAGS"):
        c[key] = True
    c.update(config)
    return c


class Config(dict):

    @property
    def VERSION(self):
        """LEM version number from git tag or dev_config.json."""
        os.chdir(Path(__file__).parent)
        try:
            # If model system is in a git repo
            return subprocess.check_output(
                ["git", "describe", "--tags"], stderr=subprocess.STDOUT,
                text=True)
        except (subprocess.CalledProcessError, WindowsError):
            # If model system is downloaded with lem-ui
            return self["LEM_VERSION"]
