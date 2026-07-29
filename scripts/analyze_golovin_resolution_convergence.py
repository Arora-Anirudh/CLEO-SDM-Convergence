"""Analyze the controlled Golovin resolution-convergence ensemble.

The formal distribution statistic is L1 of the ensemble-mean fixed-bin
distribution. Adjacent resolutions are independent ensembles; their
distribution difference therefore uses independent bootstrap resampling, not
paired member histories.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from golovin_stage0 import (
    bootstrap_ensemble_mean_l1,
    independent_bootstrap_l1_difference,
)
from ruamel.yaml import YAML
from scipy.stats import t as student_t

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BIN_COUNTS = (250, 500, 1000)
MOMENT_METRICS = {
    "golovin_relative_error_radius_moment_0_m3": (
        "moment0_relative_bias_margin",
        "moment0_relative",
    ),
    "golovin_relative_error_radius_moment_6_um6_m3": (
        "moment6_relative_bias_margin",
        "moment6_relative",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined-member-time", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--matrix-file", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    return parser.parse_args()


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


def load_yaml(filename: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    with filename.open("r", encoding="utf-8") as stream:
        return yaml.load(stream)


def sha256_file(filename: Path) -> str:
    digest = hashlib.sha256()
    with filename.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def nominal_time(value: float, decision_times: list[float]) -> float:
    matches = [
        target for target in decision_times if np.isclose(value, target, rtol=0.0, atol=1.0e-3)
    ]
    if len(matches) != 1:
        raise ValueError(f"time {value} does not match one decision time")
    return matches[0]


def student_interval(
    values: np.ndarray,
    confidence_level: float,
) -> tuple[float, float, float]:
    values = np.asarray(values, dtype=float)
    if values.size < 2 or np.any(~np.isfinite(values)):
        raise ValueError("at least two finite values are required")
    mean = float(np.mean(values))
    standard_error = float(np.std(values, ddof=1) / np.sqrt(values.size))
    multiplier = float(student_t.ppf(0.5 + confidence_level / 2.0, df=values.size - 1))
    return mean, mean - multiplier * standard_error, mean + multiplier * standard_error


def welch_difference_interval(
    candidate: np.ndarray,
    reference: np.ndarray,
    confidence_level: float,
) -> tuple[float, float, float]:
    candidate = np.asarray(candidate, dtype=float)
    reference = np.asarray(reference, dtype=float)
    if candidate.size < 2 or reference.size < 2:
        raise ValueError("both independent ensembles require at least two members")
    candidate_variance = float(np.var(candidate, ddof=1))
    reference_variance = float(np.var(reference, ddof=1))
    candidate_term = candidate_variance / candidate.size
    reference_term = reference_variance / reference.size
    standard_error = np.sqrt(candidate_term + reference_term)
    if standard_error == 0.0:
        multiplier = 0.0
    else:
        denominator = candidate_term**2 / (candidate.size - 1) + reference_term**2 / (
            reference.size - 1
        )
        degrees_freedom = (candidate_term + reference_term) ** 2 / denominator
        multiplier = float(student_t.ppf(0.5 + confidence_level / 2.0, df=degrees_freedom))
    difference = float(np.mean(candidate) - np.mean(reference))
    return (
        difference,
        difference - multiplier * standard_error,
        difference + multiplier * standard_error,
    )


def load_archives(
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
            raise RuntimeError(f"unsupported diagnostic schema: {filename}")
        if archive.get("bin_counts", np.asarray([])).tolist() != list(BIN_COUNTS):
            raise RuntimeError(f"unexpected bin counts: {filename}")
        archives[run_label] = archive
    return archives


def validate_inputs(
    rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    config: dict[str, Any],
) -> None:
    labels = [row["run_label"] for row in matrix_rows]
    if len(labels) != len(set(labels)):
        raise RuntimeError("matrix contains duplicate run labels")
    if {row["run_label"] for row in rows} != set(labels):
        raise RuntimeError("combined diagnostics do not exactly cover the matrix")
    if any(row["initialization_family"] != "controlled" for row in matrix_rows):
        raise RuntimeError("resolution experiment requires controlled initialization")
    if len({float(row["collision_timestep_s"]) for row in matrix_rows}) != 1:
        raise RuntimeError("resolution experiment must use one selected timestep")
    expected_timestep = float(
        config["timestep_selection_provenance"]["selected_collision_timestep_s"]
    )
    if {float(row["collision_timestep_s"]) for row in matrix_rows} != {expected_timestep}:
        raise RuntimeError("matrix timestep differs from selected timestep")
    if config["authorization"]["submission_authorized"] is not False:
        raise RuntimeError("analysis config must preserve separate submission authorization")
    expected_resolutions = sorted(int(value) for value in config["matrix"]["max_superdroplets"])
    actual_resolutions = sorted({int(row["max_superdroplets"]) for row in matrix_rows})
    if actual_resolutions != expected_resolutions:
        raise RuntimeError("matrix resolutions differ from the registered configuration")
    expected_members = int(config["matrix"]["members_per_cell"])
    for resolution in expected_resolutions:
        actual_members = sum(int(row["max_superdroplets"]) == resolution for row in matrix_rows)
        if actual_members != expected_members:
            raise RuntimeError(
                f"resolution {resolution} has {actual_members} rows, expected {expected_members}"
            )


def distribution_stack(
    *,
    resolution: int,
    members: list[int],
    time_s: float,
    bin_count: int,
    matrix_lookup: dict[tuple[int, int], dict[str, str]],
    archives: dict[str, dict[str, np.ndarray]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    numerical: list[np.ndarray] = []
    analytical_values: list[np.ndarray] = []
    edge_values: list[np.ndarray] = []
    for member in members:
        row = matrix_lookup[(resolution, member)]
        archive = archives[row["run_label"]]
        indices = np.flatnonzero(np.isclose(archive["time_s"], time_s, rtol=0.0, atol=1.0e-3))
        if indices.size != 1:
            raise RuntimeError(f"{row['run_label']} has {indices.size} matches for {time_s} s")
        index = int(indices[0])
        numerical.append(archive[f"numerical_gm3_per_ln_radius_{bin_count}"][index])
        analytical_values.append(archive[f"analytical_gm3_per_ln_radius_{bin_count}"][index])
        edge_values.append(archive[f"edges_um_{bin_count}"])
    analytical = analytical_values[0]
    edges = edge_values[0]
    if any(not np.array_equal(value, analytical) for value in analytical_values[1:]):
        raise RuntimeError("analytical distributions differ across members")
    if any(not np.array_equal(value, edges) for value in edge_values[1:]):
        raise RuntimeError("fixed-bin edges differ across members")
    return np.stack(numerical), analytical, edges


def derived_seed(base_seed: int, *parts: object) -> int:
    payload = "|".join([str(base_seed), *(str(part) for part in parts)]).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def analyze(
    *,
    rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    config: dict[str, Any],
    archives: dict[str, dict[str, np.ndarray]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    validate_inputs(rows, matrix_rows, config)
    diagnostics = config["diagnostics"]
    criteria = config["convergence_criteria"]
    confidence_level = float(diagnostics["confidence_level"])
    resamples = int(diagnostics["bootstrap_resamples"])
    base_seed = int(diagnostics["bootstrap_seed"])
    decision_times = [float(value) for value in diagnostics["decision_times_s"]]
    if criteria["require_pass_at_every_decision_time"] is not True:
        raise ValueError("convergence must pass at every registered decision time")
    if criteria["require_next_level_confirmation"] is not True:
        raise ValueError("the registered N/2N/4N confirmation rule is required")
    if (
        diagnostics["bin_robustness_policy"]
        != "require_resolution_decision_at_all_registered_bin_counts"
    ):
        raise ValueError("unsupported resolution bin-robustness policy")

    decision_rows = [
        {**row, "_nominal_time": nominal_time(float(row["time_s"]), decision_times)}
        for row in rows
        if any(
            np.isclose(float(row["time_s"]), time_s, rtol=0.0, atol=1.0e-3)
            for time_s in decision_times
        )
    ]
    keyed = {
        (
            int(row["max_superdroplets"]),
            int(row["member_index"]),
            float(row["_nominal_time"]),
        ): row
        for row in decision_rows
    }
    if len(keyed) != len(decision_rows):
        raise RuntimeError("duplicate resolution/member/time rows")

    resolutions = sorted({int(row["max_superdroplets"]) for row in matrix_rows})
    members_by_resolution = {
        resolution: sorted(
            int(row["member_index"])
            for row in matrix_rows
            if int(row["max_superdroplets"]) == resolution
        )
        for resolution in resolutions
    }
    matrix_lookup = {
        (int(row["max_superdroplets"]), int(row["member_index"])): row for row in matrix_rows
    }

    resolution_pass = {resolution: True for resolution in resolutions}
    analytical_rows: list[dict[str, object]] = []
    analytical_l1_margin = float(criteria["analytical_agreement"]["maximum_l1_upper_95ci"])
    l1_precision = float(criteria["maximum_95ci_half_width"]["l1_absolute"])
    for resolution in resolutions:
        members = members_by_resolution[resolution]
        selected_rows = [row for row in rows if int(row["max_superdroplets"]) == resolution]
        maximum_drift = max(abs(float(row["relative_liquid_mass_drift"])) for row in selected_rows)
        maximum_out_of_range = max(
            float(row["fixed_bin_mass_below_range_fraction"])
            + float(row["fixed_bin_mass_above_range_fraction"])
            for row in selected_rows
        )
        resolution_pass[resolution] &= maximum_drift <= float(
            criteria["maximum_relative_liquid_mass_drift"]
        )
        resolution_pass[resolution] &= maximum_out_of_range <= float(
            criteria["maximum_out_of_range_mass_fraction"]
        )

        for time_s in decision_times:
            for bin_count in BIN_COUNTS:
                stack, analytical, edges = distribution_stack(
                    resolution=resolution,
                    members=members,
                    time_s=time_s,
                    bin_count=bin_count,
                    matrix_lookup=matrix_lookup,
                    archives=archives,
                )
                estimate, ci_low, ci_high = bootstrap_ensemble_mean_l1(
                    stack,
                    analytical,
                    edges,
                    bootstrap_resamples=resamples,
                    bootstrap_seed=derived_seed(
                        base_seed,
                        "analytical_l1",
                        resolution,
                        time_s,
                        bin_count,
                    ),
                    confidence_level=confidence_level,
                )
                half_width = (ci_high - ci_low) / 2.0
                accuracy_pass = ci_high <= analytical_l1_margin
                precision_pass = half_width <= l1_precision
                resolution_pass[resolution] &= accuracy_pass and precision_pass
                analytical_rows.append(
                    {
                        "max_superdroplets": resolution,
                        "time_s": time_s,
                        "metric": f"ensemble_mean_l1_bins_{bin_count}",
                        "n_members": len(members),
                        "estimate": estimate,
                        "95ci_low": ci_low,
                        "95ci_high": ci_high,
                        "95ci_half_width": half_width,
                        "accuracy_margin": analytical_l1_margin,
                        "precision_margin": l1_precision,
                        "accuracy_pass": accuracy_pass,
                        "precision_pass": precision_pass,
                    }
                )

            for metric, (accuracy_key, precision_key) in MOMENT_METRICS.items():
                values = np.asarray(
                    [float(keyed[(resolution, member, time_s)][metric]) for member in members]
                )
                estimate, ci_low, ci_high = student_interval(
                    values,
                    confidence_level,
                )
                accuracy_margin = float(criteria["analytical_agreement"][accuracy_key])
                precision_margin = float(criteria["maximum_95ci_half_width"][precision_key])
                half_width = (ci_high - ci_low) / 2.0
                accuracy_pass = ci_low >= -accuracy_margin and ci_high <= accuracy_margin
                precision_pass = half_width <= precision_margin
                resolution_pass[resolution] &= accuracy_pass and precision_pass
                analytical_rows.append(
                    {
                        "max_superdroplets": resolution,
                        "time_s": time_s,
                        "metric": metric,
                        "n_members": len(members),
                        "estimate": estimate,
                        "95ci_low": ci_low,
                        "95ci_high": ci_high,
                        "95ci_half_width": half_width,
                        "accuracy_margin": accuracy_margin,
                        "precision_margin": precision_margin,
                        "accuracy_pass": accuracy_pass,
                        "precision_pass": precision_pass,
                    }
                )

    pair_pass: dict[tuple[int, int], bool] = {}
    adjacent_rows: list[dict[str, object]] = []
    for lower, upper in zip(resolutions[:-1], resolutions[1:], strict=True):
        pair_pass[(lower, upper)] = True
        lower_members = members_by_resolution[lower]
        upper_members = members_by_resolution[upper]
        for time_s in decision_times:
            for bin_count in BIN_COUNTS:
                lower_stack, analytical, edges = distribution_stack(
                    resolution=lower,
                    members=lower_members,
                    time_s=time_s,
                    bin_count=bin_count,
                    matrix_lookup=matrix_lookup,
                    archives=archives,
                )
                upper_stack, upper_analytical, upper_edges = distribution_stack(
                    resolution=upper,
                    members=upper_members,
                    time_s=time_s,
                    bin_count=bin_count,
                    matrix_lookup=matrix_lookup,
                    archives=archives,
                )
                if not np.array_equal(analytical, upper_analytical) or not np.array_equal(
                    edges, upper_edges
                ):
                    raise RuntimeError("adjacent resolutions use different references")
                estimate, ci_low, ci_high = independent_bootstrap_l1_difference(
                    lower_stack,
                    upper_stack,
                    analytical,
                    edges,
                    bootstrap_resamples=resamples,
                    bootstrap_seed=derived_seed(
                        base_seed,
                        "adjacent_l1",
                        lower,
                        upper,
                        time_s,
                        bin_count,
                    ),
                    confidence_level=confidence_level,
                )
                margin = float(
                    criteria["adjacent_level_equivalence"]["l1_absolute_difference_margin"]
                )
                passed = ci_low >= -margin and ci_high <= margin
                pair_pass[(lower, upper)] &= passed
                adjacent_rows.append(
                    {
                        "lower_max_superdroplets": lower,
                        "upper_max_superdroplets": upper,
                        "time_s": time_s,
                        "metric": f"ensemble_mean_l1_bins_{bin_count}",
                        "lower_n_members": len(lower_members),
                        "upper_n_members": len(upper_members),
                        "estimated_difference_lower_minus_upper": estimate,
                        "95ci_low": ci_low,
                        "95ci_high": ci_high,
                        "equivalence_margin": margin,
                        "equivalence_pass": passed,
                    }
                )

            for metric, (margin_key, _) in MOMENT_METRICS.items():
                lower_values = np.asarray(
                    [float(keyed[(lower, member, time_s)][metric]) for member in lower_members]
                )
                upper_values = np.asarray(
                    [float(keyed[(upper, member, time_s)][metric]) for member in upper_members]
                )
                estimate, ci_low, ci_high = welch_difference_interval(
                    lower_values,
                    upper_values,
                    confidence_level,
                )
                margin = float(
                    criteria["adjacent_level_equivalence"][
                        margin_key.replace(
                            "_bias_margin",
                            "_difference_margin",
                        )
                    ]
                )
                passed = ci_low >= -margin and ci_high <= margin
                pair_pass[(lower, upper)] &= passed
                adjacent_rows.append(
                    {
                        "lower_max_superdroplets": lower,
                        "upper_max_superdroplets": upper,
                        "time_s": time_s,
                        "metric": metric,
                        "lower_n_members": len(lower_members),
                        "upper_n_members": len(upper_members),
                        "estimated_difference_lower_minus_upper": estimate,
                        "95ci_low": ci_low,
                        "95ci_high": ci_high,
                        "equivalence_margin": margin,
                        "equivalence_pass": passed,
                    }
                )

    accepted: list[int] = []
    for index, resolution in enumerate(resolutions):
        if index + 2 >= len(resolutions):
            continue
        next_resolution = resolutions[index + 1]
        confirmation_resolution = resolutions[index + 2]
        if (
            resolution_pass[resolution]
            and resolution_pass[next_resolution]
            and resolution_pass[confirmation_resolution]
            and pair_pass[(resolution, next_resolution)]
            and pair_pass[(next_resolution, confirmation_resolution)]
        ):
            accepted.append(resolution)

    selected = min(accepted) if accepted else None
    decision = {
        "status": (
            "selected_controlled_resolution"
            if selected is not None
            else "no_resolution_accepted_in_initial_matrix"
        ),
        "schema": "golovin_controlled_resolution_decision_v1",
        "selected_max_superdroplets": selected,
        "tested_resolutions": resolutions,
        "members_per_resolution": {
            str(key): len(value) for key, value in members_by_resolution.items()
        },
        "resolution_analytical_and_precision_pass": {
            str(key): bool(value) for key, value in resolution_pass.items()
        },
        "adjacent_pair_equivalence_pass": {
            f"{lower}-{upper}": bool(value) for (lower, upper), value in pair_pass.items()
        },
        "confirmation_rule": (
            "N, 2N and 4N pass analytical/precision gates and both adjacent pairs pass equivalence"
        ),
        "bin_robustness_policy": diagnostics["bin_robustness_policy"],
        "l1_estimand": "relative L1 of the ensemble-mean fixed-bin distribution",
        "independent_ensemble_warning": (
            "Different resolutions use independent collision ensembles; "
            "member indices are not paired histories."
        ),
    }
    return analytical_rows, adjacent_rows, decision


def plot_result(
    analytical_rows: list[dict[str, object]],
    adjacent_rows: list[dict[str, object]],
    decision: dict[str, object],
    output: Path,
) -> None:
    def plot_estimates_and_intervals(
        axis: plt.Axes,
        x: np.ndarray,
        estimate: np.ndarray,
        low: np.ndarray,
        high: np.ndarray,
    ) -> None:
        if (
            np.any(~np.isfinite(estimate))
            or np.any(~np.isfinite(low))
            or np.any(~np.isfinite(high))
        ):
            raise ValueError("plot estimates and interval endpoints must be finite")
        if np.any(low > high):
            raise ValueError("plot interval lower endpoints exceed upper endpoints")

        (line,) = axis.plot(x, estimate, marker="o")
        # A percentile-bootstrap interval need not contain the observed
        # nonlinear estimate. Draw endpoints independently instead of passing
        # signed distances to errorbar(), which requires nonnegative values.
        axis.vlines(x, low, high, color=line.get_color())

    final_time = max(float(row["time_s"]) for row in analytical_rows)
    final_rows = [
        row
        for row in analytical_rows
        if np.isclose(float(row["time_s"]), final_time, rtol=0.0, atol=1.0e-3)
    ]
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for axis, metric, ylabel in (
        (axes[0, 0], "ensemble_mean_l1_bins_500", "ensemble-mean L1"),
        (
            axes[0, 1],
            "golovin_relative_error_radius_moment_0_m3",
            "relative M0 error",
        ),
        (
            axes[1, 0],
            "golovin_relative_error_radius_moment_6_um6_m3",
            "relative M6 error",
        ),
    ):
        selected = [row for row in final_rows if row["metric"] == metric]
        x = np.asarray([float(row["max_superdroplets"]) for row in selected])
        y = np.asarray([float(row["estimate"]) for row in selected])
        low = np.asarray([float(row["95ci_low"]) for row in selected])
        high = np.asarray([float(row["95ci_high"]) for row in selected])
        plot_estimates_and_intervals(axis, x, y, low, high)
        axis.set_xscale("log", base=2)
        axis.set_xlabel(r"$N_\mathrm{SD}$")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.25)

    pair_axis = axes[1, 1]
    final_pairs = [
        row
        for row in adjacent_rows
        if np.isclose(float(row["time_s"]), final_time, rtol=0.0, atol=1.0e-3)
        and row["metric"] == "ensemble_mean_l1_bins_500"
    ]
    x = np.arange(len(final_pairs))
    estimate = np.asarray(
        [float(row["estimated_difference_lower_minus_upper"]) for row in final_pairs]
    )
    low = np.asarray([float(row["95ci_low"]) for row in final_pairs])
    high = np.asarray([float(row["95ci_high"]) for row in final_pairs])
    plot_estimates_and_intervals(pair_axis, x, estimate, low, high)
    pair_axis.axhline(0.0, color="black", linewidth=0.8)
    pair_axis.set_xticks(
        x,
        [
            f"{row['lower_max_superdroplets']}-{row['upper_max_superdroplets']}"
            for row in final_pairs
        ],
        rotation=30,
    )
    pair_axis.set_ylabel("adjacent L1 difference")
    pair_axis.set_xlabel(r"adjacent $N_\mathrm{SD}$ pair")
    pair_axis.grid(alpha=0.25)

    fig.suptitle(f"Controlled Golovin resolution convergence\ndecision: {decision['status']}")
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
    archives = load_archives(args.run_root.resolve(), matrix_rows)
    analytical_rows, adjacent_rows, decision = analyze(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )

    output_directory.mkdir(parents=True)
    write_csv(output_directory / "analytical_agreement.csv", analytical_rows)
    write_csv(output_directory / "adjacent_resolution_equivalence.csv", adjacent_rows)
    plot_result(
        analytical_rows,
        adjacent_rows,
        decision,
        output_directory / "resolution_convergence.png",
    )
    decision.update(
        {
            "combined_member_time": str(args.combined_member_time.resolve()),
            "combined_member_time_sha256": sha256_file(args.combined_member_time.resolve()),
            "matrix_file": str(args.matrix_file.resolve()),
            "matrix_sha256": sha256_file(args.matrix_file.resolve()),
            "config": str(args.config.resolve()),
            "config_sha256": sha256_file(args.config.resolve()),
        }
    )
    (output_directory / "resolution_decision.json").write_text(
        json.dumps(decision, indent=2) + "\n",
        encoding="utf-8",
    )
    print("GOLOVIN_RESOLUTION_ANALYSIS_PASS=1")
    print(f"status={decision['status']}")
    print(f"selected_max_superdroplets={decision['selected_max_superdroplets']}")
    print(f"output_directory={output_directory}")


if __name__ == "__main__":
    main()
