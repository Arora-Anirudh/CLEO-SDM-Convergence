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
import os
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from golovin_stage0 import (
    bootstrap_ensemble_mean_l1,
    fixed_bin_relative_l1,
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


def portable_artifact_path(path: Path, *, analysis_root: Path) -> str:
    """Return an artifact path that remains valid when the analysis root moves."""
    relative = os.path.relpath(path.resolve(), start=analysis_root.resolve())
    return Path(relative).as_posix()


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


def bootstrap_l1_values(
    stack: np.ndarray,
    analytical: np.ndarray,
    edges: np.ndarray,
    draw_indices: np.ndarray,
    *,
    batch_size: int = 100,
) -> np.ndarray:
    """Return L1 values for bootstrap draws without allocating one huge cube."""
    stack = np.asarray(stack, dtype=float)
    analytical = np.asarray(analytical, dtype=float)
    edges = np.asarray(edges, dtype=float)
    draw_indices = np.asarray(draw_indices, dtype=int)
    if stack.ndim != 2:
        raise ValueError("distribution stack must have shape (members, bins)")
    if draw_indices.ndim != 2 or draw_indices.shape[1] < 1:
        raise ValueError("draw indices must have shape (resamples, ensemble size)")
    if np.any(draw_indices < 0) or np.any(draw_indices >= stack.shape[0]):
        raise ValueError("bootstrap draw index is outside the member stack")

    values = np.empty(draw_indices.shape[0], dtype=float)
    for start in range(0, draw_indices.shape[0], batch_size):
        stop = min(start + batch_size, draw_indices.shape[0])
        ensemble_means = np.mean(stack[draw_indices[start:stop]], axis=1)
        values[start:stop] = [
            fixed_bin_relative_l1(distribution, analytical, edges)
            for distribution in ensemble_means
        ]
    return values


def analyze_ensemble_size_sensitivity(
    *,
    rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    config: dict[str, Any],
    archives: dict[str, dict[str, np.ndarray]],
) -> list[dict[str, object]]:
    """Estimate how each registered property stabilizes with ensemble size.

    Bootstrap samples are drawn with replacement from the complete member pool.
    The resulting intervals describe repeat-ensemble sampling variability at
    each requested member count; they are descriptive and do not alter the
    formal convergence decision.
    """
    settings = config["diagnostics"]["ensemble_size_sensitivity"]
    time_s = float(settings["time_s"])
    member_counts = [int(value) for value in settings["member_counts"]]
    resamples = int(settings["bootstrap_resamples"])
    base_seed = int(settings["bootstrap_seed"])
    bin_count = int(settings["log_radius_bins"])
    confidence_level = float(config["diagnostics"]["confidence_level"])
    if member_counts != sorted(set(member_counts)) or member_counts[0] < 2:
        raise ValueError("ensemble-size member counts must be unique, sorted and at least two")
    if resamples < 2:
        raise ValueError("ensemble-size sensitivity requires at least two bootstrap resamples")
    if bin_count not in BIN_COUNTS:
        raise ValueError("ensemble-size L1 bin count is not registered")

    matrix_lookup = {
        (int(row["max_superdroplets"]), int(row["member_index"])): row for row in matrix_rows
    }
    resolutions = sorted({int(row["max_superdroplets"]) for row in matrix_rows})
    rows_at_time = [
        row
        for row in rows
        if np.isclose(float(row["time_s"]), time_s, rtol=0.0, atol=1.0e-3)
    ]
    diagnostic_lookup = {
        (int(row["max_superdroplets"]), int(row["member_index"])): row
        for row in rows_at_time
    }

    output_rows: list[dict[str, object]] = []
    alpha = (1.0 - confidence_level) / 2.0
    for resolution in resolutions:
        members = sorted(
            int(row["member_index"])
            for row in matrix_rows
            if int(row["max_superdroplets"]) == resolution
        )
        if member_counts[-1] > len(members):
            raise ValueError(
                f"ensemble-size sensitivity requests {member_counts[-1]} members "
                f"but resolution {resolution} has only {len(members)}"
            )
        if any((resolution, member) not in diagnostic_lookup for member in members):
            raise RuntimeError(f"missing {time_s:g}-s member diagnostics for {resolution}")

        stack, analytical, edges = distribution_stack(
            resolution=resolution,
            members=members,
            time_s=time_s,
            bin_count=bin_count,
            matrix_lookup=matrix_lookup,
            archives=archives,
        )
        moment_values = {
            metric: np.asarray(
                [float(diagnostic_lookup[(resolution, member)][metric]) for member in members]
            )
            for metric in MOMENT_METRICS
        }
        full_estimates = {
            f"ensemble_mean_l1_bins_{bin_count}": fixed_bin_relative_l1(
                np.mean(stack, axis=0),
                analytical,
                edges,
            ),
            **{metric: float(np.mean(values)) for metric, values in moment_values.items()},
        }

        for member_count in member_counts:
            rng = np.random.default_rng(
                derived_seed(base_seed, "ensemble_size", resolution, member_count)
            )
            draw_indices = rng.integers(
                0,
                len(members),
                size=(resamples, member_count),
            )
            sampled_values = {
                f"ensemble_mean_l1_bins_{bin_count}": bootstrap_l1_values(
                    stack,
                    analytical,
                    edges,
                    draw_indices,
                ),
                **{
                    metric: np.mean(values[draw_indices], axis=1)
                    for metric, values in moment_values.items()
                },
            }
            for metric, values in sampled_values.items():
                low, median, high = np.quantile(values, [alpha, 0.5, 1.0 - alpha])
                output_rows.append(
                    {
                        "max_superdroplets": resolution,
                        "time_s": time_s,
                        "metric": metric,
                        "ensemble_size": member_count,
                        "bootstrap_resamples": resamples,
                        "full_ensemble_size": len(members),
                        "full_ensemble_estimate": full_estimates[metric],
                        "bootstrap_median": float(median),
                        "bootstrap_95ci_low": float(low),
                        "bootstrap_95ci_high": float(high),
                        "bootstrap_95ci_half_width": float((high - low) / 2.0),
                    }
                )
    return output_rows


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
    config: dict[str, Any],
    output: Path,
) -> None:
    criteria = config["convergence_criteria"]
    times = sorted({float(row["time_s"]) for row in analytical_rows})
    colors = plt.get_cmap("viridis")(np.linspace(0.08, 0.92, len(times)))
    metric_settings = (
        (
            "ensemble_mean_l1_bins_500",
            "Mean distribution",
            "L1 error / %",
            float(criteria["analytical_agreement"]["maximum_l1_upper_95ci"]) * 100.0,
            False,
        ),
        (
            "golovin_relative_error_radius_moment_0_m3",
            r"$M_0$: droplet number",
            "relative bias / %",
            float(criteria["analytical_agreement"]["moment0_relative_bias_margin"]) * 100.0,
            True,
        ),
        (
            "golovin_relative_error_radius_moment_6_um6_m3",
            r"$M_6$: large-drop tail",
            "relative bias / %",
            float(criteria["analytical_agreement"]["moment6_relative_bias_margin"]) * 100.0,
            True,
        ),
    )
    resolutions = sorted({int(row["max_superdroplets"]) for row in analytical_rows})
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    for axis, (metric, title, ylabel, margin, signed) in zip(
        axes,
        metric_settings,
        strict=True,
    ):
        for time_s, color in zip(times, colors, strict=True):
            selected = sorted(
                (
                    row
                    for row in analytical_rows
                    if row["metric"] == metric
                    and np.isclose(float(row["time_s"]), time_s, rtol=0.0, atol=1.0e-3)
                ),
                key=lambda row: int(row["max_superdroplets"]),
            )
            x = np.asarray([float(row["max_superdroplets"]) for row in selected])
            estimate = np.asarray([float(row["estimate"]) for row in selected]) * 100.0
            low = np.asarray([float(row["95ci_low"]) for row in selected]) * 100.0
            high = np.asarray([float(row["95ci_high"]) for row in selected]) * 100.0
            plot_estimates_and_intervals(
                axis,
                x,
                estimate,
                low,
                high,
                color=color,
                label=f"{time_s / 60.0:g} min",
            )
        if signed:
            axis.axhspan(-margin, margin, color="#d8f0dc", zorder=0)
            axis.axhline(0.0, color="black", linewidth=0.8)
        else:
            axis.axhspan(0.0, margin, color="#d8f0dc", zorder=0)
            axis.set_ylim(bottom=0.0)
        axis.set_xscale("log", base=2)
        axis.set_xticks(
            resolutions,
            [
                f"{resolution // 1024}k"
                if resolution % 1024 == 0
                else f"{resolution:,}"
                for resolution in resolutions
            ],
        )
        axis.set_title(title)
        axis.set_xlabel(r"$N_\mathrm{SD}$")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.22)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle("Agreement with the Golovin analytical solution", y=0.98)
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=len(times),
        frameon=False,
        title="simulation time",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.80))
    fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_estimates_and_intervals(
    axis: plt.Axes,
    x: np.ndarray,
    estimate: np.ndarray,
    low: np.ndarray,
    high: np.ndarray,
    *,
    color: object | None = None,
    label: str | None = None,
) -> None:
    """Plot estimates and percentile interval endpoints safely."""
    if (
        np.any(~np.isfinite(estimate))
        or np.any(~np.isfinite(low))
        or np.any(~np.isfinite(high))
    ):
        raise ValueError("plot estimates and interval endpoints must be finite")
    if np.any(low > high):
        raise ValueError("plot interval lower endpoints exceed upper endpoints")

    (line,) = axis.plot(x, estimate, marker="o", color=color, label=label)
    # A percentile-bootstrap interval need not contain the observed nonlinear
    # estimate, so draw endpoints rather than signed error-bar distances.
    axis.vlines(x, low, high, color=line.get_color(), alpha=0.8)


