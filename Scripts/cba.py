from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path

import numpy
import pandas
from openpyxl import load_workbook
from openpyxl.utils.dataframe import dataframe_to_rows

import utils.config
import utils.log as log
import parameters.assignment as param
from datahandling.matrixdata import MatrixData


VEHICLE_KMS_FILE = "vehicle_kilometers_by_road_class.txt"
TRANSIT_KMS_FILE = "transit_kms.txt"
LINK_LENGTH_FILE = "link_lengths.txt"

BASE_TIME_PERIODS = ("aht", "pt", "iht")
OPTIONAL_TIME_PERIODS = ("it",)
BENEFIT_MATRIX_TYPES = ("time", "cost", "dist")
MAX_VALID_SKIM_VALUE = 1e10
WORKBOOK_TEMPLATE = Path(__file__).resolve().parent / "CBA_kehikko.xlsx"
CBA_TRANSPORT_CLASSES = param.transport_classes + ("walk",)


def _resolve_scenario_path(scenario, results_path):
    """Accept either a result-folder path or a scenario name under results_path."""
    scenario_path = Path(scenario)
    if scenario_path.is_dir():
        return scenario_path.resolve()
    scenario_path = Path(results_path) / scenario_path
    if scenario_path.is_dir():
        return scenario_path.resolve()
    raise FileNotFoundError(
        f"Could not find scenario results directory for '{scenario}'. "
        f"Checked '{Path(scenario).resolve()}' and '{scenario_path.resolve()}'."
    )


def _scenario_result_directory(scenario_path, submodel):
    return scenario_path / "aggregated_results" / submodel


def _scenario_matrix_directories(scenario_path, submodel):
    demand_path = scenario_path / "demand_matrices" / submodel
    los_path = scenario_path / "los_matrices" / submodel
    if demand_path.is_dir() and los_path.is_dir():
        return demand_path, los_path
    raise FileNotFoundError(
        f"Could not locate current-model demand and LOS matrices for "
        f"'{scenario_path}'. Expected 'demand_matrices/{submodel}' and "
        f"'los_matrices/{submodel}'."
    )


def _matrix_file_exists(matrix_path, matrix_type, time_period):
    return (matrix_path / f"{matrix_type}_{time_period}.omx").is_file()


def _available_periods(scenario_matrix_paths):
    periods = []
    for time_period in BASE_TIME_PERIODS:
        if all(
            _matrix_file_exists(demand_path, "demand", time_period)
            and all(
                _matrix_file_exists(los_path, matrix_type, time_period)
                for matrix_type in BENEFIT_MATRIX_TYPES
            )
            for demand_path, los_path in scenario_matrix_paths
        ):
            periods.append(time_period)
        else:
            raise FileNotFoundError(
                f"Required CBA matrices for time period '{time_period}' were "
                "not found in both scenarios."
            )

    for time_period in OPTIONAL_TIME_PERIODS:
        available = [
            _matrix_file_exists(demand_path, "demand", time_period)
            and all(
                _matrix_file_exists(los_path, matrix_type, time_period)
                for matrix_type in BENEFIT_MATRIX_TYPES
            )
            for demand_path, los_path in scenario_matrix_paths
        ]
        if all(available):
            periods.append(time_period)
        elif any(available):
            log.warn(
                f"Ignoring optional time period '{time_period}': its complete "
                "matrix set is not available for both scenarios."
            )
    return periods


def _read_matrix_zones(matrix_data, time_period):
    with matrix_data.open(
        "demand", time_period, transport_classes=()
    ) as matrices:
        return matrices.zone_numbers.copy(), set(matrices.matrix_list)


def _read_skim_classes(matrix_data, matrix_type, time_period):
    with matrix_data.open(
        matrix_type, time_period, transport_classes=()
    ) as matrices:
        return set(matrices.matrix_list)


def _matrix_data_for_scenario(scenario_path, submodel):
    demand_path, los_path = _scenario_matrix_directories(
        scenario_path, submodel
    )
    return MatrixData(demand_path), MatrixData(los_path), (demand_path, los_path)


