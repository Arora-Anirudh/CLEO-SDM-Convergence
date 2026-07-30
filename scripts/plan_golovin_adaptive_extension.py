"""Plan a cost-aware extension of the controlled Golovin ensemble.

The completed 100-member matrix is treated as a variance-and-cost pilot. This
script projects the one-sided confidence bound under larger balanced and
unequal allocations while holding the observed point estimates and estimated
per-member variance coefficients fixed.

The projection is not new convergence evidence and does not authorize model
compute. In particular, repeatedly inspecting ordinary 95% bounds and stopping
at the first pass would not preserve nominal coverage. A final fixed allocation
or a prospectively alpha-adjusted sequential design must be frozen before new
member outcomes are used for acceptance.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from analyze_golovin_practical_convergence import (
    L1_METRIC,
    METRIC_LABELS,
    PRIMARY_METRICS,
    bootstrap_mean_values,
)
from analyze_golovin_resolution_convergence import (
    bootstrap_l1_values,
    derived_seed,
    distribution_stack,
    load_archives,
    load_yaml,
    nominal_time,
    portable_artifact_path,
    read_csv,
    sha256_file,
    validate_inputs,
    write_csv,
)
from golovin_stage0 import fixed_bin_relative_l1
from scipy.stats import norm

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined-member-time", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--matrix-file", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--model-inventory", required=True, type=Path)
    parser.add_argument("--practical-change-table", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    return parser.parse_args()


def validate_planning_settings(config: dict[str, Any]) -> dict[str, Any]:
    settings = config["adaptive_extension_planning"]
    practical = config["practical_convergence"]
    resolutions = [int(value) for value in settings["active_max_superdroplets"]]
    grid = settings["allocation_grid"]
    current = int(settings["current_members_per_resolution"])
    minimum = int(grid["minimum_total_members"])
    maximum = int(grid["maximum_total_members"])
    increment = int(grid["increment"])

    if settings["status"] != "researcher_authorized_exploratory_analysis_only":
        raise ValueError("adaptive extension planning is not researcher-authorized")
    if resolutions != sorted(set(resolutions)) or len(resolutions) != 3:
        raise ValueError("adaptive planning requires three unique increasing resolutions")
    if int(settings["candidate_max_superdroplets"]) != resolutions[0]:
        raise ValueError("candidate resolution must be the first active resolution")
    if current != int(config["matrix"]["members_per_cell"]):
        raise ValueError("planning current member count differs from the completed matrix")
    if minimum != current or maximum < minimum or increment < 1:
        raise ValueError("allocation grid must begin at current members and increase positively")
    if int(settings["primary_log_radius_bins"]) != int(practical["primary_log_radius_bins"]):
        raise ValueError("planning and practical analyses must use the same primary bins")
    if not np.isclose(
        float(settings["minimum_worthwhile_improvement_absolute"]),
        float(practical["minimum_worthwhile_improvement_absolute"]),
    ):
        raise ValueError("planning and practical analyses must use the same improvement margin")
    if settings["interim_results_are_exploratory_only"] is not True:
        raise ValueError("interim results must remain exploratory")
    if settings["formal_early_stopping_requires_alpha_spending_or_confidence_sequence"] is not True:
        raise ValueError("formal early-stopping protection must be explicit")
    if (
        settings["unequal_allocation_requires_protocol_amendment_before_model_submission"]
        is not True
    ):
        raise ValueError("unequal allocation must require a protocol amendment")
    if int(settings["bootstrap_resamples"]) < 100:
        raise ValueError("planning requires at least 100 bootstrap resamples")
    if not 0.0 < float(settings["confidence_level"]) < 1.0:
        raise ValueError("planning confidence level must be between zero and one")
    return settings


def member_rows_by_key(
    rows: list[dict[str, str]],
    decision_times: list[float],
) -> dict[tuple[int, int, float], dict[str, str]]:
    selected: dict[tuple[int, int, float], dict[str, str]] = {}
    for row in rows:
        try:
            time_s = nominal_time(float(row["time_s"]), decision_times)
        except ValueError:
            continue
        key = (
            int(row["max_superdroplets"]),
            int(row["member_index"]),
            time_s,
        )
        if key in selected:
            raise RuntimeError(f"duplicate diagnostic row for {key}")
        selected[key] = row
    return selected


def estimate_variance_coefficients(
    *,
    rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    config: dict[str, Any],
    archives: dict[str, dict[str, np.ndarray]],
) -> list[dict[str, object]]:
    """Estimate Var(q-hat) = variance_coefficient / n for each resolution."""
    settings = validate_planning_settings(config)
    active = [int(value) for value in settings["active_max_superdroplets"]]
    current = int(settings["current_members_per_resolution"])
    bin_count = int(settings["primary_log_radius_bins"])
    resamples = int(settings["bootstrap_resamples"])
    base_seed = int(settings["bootstrap_seed"])
    decision_times = [float(value) for value in config["diagnostics"]["decision_times_s"]]
    matrix_lookup = {
        (int(row["max_superdroplets"]), int(row["member_index"])): row for row in matrix_rows
    }
    diagnostics = member_rows_by_key(rows, decision_times)
    output: list[dict[str, object]] = []

    for resolution in active:
        members = sorted(
            int(row["member_index"])
            for row in matrix_rows
            if int(row["max_superdroplets"]) == resolution
        )
        if len(members) != current:
            raise ValueError(f"resolution {resolution} does not have {current} pilot members")
        for time_s in decision_times:
            stack, analytical, edges = distribution_stack(
                resolution=resolution,
                members=members,
                time_s=time_s,
                bin_count=bin_count,
                matrix_lookup=matrix_lookup,
                archives=archives,
            )
            point = fixed_bin_relative_l1(np.mean(stack, axis=0), analytical, edges)
            rng = np.random.default_rng(derived_seed(base_seed, "planning-l1", resolution, time_s))
            draw_indices = rng.integers(0, current, size=(resamples, current))
            draws = bootstrap_l1_values(stack, analytical, edges, draw_indices)
            output.append(
                variance_row(
                    resolution=resolution,
                    time_s=time_s,
                    metric=L1_METRIC,
                    point=point,
                    draws=draws,
                    current_members=current,
                )
            )

            for metric in PRIMARY_METRICS[1:]:
                values = np.asarray(
                    [
                        float(diagnostics[(resolution, member, time_s)][metric])
                        for member in members
                    ],
                    dtype=float,
                )
                point = float(np.mean(values))
                draws = bootstrap_mean_values(
                    values,
                    resamples=resamples,
                    seed=derived_seed(
                        base_seed,
                        "planning-moment",
                        resolution,
                        time_s,
                        metric,
                    ),
                )
                output.append(
                    variance_row(
                        resolution=resolution,
                        time_s=time_s,
                        metric=metric,
                        point=point,
                        draws=draws,
                        current_members=current,
                    )
                )
    return output


def variance_row(
    *,
    resolution: int,
    time_s: float,
    metric: str,
    point: float,
    draws: np.ndarray,
    current_members: int,
) -> dict[str, object]:
    bootstrap_variance = float(np.var(np.asarray(draws, dtype=float), ddof=1))
    coefficient = bootstrap_variance * current_members
    if not np.isfinite(coefficient) or coefficient < 0.0:
        raise ValueError("invalid per-member variance coefficient")
    return {
        "max_superdroplets": resolution,
        "time_s": time_s,
        "metric": metric,
        "current_members": current_members,
        "point_estimate": point,
        "bootstrap_variance_of_estimate": bootstrap_variance,
        "per_member_variance_coefficient": coefficient,
        "projection_model": "variance_of_estimate_equals_coefficient_over_member_count",
    }


def measured_costs(
    model_inventory: dict[str, Any],
    active_resolutions: list[int],
) -> list[dict[str, object]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for member in model_inventory["members"]:
        resolution = int(member["max_superdroplets"])
        if resolution in active_resolutions:
            grouped[resolution].append(member)
    output: list[dict[str, object]] = []
    for resolution in active_resolutions:
        members = grouped[resolution]
        if not members:
            raise ValueError(f"model inventory has no members at resolution {resolution}")
        wall = np.asarray([float(member["job_wall_seconds"]) for member in members])
        sizes = np.asarray([float(member["zarr_bytes"]) for member in members])
        output.append(
            {
                "max_superdroplets": resolution,
                "measured_members": len(members),
                "mean_job_wall_seconds_per_member": float(np.mean(wall)),
                "median_job_wall_seconds_per_member": float(np.median(wall)),
                "mean_zarr_bytes_per_member": float(np.mean(sizes)),
            }
        )
    return output


def build_constraints(
    *,
    variance_rows: list[dict[str, object]],
    practical_rows: list[dict[str, str]],
    config: dict[str, Any],
) -> list[dict[str, object]]:
    settings = validate_planning_settings(config)
    active = [int(value) for value in settings["active_max_superdroplets"]]
    current = int(settings["current_members_per_resolution"])
    bin_count = int(settings["primary_log_radius_bins"])
    confidence_level = float(settings["confidence_level"])
    margin = float(settings["minimum_worthwhile_improvement_absolute"])
    z_value = float(norm.ppf(confidence_level))
    variance_lookup = {
        (int(row["max_superdroplets"]), float(row["time_s"]), str(row["metric"])): row
        for row in variance_rows
    }
    practical_lookup = {
        (
            int(row["lower_max_superdroplets"]),
            int(row["upper_max_superdroplets"]),
            float(row["time_s"]),
            row["metric"],
        ): row
        for row in practical_rows
        if int(row["ensemble_size"]) == current
        and int(row["log_radius_bins"]) == bin_count
        and int(row["lower_max_superdroplets"]) in active
        and int(row["upper_max_superdroplets"]) in active
    }

    output: list[dict[str, object]] = []
    for lower, upper in zip(active[:-1], active[1:], strict=True):
        keys = sorted(key for key in practical_lookup if key[0] == lower and key[1] == upper)
        if not keys:
            raise ValueError(f"practical table has no primary rows for {lower}-{upper}")
        for _, _, time_s, metric in keys:
            practical = practical_lookup[(lower, upper, time_s, metric)]
            lower_row = variance_lookup[(lower, time_s, metric)]
            upper_row = variance_lookup[(upper, time_s, metric)]
            lower_point = float(lower_row["point_estimate"])
            upper_point = float(upper_row["point_estimate"])
            point_change = abs(lower_point - upper_point)
            recorded_change = float(practical["absolute_change"])
            if not np.isclose(point_change, recorded_change, rtol=0.0, atol=1.0e-12):
                raise RuntimeError("planning point change does not reproduce practical analysis")
            lower_coefficient = float(lower_row["per_member_variance_coefficient"])
            upper_coefficient = float(upper_row["per_member_variance_coefficient"])
            normal_current = projected_upper_bound(
                point_change=point_change,
                lower_variance_coefficient=lower_coefficient,
                upper_variance_coefficient=upper_coefficient,
                lower_members=current,
                upper_members=current,
                z_value=z_value,
            )
            output.append(
                {
                    "lower_max_superdroplets": lower,
                    "upper_max_superdroplets": upper,
                    "time_s": time_s,
                    "metric": metric,
                    "point_change": point_change,
                    "minimum_worthwhile_improvement": margin,
                    "point_change_can_ever_pass_fixed_margin": point_change <= margin,
                    "lower_variance_coefficient": lower_coefficient,
                    "upper_variance_coefficient": upper_coefficient,
                    "current_members_each": current,
                    "current_percentile_bootstrap_upper_bound": float(
                        practical["one_sided_95_upper_bound"]
                    ),
                    "current_normal_projection_upper_bound": normal_current,
                    "normal_projection_minus_bootstrap": (
                        normal_current - float(practical["one_sided_95_upper_bound"])
                    ),
                    "normal_quantile": z_value,
                    "confidence_level": confidence_level,
                }
            )
    return output


def projected_upper_bound(
    *,
    point_change: float,
    lower_variance_coefficient: float,
    upper_variance_coefficient: float,
    lower_members: int,
    upper_members: int,
    z_value: float,
) -> float:
    if lower_members < 2 or upper_members < 2:
        raise ValueError("projected allocation requires at least two members per resolution")
    variance = lower_variance_coefficient / lower_members
    variance += upper_variance_coefficient / upper_members
    return float(point_change + z_value * np.sqrt(max(variance, 0.0)))


def allocation_passes(
    constraints: list[dict[str, object]],
    allocation: dict[int, int],
) -> bool:
    for row in constraints:
        lower = int(row["lower_max_superdroplets"])
        upper = int(row["upper_max_superdroplets"])
        bound = projected_upper_bound(
            point_change=float(row["point_change"]),
            lower_variance_coefficient=float(row["lower_variance_coefficient"]),
            upper_variance_coefficient=float(row["upper_variance_coefficient"]),
            lower_members=allocation[lower],
            upper_members=allocation[upper],
            z_value=float(row["normal_quantile"]),
        )
        if bound > float(row["minimum_worthwhile_improvement"]):
            return False
    return True


def worst_projected_rows(
    constraints: list[dict[str, object]],
    allocation: dict[int, int],
) -> list[dict[str, object]]:
    grouped: dict[tuple[int, int, str], list[dict[str, object]]] = defaultdict(list)
    for row in constraints:
        grouped[
            (
                int(row["lower_max_superdroplets"]),
                int(row["upper_max_superdroplets"]),
                str(row["metric"]),
            )
        ].append(row)
    output: list[dict[str, object]] = []
    for (lower, upper, metric), rows in sorted(grouped.items()):
        projected = [
            (
                projected_upper_bound(
                    point_change=float(row["point_change"]),
                    lower_variance_coefficient=float(row["lower_variance_coefficient"]),
                    upper_variance_coefficient=float(row["upper_variance_coefficient"]),
                    lower_members=allocation[lower],
                    upper_members=allocation[upper],
                    z_value=float(row["normal_quantile"]),
                ),
                row,
            )
            for row in rows
        ]
        bound, limiting = max(projected, key=lambda item: item[0])
        margin = float(limiting["minimum_worthwhile_improvement"])
        output.append(
            {
                "lower_max_superdroplets": lower,
                "upper_max_superdroplets": upper,
                "metric": metric,
                "lower_members": allocation[lower],
                "upper_members": allocation[upper],
                "limiting_time_s": float(limiting["time_s"]),
                "limiting_point_change": float(limiting["point_change"]),
                "worst_projected_one_sided_upper_bound": bound,
                "minimum_worthwhile_improvement": margin,
                "projected_pass": bound <= margin,
            }
        )
    return output


def allocation_grid(settings: dict[str, Any]) -> list[int]:
    grid = settings["allocation_grid"]
    minimum = int(grid["minimum_total_members"])
    maximum = int(grid["maximum_total_members"])
    increment = int(grid["increment"])
    values = list(range(minimum, maximum + 1, increment))
    if values[-1] != maximum:
        values.append(maximum)
    return values


def balanced_projections(
    *,
    constraints: list[dict[str, object]],
    config: dict[str, Any],
) -> tuple[list[dict[str, object]], dict[int, int] | None]:
    settings = validate_planning_settings(config)
    active = [int(value) for value in settings["active_max_superdroplets"]]
    counts = [int(value) for value in settings["balanced_projection_member_counts"]]
    if counts != sorted(set(counts)) or counts[0] < int(settings["current_members_per_resolution"]):
        raise ValueError("balanced projection counts must be unique, increasing and available")
    rows: list[dict[str, object]] = []
    for count in counts:
        allocation = {resolution: count for resolution in active}
        for row in worst_projected_rows(constraints, allocation):
            rows.append({"design": "balanced", "total_members_each": count, **row})

    selected = None
    for count in allocation_grid(settings):
        allocation = {resolution: count for resolution in active}
        if allocation_passes(constraints, allocation):
            selected = allocation
            break
    return rows, selected


def cost_optimal_allocation(
    *,
    constraints: list[dict[str, object]],
    cost_rows: list[dict[str, object]],
    config: dict[str, Any],
) -> tuple[list[dict[str, object]], dict[int, int] | None]:
    settings = validate_planning_settings(config)
    lower, middle, upper = [int(value) for value in settings["active_max_superdroplets"]]
    current = int(settings["current_members_per_resolution"])
    counts = allocation_grid(settings)
    costs = {
        int(row["max_superdroplets"]): float(row["mean_job_wall_seconds_per_member"])
        for row in cost_rows
    }
    storage = {
        int(row["max_superdroplets"]): float(row["mean_zarr_bytes_per_member"]) for row in cost_rows
    }
    first_pair = [
        row
        for row in constraints
        if int(row["lower_max_superdroplets"]) == lower
        and int(row["upper_max_superdroplets"]) == middle
    ]
    second_pair = [
        row
        for row in constraints
        if int(row["lower_max_superdroplets"]) == middle
        and int(row["upper_max_superdroplets"]) == upper
    ]
    if not first_pair or not second_pair:
        raise ValueError("cost optimization requires both adjacent active pairs")

    frontier: list[dict[str, object]] = []
    best_allocation: dict[int, int] | None = None
    best_cost = float("inf")
    for middle_count in counts:
        lower_count = next(
            (
                count
                for count in counts
                if allocation_passes(
                    first_pair,
                    {lower: count, middle: middle_count},
                )
            ),
            None,
        )
        upper_count = next(
            (
                count
                for count in counts
                if allocation_passes(
                    second_pair,
                    {middle: middle_count, upper: count},
                )
            ),
            None,
        )
        if lower_count is None or upper_count is None:
            continue
        allocation = {
            lower: lower_count,
            middle: middle_count,
            upper: upper_count,
        }
        additional_seconds = sum(
            (allocation[resolution] - current) * costs[resolution] for resolution in allocation
        )
        additional_bytes = sum(
            (allocation[resolution] - current) * storage[resolution] for resolution in allocation
        )
        maximum_bound = max(
            float(row["worst_projected_one_sided_upper_bound"])
            for row in worst_projected_rows(constraints, allocation)
        )
        frontier.append(
            {
                "lower_members": lower_count,
                "middle_members": middle_count,
                "upper_members": upper_count,
                "additional_members": sum(value - current for value in allocation.values()),
                "projected_additional_cpu_hours": additional_seconds / 3600.0,
                "projected_additional_zarr_gb": additional_bytes / 1.0e9,
                "maximum_projected_upper_bound": maximum_bound,
            }
        )
        if additional_seconds < best_cost:
            best_cost = additional_seconds
            best_allocation = allocation
    return frontier, best_allocation


def design_summary_row(
    *,
    name: str,
    allocation: dict[int, int] | None,
    constraints: list[dict[str, object]],
    cost_rows: list[dict[str, object]],
    config: dict[str, Any],
) -> dict[str, object]:
    settings = validate_planning_settings(config)
    active = [int(value) for value in settings["active_max_superdroplets"]]
    current = int(settings["current_members_per_resolution"])
    if allocation is None:
        return {
            "design": name,
            "feasible_within_planning_grid": False,
            **{f"members_{resolution}": "" for resolution in active},
            "additional_members": "",
            "projected_additional_cpu_hours": "",
            "projected_additional_zarr_gb": "",
            "maximum_projected_upper_bound": "",
        }
    costs = {
        int(row["max_superdroplets"]): float(row["mean_job_wall_seconds_per_member"])
        for row in cost_rows
    }
    storage = {
        int(row["max_superdroplets"]): float(row["mean_zarr_bytes_per_member"]) for row in cost_rows
    }
    worst = worst_projected_rows(constraints, allocation)
    return {
        "design": name,
        "feasible_within_planning_grid": True,
        **{f"members_{resolution}": allocation[resolution] for resolution in active},
        "additional_members": sum(allocation[value] - current for value in active),
        "projected_additional_cpu_hours": sum(
            (allocation[value] - current) * costs[value] for value in active
        )
        / 3600.0,
        "projected_additional_zarr_gb": sum(
            (allocation[value] - current) * storage[value] for value in active
        )
        / 1.0e9,
        "maximum_projected_upper_bound": max(
            float(row["worst_projected_one_sided_upper_bound"]) for row in worst
        ),
    }


def plot_balanced_projection(
    rows: list[dict[str, object]],
    output: Path,
) -> None:
    pairs = sorted(
        {(int(row["lower_max_superdroplets"]), int(row["upper_max_superdroplets"])) for row in rows}
    )
    colors = plt.get_cmap("viridis")(np.linspace(0.15, 0.85, len(pairs)))
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0), sharex=True)
    for axis, metric in zip(axes, PRIMARY_METRICS, strict=True):
        for color, pair in zip(colors, pairs, strict=True):
            selected = sorted(
                (
                    row
                    for row in rows
                    if row["metric"] == metric
                    and (
                        int(row["lower_max_superdroplets"]),
                        int(row["upper_max_superdroplets"]),
                    )
                    == pair
                ),
                key=lambda row: int(row["total_members_each"]),
            )
            axis.plot(
                [int(row["total_members_each"]) for row in selected],
                [float(row["worst_projected_one_sided_upper_bound"]) * 100.0 for row in selected],
                marker="o",
                color=color,
                label=f"{pair[0]:,}→{pair[1]:,}",
            )
        axis.axhspan(0.0, 1.0, color="#58a65c", alpha=0.13)
        axis.axhline(1.0, color="#3a9147", linewidth=1.0)
        axis.set_title(METRIC_LABELS[metric], fontsize=12)
        axis.set_xlabel("balanced members per resolution", fontsize=10)
        axis.tick_params(labelsize=9)
        axis.grid(alpha=0.2)
    axes[0].set_ylabel("projected worst upper bound / pp", fontsize=10)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle(
        "Pilot-based balanced-ensemble precision projection",
        y=0.98,
        fontsize=14,
    )
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.89),
        ncol=2,
        fontsize=9,
    )
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.15, top=0.72, wspace=0.25)
    fig.savefig(output, dpi=300, facecolor="white")
    plt.close(fig)


def plot_design_costs(
    rows: list[dict[str, object]],
    output: Path,
) -> None:
    feasible = [row for row in rows if bool(row["feasible_within_planning_grid"])]
    if not feasible:
        fig, axis = plt.subplots(figsize=(8.5, 3.8))
        axis.axis("off")
        axis.text(
            0.5,
            0.5,
            "No fixed design passed within the registered planning grid.",
            ha="center",
            va="center",
            fontsize=12,
        )
        fig.savefig(output, dpi=300, facecolor="white")
        plt.close(fig)
        return
    labels = [str(row["design"]).replace("_", " ") for row in feasible]
    cpu = [float(row["projected_additional_cpu_hours"]) for row in feasible]
    storage = [float(row["projected_additional_zarr_gb"]) for row in feasible]
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.8))
    axes[0].bar(labels, cpu, color=("#4c78a8", "#f58518")[: len(labels)])
    axes[0].set_ylabel("additional model CPU-hours")
    axes[1].bar(labels, storage, color=("#4c78a8", "#f58518")[: len(labels)])
    axes[1].set_ylabel("additional raw Zarr / GB")
    for axis in axes:
        axis.grid(axis="y", alpha=0.2)
        axis.tick_params(axis="x", rotation=15)
    fig.suptitle("Projected cost of fixed final allocations")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(output, dpi=300, facecolor="white")
    plt.close(fig)


def write_optional_csv(
    filename: Path,
    rows: list[dict[str, object]],
    fieldnames: list[str],
) -> None:
    """Write rows or a header-only table for a valid empty planning result."""
    if rows:
        write_csv(filename, rows)
        return
    with filename.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()


def analyze(
    *,
    rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    config: dict[str, Any],
    archives: dict[str, dict[str, np.ndarray]],
    model_inventory: dict[str, Any],
    practical_rows: list[dict[str, str]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    validate_inputs(rows, matrix_rows, config)
    settings = validate_planning_settings(config)
    active = [int(value) for value in settings["active_max_superdroplets"]]
    variance_rows = estimate_variance_coefficients(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )
    cost_rows = measured_costs(model_inventory, active)
    constraints = build_constraints(
        variance_rows=variance_rows,
        practical_rows=practical_rows,
        config=config,
    )
    balanced_rows, balanced_allocation = balanced_projections(
        constraints=constraints,
        config=config,
    )
    frontier, optimized_allocation = cost_optimal_allocation(
        constraints=constraints,
        cost_rows=cost_rows,
        config=config,
    )
    summaries = [
        design_summary_row(
            name="balanced_fixed_final",
            allocation=balanced_allocation,
            constraints=constraints,
            cost_rows=cost_rows,
            config=config,
        ),
        design_summary_row(
            name="cost_optimized_fixed_final",
            allocation=optimized_allocation,
            constraints=constraints,
            cost_rows=cost_rows,
            config=config,
        ),
    ]
    design_constraints: list[dict[str, object]] = []
    for name, allocation in (
        ("balanced_fixed_final", balanced_allocation),
        ("cost_optimized_fixed_final", optimized_allocation),
    ):
        if allocation is not None:
            design_constraints.extend(
                {"design": name, **row} for row in worst_projected_rows(constraints, allocation)
            )
    current = int(settings["current_members_per_resolution"])
    first_variance_update = {resolution: current + 50 for resolution in active}
    decision = {
        "schema": "golovin_adaptive_extension_plan_v1",
        "status": (
            "fixed_final_designs_projected"
            if balanced_allocation is not None and optimized_allocation is not None
            else "planning_grid_did_not_find_all_designs"
        ),
        "candidate_max_superdroplets": int(settings["candidate_max_superdroplets"]),
        "active_max_superdroplets": active,
        "current_members_per_resolution": current,
        "balanced_fixed_final_allocation": balanced_allocation,
        "cost_optimized_fixed_final_allocation": optimized_allocation,
        "recommended_first_variance_update_target": first_variance_update,
        "first_update_scientific_role": (
            "variance-model validation only; not a formal unadjusted early-stopping look"
        ),
        "projection_assumptions": [
            "observed pilot point estimates remain fixed",
            "per-member variance coefficients remain fixed",
            "independent ensembles imply additive variance contributions",
            "normal one-sided approximation replaces the final percentile bootstrap",
            "measured job wall seconds are used as a model-compute cost proxy",
        ],
        "formal_acceptance_warning": (
            "Freeze one final allocation before inspecting new outcomes, or prospectively "
            "adopt alpha spending/confidence sequences for formal interim stopping."
        ),
        "unequal_allocation_warning": (
            "The current practical analyzer uses common member prefixes. A cost-optimized "
            "unequal allocation requires a reviewed protocol and analyzer amendment."
        ),
        "new_model_compute_authorized": False,
    }
    return (
        variance_rows,
        cost_rows,
        constraints,
        balanced_rows,
        frontier,
        summaries,
        design_constraints,
        decision,
    )


def main() -> None:
    args = parse_args()
    for filename in (
        args.combined_member_time,
        args.matrix_file,
        args.config,
        args.model_inventory,
        args.practical_change_table,
    ):
        if not filename.is_file():
            raise FileNotFoundError(filename)
    if not args.run_root.is_dir():
        raise NotADirectoryError(args.run_root)
    if args.output_directory.exists():
        raise FileExistsError(args.output_directory)

    rows = read_csv(args.combined_member_time)
    matrix_rows = read_csv(args.matrix_file, delimiter="\t")
    config = load_yaml(args.config)
    settings = validate_planning_settings(config)
    active = [int(value) for value in settings["active_max_superdroplets"]]
    active_matrix_rows = [row for row in matrix_rows if int(row["max_superdroplets"]) in active]
    archives = load_archives(args.run_root, active_matrix_rows)
    model_inventory = json.loads(args.model_inventory.read_text(encoding="utf-8"))
    practical_rows = read_csv(args.practical_change_table)

    (
        variance_rows,
        cost_rows,
        constraints,
        balanced_rows,
        frontier,
        summaries,
        design_constraints,
        decision,
    ) = analyze(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
        model_inventory=model_inventory,
        practical_rows=practical_rows,
    )

    args.output_directory.mkdir(parents=True)
    write_csv(args.output_directory / "variance_coefficients.csv", variance_rows)
    write_csv(args.output_directory / "measured_member_costs.csv", cost_rows)
    write_csv(args.output_directory / "projection_constraints.csv", constraints)
    write_csv(args.output_directory / "balanced_projection.csv", balanced_rows)
    write_optional_csv(
        args.output_directory / "cost_optimization_frontier.csv",
        frontier,
        [
            "lower_members",
            "middle_members",
            "upper_members",
            "additional_members",
            "projected_additional_cpu_hours",
            "projected_additional_zarr_gb",
            "maximum_projected_upper_bound",
        ],
    )
    write_csv(args.output_directory / "fixed_design_summary.csv", summaries)
    write_optional_csv(
        args.output_directory / "fixed_design_limiting_constraints.csv",
        design_constraints,
        [
            "design",
            "lower_max_superdroplets",
            "upper_max_superdroplets",
            "metric",
            "lower_members",
            "upper_members",
            "limiting_time_s",
            "limiting_point_change",
            "worst_projected_one_sided_upper_bound",
            "minimum_worthwhile_improvement",
            "projected_pass",
        ],
    )
    plot_balanced_projection(
        balanced_rows,
        args.output_directory / "balanced_precision_projection.png",
    )
    plot_design_costs(
        summaries,
        args.output_directory / "fixed_design_cost_comparison.png",
    )
    decision.update(
        {
            "combined_member_time": portable_artifact_path(
                args.combined_member_time,
                args.output_directory,
            ),
            "combined_member_time_sha256": sha256_file(args.combined_member_time),
            "matrix_file": str(args.matrix_file.resolve()),
            "matrix_sha256": sha256_file(args.matrix_file),
            "config": str(args.config.resolve()),
            "config_sha256": sha256_file(args.config),
            "model_inventory": portable_artifact_path(
                args.model_inventory,
                args.output_directory,
            ),
            "model_inventory_sha256": sha256_file(args.model_inventory),
            "practical_change_table": portable_artifact_path(
                args.practical_change_table,
                args.output_directory,
            ),
            "practical_change_table_sha256": sha256_file(args.practical_change_table),
        }
    )
    (args.output_directory / "adaptive_extension_plan.json").write_text(
        json.dumps(decision, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
