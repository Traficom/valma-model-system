"""Run CBA directly from editable settings, without command-line arguments."""

from argparse import Namespace
from pathlib import Path

import pandas

import cba as cba_module
import utils.config
import utils.log as log


# Edit these settings before running the script.
_MODEL_CONFIG = utils.config.read_from_file()

RESULTS_PATH = Path(_MODEL_CONFIG.get("RESULT_DATA_FOLDER") or ".")
OUTPUT_DIRECTORY = RESULTS_PATH
BASELINE_SCENARIO = "2018_feat_new_zonedata_29092026_lyhyet"
PROJECTED_SCENARIO = "2018_feat_new_zonedata_29092026_lyhyet"
BASELINE_SCENARIO_2 = None
PROJECTED_SCENARIO_2 = None
SUBMODEL = _MODEL_CONFIG.get("SUBMODEL") or "uusimaa"
SCENARIO_NAME = _MODEL_CONFIG.get("SCENARIO_NAME") or "cba_debug"
LOG_LEVEL = _MODEL_CONFIG.get("LOG_LEVEL") or "INFO"
LOG_FORMAT = "TEXT"


def main():
    """Run the CBA using the settings above and save the Excel and text files."""
    if bool(BASELINE_SCENARIO_2) != bool(PROJECTED_SCENARIO_2):
        raise ValueError(
            "Set both BASELINE_SCENARIO_2 and PROJECTED_SCENARIO_2, or leave "
            "both as None."
        )

    results_path = RESULTS_PATH.expanduser().resolve()
    output_directory = OUTPUT_DIRECTORY.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    log.initialize(
        Namespace(
            log_level=LOG_LEVEL,
            log_format=LOG_FORMAT,
            scenario_name=SCENARIO_NAME,
            result_data_folder=str(results_path),
        )
    )

    scenario_pairs = [
        (1, BASELINE_SCENARIO, PROJECTED_SCENARIO),
    ]
    if BASELINE_SCENARIO_2:
        scenario_pairs.append(
            (2, BASELINE_SCENARIO_2, PROJECTED_SCENARIO_2)
        )

    resolved_pairs = [
        (
            year,
            cba_module._resolve_scenario_path(baseline, results_path),
            cba_module._resolve_scenario_path(projected, results_path),
        )
        for year, baseline, projected in scenario_pairs
    ]

    output_name = cba_module._result_filename(
        PROJECTED_SCENARIO, BASELINE_SCENARIO
    )
    output_path = output_directory / f"{output_name}.xlsx"
    workbook = cba_module._make_workbook()

    benefit_summary = []
    revenue_summary = []
    network_differences = []
    availability = []
    zone_results = []
    csv_results = []

    for year, baseline_path, projected_path in resolved_pairs:
        log.info(f"Analyse year {year}...")
        result = cba_module.run_cost_benefit_analysis(
            baseline_path,
            projected_path,
            year,
            workbook,
            SUBMODEL,
            benefit_summary,
            revenue_summary,
        )
        csv_results.append(result.add_prefix(f"year_{year}_"))
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

        differences, input_status = cba_module._collect_network_differences(
            baseline_path, projected_path, SUBMODEL, year
        )
        network_differences.extend(differences)
        availability.extend(input_status)

    cba_module._write_results_workbook(
        workbook,
        scenario_pairs,
        SUBMODEL,
        benefit_summary,
        revenue_summary,
        network_differences,
        availability,
        zone_results,
    )
    workbook.save(output_path)
    pandas.concat(csv_results, axis=1).to_csv(
        output_directory / f"{output_name}.txt",
        sep="\t",
        float_format="%8.1f",
    )
    log.info(f"CBA results saved to file: {output_path}")


if __name__ == "__main__":
    main()
