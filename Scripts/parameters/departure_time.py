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
            # Vans are calculated by multiplying car demand with this share.
            # This is a ratio of total mileage by vans / car driver (Statfi).
            # Peaks are calculated by assuming that vans have even demand distribution through day.
            "aht": (0.10, 0),
            "pt": (0.17, 0),
            "iht": (0.08, 0),
        },
    },
    "external": {
        "icev": {
            "aht": (0.2228, 0.0),
            "pt": (0.507, 0.0),
            "iht": (0.2702, 0.0),
            "it": (0.0, 0.0),
        },
        "bev": {
            "aht": (0.2228, 0.0),
            "pt": (0.507, 0.0),
            "iht": (0.2702, 0.0),
            "it": (0.0, 0.0),
        },
        "phev": {
            "aht": (0.2228, 0.0),
            "pt": (0.507, 0.0),
            "iht": (0.2702, 0.0),
            "it": (0.0, 0.0),
        },
        "airplane": {
            "aht": (0.2135, 0.0),
            "pt": (0.3052, 0.0),
            "iht": (0.2529, 0.0),
            "it": (0.2283, 0.0),
        },
        "transit": {
            "aht": (0.2135, 0.0),
            "pt": (0.3052, 0.0),
            "iht": (0.2529, 0.0),
            "it": (0.2283, 0.0),
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
