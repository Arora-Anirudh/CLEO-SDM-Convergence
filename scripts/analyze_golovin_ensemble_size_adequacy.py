#!/usr/bin/env python3
"""Retrospectively project formal Golovin adequacy versus ensemble size.

This script is analysis-only. It treats the completed 50-member ensemble at
each resolution as the empirical parent population and projects the sampling
intervals for fresh ensembles of size 5--50. It never modifies or reruns CLEO.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import yaml
from scipy.stats import t as student_t

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from golovin_stage0 import fixed_bin_relative_l1  # noqa: E402, I001


M0 = "golovin_relative_error_radius_moment_0_m3"
M6 = "golovin_relative_error_radius_moment_6_um6_m3"
MOMENTS = (M0, M6)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--member-time", required=True, type=Path)
    parser.add_argument("--stage0-root", required=True, type=Path)
    parser.add_argument("--resolution-decision", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_formal_target_resolution(path: Path) -> int:
    """Read the immutable full-50 operational selection used as the adequacy target."""
    with path.open(encoding="utf-8") as source:
        decision = json.load(source)
    if decision.get("status") != "selected_operational_resolution":
        raise ValueError("resolution decision does not contain an operational selection")
    target = decision.get("selected_max_superdroplets")
    if not isinstance(target, int) or target <= 0:
        raise ValueError("resolution decision has no positive selected superdroplet count")
    return target


def derived_seed(base: int, *parts: object) -> int:
    payload = "|".join([str(base), *(str(part) for part in parts)])
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big")


def read_csv(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source, delimiter=delimiter))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def nominal_time(value: float, decision_times: list[float]) -> float:
    nearest = min(decision_times, key=lambda candidate: abs(candidate - value))
    if not np.isclose(value, nearest, rtol=0.0, atol=1.0e-3):
        raise ValueError(f"time {value} is not one of the registered decision times")
    return nearest


def projected_student_interval(
    values: np.ndarray,
    member_count: int,
    confidence_level: float,
) -> tuple[float, float, float]:
    values = np.asarray(values, dtype=float)
    mean = float(np.mean(values))
    standard_error = float(np.std(values, ddof=1) / math.sqrt(member_count))
    multiplier = float(student_t.ppf(0.5 + confidence_level / 2.0, member_count - 1))
    return mean, mean - multiplier * standard_error, mean + multiplier * standard_error


def projected_welch_interval(
    lower: np.ndarray,
    upper: np.ndarray,
    member_count: int,
    confidence_level: float,
) -> tuple[float, float, float]:
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    lower_term = float(np.var(lower, ddof=1) / member_count)
    upper_term = float(np.var(upper, ddof=1) / member_count)
    standard_error = math.sqrt(lower_term + upper_term)
    if standard_error == 0.0:
        multiplier = 0.0
    else:
        denominator = lower_term**2 / (member_count - 1) + upper_term**2 / (member_count - 1)
        degrees_freedom = (lower_term + upper_term) ** 2 / denominator
        multiplier = float(student_t.ppf(0.5 + confidence_level / 2.0, degrees_freedom))
    difference = float(np.mean(lower) - np.mean(upper))
    return (
        difference,
        difference - multiplier * standard_error,
        difference + multiplier * standard_error,
    )


def bootstrap_l1_all_counts(
    stack: np.ndarray,
    analytical: np.ndarray,
    edges: np.ndarray,
    member_counts: list[int],
    *,
    resamples: int,
    seed: int,
    batch_size: int = 100,
) -> np.ndarray:
    """Return L1 bootstrap draws with shape (counts, resamples, times).

    A common nested bootstrap index stream is used across member counts. Each
    resolution receives an independently derived seed.
    """
    stack = np.asarray(stack, dtype=float)
    analytical = np.asarray(analytical, dtype=float)
    edges = np.asarray(edges, dtype=float)
    if stack.ndim != 3 or stack.shape[0] != 50:
        raise ValueError("distribution stack must have shape (50, times, bins)")
    if analytical.shape != stack.shape[1:]:
        raise ValueError("analytical distribution shape does not match member stack")
    if edges.shape != (stack.shape[2] + 1,):
        raise ValueError("fixed-bin edges do not match the distribution stack")
    if member_counts != list(range(member_counts[0], member_counts[-1] + 1)):
        raise ValueError("member counts must be a consecutive integer range")

    delta_ln = np.diff(np.log(edges))
    denominator = np.sum(np.abs(analytical) * delta_ln[None, :], axis=1)
    if np.any(denominator <= 0.0):
        raise ValueError("analytical L1 denominator must be positive at every time")

    generator = np.random.default_rng(seed)
    indices = generator.integers(0, stack.shape[0], size=(resamples, member_counts[-1]))
    output = np.empty(
        (len(member_counts), resamples, stack.shape[1]),
        dtype=np.float64,
    )
    count_to_position = {count: index for index, count in enumerate(member_counts)}

    for start in range(0, resamples, batch_size):
        stop = min(start + batch_size, resamples)
        running = np.zeros((stop - start, stack.shape[1], stack.shape[2]), dtype=float)
        for draw_position in range(member_counts[-1]):
            running += stack[indices[start:stop, draw_position]]
            member_count = draw_position + 1
            if member_count not in count_to_position:
                continue
            means = running / member_count
            l1 = (
                np.sum(
                    np.abs(means - analytical[None, :, :]) * delta_ln[None, None, :],
                    axis=2,
                )
                / denominator[None, :]
            )
            output[count_to_position[member_count], start:stop, :] = l1
    return output


def validate_and_load(
    *,
    config: dict[str, Any],
    cases_path: Path,
    member_time_path: Path,
    stage0_root: Path,
) -> tuple[
    list[int],
    list[int],
    list[float],
    dict[int, np.ndarray],
    dict[int, np.ndarray],
    np.ndarray,
    dict[int, dict[str, np.ndarray]],
    dict[int, bool],
    list[dict[str, object]],
]:
    settings = config["analysis"]
    diagnostics = config["diagnostics"]
    member_counts = list(
        range(
            int(settings["tested_member_counts"]["minimum"]),
            int(settings["tested_member_counts"]["maximum"]) + 1,
            int(settings["tested_member_counts"]["step"]),
        )
    )
    decision_times = [float(value) for value in diagnostics["decision_times_s"]]
    bin_count = int(diagnostics["primary_log_radius_bins"])

    cases = read_csv(cases_path, delimiter="\t")
    rows = read_csv(member_time_path)
    if len(cases) != 450:
        raise ValueError(f"expected 450 matrix cases, found {len(cases)}")
    labels = [row["run_label"] for row in cases]
    if len(labels) != len(set(labels)):
        raise ValueError("matrix contains duplicate run labels")
    resolutions = sorted({int(row["max_superdroplets"]) for row in cases})
    if len(resolutions) != 9:
        raise ValueError(f"expected nine resolutions, found {resolutions}")

    case_lookup: dict[tuple[int, int], dict[str, str]] = {}
    for row in cases:
        key = (int(row["max_superdroplets"]), int(row["member_index"]))
        if key in case_lookup:
            raise ValueError(f"duplicate resolution/member case: {key}")
        case_lookup[key] = row
    for resolution in resolutions:
        members = sorted(member for res, member in case_lookup if res == resolution)
        if members != list(range(50)):
            raise ValueError(f"resolution {resolution} does not contain members 0--49")

    diagnostic_lookup: dict[tuple[int, int, float], dict[str, str]] = {}
    for row in rows:
        raw_time = float(row["time_s"])
        if not any(np.isclose(raw_time, time, rtol=0.0, atol=1.0e-3) for time in decision_times):
            continue
        time = nominal_time(raw_time, decision_times)
        key = (int(row["max_superdroplets"]), int(row["member_index"]), time)
        if key in diagnostic_lookup:
            raise ValueError(f"duplicate diagnostic row: {key}")
        diagnostic_lookup[key] = row
    if len(diagnostic_lookup) != len(resolutions) * 50 * len(decision_times):
        raise ValueError("member-time diagnostics do not form the exact 9x50x6 matrix")

    stacks: dict[int, np.ndarray] = {}
    analytical_by_resolution: dict[int, np.ndarray] = {}
    edges_reference: np.ndarray | None = None
    moments: dict[int, dict[str, np.ndarray]] = {}
    validity: dict[int, bool] = {}
    archive_hash_rows: list[dict[str, object]] = []

    for resolution in resolutions:
        member_arrays = []
        analytical_reference: np.ndarray | None = None
        moment_arrays = {
            metric: np.empty((50, len(decision_times)), dtype=float) for metric in MOMENTS
        }
        valid = True
        for member in range(50):
            case = case_lookup[(resolution, member)]
            run_label = case["run_label"]
            archive_path = (
                stage0_root / run_label / "analysis_stage0_v2" / "fixed_bin_distributions.npz"
            )
            if not archive_path.is_file():
                raise FileNotFoundError(f"missing Stage-0 archive: {archive_path}")
            archive_hash_rows.append(
                {
                    "run_label": run_label,
                    "path": f"{run_label}/analysis_stage0_v2/fixed_bin_distributions.npz",
                    "sha256": sha256(archive_path),
                }
            )
            with np.load(archive_path, allow_pickle=False) as source:
                archive_times = np.asarray(source["time_s"], dtype=float)
                time_indices = [
                    int(np.argmin(np.abs(archive_times - time))) for time in decision_times
                ]
                for time, index in zip(decision_times, time_indices, strict=True):
                    if not np.isclose(archive_times[index], time, rtol=0.0, atol=1.0e-3):
                        raise ValueError(f"archive {run_label} lacks registered time {time}")
                edges = np.asarray(source[f"edges_um_{bin_count}"], dtype=float)
                numerical = np.asarray(
                    source[f"numerical_gm3_per_ln_radius_{bin_count}"], dtype=float
                )[time_indices]
                analytical = np.asarray(
                    source[f"analytical_gm3_per_ln_radius_{bin_count}"], dtype=float
                )[time_indices]
            if edges_reference is None:
                edges_reference = edges
            elif not np.array_equal(edges_reference, edges):
                raise ValueError("primary fixed-bin edges differ between members")
            if analytical_reference is None:
                analytical_reference = analytical
            elif not np.array_equal(analytical_reference, analytical):
                raise ValueError(f"analytical arrays differ within resolution {resolution}")
            member_arrays.append(numerical)

            for time_index, time in enumerate(decision_times):
                row = diagnostic_lookup[(resolution, member, time)]
                for metric in MOMENTS:
                    moment_arrays[metric][member, time_index] = float(row[metric])
                drift = abs(float(row["relative_liquid_mass_drift"]))
                outside = float(row["fixed_bin_mass_below_range_fraction"]) + float(
                    row["fixed_bin_mass_above_range_fraction"]
                )
                valid &= drift <= float(
                    config["convergence_criteria"]["maximum_relative_liquid_mass_drift"]
                )
                valid &= outside <= float(
                    config["convergence_criteria"]["maximum_out_of_range_mass_fraction"]
                )
        if analytical_reference is None:
            raise RuntimeError("analytical reference was not loaded")
        stacks[resolution] = np.asarray(member_arrays, dtype=float)
        analytical_by_resolution[resolution] = analytical_reference
        moments[resolution] = moment_arrays
        validity[resolution] = valid

    if edges_reference is None:
        raise RuntimeError("fixed-bin edges were not loaded")
    first_reference = analytical_by_resolution[resolutions[0]]
    for resolution in resolutions[1:]:
        if not np.array_equal(first_reference, analytical_by_resolution[resolution]):
            raise ValueError("analytical arrays differ between resolutions")

    return (
        resolutions,
        member_counts,
        decision_times,
        stacks,
        analytical_by_resolution,
        edges_reference,
        moments,
        validity,
        archive_hash_rows,
    )


def analyze(
    *,
    config: dict[str, Any],
    resolutions: list[int],
    member_counts: list[int],
    decision_times: list[float],
    stacks: dict[int, np.ndarray],
    analytical: dict[int, np.ndarray],
    edges: np.ndarray,
    moments: dict[int, dict[str, np.ndarray]],
    validity: dict[int, bool],
    formal_target_resolution: int,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    settings = config["analysis"]
    criteria = config["convergence_criteria"]
    confidence = float(settings["confidence_level"])
    resamples = int(settings["bootstrap_resamples"])
    base_seed = int(settings["bootstrap_seed"])
    alpha = (1.0 - confidence) / 2.0

    l1_draws = {
        resolution: bootstrap_l1_all_counts(
            stacks[resolution],
            analytical[resolution],
            edges,
            member_counts,
            resamples=resamples,
            seed=derived_seed(base_seed, "resolution", resolution),
        )
        for resolution in resolutions
    }
    point_l1 = {
        resolution: np.asarray(
            [
                fixed_bin_relative_l1(
                    np.mean(stacks[resolution][:, time_index, :], axis=0),
                    analytical[resolution][time_index],
                    edges,
                )
                for time_index in range(len(decision_times))
            ]
        )
        for resolution in resolutions
    }

    analytical_rows: list[dict[str, object]] = []
    adjacent_rows: list[dict[str, object]] = []
    selection_rows: list[dict[str, object]] = []
    limiting_rows: list[dict[str, object]] = []
    selections: dict[int, int | None] = {}
    if settings["target_selected_resolution"] != "derived_from_full_50_selection":
        raise ValueError("adequacy analysis must derive its target from the full-50 decision")
    if formal_target_resolution not in resolutions:
        raise ValueError("formal target resolution is absent from the adequacy matrix")

    for count_index, member_count in enumerate(member_counts):
        resolution_pass = {resolution: validity[resolution] for resolution in resolutions}
        pair_pass = {
            (lower, upper): True
            for lower, upper in zip(resolutions[:-1], resolutions[1:], strict=True)
        }
        analytical_for_count: list[dict[str, object]] = []
        adjacent_for_count: list[dict[str, object]] = []

        for resolution in resolutions:
            for time_index, time in enumerate(decision_times):
                values = l1_draws[resolution][count_index, :, time_index]
                low, high = np.quantile(values, [alpha, 1.0 - alpha])
                estimate = float(point_l1[resolution][time_index])
                half_width = float((high - low) / 2.0)
                accuracy_margin = float(criteria["analytical_agreement"]["maximum_l1_upper_95ci"])
                precision_margin = float(criteria["maximum_95ci_half_width"]["l1_absolute"])
                accuracy_pass = bool(high <= accuracy_margin)
                precision_pass = bool(half_width <= precision_margin)
                resolution_pass[resolution] &= accuracy_pass and precision_pass
                analytical_for_count.append(
                    {
                        "ensemble_size": member_count,
                        "max_superdroplets": resolution,
                        "time_s": time,
                        "metric": "ensemble_mean_l1_bins_500",
                        "full50_point_estimate": estimate,
                        "projected_95ci_low": float(low),
                        "projected_95ci_high": float(high),
                        "projected_95ci_half_width": half_width,
                        "accuracy_margin": accuracy_margin,
                        "precision_margin": precision_margin,
                        "accuracy_pass": accuracy_pass,
                        "precision_pass": precision_pass,
                    }
                )

                for metric, accuracy_key, precision_key in (
                    (M0, "moment0_relative_bias_margin", "moment0_relative"),
                    (M6, "moment6_relative_bias_margin", "moment6_relative"),
                ):
                    estimate, low, high = projected_student_interval(
                        moments[resolution][metric][:, time_index],
                        member_count,
                        confidence,
                    )
                    accuracy_margin = float(criteria["analytical_agreement"][accuracy_key])
                    precision_margin = float(criteria["maximum_95ci_half_width"][precision_key])
                    half_width = (high - low) / 2.0
                    accuracy_pass = low >= -accuracy_margin and high <= accuracy_margin
                    precision_pass = half_width <= precision_margin
                    resolution_pass[resolution] &= accuracy_pass and precision_pass
                    analytical_for_count.append(
                        {
                            "ensemble_size": member_count,
                            "max_superdroplets": resolution,
                            "time_s": time,
                            "metric": metric,
                            "full50_point_estimate": estimate,
                            "projected_95ci_low": low,
                            "projected_95ci_high": high,
                            "projected_95ci_half_width": half_width,
                            "accuracy_margin": accuracy_margin,
                            "precision_margin": precision_margin,
                            "accuracy_pass": accuracy_pass,
                            "precision_pass": precision_pass,
                        }
                    )

        for lower, upper in zip(resolutions[:-1], resolutions[1:], strict=True):
            for time_index, time in enumerate(decision_times):
                differences = (
                    l1_draws[lower][count_index, :, time_index]
                    - l1_draws[upper][count_index, :, time_index]
                )
                low, high = np.quantile(differences, [alpha, 1.0 - alpha])
                estimate = float(point_l1[lower][time_index] - point_l1[upper][time_index])
                margin = float(
                    criteria["adjacent_level_equivalence"]["l1_absolute_difference_margin"]
                )
                passed = bool(low >= -margin and high <= margin)
                pair_pass[(lower, upper)] &= passed
                adjacent_for_count.append(
                    {
                        "ensemble_size": member_count,
                        "lower_max_superdroplets": lower,
                        "upper_max_superdroplets": upper,
                        "time_s": time,
                        "metric": "ensemble_mean_l1_bins_500",
                        "full50_point_difference_lower_minus_upper": estimate,
                        "projected_95ci_low": float(low),
                        "projected_95ci_high": float(high),
                        "equivalence_margin": margin,
                        "equivalence_pass": passed,
                    }
                )

                for metric, margin_key in (
                    (M0, "moment0_relative_difference_margin"),
                    (M6, "moment6_relative_difference_margin"),
                ):
                    estimate, low, high = projected_welch_interval(
                        moments[lower][metric][:, time_index],
                        moments[upper][metric][:, time_index],
                        member_count,
                        confidence,
                    )
                    margin = float(criteria["adjacent_level_equivalence"][margin_key])
                    passed = low >= -margin and high <= margin
                    pair_pass[(lower, upper)] &= passed
                    adjacent_for_count.append(
                        {
                            "ensemble_size": member_count,
                            "lower_max_superdroplets": lower,
                            "upper_max_superdroplets": upper,
                            "time_s": time,
                            "metric": metric,
                            "full50_point_difference_lower_minus_upper": estimate,
                            "projected_95ci_low": low,
                            "projected_95ci_high": high,
                            "equivalence_margin": margin,
                            "equivalence_pass": passed,
                        }
                    )

        accepted = []
        for index, resolution in enumerate(resolutions[:-2]):
            double = resolutions[index + 1]
            quadruple = resolutions[index + 2]
            if (
                resolution_pass[resolution]
                and resolution_pass[double]
                and resolution_pass[quadruple]
                and pair_pass[(resolution, double)]
                and pair_pass[(double, quadruple)]
            ):
                accepted.append(resolution)
        selected = min(accepted) if accepted else None
        selections[member_count] = selected
        selection_rows.append(
            {
                "ensemble_size": member_count,
                "selected_max_superdroplets": selected if selected is not None else "",
                "accepted_candidates": ";".join(str(value) for value in accepted),
            }
        )

        analytical_rows.extend(analytical_for_count)
        adjacent_rows.extend(adjacent_for_count)

    target = formal_target_resolution
    for row in selection_rows:
        selected = row["selected_max_superdroplets"]
        row["target_selected_resolution"] = target if target is not None else ""
        row["target_resolution_selected"] = (
            target is not None and selected != "" and int(selected) == target
        )
    if target is None:
        decision = {
            "schema": "golovin_fixed50_ensemble_size_adequacy_v2",
            "status": "not_assessed_no_full_50_resolution_selection",
            "smallest_retrospectively_supported_tested_ensemble_size": None,
            "target_selected_resolution": None,
            "target_selection_source": "formal_operational_resolution_decision",
            "tested_member_counts": member_counts,
            "formal_rule": (
                "no target exists because the full 50-member formal analysis selected none"
            ),
            "interpretation": config["interpretation"]["allowed_claim"],
            "prohibited_claims": config["interpretation"]["prohibited_claims"],
        }
        return analytical_rows, adjacent_rows, selection_rows, limiting_rows, decision

    target_index = resolutions.index(target)
    if target_index > len(resolutions) - 3:
        raise ValueError("selected target has no N/2N/4N confirmation triple")
    triple = set(resolutions[target_index : target_index + 3])
    pairs = {
        (resolutions[target_index], resolutions[target_index + 1]),
        (resolutions[target_index + 1], resolutions[target_index + 2]),
    }
    for member_count in member_counts:
        for metric in ("ensemble_mean_l1_bins_500", M0, M6):
            relevant_analytical = [
                row
                for row in analytical_rows
                if int(row["ensemble_size"]) == member_count
                and row["metric"] == metric
                and int(row["max_superdroplets"]) in triple
            ]
            relevant_adjacent = [
                row
                for row in adjacent_rows
                if int(row["ensemble_size"]) == member_count
                and row["metric"] == metric
                and (int(row["lower_max_superdroplets"]), int(row["upper_max_superdroplets"]))
                in pairs
            ]
            analytical_ratio = max(
                (
                    float(row["projected_95ci_high"]) / float(row["accuracy_margin"])
                    if metric == "ensemble_mean_l1_bins_500"
                    else max(
                        abs(float(row["projected_95ci_low"])),
                        abs(float(row["projected_95ci_high"])),
                    )
                    / float(row["accuracy_margin"])
                )
                for row in relevant_analytical
            )
            precision_ratio = max(
                float(row["projected_95ci_half_width"]) / float(row["precision_margin"])
                for row in relevant_analytical
            )
            adjacent_ratio = max(
                max(
                    abs(float(row["projected_95ci_low"])),
                    abs(float(row["projected_95ci_high"])),
                )
                / float(row["equivalence_margin"])
                for row in relevant_adjacent
            )
            limiting_rows.append(
                {
                    "ensemble_size": member_count,
                    "metric": metric,
                    "worst_analytical_bound_over_margin": analytical_ratio,
                    "worst_precision_half_width_over_margin": precision_ratio,
                    "worst_adjacent_bound_over_margin": adjacent_ratio,
                    "worst_formal_gate_ratio": max(
                        analytical_ratio,
                        precision_ratio,
                        adjacent_ratio,
                    ),
                    "all_target_triple_gates_pass": max(
                        analytical_ratio,
                        precision_ratio,
                        adjacent_ratio,
                    )
                    <= 1.0,
                }
            )

    adequate = None
    for member_count in member_counts:
        if all(selections[count] == target for count in member_counts if count >= member_count):
            adequate = member_count
            break
    decision = {
        "schema": "golovin_fixed50_ensemble_size_adequacy_v2",
        "status": (
            "retrospective_adequate_count_identified"
            if adequate is not None
            else "no_retrospective_adequate_count_identified"
        ),
        "smallest_retrospectively_supported_tested_ensemble_size": adequate,
        "target_selected_resolution": target,
        "target_selection_source": "formal_operational_resolution_decision",
        "tested_member_counts": member_counts,
        "bootstrap_resamples": resamples,
        "selection_by_member_count": {str(count): selections[count] for count in member_counts},
        "formal_rule": (
            "primary 500-bin N/2N/4N analytical, precision and adjacent-equivalence "
            "gates at every 600--3600-s decision time"
        ),
        "interpretation": config["interpretation"]["allowed_claim"],
        "prohibited_claims": config["interpretation"]["prohibited_claims"],
    }
    return analytical_rows, adjacent_rows, selection_rows, limiting_rows, decision


def refine_boundary(
    *,
    config: dict[str, Any],
    resolutions: list[int],
    decision_times: list[float],
    stacks: dict[int, np.ndarray],
    analytical: dict[int, np.ndarray],
    edges: np.ndarray,
    adjacent_rows: list[dict[str, object]],
    selection_rows: list[dict[str, object]],
    limiting_rows: list[dict[str, object]],
    decision: dict[str, object],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Refine a near-threshold L1 boundary with independent large bootstraps."""
    initial_adequate = decision["smallest_retrospectively_supported_tested_ensemble_size"]
    if initial_adequate is None:
        decision["boundary_refinement"] = {"status": "not_triggered_no_initial_count"}
        return [], decision

    settings = config["analysis"]["boundary_refinement"]
    target = decision["target_selected_resolution"]
    if target is None:
        decision["boundary_refinement"] = {"status": "not_triggered_no_target_selection"}
        return [], decision
    target = int(target)
    target_index = resolutions.index(target)
    target_pairs = {
        (resolutions[target_index], resolutions[target_index + 1]),
        (resolutions[target_index + 1], resolutions[target_index + 2]),
    }
    candidates = [
        row
        for row in adjacent_rows
        if int(row["ensemble_size"]) == int(initial_adequate)
        and row["metric"] == "ensemble_mean_l1_bins_500"
        and (int(row["lower_max_superdroplets"]), int(row["upper_max_superdroplets"]))
        in target_pairs
    ]

    def normalized_ratio(row: dict[str, object]) -> float:
        return max(
            abs(float(row["projected_95ci_low"])),
            abs(float(row["projected_95ci_high"])),
        ) / float(row["equivalence_margin"])

    critical = max(candidates, key=normalized_ratio)
    critical_ratio = normalized_ratio(critical)
    trigger = float(settings["trigger_within_normalized_margin"])
    if abs(critical_ratio - 1.0) > trigger:
        decision["boundary_refinement"] = {
            "status": "not_triggered_outside_margin_window",
            "critical_normalized_ratio": critical_ratio,
        }
        return [], decision

    radius = int(settings["member_count_radius"])
    tested_counts = [int(value) for value in decision["tested_member_counts"]]
    counts = list(
        range(
            max(min(tested_counts), int(initial_adequate) - radius),
            min(max(tested_counts), int(initial_adequate) + radius) + 1,
        )
    )
    lower = int(critical["lower_max_superdroplets"])
    upper = int(critical["upper_max_superdroplets"])
    time_s = float(critical["time_s"])
    time_index = decision_times.index(time_s)
    resamples = int(settings["bootstrap_resamples_per_seed"])
    seeds = [int(value) for value in settings["bootstrap_seeds"]]
    margin = float(critical["equivalence_margin"])

    draws_by_count: dict[int, list[np.ndarray]] = {count: [] for count in counts}
    seed_pass_by_count: dict[int, list[bool]] = {count: [] for count in counts}
    output_rows: list[dict[str, object]] = []
    for seed in seeds:
        lower_draws = bootstrap_l1_all_counts(
            stacks[lower][:, [time_index], :],
            analytical[lower][[time_index], :],
            edges,
            counts,
            resamples=resamples,
            seed=derived_seed(seed, "lower", lower),
            batch_size=200,
        )[:, :, 0]
        upper_draws = bootstrap_l1_all_counts(
            stacks[upper][:, [time_index], :],
            analytical[upper][[time_index], :],
            edges,
            counts,
            resamples=resamples,
            seed=derived_seed(seed, "upper", upper),
            batch_size=200,
        )[:, :, 0]
        for index, count in enumerate(counts):
            differences = lower_draws[index] - upper_draws[index]
            draws_by_count[count].append(differences)
            low, high = np.quantile(differences, [0.025, 0.975])
            passed = bool(low >= -margin and high <= margin)
            seed_pass_by_count[count].append(passed)
            output_rows.append(
                {
                    "record_type": "independent_seed",
                    "bootstrap_seed": seed,
                    "ensemble_size": count,
                    "lower_max_superdroplets": lower,
                    "upper_max_superdroplets": upper,
                    "time_s": time_s,
                    "metric": "ensemble_mean_l1_bins_500",
                    "bootstrap_resamples": resamples,
                    "projected_95ci_low": float(low),
                    "projected_95ci_high": float(high),
                    "equivalence_margin": margin,
                    "normalized_worst_bound": max(abs(float(low)), abs(float(high))) / margin,
                    "equivalence_pass": passed,
                }
            )

    pooled_ratio: dict[int, float] = {}
    stable_pass: dict[int, bool] = {}
    for count in counts:
        pooled = np.concatenate(draws_by_count[count])
        low, high = np.quantile(pooled, [0.025, 0.975])
        pooled_pass = bool(low >= -margin and high <= margin)
        pooled_ratio[count] = max(abs(float(low)), abs(float(high))) / margin
        stable_pass[count] = (pooled_pass or not bool(settings["require_pooled_pass"])) and (
            all(seed_pass_by_count[count]) or not bool(settings["require_every_seed_pass"])
        )
        output_rows.append(
            {
                "record_type": "pooled_seeds",
                "bootstrap_seed": "pooled",
                "ensemble_size": count,
                "lower_max_superdroplets": lower,
                "upper_max_superdroplets": upper,
                "time_s": time_s,
                "metric": "ensemble_mean_l1_bins_500",
                "bootstrap_resamples": resamples * len(seeds),
                "projected_95ci_low": float(low),
                "projected_95ci_high": float(high),
                "equivalence_margin": margin,
                "normalized_worst_bound": pooled_ratio[count],
                "equivalence_pass": pooled_pass,
            }
        )

    selection_lookup = {int(row["ensemble_size"]): row for row in selection_rows}
    for count in counts:
        row = selection_lookup[count]
        accepted = [int(value) for value in str(row["accepted_candidates"]).split(";") if value]
        if target in accepted and not stable_pass[count]:
            accepted.remove(target)
        selected = min(accepted) if accepted else None
        row["accepted_candidates"] = ";".join(str(value) for value in accepted)
        row["selected_max_superdroplets"] = selected if selected is not None else ""
        row["target_selected_resolution"] = target
        row["target_resolution_selected"] = selected == target

    updated_selections = {
        int(row["ensemble_size"]): (
            int(row["selected_max_superdroplets"])
            if row["selected_max_superdroplets"] != ""
            else None
        )
        for row in selection_rows
    }
    refined_adequate = None
    for count in tested_counts:
        if all(updated_selections[larger] == target for larger in tested_counts if larger >= count):
            refined_adequate = count
            break

    for row in limiting_rows:
        count = int(row["ensemble_size"])
        if row["metric"] != "ensemble_mean_l1_bins_500" or count not in counts:
            continue
        row["worst_adjacent_bound_over_margin"] = max(
            float(row["worst_adjacent_bound_over_margin"]),
            pooled_ratio[count],
        )
        row["worst_formal_gate_ratio"] = max(
            float(row["worst_analytical_bound_over_margin"]),
            float(row["worst_precision_half_width_over_margin"]),
            float(row["worst_adjacent_bound_over_margin"]),
        )
        row["all_target_triple_gates_pass"] = (
            float(row["worst_formal_gate_ratio"]) <= 1.0 and stable_pass[count]
        )

    decision["initial_10000_resample_adequate_count"] = initial_adequate
    decision["smallest_retrospectively_supported_tested_ensemble_size"] = refined_adequate
    decision["selection_by_member_count"] = {
        str(count): updated_selections[count] for count in tested_counts
    }
    decision["boundary_refinement"] = {
        "status": "completed",
        "critical_pair": [lower, upper],
        "critical_time_s": time_s,
        "tested_member_counts": counts,
        "bootstrap_resamples_per_seed": resamples,
        "bootstrap_seeds": seeds,
        "pooled_resamples_per_count": resamples * len(seeds),
        "require_pooled_pass": bool(settings["require_pooled_pass"]),
        "require_every_seed_pass": bool(settings["require_every_seed_pass"]),
        "stable_pass_by_member_count": {str(count): stable_pass[count] for count in counts},
    }
    return output_rows, decision


