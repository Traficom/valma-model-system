# Share of demand that will be simulated in agent model
from typing import Any, Dict, List, Tuple, Union

# O-D pairs with demand below threshold are neglected in sec dest calculation
secondary_destination_threshold = 0.1

agent_demand_fraction = 1.0

# Seed number for population attributes:
# int = fixed seed and same population for each run
# None = different population for each run
population_draw = 31

# Age groups in zone data
age_groups: List[Tuple[int, int]] = [ #changed to list for type checker
        (7, 17),
        (18, 29),
        (30, 49),
        (50, 64),
        (65, 99),
]

### DEMAND MODEL REFERENCES ###

# Tour purpose zone intervals
# Some demand models have separate sub-region parameters,
# hence need sub-intervals defined.
purpose_areas: Dict[str, Tuple[int,int]] = {
    "domestic": (0, 50000),
    "external": (50000, 60000),
    "foreign": (60000, 70000),
    "all": (0, 70000),
}
tour_length_intervals = (0, 3, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100,
                         200, 300, 400, 500, 600, 700, 800, float("inf"))
# Population in noise zones as share of total area population as
# function only of zone area, calculated by Ramboll Feb 2021
pop_share_per_noise_area = {
    "helsinki_cbd": 0.028816313,
    "helsinki_other": 0.005536503,
    "espoo_vant_kau": 0.002148004,
    "surround_train": 0.0019966,
    "surround_other": 0.001407824,
    "peripheral": 0,  # Not calculated
}

# Finnish ports and road border control points
finland_border_points = {
    "FIHEL": {"name": "Vuosaari", "id": 524},
    "FISKV": {"name": "Skoljdvik", "id": 3607},
    "FIHNK": {"name": "Hanko", "id": 4102},
    "FIINK": {"name": "Inkoo", "id": 4201},
    "FIPOR": {"name": "Pori", "id": 10411},
    "FIRAU": {"name": "Rauma", "id": 11233},
    "FITKU": {"name": "Turku", "id": 12548},
    "FIPAR": {"name": "Parainen", "id": 13924},
    "FIUKI": {"name": "Uusikaupunki", "id": 14111},
    "FIVAI": {"name": "Vainikkala", "id": 15106},
    "FILPP": {"name": "Lappeenranta", "id": 15172},
    "FIHMN": {"name": "KotkaHamina", "id": 19401},
    "FIVAL": {"name": "Vaalimaa", "id": 19705},
    "FIJOE": {"name": "Joensuu", "id": 20128},
    "FISII": {"name": "Siilinjarvi", "id": 22126},
    "FIVRK": {"name": "Varkaus", "id": 22623},
    "FIVAR": {"name": "Vartius", "id": 26946},
    "FIKOK": {"name": "Kokkola", "id": 27964},
    "FIHAA": {"name": "Haaparanta", "id": 28615},
    "FIKEM": {"name": "Kemi", "id": 28700},
    "FIKIL": {"name": "Kilpisjarvi", "id": 30219},
    "FIKAS": {"name": "Kaskinen", "id": 31000},
    "FIVAA": {"name": "Vaasa", "id": 31143},
    "FIOUL": {"name": "Oulu", "id": 32855},
    "FIRAA": {"name": "Raahe", "id": 34216},
    "FIKJO": {"name": "Kalajoki", "id": 34611},
}

# Clusters of foreign ports and border control points
cluster_border_points = {
    "AEJEA": {"name": "Jebel Ali", "id": 50100},
    "BRITQ": {"name": "Itaqui", "id": 50101},
    "CIABJ": {"name": "Abidjan", "id": 50102},
    "CNTSN": {"name": "Tianjin", "id": 50103},
    "DEBRV": {"name": "Bremenhaven", "id": 50104},
    "DETRA": {"name": "Travemunde", "id": 50105},
    "DKAAR": {"name": "Aarhus", "id": 50106},
    "EETLL": {"name": "Tallin", "id": 50107},
    "ESLCG": {"name": "La Coruna", "id": 50108},
    "FRLEH": {"name": "Le Havre", "id": 50109},
    "GBFXT": {"name": "Felixstowe", "id": 50110},
    "GRPIR": {"name": "Pireus", "id": 50111},
    "IEDUB": {"name": "Dublin", "id": 50112},
    "ISREK": {"name": "Reykjavik", "id": 50113},
    "ITSVN": {"name": "Savona", "id": 50114},
    "JPNGO": {"name": "Nagoya", "id": 50115},
    "NLRTM": {"name": "Rotterdam", "id": 50116},
    "NOKIL": {"name": "Kilpisjarvi", "id": 50117},
    "NOOSL": {"name": "Oslo", "id": 50118},
    "PLGDY": {"name": "Gdansk", "id": 50119},
    "RUVAI": {"name": "Vainikkala", "id": 50120},
    "RUVAR": {"name": "Vartius", "id": 50121},
    "RUVAL": {"name": "Vaalimaa", "id": 50122},
    "RULED": {"name": "Saint Petersburg", "id": 50123},
    "SEHAA": {"name": "Haaparanta", "id": 50124},
    "SEGOT": {"name": "Goteborg", "id": 50125},
    "SEHLD": {"name": "Umea", "id": 50126},
    "SESTO": {"name": "Stockholm", "id": 50127},
    "SGJUR": {"name": "Singapore", "id": 50128},
    "TRIST": {"name": "Istanbul", "id": 50129},
    "USHOU": {"name": "Houston", "id": 50130},
}
