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
                "constant": 0.295158762
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
                "constant": -0.09826214
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
                "constant": 0.432910651
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
                "constant": -0.05476665
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
                "constant": -0.35784365
            }
        },
        "1": {
            "constant": 4.015710,
            "generation": {
                "sqrt_pop_density": -0.020883,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -1.663979,
                "sh_income_20_39*sh_hh_2_adults_no_children": -0.225171,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0,
                "sh_income_100_*sh_hh_2_adults_no_children": 0,
                "sh_income_0_19*sh_hh_2_adults_children": -1.663979+0.379870,
                "sh_income_20_39*sh_hh_2_adults_children": -0.225171+0.379870,
                "sh_income_40_59*sh_hh_2_adults_children": 0.379870,
                "sh_income_60_79*sh_hh_2_adults_children": 0.379870,
                "sh_income_80_99*sh_hh_2_adults_children": 0.379870,
                "sh_income_100_*sh_hh_2_adults_children": 0.379870,
            },
            "calibration": {
                "constant": -0.01644901
            }
        },
        "2": {
            "constant": 5.160160,
            "generation": {
                "sqrt_pop_density": -0.055125,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -2.635365,
                "sh_income_20_39*sh_hh_2_adults_no_children": -0.866118,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0.363252,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0.590681,
                "sh_income_100_*sh_hh_2_adults_no_children": 1.133864,
                "sh_income_0_19*sh_hh_2_adults_children": -2.635365+0.573108,
                "sh_income_20_39*sh_hh_2_adults_children": -0.866118+0.573108,
                "sh_income_40_59*sh_hh_2_adults_children": 0.573108,
                "sh_income_60_79*sh_hh_2_adults_children": 0.363252+0.573108,
                "sh_income_80_99*sh_hh_2_adults_children": 0.590681+0.573108,
                "sh_income_100_*sh_hh_2_adults_children": 1.133864+0.573108,
            },
            "calibration": {
                "constant": 0.061056609
            }
        }
    }
}
