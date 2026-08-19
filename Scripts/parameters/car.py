### CAR DENSITY AND USAGE PARAMETERS ###

# Driver share of car tours
# Inverse of car occupancy
from typing import Any, Dict, Tuple, Union

car_ownership = {
    "hh1_lic1": {
        "0": {
            "constant": 0.0,
            "generation": {},
            "individual_dummy": {
                "sh_income_0_19*sh_hh_1_adult_no_children": 0,
                "sh_income_20_39*sh_hh_1_adult_no_children": 0,
                "sh_income_40_59*sh_hh_1_adult_no_children": 0,
                "sh_income_60_79*sh_hh_1_adult_no_children": 0,
                "sh_income_80_99*sh_hh_1_adult_no_children": 0,
                "sh_income_100_*sh_hh_1_adult_no_children": 0,
                "sh_income_0_19*sh_hh_1_adult_children": 0,
                "sh_income_20_39*sh_hh_1_adult_children": 0,
                "sh_income_40_59*sh_hh_1_adult_children": 0,
                "sh_income_60_79*sh_hh_1_adult_children": 0,
                "sh_income_80_99*sh_hh_1_adult_children": 0,
                "sh_income_100_*sh_hh_1_adult_children": 0,
            },
            "calibration": {
                "constant": 0.241671346
            }
        },
        "1": {
            "constant": 3.065065,
            "generation": {
                "sqrt_pop_density": -0.022965,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_1_adult_no_children": -1.553698,
                "sh_income_20_39*sh_hh_1_adult_no_children": -0.580916,
                "sh_income_40_59*sh_hh_1_adult_no_children": 0,
                "sh_income_60_79*sh_hh_1_adult_no_children": 0,
                "sh_income_80_99*sh_hh_1_adult_no_children": 0,
                "sh_income_100_*sh_hh_1_adult_no_children": 0,
                "sh_income_0_19*sh_hh_1_adult_children": -1.553698+0.530891,
                "sh_income_20_39*sh_hh_1_adult_children": -0.580916+0.530891,
                "sh_income_40_59*sh_hh_1_adult_children": 0.530891,
                "sh_income_60_79*sh_hh_1_adult_children": 0.530891,
                "sh_income_80_99*sh_hh_1_adult_children": 0.530891,
                "sh_income_100_*sh_hh_1_adult_children": 0.530891,
            },
            "calibration": {
                "constant": -0.08120386
            },
        }
    },
    "hh2_lic1": {
        "0": {
            "constant": 0.0,
            "generation": {},
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": 0,
                "sh_income_20_39*sh_hh_2_adults_no_children": 0,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0,
                "sh_income_100_*sh_hh_2_adults_no_children": 0,
                "sh_income_0_19*sh_hh_2_adults_children": 0,
                "sh_income_20_39*sh_hh_2_adults_children": 0,
                "sh_income_40_59*sh_hh_2_adults_children": 0,
                "sh_income_60_79*sh_hh_2_adults_children": 0,
                "sh_income_80_99*sh_hh_2_adults_children": 0,
                "sh_income_100_*sh_hh_2_adults_children": 0,
            },
            "calibration": {
                "constant": 0.367440245
            }
        },
        "1": {
            "constant": 3.899001,
            "generation": {
                "sqrt_pop_density": -0.023521,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -1.608033,
                "sh_income_20_39*sh_hh_2_adults_no_children": -0.541490,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0,
                "sh_income_100_*sh_hh_2_adults_no_children": 0,
                "sh_income_0_19*sh_hh_2_adults_children": -1.608033+0.197250,
                "sh_income_20_39*sh_hh_2_adults_children": -0.541490+0.197250,
                "sh_income_40_59*sh_hh_2_adults_children": 0.197250,
                "sh_income_60_79*sh_hh_2_adults_children": 0.197250,
                "sh_income_80_99*sh_hh_2_adults_children": 0.197250,
                "sh_income_100_*sh_hh_2_adults_children": 0.197250,
            },
            "calibration": {
                "constant": -0.048012218
            }
        },
    },
    "hh2_lic2": {
        "0": {
            "constant": 0.0,
            "generation": {},
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": 0,
                "sh_income_20_39*sh_hh_2_adults_no_children": 0,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0,
                "sh_income_100_*sh_hh_2_adults_no_children": 0,
                "sh_income_0_19*sh_hh_2_adults_children": 0,
                "sh_income_20_39*sh_hh_2_adults_children": 0,
                "sh_income_40_59*sh_hh_2_adults_children": 0,
                "sh_income_60_79*sh_hh_2_adults_children": 0,
                "sh_income_80_99*sh_hh_2_adults_children": 0,
                "sh_income_100_*sh_hh_2_adults_children": 0,
            },
            "calibration": {
                "constant": -0.308020961
            }
        },
        "1": {
            "constant": 4.014036,
            "generation": {
                "sqrt_pop_density": -0.020899,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -1.656960,
                "sh_income_20_39*sh_hh_2_adults_no_children": -0.221326,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0,
                "sh_income_100_*sh_hh_2_adults_no_children": 0,
                "sh_income_0_19*sh_hh_2_adults_children": -1.656960+0.374802,
                "sh_income_20_39*sh_hh_2_adults_children": -0.221326+0.374802,
                "sh_income_40_59*sh_hh_2_adults_children": 0.374802,
                "sh_income_60_79*sh_hh_2_adults_children": 0.374802,
                "sh_income_80_99*sh_hh_2_adults_children": 0.374802,
                "sh_income_100_*sh_hh_2_adults_children": 0.374802,
            },
            "calibration": {
                "constant": -0.032973231
            }
        },
        "2": {
            "constant": 4.339155,
            "generation": {
                "sqrt_pop_density": -0.046784,
                "sh_row_or_detached": 0.842144
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -2.615898,
                "sh_income_20_39*sh_hh_2_adults_no_children": -0.829158,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0.361476,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0.571395,
                "sh_income_100_*sh_hh_2_adults_no_children": 1.104780,
                "sh_income_0_19*sh_hh_2_adults_children": -2.615898+0.542211,
                "sh_income_20_39*sh_hh_2_adults_children": -0.829158+0.542211,
                "sh_income_40_59*sh_hh_2_adults_children": 0.542211,
                "sh_income_60_79*sh_hh_2_adults_children": 0.361476+0.542211,
                "sh_income_80_99*sh_hh_2_adults_children": 0.571395+0.542211,
                "sh_income_100_*sh_hh_2_adults_children": 1.104780+0.542211,
            },
            "calibration": {
                "constant": 0.065435697
            }
        }
    }
}