def run_cost_benefit_analysis(
    scenario_0,
    scenario_1,
    year,
    workbook=None,
    submodel="uusimaa",
    benefit_summary=None,
    revenue_summary=None,
):
    """Calculate consumer and producer benefits from current model matrices.

    Scenario arguments are result directory paths. Demand and LOS matrices are
    read from their current-model output directories.
    """
    if year not in (1, 2):
        raise ValueError("Evaluation year must be either 1 or 2")

    scenario_paths = (Path(scenario_0), Path(scenario_1))
    matrix_data = [
        _matrix_data_for_scenario(path, submodel) for path in scenario_paths
    ]
    periods = _available_periods([data[2] for data in matrix_data])

    results = defaultdict(float)
    all_zone_numbers = set()

    for time_period in periods:
        demand_matrices = [item[0] for item in matrix_data]
        los_matrices = [item[1] for item in matrix_data]
        scenario_zones = []
        available_classes = []
        for demand_data in demand_matrices:
            zones, matrix_classes = _read_matrix_zones(
                demand_data, time_period
            )
            scenario_zones.append(zones)
            available_classes.append(matrix_classes)

        zone_numbers = numpy.union1d(*scenario_zones)
        all_zone_numbers.update(zone_numbers.tolist())
        shared_classes = set.intersection(*available_classes)
        unpaired_classes = set.union(*available_classes) - shared_classes
        if unpaired_classes:
            raise ValueError(
                f"Demand matrix classes differ between scenarios for "
                f"'{time_period}': {sorted(unpaired_classes)}"
            )
        unsupported_classes = shared_classes - set(CBA_TRANSPORT_CLASSES)
        if unsupported_classes:
            raise ValueError(
                f"Demand matrix classes are not configured for CBA in "
                f"'{time_period}': {sorted(unsupported_classes)}"
            )
        skim_classes = {
            matrix_type: [
                _read_skim_classes(los_data, matrix_type, time_period)
                for los_data in los_matrices
            ]
            for matrix_type in BENEFIT_MATRIX_TYPES
        }

        for transport_class in CBA_TRANSPORT_CLASSES:
            if transport_class not in shared_classes:
                continue
            if time_period not in param.volume_factors.get(
                transport_class, {}
            ):
                continue

            demand = {}
            for label, demand_data in zip(("scen_0", "scen_1"), demand_matrices):
                with demand_data.open(
                    "demand",
                    time_period,
                    zone_numbers=zone_numbers,
                    transport_classes=(),
                ) as matrices:
                    demand[label] = matrices[transport_class]

            volume_factor = param.volume_factors[transport_class][time_period]
            for matrix_type in BENEFIT_MATRIX_TYPES:
                if (
                    transport_class in ("bike", "walk")
                    and matrix_type == "cost"
                ):
                    costs = {"scen_0": 0.0, "scen_1": 0.0}
                else:
                    class_availability = [
                        transport_class in classes
                        for classes in skim_classes[matrix_type]
                    ]
                    if class_availability[0] != class_availability[1]:
                        raise ValueError(
                            f"Skim class '{transport_class}' is present in "
                            f"only one scenario for '{matrix_type}_{time_period}'."
                        )
                    if not all(class_availability):
                        log.warn(
                            f"Skipping {matrix_type} benefit for "
                            f"'{transport_class}' in '{time_period}': "
                            "this skim is not produced by the current model."
                        )
                        if benefit_summary is not None:
                            benefit_summary.append(
                                {
                                    "Year": year,
                                    "Time period": time_period,
                                    "Transport class": transport_class,
                                    "Measure": matrix_type,
                                    "Status": "not produced by the model",
                                }
                            )
                        continue
                    costs = {
                        label: read_costs(
                            los_data,
                            time_period,
                            transport_class,
                            matrix_type,
                            zone_numbers,
                        )
                        for label, los_data in zip(
                            ("scen_0", "scen_1"), los_matrices
                        )
                    }
                existing, additional = calc_gains(demand, costs)
                metric_name = f"{transport_class}_{matrix_type}"
                result = volume_factor * (existing + additional)
                if metric_name in results:
                    results[metric_name] += result
                else:
                    results[metric_name] = result

                if benefit_summary is not None:
                    benefit_summary.append(
                        {
                            "Year": year,
                            "Time period": time_period,
                            "Transport class": transport_class,
                            "Measure": matrix_type,
                            "Existing users": float(existing.sum()),
                            "Additional users": float(additional.sum()),
                            "Combined result": float(
                                (existing + additional).sum()
                            ),
                            "Volume factor": volume_factor,
                        }
                    )

                if matrix_type == "cost":
                    revenue = calc_revenue(demand, costs)
                    if (
                        transport_class in param.transit_classes
                        or transport_class in param.assignment_modes
                    ):
                        results[f"{transport_class}_revenue"] += (
                            volume_factor * revenue
                        )
                        if revenue_summary is not None:
                            revenue_summary.append(
                                {
                                    "Year": year,
                                    "Time period": time_period,
                                    "Transport class": transport_class,
                                    "Revenue difference": float(revenue.sum()),
                                    "Volume factor": volume_factor,
                                    "Expanded revenue difference": float(
                                        (volume_factor * revenue).sum()
                                    ),
                                }
                            )

    if not all_zone_numbers:
        raise ValueError("No demand matrices were found for the requested CBA.")
    if not results:
        raise ValueError(
            "Demand matrices were found, but no transport classes have "
            "matching CBA volume factors for the available time periods."
        )
    result = pandas.DataFrame(results, index=sorted(all_zone_numbers))
    if workbook is not None:
        zone_table = result.stack().rename("Value").reset_index()
        zone_table.columns = ("Zone", "Measure", "Value")
        zone_table.insert(0, "Year", year)
        _write_sheet(workbook, "Zone Results", zone_table)
    return result


