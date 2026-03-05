# Parameters to transform LOS matrices

cost_discount = {
    "hb_edu_student": {
        "transit": 0.5
    }
}

activity_time = {
    "hb_work": 7.2,
    "hb_edu_student": 4.8,
    "hb_grocery": 0.7,
    "hb_other_shop": 1.2,
    "hb_leisure": 2.1,
    "hb_sport": 1.6,
    "hb_visit": 2.4,
    "hb_leisure_overnight": 8.9,
    "hb_business": 4.9,
    "hb_escort": 0.4
}

share_paying = {
    "hb_work": 0.50,
    "hb_edu_student": 0.30,
    "hb_grocery": 1.00,
    "hb_other_shop": 0.15,
    "hb_leisure": 0.75,
    "hb_sport": 0.00,
    "hb_visit": 0.75,
    "hb_leisure_overnight": 1.00,
    "hb_business": 0.5,
    "hb_escort": 0.00
} 

sharing_factor = {
    "hb_work": 0.00,
    "hb_edu_student": 0.50,
    "hb_grocery": 1.00,
    "hb_other_shop": 1.00,
    "hb_leisure": 1.00,
    "hb_sport": 1.00,
    "hb_visit": 0.25,
    "hb_leisure_overnight": 1.00,
    "hb_business": 0.00,
    "hb_escort": 1.00
}

car_drv_occupancy = {
    "hb_work": 1.152,
    "hb_edu_student": 1.445,
    "hb_grocery": 1.530,
    "hb_other_shop": 1.524,
    "hb_leisure": 1.731,
    "hb_sport": 1.651,
    "hb_visit": 1.739,
    "hb_leisure_overnight": 1.822,
    "hb_business": 1.171,
    "hb_escort": 1.81
}

car_pax_occupancy = {
    "hb_work": 2.055,
    "hb_edu_student": 2.238,
    "hb_grocery": 2.395,
    "hb_other_shop": 2.502,
    "hb_leisure": 2.841,
    "hb_sport": 2.791,
    "hb_visit": 2.936,
    "hb_leisure_overnight": 2.836,
    "hb_business": 2.483,
    "hb_escort": 2.89
}

vot = {
    "hb_leisure_overnight": {
        "airplane": 11.4,
        "airpl_car_acc": 11.4,
        "airpl_taxi_acc": 11.4,
        "airpl_car_egr": 11.4,
        "transit": 7.7,
        "pt_car_acc": 7.7,
        "pt_taxi_acc": 7.7,
        "pt_car_egr": 7.7,
        "pt_taxi_egr": 7.7,
        "car_drv": 11.4,
        "car_pax": 11.4,
    },
    "hb_business": {
        "airplane": 11.4,
        "airpl_car_acc": 11.4,
        "airpl_taxi_acc": 11.4,
        "airpl_car_egr": 11.4,
        "transit": 7.7,
        "pt_car_acc": 7.7,
        "pt_taxi_acc": 7.7,
        "pt_car_egr": 7.7,
        "pt_taxi_egr": 7.7,
        "car_drv": 11.4,
        "car_pax": 11.4,
    }
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
