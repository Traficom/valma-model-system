# Running the model system

The main entry points are `valma_travel.py` and `valma_freight.py`.
Run `python valma_travel.py --help` to see parameter syntax.
You can also feed parameters from a json file
(`valma_travel.py --json your_file_path`).
The json variable names are the same as `valma_travel.py` parameters,
but with capital letters, and underscore instead of hyphen.
If you run `python valma_travel.py` without parameters,
all parameters will be taken from `dev-config.json`,
which can be used to setup the model run in advance.

## Configuring the model run with json

### `LEM_VERSION`

The version number is logged in model runs.
This should not be changed unless model code is changed.

### `LOG_LEVEL`

Model runs are logged to the command prompt and to a log file.
You can choose the level of detail of logging:
`DEBUG`, `INFO`, `WARNING`, `CRITICAL`, `ERROR`

### `LOG_FORMAT`

The default is `TEXT`, but this can be changed to `JSON`.

### `SCENARIO_NAME`

Then, you need to set the name of your scenario.
If you are trying the test model, write `"test"`.

### `RESULT_DATA_FOLDER`

You need to set the path to your results folder where you wish your
result tables and matrices are written to.
This data will be written over during the model run.

If you are trying the test model, try
`"C:\\FILL_YOUR_PATH\\model-system\\Scripts\\tests\\test_data\\Results"`.
If you are trying another model, fill in whatever the path is.

When running the `SCENARIO_NAME` scenario, its results are written in `RESULT_PATH\\SCENARIO_NAME`.
If you are using mock assignment instead or proper Emme assignment,
you need to initialize temporary result matrices to `RESULT_PATH\\SCENARIO_NAME\\Matrices`.

### `SUBMODEL`

Name of submodel (e.g., "uusimaa", "koko_suomi"),
used for choosing appropriate zone mapping and base matrices.

### `EMME_PATH`

If you are using Emme assignment, you need to specify where your `.emp` file is located.

### `FIRST_SCENARIO_ID`

EMME scenario ID of the network.

### `FIRST_MATRIX_ID`

First matrix ID within EMME project (.emp).
Used only if `SAVE_MATRICES_IN_EMME` is set to `true`.

### `BASE_DATA_FOLDER`

You need data and matrices for the initialization phase.
This data will not be written over at any point - it is read-only.
The location of this data is defined in `BASE_DATA_FOLDER` key.

If you are trying the test model, try
`"C:\\FILL_YOUR_PATH\\model-system\\Scripts\\tests\\test_data\\Base_input_data"`.
If you are trying another model, fill in whatever the path is.

There should be two directiories under the path: `2018_zonedata` and `Matrices`.
The names of these directories are hardcoded.

There are 13 different input vector files in `2018_zonedata` from `.car` to `.wrk`.
In the `2018_zonedata` directory, there must also exist a .zmp file that matches
the name of the chosen [`SUBMODEL`](#submodel),
which maps the data to the zone system of the network.

`Matrices` contains `.omx` files for demand, external traffic and freight traffic.
The matrices may have missing zones (compared to the network), but cannot have extra zones.

### `ZONE_DATA_FILE`

Then, you need zonedata file for the forecast scenario.
This data will also not be written over at any point - it is read-only.
The location of this data is defined in `ZONE_DATA_FILE` key.
Usually this data is in `GPKG` format.

If you are trying the test model, try
`"C:\\FILL_YOUR_PATH\\model-system\\Scripts\\tests\\test_data\\Scenario_input_data\\2030_test\\zonedata_test.gpkg"`.
If you are trying another model, fill in whatever the path is.

### `LONG_DIST_DEMAND_FORECAST`

If 'calc', runs assigment with free-flow speed and calculates demand for long-distance trips.
If 'base', takes long-distance trips from [base matrices](#BASE_DATA_FOLDER).
If path, takes long-distance trips from that path.
The zone system of the long-distance trips in path must match the baseline data
in `2018_zonedata` directory.

### `FREIGHT_MATRIX_PATH`

If specified, take freight demand matrices from path.

### `ITERATIONS`

Maximum number of demand model iterations to run
(each using re-calculated impedance from traffic and transit assignment).

### `MAX_GAP`

Convergence criterion: Car work matrix maximum change between iterations.

### `REL_GAP`

Convergence criterion: Car work matrix relative change between iterations.

### `OPTIONAL_FLAGS`

These should not be used when running model system from command line!
Instead `lem.py` flag parameters should be used.
These can be set if model system is run from UI, to set parameters that cannot be set in UI.
A flag is activated by putting its name inside the brackets,
flags are separated by commas (e.g., `"OPTIONAL_FLAGS": ["RUN_AGENT_SIMULATION", "DO_NOT_USE_EMME"]`).

#### `END_ASSIGNMENT_ONLY`

Using this flag runs only end assignment of base demand matrices.

#### `STORED_SPEED_ASSIGNMENT`

Using this flag runs assigment with stored (fixed) speed.
Forces the number of iterations to one, as speeds will not change.

#### `RUN_AGENT_SIMULATION`

Using this flag runs agent simulations instead of aggregate model.

#### `DO_NOT_USE_EMME`

Add this flag if you do not have the Emme license or wish to use the mock assignment.

#### `SEPARATE_EMME_SCENARIOS`

Using this flag creates four new EMME scenarios and saves
network time-period specific results in them.

#### `SAVE_EMME_MATRICES`

If active, demand and skim matrices (including transit trip parts) for all time
periods will be saved to EMME project Database folder.

#### `DEL_STRAT_FILES`

Transit assignment in EMME stores large files which are used for assignment analyses.
If activated, these files will be deleted after the model run.
