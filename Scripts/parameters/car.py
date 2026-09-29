### CAR DENSITY AND USAGE PARAMETERS ###

# Driver share of car tours
# Inverse of car occupancy
from typing import Any, Dict, Tuple, Union

car_ownership = {
    "adults1_lic1": {
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
                "constant": 0.315740549
            }
        },
        "1": {
            "constant": 3.253071,
            "generation": {
                "sqrt_pop_density": -0.025225,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_1_adult_no_children": -1.579144,
                "sh_income_20_39*sh_hh_1_adult_no_children": -0.781682,
                "sh_income_40_59*sh_hh_1_adult_no_children": 0,
                "sh_income_60_79*sh_hh_1_adult_no_children": 0,
                "sh_income_80_99*sh_hh_1_adult_no_children": 0,
                "sh_income_100_*sh_hh_1_adult_no_children": 0,
                "sh_income_0_19*sh_hh_1_adult_children": -1.579144+0.710698,
                "sh_income_20_39*sh_hh_1_adult_children": -0.781682+0.710698,
                "sh_income_40_59*sh_hh_1_adult_children": 0.710698,
                "sh_income_60_79*sh_hh_1_adult_children": 0.710698,
                "sh_income_80_99*sh_hh_1_adult_children": 0.710698,
                "sh_income_100_*sh_hh_1_adult_children": 0.710698,
            },
            "calibration": {
                "constant": -0.102169711
            },
        }
    },
    "adults2_lic1": {
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
                "constant": 0.318705801
            }
        },
        "1": {
            "constant": 3.423883,
            "generation": {
                "sqrt_pop_density": -0.022518 ,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -0.925358,
                "sh_income_20_39*sh_hh_2_adults_no_children": -0.273038 ,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0,
                "sh_income_100_*sh_hh_2_adults_no_children": 0,
                "sh_income_0_19*sh_hh_2_adults_children": -0.925358+0.022007,
                "sh_income_20_39*sh_hh_2_adults_children": -0.273038+0.022007,
                "sh_income_40_59*sh_hh_2_adults_children": 0.022007,
                "sh_income_60_79*sh_hh_2_adults_children": 0.022007,
                "sh_income_80_99*sh_hh_2_adults_children": 0.022007,
                "sh_income_100_*sh_hh_2_adults_children": 0.022007,
            },
            "calibration": {
                "constant": -0.017934711
            }
        },
    },
    "adults2_lic2": {
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
                "constant": -0.379571216
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
                "constant": -0.045729366
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
                "constant": 0.090096016
            }
        }
    }
}
