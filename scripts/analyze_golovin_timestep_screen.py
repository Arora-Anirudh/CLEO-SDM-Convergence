"""Evaluate the controlled Golovin collision-timestep screen.

The distribution estimand is the L1 error of the ensemble-mean fixed-bin
distribution, not the mean of nonlinear per-member L1 values. The screen
reuses one frozen initialization and the same collision-seed labels at every
timestep. Those are reproducible common-stream comparisons, not paired
collision histories.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from golovin_stage0 import (
    common_stream_bootstrap_l1_difference,
    ensemble_mean_fixed_bin_relative_l1,
)
from ruamel.yaml import YAML
from scipy.stats import t as student_t

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

MOMENT_COMPARISON_METRICS = {
    "golovin_relative_error_radius_moment_0_m3": ("maximum_moment0_mean_relative_difference"),
    "golovin_relative_error_radius_moment_6_um6_m3": ("maximum_moment6_mean_relative_difference"),
}
ROBUSTNESS_COUNTS = (250, 500, 1000)
PRIMARY_BIN_COUNT = 500


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined-member-time", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--matrix-file", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    return parser.parse_args()


def load_yaml(filename: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    with filename.open("r", encoding="utf-8") as stream:
        return yaml.load(stream)


def read_csv(filename: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    with filename.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def write_csv(filename: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {filename}")
    with filename.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(filename: Path) -> str:
    digest = hashlib.sha256()
    with filename.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def nominal_time(value: float, decision_times_s: list[float]) -> float:
    matches = [
        target for target in decision_times_s if np.isclose(value, target, rtol=0.0, atol=1.0e-3)
    ]
    if len(matches) != 1:
        raise ValueError(f"time {value} does not match exactly one registered decision time")
    return matches[0]


def confidence_interval(
    values: np.ndarray,
    confidence_level: float = 0.95,
) -> tuple[float, float]:
    values = np.asarray(values, dtype=float)
    if values.size < 2 or np.any(~np.isfinite(values)):
        raise ValueError("at least two finite common-stream differences are required")
    mean = float(np.mean(values))
    standard_error = float(np.std(values, ddof=1) / np.sqrt(values.size))
    multiplier = float(student_t.ppf(0.5 + confidence_level / 2.0, df=values.size - 1))
    return mean - multiplier * standard_error, mean + multiplier * standard_error


def load_fixed_bin_archives(
    run_root: Path,
    matrix_rows: list[dict[str, str]],
) -> dict[str, dict[str, np.ndarray]]:
    archives: dict[str, dict[str, np.ndarray]] = {}
    for row in matrix_rows:
        run_label = row["run_label"]
        filename = run_root / run_label / "analysis_stage0_v2" / "fixed_bin_distributions.npz"
        if not filename.is_file():
            raise FileNotFoundError(f"missing fixed-bin archive: {filename}")
        with np.load(filename, allow_pickle=False) as source:
            archive = {key: np.asarray(source[key]) for key in source.files}
        if archive.get("diagnostic_schema_version", np.asarray([])).tolist() != [3]:
            raise RuntimeError(f"unsupported fixed-bin archive schema: {filename}")
        if archive.get("bin_counts", np.asarray([])).tolist() != list(ROBUSTNESS_COUNTS):
            raise RuntimeError(f"unexpected fixed-bin counts: {filename}")
        archives[run_label] = archive
    if len(archives) != len(matrix_rows):
        raise RuntimeError("fixed-bin archives do not exactly cover the matrix")
    return archives


def validate_matrix_and_rows(
    matrix_rows: list[dict[str, str]],
    rows: list[dict[str, str]],
) -> None:
    expected_labels = {row["run_label"] for row in matrix_rows}
    if len(expected_labels) != len(matrix_rows):
        raise RuntimeError("matrix contains duplicate run labels")
    actual_labels = {row["run_label"] for row in rows}
    if actual_labels != expected_labels:
        raise RuntimeError("combined diagnostics do not exactly cover the timestep matrix")
    for row in matrix_rows:
        if row["initialization_family"] != "controlled":
            raise RuntimeError("timestep screen requires controlled initialization")
        if row["controlled_bundle_label"] == "not_applicable":
            raise RuntimeError("controlled timestep row is missing its bundle label")

    seeds_by_member: dict[str, set[str]] = defaultdict(set)
    for row in matrix_rows:
        seeds_by_member[row["member_index"]].add(row["collision_seed"])
    if any(len(seeds) != 1 for seeds in seeds_by_member.values()):
        raise RuntimeError("collision-seed labels are not reused consistently across timesteps")


def distribution_stacks(
    *,
    archives: dict[str, dict[str, np.ndarray]],
    matrix_lookup: dict[tuple[float, int], dict[str, str]],
    timestep: float,
    reference_timestep: float,
    members: list[int],
    time_s: float,
    bin_count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    candidate: list[np.ndarray] = []
    reference: list[np.ndarray] = []
    analytical_values: list[np.ndarray] = []
    edges_values: list[np.ndarray] = []
    for member in members:
        for selected_timestep, target in (
            (timestep, candidate),
            (reference_timestep, reference),
        ):
            matrix_row = matrix_lookup[(selected_timestep, member)]
            archive = archives[matrix_row["run_label"]]
            stored_times = archive["time_s"]
            matches = np.flatnonzero(np.isclose(stored_times, time_s, rtol=0.0, atol=1.0e-3))
            if matches.size != 1:
                raise RuntimeError(
                    f"{matrix_row['run_label']} has {matches.size} matches for {time_s} s"
                )
            time_index = int(matches[0])
            target.append(archive[f"numerical_gm3_per_ln_radius_{bin_count}"][time_index])
            analytical_values.append(
                archive[f"analytical_gm3_per_ln_radius_{bin_count}"][time_index]
            )
            edges_values.append(archive[f"edges_um_{bin_count}"])

    analytical = analytical_values[0]
    edges = edges_values[0]
    if any(not np.array_equal(value, analytical) for value in analytical_values[1:]):
        raise RuntimeError("analytical fixed-bin distributions differ across screen members")
    if any(not np.array_equal(value, edges) for value in edges_values[1:]):
        raise RuntimeError("fixed-bin edges differ across screen members")
    return np.stack(candidate), np.stack(reference), analytical, edges


def _bootstrap_seed(base_seed: int, timestep: float, time_s: float, bin_count: int) -> int:
    payload = f"{base_seed}|{timestep:.17g}|{time_s:.17g}|{bin_count}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def analyze(
    *,
    rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    config: dict[str, Any],
    fixed_bin_archives: dict[str, dict[str, np.ndarray]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    validate_matrix_and_rows(matrix_rows, rows)
    screening = config["screening"]
    reference_timestep = float(screening["reference_collision_timestep_s"])
    decision_times = [float(value) for value in screening["decision_times_s"]]
    confidence_level = 0.95
    bootstrap_resamples = int(screening["bootstrap_resamples"])
    bootstrap_seed = int(screening["bootstrap_seed"])
    if screening.get("require_pass_at_every_decision_time") is not True:
        raise ValueError("the registered screen must pass at every decision time")

    decision_rows = [
        {**row, "_nominal_time_s": nominal_time(float(row["time_s"]), decision_times)}
        for row in rows
        if any(
            np.isclose(float(row["time_s"]), target, rtol=0.0, atol=1.0e-3)
            for target in decision_times
        )
    ]
    keyed = {
        (
            float(row["collision_timestep_s"]),
            int(row["member_index"]),
            float(row["_nominal_time_s"]),
        ): row
        for row in decision_rows
    }
    if len(keyed) != len(decision_rows):
        raise RuntimeError("duplicate timestep/member/time diagnostic rows")

    timesteps = sorted({float(row["collision_timestep_s"]) for row in matrix_rows})
    members = sorted({int(row["member_index"]) for row in matrix_rows})
    matrix_lookup = {
        (float(row["collision_timestep_s"]), int(row["member_index"])): row for row in matrix_rows
    }
    if len(matrix_lookup) != len(matrix_rows):
        raise RuntimeError("duplicate timestep/member matrix row")
    if reference_timestep not in timesteps:
        raise RuntimeError("reference timestep is absent from the matrix")

    comparisons: list[dict[str, object]] = []
    timestep_pass: dict[float, bool] = {timestep: True for timestep in timesteps}
    for timestep in timesteps:
        for time_s in decision_times:
            for metric, margin_key in MOMENT_COMPARISON_METRICS.items():
                differences = np.asarray(
                    [
                        float(keyed[(timestep, member, time_s)][metric])
                        - float(keyed[(reference_timestep, member, time_s)][metric])
                        for member in members
                    ],
                    dtype=float,
                )
                mean_difference = float(np.mean(differences))
                ci_low, ci_high = confidence_interval(differences, confidence_level)
                margin = float(screening[margin_key])
                passed = ci_low >= -margin and ci_high <= margin
                timestep_pass[timestep] = timestep_pass[timestep] and passed
                comparisons.append(
                    {
                        "collision_timestep_s": timestep,
                        "reference_collision_timestep_s": reference_timestep,
                        "time_s": time_s,
                        "metric": metric,
                        "n_common_streams": len(members),
                        "estimated_difference": mean_difference,
                        "ci_method": "student_common_stream_difference",
                        "95ci_low": ci_low,
                        "95ci_high": ci_high,
                        "equivalence_margin": margin,
                        "equivalence_pass": passed,
                    }
                )

    mass_drift_limit = float(screening["maximum_relative_liquid_mass_drift"])
    maximum_mass_drift_by_timestep = {
        timestep: max(
            abs(float(row["relative_liquid_mass_drift"]))
            for row in rows
            if float(row["collision_timestep_s"]) == timestep
        )
        for timestep in timesteps
    }
    for timestep, maximum_drift in maximum_mass_drift_by_timestep.items():
        timestep_pass[timestep] = timestep_pass[timestep] and maximum_drift <= mass_drift_limit

    out_of_range_limit = float(screening["maximum_out_of_range_mass_fraction"])
    maximum_out_of_range_by_timestep = {
        timestep: max(
            float(row["fixed_bin_mass_below_range_fraction"])
            + float(row["fixed_bin_mass_above_range_fraction"])
            for row in rows
            if float(row["collision_timestep_s"]) == timestep
        )
        for timestep in timesteps
    }
    for timestep, maximum_out_of_range in maximum_out_of_range_by_timestep.items():
        timestep_pass[timestep] = (
            timestep_pass[timestep] and maximum_out_of_range <= out_of_range_limit
        )

    robustness_limit = float(screening["maximum_bin_robustness_absolute_difference"])
    l1_margin = float(screening["maximum_l1_mean_absolute_difference"])
    robustness: list[dict[str, object]] = []
    for timestep in timesteps:
        for time_s in decision_times:
            record: dict[str, object] = {
                "collision_timestep_s": timestep,
                "time_s": time_s,
                "n_members": len(members),
            }
            l1_by_count: dict[int, float] = {}
            for count in ROBUSTNESS_COUNTS:
                (
                    candidate_stack,
                    reference_stack,
                    analytical,
                    edges,
                ) = distribution_stacks(
                    archives=fixed_bin_archives,
                    matrix_lookup=matrix_lookup,
                    timestep=timestep,
                    reference_timestep=reference_timestep,
                    members=members,
                    time_s=time_s,
                    bin_count=count,
                )
                l1_value = ensemble_mean_fixed_bin_relative_l1(
                    candidate_stack,
                    analytical,
                    edges,
                )
                reference_l1 = ensemble_mean_fixed_bin_relative_l1(
                    reference_stack,
                    analytical,
                    edges,
                )
                (
                    observed_difference,
                    ci_low,
                    ci_high,
                ) = common_stream_bootstrap_l1_difference(
                    candidate_stack,
                    reference_stack,
                    analytical,
                    edges,
                    bootstrap_resamples=bootstrap_resamples,
                    bootstrap_seed=_bootstrap_seed(
                        bootstrap_seed,
                        timestep,
                        time_s,
                        count,
                    ),
                    confidence_level=confidence_level,
                )
                equivalent = ci_low >= -l1_margin and ci_high <= l1_margin
                l1_by_count[count] = l1_value
                record[f"ensemble_mean_l1_bins_{count}"] = l1_value
                record[f"reference_ensemble_mean_l1_bins_{count}"] = reference_l1
                record[f"bootstrap_95ci_low_bins_{count}"] = ci_low
                record[f"bootstrap_95ci_high_bins_{count}"] = ci_high
                record[f"timestep_equivalence_pass_bins_{count}"] = equivalent
                timestep_pass[timestep] = timestep_pass[timestep] and equivalent
                comparisons.append(
                    {
                        "collision_timestep_s": timestep,
                        "reference_collision_timestep_s": reference_timestep,
                        "time_s": time_s,
                        "metric": (f"golovin_ensemble_mean_fixed_bin_l1_relative_bins_{count}"),
                        "n_common_streams": len(members),
                        "estimated_difference": observed_difference,
                        "ci_method": "common_stream_percentile_bootstrap",
                        "95ci_low": ci_low,
                        "95ci_high": ci_high,
                        "equivalence_margin": l1_margin,
                        "equivalence_pass": equivalent,
                    }
                )

            primary_l1 = l1_by_count[PRIMARY_BIN_COUNT]
            for count in ROBUSTNESS_COUNTS:
                absolute_difference = abs(l1_by_count[count] - primary_l1)
                robust = absolute_difference <= robustness_limit
                record[f"absolute_difference_from_500_bins_{count}"] = absolute_difference
                record[f"robustness_pass_bins_{count}"] = robust
                timestep_pass[timestep] = timestep_pass[timestep] and robust
            robustness.append(record)

    passing_timesteps = sorted(
        (timestep for timestep, passed in timestep_pass.items() if passed),
        reverse=True,
    )
    if not passing_timesteps:
        raise RuntimeError("no collision timestep passed, including the reference timestep")
    selected_timestep = passing_timesteps[0]
    selection = {
        "status": "selected_preconvergence_timestep",
        "schema": "golovin_controlled_timestep_selection_v2",
        "selected_collision_timestep_s": selected_timestep,
        "reference_collision_timestep_s": reference_timestep,
        "selection_rule": screening["selection_rule"],
        "confidence_level": confidence_level,
        "bootstrap_resamples": bootstrap_resamples,
        "bootstrap_seed": bootstrap_seed,
        "decision_times_s": decision_times,
        "member_count_per_timestep": len(members),
        "timestep_pass": {str(key): value for key, value in timestep_pass.items()},
        "maximum_absolute_mass_drift_by_timestep": {
            str(key): value for key, value in maximum_mass_drift_by_timestep.items()
        },
        "maximum_relative_liquid_mass_drift": mass_drift_limit,
        "maximum_out_of_range_mass_fraction_by_timestep": {
            str(key): value for key, value in maximum_out_of_range_by_timestep.items()
        },
        "maximum_out_of_range_mass_fraction": out_of_range_limit,
        "maximum_bin_robustness_absolute_difference": robustness_limit,
        "bin_robustness_is_an_acceptance_gate": True,
        "l1_estimand": (
            "relative L1 of the ensemble-mean fixed-bin distribution, "
            "not the mean of per-member L1 values"
        ),
        "common_stream_warning": (
            "The same collision-seed labels are reused, but different timesteps "
            "do not produce paired event histories."
        ),
    }
    return comparisons, robustness, selection


def plot_screen(
    rows: list[dict[str, str]],
    robustness_rows: list[dict[str, object]],
    *,
    selection: dict[str, object],
    output: Path,
) -> None:
    moment_metrics = (
        ("golovin_relative_error_radius_moment_0_m3", "relative M0 error"),
        ("golovin_relative_error_radius_moment_6_um6_m3", "relative M6 error"),
    )
    timesteps = sorted({float(row["collision_timestep_s"]) for row in rows}, reverse=True)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for axis, (metric, ylabel) in zip(axes.flat[:2], moment_metrics, strict=True):
        for timestep in timesteps:
            selected = [row for row in rows if float(row["collision_timestep_s"]) == timestep]
            times = sorted({float(row["time_s"]) for row in selected})
            means = [
                np.mean([float(row[metric]) for row in selected if float(row["time_s"]) == time_s])
                for time_s in times
            ]
            axis.plot(np.asarray(times) / 60.0, means, marker="o", label=f"{timestep:g} s")
        axis.set_xlabel("time /min")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.25)

    final_time = max(float(row["time_s"]) for row in robustness_rows)
    final_robustness = [
        row
        for row in robustness_rows
        if np.isclose(float(row["time_s"]), final_time, rtol=0.0, atol=1.0e-3)
    ]
    l1_axis = axes.flat[2]
    robustness_axis = axes.flat[3]
    for count in ROBUSTNESS_COUNTS:
        l1_axis.plot(
            [float(row["collision_timestep_s"]) for row in final_robustness],
            [float(row[f"ensemble_mean_l1_bins_{count}"]) for row in final_robustness],
            marker="o",
            label=f"{count} bins",
        )
        robustness_axis.plot(
            [float(row["collision_timestep_s"]) for row in final_robustness],
            [float(row[f"absolute_difference_from_500_bins_{count}"]) for row in final_robustness],
            marker="o",
            label=f"{count} bins",
        )
    for axis in (l1_axis, robustness_axis):
        axis.set_xscale("log")
        axis.invert_xaxis()
        axis.set_xlabel("collision timestep /s")
        axis.grid(alpha=0.25)
        axis.legend()
    l1_axis.set_ylabel(f"{final_time:g}-s ensemble-mean L1")
    robustness_axis.set_ylabel("absolute difference from 500-bin L1")

    axes.flat[0].legend(title="collision timestep")
    fig.suptitle(
        "Controlled Golovin collision-timestep screen\n"
        f"selected timestep = {selection['selected_collision_timestep_s']:g} s"
    )
    fig.tight_layout()
    fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    output_directory = args.output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"refusing to overwrite: {output_directory}")
    rows = read_csv(args.combined_member_time.resolve())
    matrix_rows = read_csv(args.matrix_file.resolve(), delimiter="\t")
    config = load_yaml(args.config.resolve())
    fixed_bin_archives = load_fixed_bin_archives(
        args.run_root.resolve(),
        matrix_rows,
    )
    comparisons, robustness, selection = analyze(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        fixed_bin_archives=fixed_bin_archives,
    )

    output_directory.mkdir(parents=True)
    write_csv(output_directory / "timestep_comparisons.csv", comparisons)
    write_csv(output_directory / "bin_robustness.csv", robustness)
    plot_screen(
        rows,
        robustness,
        selection=selection,
        output=output_directory / "timestep_screen.png",
    )
    selection.update(
        {
            "combined_member_time": str(args.combined_member_time.resolve()),
            "combined_member_time_sha256": sha256_file(args.combined_member_time.resolve()),
            "run_root": str(args.run_root.resolve()),
            "matrix_file": str(args.matrix_file.resolve()),
            "matrix_sha256": sha256_file(args.matrix_file.resolve()),
            "config": str(args.config.resolve()),
            "config_sha256": sha256_file(args.config.resolve()),
        }
    )
    (output_directory / "timestep_selection.json").write_text(
        json.dumps(selection, indent=2) + "\n",
        encoding="utf-8",
    )
    print("GOLOVIN_TIMESTEP_SCREEN_ANALYSIS_PASS=1")
    print(f"selected_collision_timestep_s={selection['selected_collision_timestep_s']}")
    print(f"output_directory={output_directory}")


if __name__ == "__main__":
    main()
