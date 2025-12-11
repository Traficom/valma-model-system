### DEPARTURE TIME PARAMETERS ###

# Demand shares for different time periods
from typing import Any, Dict


demand_share: Dict[str,Dict[str,Any]] = {
    "freight": {
        "trailer_truck": {
            "aht": (0.066, 0),
            "pt": (0.07, 0),
            "iht": (0.066, 0),
        },
        "truck": {
            "aht": (0.066, 0),
            "pt": (0.07, 0),
            "iht": (0.066, 0),
        },
        "van": {
            # As shares of car traffic
            # On top of this, the trucks sum is added
            "aht": (0.054, 0),
            "pt": (0.07, 0),
            "iht": (0.044, 0),
        },
    },
    "external": {
        "car_work": {
            "aht": (0.321, 0.0),
            "pt": (0.403, 0.0),
            "iht": (0.277, 0.0),
            "it": (0.0, 0.0),
        },
        "car_leisure": {
            "aht": (0.0601, 0.0),
            "pt": (0.691, 0.0),
            "iht": (0.249, 0.0),
            "it": (0.0, 0.0),
        },
        "train": {
            "aht": (0.200, 0.0),
            "pt": (0.327, 0.0),
            "iht": (0.270, 0.0),
            "it": (0.203, 0.0),
        },
        "airplane": {
            "aht": (0.200, 0.0),
            "pt": (0.327, 0.0),
            "iht": (0.270, 0.0),
            "it": (0.203, 0.0),
        },
        "coach": {
            "aht": (0.200, 0.0),
            "pt": (0.327, 0.0),
            "iht": (0.270, 0.0),
            "it": (0.203, 0.0),
        },
        "trailer_truck": {
            "aht": (0.33, 0.0),
            "pt": (0.34, 0.0),
            "iht": (0.33, 0.0),
        },
        "semi_trailer": {
            "aht": (0.33, 0.0),
            "pt": (0.34, 0.0),
            "iht": (0.33, 0.0),
        },
        "truck": {
            "aht": (0.33, 0.0),
            "pt": (0.34, 0.0),
            "iht": (0.33, 0.0),
        },
    },
}
backup_demand_share = {
    "aht": (0.042, 0.028),
    "pt": (0.05, 0.05),
    "iht": (0.045, 0.055),
}