def plot_result(
    selection_rows: list[dict[str, object]],
    limiting_rows: list[dict[str, object]],
    decision: dict[str, object],
    output: Path,
) -> None:
    counts = np.asarray([int(row["ensemble_size"]) for row in selection_rows])
    selected_values = [
        int(row["selected_max_superdroplets"]) if row["selected_max_superdroplets"] != "" else None
        for row in selection_rows
    ]
    categorical_position = {None: 0, 131072: 1, 262144: 2, 524288: 3, 1048576: 4}
    selected = np.asarray([categorical_position[value] for value in selected_values], dtype=float)
    adequate = decision["smallest_retrospectively_supported_tested_ensemble_size"]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 7.6), constrained_layout=True)
    colors = {
        "ensemble_mean_l1_bins_500": "#2869a8",
        M0: "#2c8c61",
        M6: "#d66a2c",
    }
    labels = {
        "ensemble_mean_l1_bins_500": "Distribution L1",
        M0: r"$M_0$",
        M6: r"$M_6$",
    }

    ax = axes[0]
    no_selection = np.asarray([value is None for value in selected_values])
    ax.scatter(counts[no_selection], selected[no_selection], color="#c94c4c", s=34, zorder=3)
    ax.plot(
        counts[~no_selection],
        selected[~no_selection],
        marker="o",
        color="#2869a8",
        linewidth=2,
    )
    ax.set_yticks([0, 1, 2, 3])
    ax.set_yticklabels(["No selection", "131,072", "262,144", "524,288"])
    ax.set_ylim(-0.35, 3.25)
    ax.set_ylabel(r"Selected base resolution, $N_{SD}$")
    ax.set_title("A. Full formal N/2N/4N decision reconstructed at each ensemble size", loc="left")
    ax.text(
        0.01,
        0.035,
        "Red markers at the baseline indicate that no resolution passed the complete rule.",
        transform=ax.transAxes,
        fontsize=9,
        color="#555555",
    )

    ax = axes[1]
    for metric, color in colors.items():
        rows = [row for row in limiting_rows if row["metric"] == metric]
        ax.plot(
            [int(row["ensemble_size"]) for row in rows],
            [float(row["worst_formal_gate_ratio"]) for row in rows],
            label=labels[metric],
            color=color,
            linewidth=2.2,
        )
    ax.axhline(1.0, color="#222222", linestyle="--", linewidth=1.4, label="Pass boundary")
    ax.set_xlabel("Independent collision histories per resolution")
    ax.set_ylabel("Worst formal bound / allowed margin")
    ax.set_title(
        "B. Limiting normalized gate for the 131,072 / 262,144 / 524,288 triple",
        loc="left",
    )
    ax.legend(ncol=4, frameon=True, fontsize=9)
    ax.set_ylim(bottom=0.0)

    if adequate is not None:
        for current in axes:
            current.axvline(float(adequate), color="#8a55a3", linestyle=":", linewidth=2)
        axes[0].annotate(
            f"smallest sustained count = {adequate}",
            xy=(adequate, 1),
            xytext=(adequate + 3, 1.55),
            arrowprops={"arrowstyle": "->", "color": "#8a55a3"},
            color="#6b3d82",
            fontsize=10,
        )

    fig.suptitle(
        "Retrospective ensemble-size adequacy for the completed Golovin ensemble\n"
        "10,000 bootstrap projections; primary 500-bin rule; all six decision times",
        fontsize=14,
        fontweight="bold",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=240, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    with args.config.open(encoding="utf-8") as source:
        config = yaml.safe_load(source)
    args.output.mkdir(parents=True, exist_ok=False)
    formal_target_resolution = load_formal_target_resolution(args.resolution_decision)

    (
        resolutions,
        member_counts,
        decision_times,
        stacks,
        analytical,
        edges,
        moments,
        validity,
        archive_hash_rows,
    ) = validate_and_load(
        config=config,
        cases_path=args.cases,
        member_time_path=args.member_time,
        stage0_root=args.stage0_root,
    )
    analytical_rows, adjacent_rows, selection_rows, limiting_rows, decision = analyze(
        config=config,
        resolutions=resolutions,
        member_counts=member_counts,
        decision_times=decision_times,
        stacks=stacks,
        analytical=analytical,
        edges=edges,
        moments=moments,
        validity=validity,
        formal_target_resolution=formal_target_resolution,
    )
    boundary_rows, decision = refine_boundary(
        config=config,
        resolutions=resolutions,
        decision_times=decision_times,
        stacks=stacks,
        analytical=analytical,
        edges=edges,
        adjacent_rows=adjacent_rows,
        selection_rows=selection_rows,
        limiting_rows=limiting_rows,
        decision=decision,
    )

    write_csv(args.output / "projected_analytical_agreement.csv", analytical_rows)
    write_csv(args.output / "projected_adjacent_equivalence.csv", adjacent_rows)
    write_csv(args.output / "selection_by_ensemble_size.csv", selection_rows)
    write_csv(args.output / "limiting_gate_by_ensemble_size.csv", limiting_rows)
    if boundary_rows:
        write_csv(args.output / "boundary_refinement.csv", boundary_rows)
    write_csv(args.output / "stage0_archive_hashes.csv", archive_hash_rows)
    with (args.output / "ensemble_size_decision.json").open("w", encoding="utf-8") as target:
        json.dump(decision, target, indent=2)
        target.write("\n")
    plot_result(
        selection_rows,
        limiting_rows,
        decision,
        args.output / "golovin_ensemble_size_formal_adequacy.png",
    )

    aggregate = hashlib.sha256()
    for row in sorted(archive_hash_rows, key=lambda item: str(item["run_label"])):
        aggregate.update(f"{row['sha256']}  {row['path']}\n".encode())
    metadata = {
        "schema": "golovin_fixed50_ensemble_size_adequacy_metadata_v1",
        "input_hashes": {
            "config": sha256(args.config),
            "cases": sha256(args.cases),
            "member_time": sha256(args.member_time),
            "resolution_decision": sha256(args.resolution_decision),
            "stage0_archive_inventory": aggregate.hexdigest(),
        },
        "stage0_archive_count": len(archive_hash_rows),
        "resolutions": resolutions,
        "members_per_resolution": 50,
        "decision_times_s": decision_times,
        "primary_log_radius_bins": int(config["diagnostics"]["primary_log_radius_bins"]),
        "analysis_only": True,
        "cleo_rerun": False,
        "slurm_job": False,
    }
    with (args.output / "analysis_metadata.json").open("w", encoding="utf-8") as target:
        json.dump(metadata, target, indent=2)
        target.write("\n")

    hash_lines = []
    for path in sorted(args.output.iterdir()):
        if path.name == "SHA256SUMS" or not path.is_file():
            continue
        hash_lines.append(f"{sha256(path)}  {path.name}")
    (args.output / "SHA256SUMS").write_text("\n".join(hash_lines) + "\n", encoding="utf-8")
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
