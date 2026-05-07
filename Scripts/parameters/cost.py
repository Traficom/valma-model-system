# Parameters to transform LOS matrices

value_of_time = {  # [eur/hour]
    "car": 9.18,
    "transit": 7.3,
    "airplane": 11.4,
    "pt_car_acc": 7.7,
    "pt_taxi_acc": 7.7,
    "airpl_car_acc": 11.4,
    "pt_car_egr": 7.7,
    "pt_taxi_egr": 7.7,
    "airpl_car_egr": 11.4,
    "van": 29.02,
}

tour_duration = {
    "pt_car_acc": {
        "avg": 2.18,
        "hb_business": 1.12,
        "hb_leisure_overnight": 9,
    },
    "pt_taxi_acc": {
        "avg": 2.18,
        "hb_business": 1.12,
        "hb_leisure_overnight": 9,
    },
    "airpl_car_acc": {
        "avg": 2.39,
        "hb_business": 2.01,
        "hb_leisure_overnight": 9,
    },
    "pt_car_egr": {
        "avg": 2.18,
        "hb_business": 1.12,
        "hb_leisure_overnight": 9,
    },
    "pt_taxi_egr": {
        "avg": 2.18,
        "hb_business": 1.12,
        "hb_leisure_overnight": 9,
    },
    "airpl_car_egr": {
        "avg": 2.39,
        "hb_business": 2.01,
        "hb_leisure_overnight": 9,
    }
}
