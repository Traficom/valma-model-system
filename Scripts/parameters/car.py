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
                "constant": 0
            }
        },
        "1": {
            "constant": 3.661863,
            "generation": {
                "hb_leisure_sustainable": -0.653260,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_1_adult_no_children": -1.488385,
                "sh_income_20_39*sh_hh_1_adult_no_children": -0.500473,
                "sh_income_40_59*sh_hh_1_adult_no_children": 0,
                "sh_income_60_79*sh_hh_1_adult_no_children": 0,
                "sh_income_80_99*sh_hh_1_adult_no_children": 0,
                "sh_income_100_*sh_hh_1_adult_no_children": 0,
                "sh_income_0_19*sh_hh_1_adult_children": -1.488385+0.528040,
                "sh_income_20_39*sh_hh_1_adult_children": -0.500473+0.528040,
                "sh_income_40_59*sh_hh_1_adult_children": 0.528040,
                "sh_income_60_79*sh_hh_1_adult_children": 0.528040,
                "sh_income_80_99*sh_hh_1_adult_children": 0.528040,
                "sh_income_100_*sh_hh_1_adult_children": 0.528040,
            },
            "calibration": {
                "constant": 0
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
                "constant": 0
            }
        },
        "1": {
            "constant": 5.321504,
            "generation": {
                "hb_leisure_sustainable": -0.869877,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -1.833297,
                "sh_income_20_39*sh_hh_2_adults_no_children": -0.673249,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0,
                "sh_income_100_*sh_hh_2_adults_no_children": 0,
                "sh_income_0_19*sh_hh_2_adults_children": -1.833297+0.179828,
                "sh_income_20_39*sh_hh_2_adults_children": -0.673249+0.179828,
                "sh_income_40_59*sh_hh_2_adults_children": 0.179828,
                "sh_income_60_79*sh_hh_2_adults_children": 0.179828,
                "sh_income_80_99*sh_hh_2_adults_children": 0.179828,
                "sh_income_100_*sh_hh_2_adults_children": 0.179828,
            },
            "calibration": {
                "constant": 0
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
                "constant": 0
            }
        },
        "1": {
            "constant": 4.778818,
            "generation": {
                "hb_leisure_sustainable": -0.694607,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -1.657740,
                "sh_income_20_39*sh_hh_2_adults_no_children": -0.238010,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0,
                "sh_income_100_*sh_hh_2_adults_no_children": 0,
                "sh_income_0_19*sh_hh_2_adults_children": -1.657740+0.397982,
                "sh_income_20_39*sh_hh_2_adults_children": -0.238010+0.397982,
                "sh_income_40_59*sh_hh_2_adults_children": 0.397982,
                "sh_income_60_79*sh_hh_2_adults_children": 0.397982,
                "sh_income_80_99*sh_hh_2_adults_children": 0.397982,
                "sh_income_100_*sh_hh_2_adults_children": 0.397982,
            },
            "calibration": {
                "constant": 0
            }
        },
        "2": {
            "constant": 5.677953,
            "generation": {
                "hb_leisure_sustainable": -1.074284,
            },
            "individual_dummy": {
                "sh_income_0_19*sh_hh_2_adults_no_children": -2.824242,
                "sh_income_20_39*sh_hh_2_adults_no_children": -0.947093,
                "sh_income_40_59*sh_hh_2_adults_no_children": 0,
                "sh_income_60_79*sh_hh_2_adults_no_children": 0.331296,
                "sh_income_80_99*sh_hh_2_adults_no_children": 0.535889,
                "sh_income_100_*sh_hh_2_adults_no_children": 0.959502,
                "sh_income_0_19*sh_hh_2_adults_children": -2.824242+0.650635,
                "sh_income_20_39*sh_hh_2_adults_children": -0.947093+0.650635,
                "sh_income_40_59*sh_hh_2_adults_children": 0.650635,
                "sh_income_60_79*sh_hh_2_adults_children": 0.331296+0.650635,
                "sh_income_80_99*sh_hh_2_adults_children": 0.535889+0.650635,
                "sh_income_100_*sh_hh_2_adults_children": 0.959502+0.650635,
            },
            "calibration": {
                "constant": 0
            }
        }
    }
}
