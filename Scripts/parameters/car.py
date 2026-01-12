### CAR DENSITY AND USAGE PARAMETERS ###

# Driver share of car tours
# Inverse of car occupancy
from typing import Any, Dict, Tuple, Union


car_driver_share = { }

car_usage: Dict[str,Any] = {
    "constant": 0.0,
    "generation": {},
    "log": { },
    "individual_dummy": { },
}
car_density = {
    "constant": 0.0,
    "generation": { },
    "log": { },
}
car_ownership = {
    "hh1": {
        "0": {
            "constant": 0.0,
            "generation": {},
            "individual_dummy": {
                "sh_income_0_19": 0,
                "sh_income_20_39": 0,
                "sh_income_40_59": 0,
                "sh_income_60_79": 0,
                "sh_income_80_99": 0,
                "sh_income_100_": 0
            },
            "calibration": {
                "constant": 0.382845731
            }
        },
        "1": {
            "constant": 3.221865,
            "generation": {
                "hb_leisure_sustainable": -0.099956,
                "sh_row_or_detached": 0.723959,
                "avg_park_time": -0.213470
            },
            "individual_dummy": {
                "sh_income_0_19": -2.003805,
                "sh_income_20_39": -0.761191,
                "sh_income_40_59": 0,
                "sh_income_60_79": 0,
                "sh_income_80_99": 0,
                "sh_income_100_": 0
            },
            "calibration": {
                "constant": -0.27793487
            },
        }
    },
    "hh2": {
        "0": {
            "constant": 0.0,
            "generation": {},
            "individual_dummy": {
                "sh_income_0_19": 0,
                "sh_income_20_39": 0,
                "sh_income_40_59": 0,
                "sh_income_60_79": 0,
                "sh_income_80_99": 0,
                "sh_income_100_": 0
            },
            "calibration": {
                "constant": 0.081983161
            }
        },
        "1": {
            "constant": 3.477066,
            "generation": {
                "hb_leisure_sustainable": -0.224521,
                "sh_row_or_detached": 1.361005,
                "avg_park_time": -0.102693
            },
            "individual_dummy": {
                "sh_income_0_19": -2.006058,
                "sh_income_20_39": -0.722163,
                "sh_income_40_59": 0,
                "sh_income_60_79": 0,
                "sh_income_80_99": 0,
                "sh_income_100_": 0
            },
            "calibration": {
                "constant": -0.014866763
            }
        },
        "2": {
            "constant": 5.380643,
            "generation": {
                "hb_leisure_sustainable": -0.396650,
                "sh_row_or_detached": 1.934757,
                "avg_park_time": -0.482368
            },
            "individual_dummy": {
                "sh_income_0_19": -3.305633,
                "sh_income_20_39": -1.418181,
                "sh_income_40_59": 0,
                "sh_income_60_79": 0.424536,
                "sh_income_80_99": 0.730079,
                "sh_income_100_": 1.241246
            },
            "calibration": {
                "constant": -0.007232359
            }
        }
    },
    "hh3": {
        "0": {
            "constant": 0.0,
            "generation": {},
            "individual_dummy": {
                "sh_income_0_19": 0,
                "sh_income_20_39": 0,
                "sh_income_40_59": 0,
                "sh_income_60_79": 0,
                "sh_income_80_99": 0,
                "sh_income_100_": 0
            },
            "calibration": {
                "constant": -0.071076673
            }
        },
        "1": {
            "constant": 3.646567,
            "generation": {
                "hb_leisure_sustainable": -0.224521,
                "sh_row_or_detached": 1.361005,
                "avg_park_time": -0.102693
            },
            "individual_dummy": {
                "sh_income_0_19": -2.006058,
                "sh_income_20_39": -0.722163,
                "sh_income_40_59": 0,
                "sh_income_60_79": 0,
                "sh_income_80_99": 0,
                "sh_income_100_": 0
            },
            "calibration": {
                "constant": -0.100249666
            }
        },
        "2": {
            "constant": 6.328425,
            "generation": {
                "hb_leisure_sustainable": -0.396650,
                "sh_row_or_detached": 1.934757,
                "avg_park_time": -0.482368
            },
            "individual_dummy": {
                "sh_income_0_19": -3.305633,
                "sh_income_20_39": -1.418181,
                "sh_income_40_59": 0,
                "sh_income_60_79": 0.424536,
                "sh_income_80_99": 0.730079,
                "sh_income_100_": 1.241246
            },
            "calibration": {
                "constant": 0.094130157
            }
        }
    }
}