def read_costs(matrixdata, time_period, transport_class, mtx_type,
               zone_numbers=None):
    if transport_class == "bike" and mtx_type == "cost":
        return 0

    with matrixdata.open(
        mtx_type,
        time_period,
        zone_numbers=zone_numbers,
        transport_classes=(),
    ) as matrices:
        return matrices[transport_class]


def calc_gains(demands, costs):
    """Calculate differences in user benefits by origin zone."""
    gain = costs["scen_1"] - costs["scen_0"]
    demand_change = demands["scen_1"] - demands["scen_0"]
    demand_incr = demand_change >= 0
    demand_decr = demand_change < 0

    cost_0 = numpy.asarray(costs["scen_0"])
    cost_1 = numpy.asarray(costs["scen_1"])
    valid_costs = (
        numpy.isfinite(cost_0)
        & numpy.isfinite(cost_1)
        & (cost_0 <= MAX_VALID_SKIM_VALUE)
        & (cost_1 <= MAX_VALID_SKIM_VALUE)
    )
    gain = numpy.where(valid_costs, gain, 0)
    demand_incr = numpy.logical_and(demand_incr, valid_costs)
    demand_decr = numpy.logical_and(demand_decr, valid_costs)

    gains_existing = numpy.zeros_like(demand_change, dtype=float)
    gains_existing[demand_incr] = (
        demands["scen_0"] * gain
    )[demand_incr]
    gains_existing[demand_decr] = (
        demands["scen_1"] * gain
    )[demand_decr]
    gains_additional = numpy.zeros_like(demand_change, dtype=float)
    gains_additional[demand_incr] = (
        0.5 * demand_change * gain
    )[demand_incr]
    gains_additional[demand_decr] = (
        -0.5 * demand_change * gain
    )[demand_decr]

    if gains_additional.sum() > 1e9:
        log.warn(
            "Gains for additional users are very high: "
            f"{gains_additional.sum():.2f}"
        )
    return gains_existing.sum(axis=0), gains_additional.sum(axis=0)


def calc_revenue(demands, costs):
    """Calculate the producer-revenue difference by origin zone."""
    demand_change = demands["scen_1"] - demands["scen_0"]
    demand_incr = demand_change >= 0
    demand_decr = demand_change < 0

    cost_0, cost_1 = numpy.broadcast_arrays(
        numpy.asarray(costs["scen_0"]),
        numpy.asarray(costs["scen_1"]),
    )
    valid_costs = (
        numpy.isfinite(cost_0)
        & numpy.isfinite(cost_1)
        & (cost_0 <= MAX_VALID_SKIM_VALUE)
        & (cost_1 <= MAX_VALID_SKIM_VALUE)
    )
    cost_0 = numpy.where(valid_costs, cost_0, 0)
    cost_1 = numpy.where(valid_costs, cost_1, 0)
    cost_change = cost_1 - cost_0
    revenue = numpy.zeros_like(demand_change, dtype=float)
    revenue[demand_incr] = (
        (cost_1 * demand_change + cost_change * demands["scen_0"])
    )[demand_incr]
    revenue[demand_decr] = (
        (cost_0 * demand_change + cost_change * demands["scen_1"])
    )[demand_decr]
    return revenue.sum(axis=0)


def _read_report_table(result_directory, file_name):
    path = Path(result_directory) / file_name
    if not path.is_file():
        return None
    return pandas.read_csv(
        path,
        sep=r"\s+",
        index_col=0,
    )


