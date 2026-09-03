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
                "constant": 0.349753
            }
        },
        "1": {
            "constant": 3.052168,
            "generation": {
                "sqrt_pop_density": -0.022315,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_1_adult_no_children": -1.551594,
                "sh_income_20_39*sh_hh_1_adult_no_children": -0.592532,
                "sh_income_40_59*sh_hh_1_adult_no_children": 0,
                "sh_income_60_79*sh_hh_1_adult_no_children": 0,
                "sh_income_80_99*sh_hh_1_adult_no_children": 0,
                "sh_income_100_*sh_hh_1_adult_no_children": 0,
                "sh_income_0_19*sh_hh_1_adult_children": -1.551594+0.517062,
                "sh_income_20_39*sh_hh_1_adult_children": -0.592532+0.517062,
                "sh_income_40_59*sh_hh_1_adult_children": 0.517062,
                "sh_income_60_79*sh_hh_1_adult_children": 0.517062,
                "sh_income_80_99*sh_hh_1_adult_children": 0.517062,
                "sh_income_100_*sh_hh_1_adult_children": 0.517062,
            },
            "calibration": {
                "constant": -0.09151
            },
        },
        "2": {
            "constant": 1.052763,
            "generation": {
                "sqrt_pop_density": -0.0336664,
                "sh_row_or_detached": 0.584557
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_1_adult_no_children": -2.852715,
                "sh_income_20_39*sh_hh_1_adult_no_children": -1.645923,
                "sh_income_40_59*sh_hh_1_adult_no_children": 0,
                "sh_income_60_79*sh_hh_1_adult_no_children": 0,
                "sh_income_80_99*sh_hh_1_adult_no_children": 0,
                "sh_income_100_*sh_hh_1_adult_no_children": 0,
                "sh_income_0_19*sh_hh_1_adult_children": -2.852715+0.146780,
                "sh_income_20_39*sh_hh_1_adult_children": -1.645923+0.146780,
                "sh_income_40_59*sh_hh_1_adult_children": 0.146780,
                "sh_income_60_79*sh_hh_1_adult_children": 0.146780,
                "sh_income_80_99*sh_hh_1_adult_children": 0.146780,
                "sh_income_100_*sh_hh_1_adult_children": 0.146780,
            },
            "calibration": {
                "constant": -0.48209
            }
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
                "constant": 0.781539
            }
        },
        "1": {
            "constant": 3.879711,
            "generation": {
                "sqrt_pop_density": -0.022994,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -1.591287,
                "sh_income_20_39*sh_hh_2_adults_no_children": -0.539662,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0,
                "sh_income_100_*sh_hh_2_adults_no_children": 0,
                "sh_income_0_19*sh_hh_2_adults_children": -1.591287+0.144313,
                "sh_income_20_39*sh_hh_2_adults_children": -0.539662+0.144313,
                "sh_income_40_59*sh_hh_2_adults_children": 0.144313,
                "sh_income_60_79*sh_hh_2_adults_children": 0.144313,
                "sh_income_80_99*sh_hh_2_adults_children": 0.144313,
                "sh_income_100_*sh_hh_2_adults_children": 0.144313,
            },
            "calibration": {
                "constant": 0.34848
            }
        },
        "2": {
            "constant": 3.105027,
            "generation": {
                "sqrt_pop_density": -0.041752,
                "sh_row_or_detached": 0.974567
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -3.424101,
                "sh_income_20_39*sh_hh_2_adults_no_children": -1.396488,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0.569071,
                "sh_income_80_99*sh_hh_2_adults_no_children": 1.196244,
                "sh_income_100_*sh_hh_2_adults_no_children": 1.423148,
                "sh_income_0_19*sh_hh_2_adults_children": -3.424101+0.587908,
                "sh_income_20_39*sh_hh_2_adults_children": -1.396488+0.587908,
                "sh_income_40_59*sh_hh_2_adults_children": 0.587908,
                "sh_income_60_79*sh_hh_2_adults_children": 0.569071+0.587908,
                "sh_income_80_99*sh_hh_2_adults_children": 1.196244+0.587908,
                "sh_income_100_*sh_hh_2_adults_children": 1.423148+0.587908,
            },
            "calibration": {
                "constant": -2.49148
            }
        }
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
                "constant": -0.37957
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
                "constant": -0.04573
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
                "constant": 0.090096
            }
        }
    }
}
