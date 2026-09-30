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
                "constant": 0.337669791
            }
        },
        "1": {
            "constant": 3.119002,
            "generation": {
                "sqrt_pop_density": -0.024650,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_1_adult_no_children": -1.508132,
                "sh_income_20_39*sh_hh_1_adult_no_children": -0.726566,
                "sh_income_40_59*sh_hh_1_adult_no_children": 0,
                "sh_income_60_79*sh_hh_1_adult_no_children": 0,
                "sh_income_80_99*sh_hh_1_adult_no_children": 0,
                "sh_income_100_*sh_hh_1_adult_no_children": 0,
                "sh_income_0_19*sh_hh_1_adult_children": -1.508132+0.730772,
                "sh_income_20_39*sh_hh_1_adult_children": -0.726566+0.730772,
                "sh_income_40_59*sh_hh_1_adult_children": 0.730772,
                "sh_income_60_79*sh_hh_1_adult_children": 0.730772,
                "sh_income_80_99*sh_hh_1_adult_children": 0.730772,
                "sh_income_100_*sh_hh_1_adult_children": 0.730772,
            },
            "calibration": {
                "constant": -0.079920812
            },
        },
        "2": {
            "constant": 0.422826,
            "generation": {
                "sqrt_pop_density": -0.026257,
                "sh_row_or_detached": 1.293953
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_1_adult_no_children": -2.697716,
                "sh_income_20_39*sh_hh_1_adult_no_children": -1.585601,
                "sh_income_40_59*sh_hh_1_adult_no_children": 0,
                "sh_income_60_79*sh_hh_1_adult_no_children": 0,
                "sh_income_80_99*sh_hh_1_adult_no_children": 0,
                "sh_income_100_*sh_hh_1_adult_no_children": 0,
                "sh_income_0_19*sh_hh_1_adult_children": -2.697716+0.124026,
                "sh_income_20_39*sh_hh_1_adult_children": -1.585601+0.124026,
                "sh_income_40_59*sh_hh_1_adult_children": 0.124026,
                "sh_income_60_79*sh_hh_1_adult_children": 0.124026,
                "sh_income_80_99*sh_hh_1_adult_children": 0.124026,
                "sh_income_100_*sh_hh_1_adult_children": 0.124026,
            },
            "calibration": {
                "constant": -0.510380073
            }
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
                "constant": 0.647576393
            }
        },
        "1": {
            "constant": 3.299670,
            "generation": {
                "sqrt_pop_density": -0.021744,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -0.863270,
                "sh_income_20_39*sh_hh_2_adults_no_children": -0.238043,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0,
                "sh_income_100_*sh_hh_2_adults_no_children": 0,
                "sh_income_0_19*sh_hh_2_adults_children": -0.863270+0.024707,
                "sh_income_20_39*sh_hh_2_adults_children": -0.238043+0.024707,
                "sh_income_40_59*sh_hh_2_adults_children": 0.024707,
                "sh_income_60_79*sh_hh_2_adults_children": 0.024707,
                "sh_income_80_99*sh_hh_2_adults_children": 0.024707,
                "sh_income_100_*sh_hh_2_adults_children": 0.024707,
            },
            "calibration": {
                "constant": 0.329531967
            }
        },
        "2": {
            "constant": 1.449275,
            "generation": {
                "sqrt_pop_density": -0.043928,
                "sh_row_or_detached": 0.106414
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -1.994359,
                "sh_income_20_39*sh_hh_2_adults_no_children": -0.615668,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0.292203,
                "sh_income_80_99*sh_hh_2_adults_no_children": 1.350249,
                "sh_income_100_*sh_hh_2_adults_no_children": 0.612198,
                "sh_income_0_19*sh_hh_2_adults_children": -1.994359+0.040255,
                "sh_income_20_39*sh_hh_2_adults_children": -0.615668+0.040255,
                "sh_income_40_59*sh_hh_2_adults_children": 0.040255,
                "sh_income_60_79*sh_hh_2_adults_children": 0.292203+0.040255,
                "sh_income_80_99*sh_hh_2_adults_children": 1.350249+0.040255,
                "sh_income_100_*sh_hh_2_adults_children": 0.612198+0.040255,
            },
            "calibration": {
                "constant": -0.414033701
            }
        }
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
                "constant": -0.396758559
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
                "constant": -0.04723345
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
                "constant": 0.100527635
            }
        }
    }
}