def _read_road_mileage(result_directory):
    path = Path(result_directory) / VEHICLE_KMS_FILE
    if not path.is_file():
        return None
    table = pandas.read_csv(path, sep=r"\s+", index_col=[0, 1])
    if "veh_km" not in table.columns:
        raise ValueError(
            f"Current vehicle-kilometre report '{path}' has no 'veh_km' column."
        )
    return table["veh_km"].unstack(level=1)


def _aligned_difference(scenario_0, scenario_1):
    if scenario_0 is None or scenario_1 is None:
        return None
    old, new = scenario_0.align(scenario_1, join="outer", fill_value=0)
    return new - old


def _collect_network_differences(scenario_0, scenario_1, submodel, year):
    result_directories = [
        _scenario_result_directory(path, submodel)
        for path in (scenario_0, scenario_1)
    ]
    definitions = (
        ("Road vehicle kilometres by class and road type",
         _read_road_mileage, "vehicle-kilometres"),
        ("Transit vehicle kilometres",
         lambda folder: _read_report_table(folder, TRANSIT_KMS_FILE),
         "model output units"),
        ("Road and rail link lengths",
         lambda folder: _read_report_table(folder, LINK_LENGTH_FILE),
         "kilometres"),
    )

    differences = []
    availability = []
    for label, reader, unit in definitions:
        tables = [reader(folder) for folder in result_directories]
        if all(table is not None for table in tables):
            difference = _aligned_difference(tables[0], tables[1])
            stacked = difference.stack(dropna=False).rename("Value")
            for index, value in stacked.items():
                index_parts = index if isinstance(index, tuple) else (index,)
                differences.append(
                    {
                        "Year": year,
                        "Measure": label,
                        "Item": " / ".join(str(part) for part in index_parts),
                        "Value": value,
                        "Unit": unit,
                    }
                )
            availability.append(
                {"Year": year, "Measure": label, "Status": "available"}
            )
        else:
            filenames = {
                "Road vehicle kilometres by class and road type":
                    VEHICLE_KMS_FILE,
                "Transit vehicle kilometres": TRANSIT_KMS_FILE,
                "Road and rail link lengths": LINK_LENGTH_FILE,
            }
            missing = []
            for folder, table in zip(result_directories, tables):
                if table is None:
                    missing.append(str(folder / filenames[label]))
            availability.append(
                {
                    "Year": year,
                    "Measure": label,
                    "Status": "unavailable: " + ", ".join(missing),
                }
            )
    return differences, availability


def _excel_value(value):
    if pandas.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def _write_sheet(workbook, sheet_name, dataframe):
    if sheet_name in workbook.sheetnames:
        worksheet = workbook[sheet_name]
        if worksheet.max_row:
            worksheet.delete_rows(1, worksheet.max_row)
    else:
        worksheet = workbook.create_sheet(sheet_name)

    for row in dataframe_to_rows(dataframe, index=True, header=True):
        worksheet.append([_excel_value(value) for value in row])
    worksheet.freeze_panes = "A2"
    if worksheet.max_row and worksheet.max_column:
        worksheet.auto_filter.ref = worksheet.dimensions


def _make_workbook(template_path=WORKBOOK_TEMPLATE):
    """Load the CBA workbook template, preserving its sheets and formulas."""
    template_path = Path(template_path)
    if not template_path.is_file():
        raise FileNotFoundError(
            f"CBA workbook template not found: '{template_path}'. "
            "Place CBA_kehikko.xlsx alongside cba.py or provide a valid "
            "template path."
        )
    return load_workbook(template_path)


def _write_results_workbook(
    workbook,
    scenario_pairs,
    submodel,
    benefit_summary,
    revenue_summary,
    network_differences,
    availability,
    zone_results,
):
    overview = pandas.DataFrame(
        [
            ("Submodel", submodel),
            ("Scenario pairs", "; ".join(
                f"year {year}: {Path(project).name} vs {Path(baseline).name}"
                for year, baseline, project in scenario_pairs
            )),
            (
                "Benefit convention",
                "Existing and additional user benefits use the "
                "consumer-surplus calculation. Interpret units using the "
                "input skims; no extra valuation or discounting is applied.",
            ),
            (
                "Workbook note",
                "Benefits are calculated from model skims and volume factors. "
                "No additional monetary valuation or discounting is applied.",
            ),
        ],
        columns=("Item", "Value"),
    )
    _write_sheet(workbook, "Overview", overview)
    _write_sheet(
        workbook,
        "Travel Benefits",
        pandas.DataFrame(benefit_summary),
    )
    _write_sheet(
        workbook,
        "Producer Revenues",
        pandas.DataFrame(revenue_summary),
    )
    _write_sheet(
        workbook,
        "Network Changes",
        pandas.DataFrame(network_differences),
    )
    _write_sheet(
        workbook,
        "Input Availability",
        pandas.DataFrame(availability),
    )
    _write_sheet(
        workbook,
        "Zone Results",
        pandas.DataFrame(zone_results),
    )