def plot_adjacent_equivalence(
    adjacent_rows: list[dict[str, object]],
    config: dict[str, Any],
    output: Path,
) -> None:
    criteria = config["convergence_criteria"]
    times = sorted({float(row["time_s"]) for row in adjacent_rows})
    colors = plt.get_cmap("viridis")(np.linspace(0.08, 0.92, len(times)))
    metric_settings = (
        (
            "ensemble_mean_l1_bins_500",
            "Mean distribution",
            "L1 change / percentage points",
            float(
                criteria["adjacent_level_equivalence"]["l1_absolute_difference_margin"]
            )
            * 100.0,
        ),
        (
            "golovin_relative_error_radius_moment_0_m3",
            r"$M_0$: droplet number",
            "relative change / %",
            float(
                criteria["adjacent_level_equivalence"]["moment0_relative_difference_margin"]
            )
            * 100.0,
        ),
        (
            "golovin_relative_error_radius_moment_6_um6_m3",
            r"$M_6$: large-drop tail",
            "relative change / %",
            float(
                criteria["adjacent_level_equivalence"]["moment6_relative_difference_margin"]
            )
            * 100.0,
        ),
    )
    pairs = sorted(
        {
            (int(row["lower_max_superdroplets"]), int(row["upper_max_superdroplets"]))
            for row in adjacent_rows
        }
    )
    pair_x = np.arange(len(pairs), dtype=float)
    pair_labels = [f"{lower // 1024}k→{upper // 1024}k" for lower, upper in pairs]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    for axis, (metric, title, ylabel, margin) in zip(
        axes,
        metric_settings,
        strict=True,
    ):
        for time_s, color in zip(times, colors, strict=True):
            selected_lookup = {
                (
                    int(row["lower_max_superdroplets"]),
                    int(row["upper_max_superdroplets"]),
                ): row
                for row in adjacent_rows
                if row["metric"] == metric
                and np.isclose(float(row["time_s"]), time_s, rtol=0.0, atol=1.0e-3)
            }
            selected = [selected_lookup[pair] for pair in pairs]
            estimate = (
                np.asarray(
                    [float(row["estimated_difference_lower_minus_upper"]) for row in selected]
                )
                * 100.0
            )
            low = np.asarray([float(row["95ci_low"]) for row in selected]) * 100.0
            high = np.asarray([float(row["95ci_high"]) for row in selected]) * 100.0
            plot_estimates_and_intervals(
                axis,
                pair_x,
                estimate,
                low,
                high,
                color=color,
                label=f"{time_s / 60.0:g} min",
            )
        axis.axhspan(-margin, margin, color="#d8f0dc", zorder=0)
        axis.axhline(0.0, color="black", linewidth=0.8)
        axis.set_xticks(pair_x, pair_labels)
        axis.set_title(title)
        axis.set_xlabel(r"resolution doubling")
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.22)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle("Change when the superdroplet resolution is doubled", y=0.98)
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.91),
        ncol=len(times),
        frameon=False,
        title="simulation time",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.80))
    fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_ensemble_size_sensitivity(
    sensitivity_rows: list[dict[str, object]],
    config: dict[str, Any],
    output: Path,
) -> None:
    criteria = config["convergence_criteria"]
    resolutions = sorted({int(row["max_superdroplets"]) for row in sensitivity_rows})
    metric_settings = (
        (
            "ensemble_mean_l1_bins_500",
            "L1 error / %",
            float(criteria["analytical_agreement"]["maximum_l1_upper_95ci"]) * 100.0,
            False,
        ),
        (
            "golovin_relative_error_radius_moment_0_m3",
            r"$M_0$ bias / %",
            float(criteria["analytical_agreement"]["moment0_relative_bias_margin"]) * 100.0,
            True,
        ),
        (
            "golovin_relative_error_radius_moment_6_um6_m3",
            r"$M_6$ bias / %",
            float(criteria["analytical_agreement"]["moment6_relative_bias_margin"]) * 100.0,
            True,
        ),
    )
    fig, axes = plt.subplots(
        len(metric_settings),
        len(resolutions),
        figsize=(16, 10),
        sharex=True,
        sharey="row",
    )
    for column, resolution in enumerate(resolutions):
        axes[0, column].set_title(f"{resolution:,} SDs")
        for row_index, (metric, ylabel, margin, signed) in enumerate(metric_settings):
            axis = axes[row_index, column]
            selected = sorted(
                (
                    row
                    for row in sensitivity_rows
                    if int(row["max_superdroplets"]) == resolution and row["metric"] == metric
                ),
                key=lambda row: int(row["ensemble_size"]),
            )
            ensemble_size = np.asarray([int(row["ensemble_size"]) for row in selected])
            median = np.asarray([float(row["bootstrap_median"]) for row in selected]) * 100.0
            low = np.asarray([float(row["bootstrap_95ci_low"]) for row in selected]) * 100.0
            high = np.asarray([float(row["bootstrap_95ci_high"]) for row in selected]) * 100.0
            full_estimate = float(selected[0]["full_ensemble_estimate"]) * 100.0

            axis.fill_between(
                ensemble_size,
                low,
                high,
                color="#8fb9dd",
                alpha=0.45,
                label="95% bootstrap range" if column == 0 and row_index == 0 else None,
            )
            axis.plot(
                ensemble_size,
                median,
                marker="o",
                color="#2468a2",
                label="bootstrap median" if column == 0 and row_index == 0 else None,
            )
            axis.axhline(
                full_estimate,
                color="#d95f02",
                linestyle="--",
                linewidth=1.2,
                label="100-member estimate" if column == 0 and row_index == 0 else None,
            )
            if signed:
                axis.axhline(0.0, color="black", linewidth=0.7)
                axis.set_ylim(-margin * 1.1, margin * 1.1)
            else:
                axis.axhline(margin, color="#3a9147", linewidth=1.0)
                axis.set_ylim(bottom=0.0)
            axis.grid(alpha=0.2)
            if column == 0:
                axis.set_ylabel(ylabel)
            if row_index == len(metric_settings) - 1:
                axis.set_xlabel("ensemble members")

    handles, labels = axes[0, 0].get_legend_handles_labels()
    time_s = float(sensitivity_rows[0]["time_s"])
    fig.suptitle(f"Ensemble-size stability at {time_s / 60.0:g} min", y=0.985)
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.945),
        ncol=3,
        frameon=False,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
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
    sensitivity_rows = analyze_ensemble_size_sensitivity(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )

    output_directory.mkdir(parents=True)
    write_csv(output_directory / "analytical_agreement.csv", analytical_rows)
    write_csv(output_directory / "adjacent_resolution_equivalence.csv", adjacent_rows)
    write_csv(output_directory / "ensemble_size_sensitivity.csv", sensitivity_rows)
    plot_result(
        analytical_rows,
        config,
        output_directory / "analytical_accuracy.png",
    )
    plot_adjacent_equivalence(
        adjacent_rows,
        config,
        output_directory / "adjacent_resolution_equivalence.png",
    )
    plot_ensemble_size_sensitivity(
        sensitivity_rows,
        config,
        output_directory / "ensemble_size_stability.png",
    )
    decision.update(
        {
            "combined_member_time": portable_artifact_path(
                args.combined_member_time,
                analysis_root=output_directory.parent,
            ),
            "combined_member_time_path_base": "analysis_root",
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