def _result_filename(projected_scenario, baseline_scenario):
    return f"cba_{Path(projected_scenario).name}_{Path(baseline_scenario).name}"


if __name__ == "__main__":
    config = utils.config.read_from_file()
    parser = ArgumentParser(
        epilog=(
            "Calculates a cost-benefit comparison from two "
            "model result scenarios and writes an Excel workbook."
        )
    )
    parser.add_argument(
        "baseline_scenario",
        help="Baseline result directory, or scenario name under --results-path",
    )
    parser.add_argument(
        "projected_scenario",
        help="Project result directory, or scenario name under --results-path",
    )
    parser.add_argument(
        "baseline_scenario_2",
        nargs="?",
        help="Optional baseline scenario for the second evaluation year",
    )
    parser.add_argument(
        "projected_scenario_2",
        nargs="?",
        help="Optional project scenario for the second evaluation year",
    )
    parser.add_argument("--log-format", choices={"TEXT", "JSON"}, default="JSON")
    parser.add_argument(
        "--log-level",
        choices={"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
        default=config.get("LOG_LEVEL") or "INFO",
    )
    parser.add_argument(
        "--scenario-name",
        default=config.get("SCENARIO_NAME") or "cba",
        help="Name used by the model logging configuration.",
    )
    parser.add_argument(
        "--results-path",
        dest="result_data_folder",
        required=True,
        help="Results root and destination for the CBA workbook and text file.",
    )
    parser.add_argument(
        "--submodel",
        default=config.get("SUBMODEL") or "uusimaa",
        help="Submodel name used to locate current-model matrices.",
    )
    args = parser.parse_args()
    log.initialize(args)

    if bool(args.baseline_scenario_2) != bool(args.projected_scenario_2):
        parser.error(
            "baseline_scenario_2 and projected_scenario_2 must be supplied "
            "together."
        )
    if args.baseline_scenario_2 == "undefined":
        args.baseline_scenario_2 = None
    if args.projected_scenario_2 == "undefined":
        args.projected_scenario_2 = None
    if bool(args.baseline_scenario_2) != bool(args.projected_scenario_2):
        parser.error(
            "Both second-year scenario arguments must be real scenario "
            "directories or both must be 'undefined'."
        )

    results_path = Path(args.result_data_folder).resolve()
    results_path.mkdir(parents=True, exist_ok=True)
    pairs = [(1, args.baseline_scenario, args.projected_scenario)]
    if args.baseline_scenario_2:
        pairs.append(
            (2, args.baseline_scenario_2, args.projected_scenario_2)
        )

    resolved_pairs = [
        (
            year,
            _resolve_scenario_path(baseline, results_path),
            _resolve_scenario_path(projected, results_path),
        )
        for year, baseline, projected in pairs
    ]
    output_name = _result_filename(
        args.projected_scenario, args.baseline_scenario
    )
    output_path = results_path / f"{output_name}.xlsx"
    workbook = _make_workbook()

    benefit_summary = []
    revenue_summary = []
    network_differences = []
    availability = []
    zone_results = []
    csv_results = []
    for year, baseline_path, projected_path in resolved_pairs:
        log.info(f"Analyse year {year}...")
        result = run_cost_benefit_analysis(
            baseline_path,
            projected_path,
            year,
            workbook,
            args.submodel,
            benefit_summary,
            revenue_summary,
        )
        csv_result = result.add_prefix(f"year_{year}_")
        csv_results.append(csv_result)
        for zone, values in result.iterrows():
            for measure, value in values.items():
                zone_results.append(
                    {
                        "Year": year,
                        "Zone": zone,
                        "Measure": measure,
                        "Value": value,
                    }
                )
        changes, input_status = _collect_network_differences(
            baseline_path, projected_path, args.submodel, year
        )
        network_differences.extend(changes)
        availability.extend(input_status)

    _write_results_workbook(
        workbook,
        pairs,
        args.submodel,
        benefit_summary,
        revenue_summary,
        network_differences,
        availability,
        zone_results,
    )
    workbook.save(output_path)
    pandas.concat(csv_results, axis=1).to_csv(
        results_path / f"{output_name}.txt",
        sep="\t",
        float_format="%8.1f",
    )
    log.info(f"CBA results saved to file: {output_path}")
