"""Apply the practical Golovin diminishing-returns criterion.

This analysis does not replace the registered strict adjacent-equivalence
result. It asks whether two successive resolution doublings provide less than
one prospectively defined minimum worthwhile improvement while the analytical,
conservation, range and provenance gates remain satisfied.

Different resolutions contain independent collision ensembles. Bootstrap
draws are therefore independent across resolutions and are never described as
paired histories.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
from analyze_golovin_resolution_convergence import (
    BIN_COUNTS,
    MOMENT_METRICS,
    bootstrap_l1_values,
    derived_seed,
    distribution_stack,
    load_archives,
    load_yaml,
    nominal_time,
    portable_artifact_path,
    read_csv,
    sha256_file,
    student_interval,
    validate_inputs,
    write_csv,
)
from golovin_stage0 import fixed_bin_relative_l1

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

L1_METRIC = "ensemble_mean_l1"
PRIMARY_METRICS = (
    L1_METRIC,
    "golovin_relative_error_radius_moment_0_m3",
    "golovin_relative_error_radius_moment_6_um6_m3",
)
METRIC_LABELS = {
    L1_METRIC: "Distribution L1 error",
    "golovin_relative_error_radius_moment_0_m3": r"$M_0$ analytical bias",
    "golovin_relative_error_radius_moment_6_um6_m3": r"$M_6$ analytical bias",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combined-member-time", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--matrix-file", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    return parser.parse_args()


def bootstrap_mean_values(
    values: np.ndarray,
    *,
    resamples: int,
    seed: int,
) -> np.ndarray:
    """Return independent bootstrap estimates of a scalar ensemble mean."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or values.size < 2 or np.any(~np.isfinite(values)):
        raise ValueError("bootstrap mean requires at least two finite values")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, values.size, size=(resamples, values.size))
    return np.mean(values[indices], axis=1)


def percentile_interval(
    values: np.ndarray,
    confidence_level: float,
) -> tuple[float, float]:
    alpha = (1.0 - confidence_level) / 2.0
    low, high = np.quantile(np.asarray(values, dtype=float), [alpha, 1.0 - alpha])
    return float(low), float(high)


def validate_settings(config: dict[str, Any]) -> dict[str, Any]:
    settings = config["practical_convergence"]
    targeted_counts = settings.get("targeted_member_counts_by_resolution")
    prefixes = [int(value) for value in settings.get("ensemble_prefixes", [])]
    final_prefixes = [int(value) for value in settings.get("final_prefixes_for_stability", [])]
    primary_bins = int(settings["primary_log_radius_bins"])
    sensitivity_bins = [int(value) for value in settings["sensitivity_log_radius_bins"]]
    prospective_fixed_design_statuses = {
        "researcher_approved_prospective_fixed_design",
        "researcher_approved_same_rule_as_frozen_experiment",
    }
    approved_statuses = {
        "researcher_approved_existing_data_reanalysis_pending_clara_review",
        *prospective_fixed_design_statuses,
    }
    if settings["status"] not in approved_statuses:
        raise ValueError("practical criterion has not been approved for this analysis scope")
    if targeted_counts is None:
        if not prefixes or prefixes != sorted(set(prefixes)) or prefixes[0] < 2:
            raise ValueError("ensemble prefixes must be unique, increasing and at least two")
        if final_prefixes != prefixes[-2:]:
            raise ValueError("stability prefixes must be the final two ensemble prefixes")
    else:
        if not isinstance(targeted_counts, dict) or not targeted_counts:
            raise ValueError("targeted member counts must be a non-empty mapping")
        if any(int(value) < 2 for value in targeted_counts.values()):
            raise ValueError("targeted member counts must be at least two")
    if primary_bins not in BIN_COUNTS:
        raise ValueError("primary practical-convergence bin count is not registered")
    if sorted([primary_bins, *sensitivity_bins]) != list(BIN_COUNTS):
        raise ValueError("primary and sensitivity bin counts must exactly cover registered bins")
    if settings["require_two_successive_doublings"] is not True:
        raise ValueError("practical convergence requires two successive doublings")
    if settings["sensitivity_bins_are_diagnostic_only"] is not True:
        raise ValueError("sensitivity-bin role must remain diagnostic only")
    if not 0.0 < float(settings["confidence_level"]) < 1.0:
        raise ValueError("confidence level must be between zero and one")
    if int(settings["bootstrap_resamples"]) < 100:
        raise ValueError("at least 100 bootstrap resamples are required")
    if float(settings["minimum_worthwhile_improvement_absolute"]) <= 0.0:
        raise ValueError("minimum worthwhile improvement must be positive")
    return settings


def decision_rows_by_key(
    rows: list[dict[str, str]],
    decision_times: list[float],
) -> dict[tuple[int, int, float], dict[str, str]]:
    selected = [
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
        for row in selected
    }
    if len(keyed) != len(selected):
        raise RuntimeError("duplicate resolution/member/time diagnostic rows")
    return keyed


def evaluate_prefix(
    *,
    rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    config: dict[str, Any],
    archives: dict[str, dict[str, np.ndarray]],
    member_count: int,
    bin_count: int,
    member_counts_by_resolution: dict[int, int] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Evaluate one member prefix and one fixed-bin definition.

    ``member_counts_by_resolution`` supports a documented targeted follow-up
    with unequal complete ensembles. When omitted, the ordinary balanced
    prefix definition is retained exactly.
    """
    settings = validate_settings(config)
    criteria = config["convergence_criteria"]
    decision_times = [float(value) for value in config["diagnostics"]["decision_times_s"]]
    confidence_level = float(settings["confidence_level"])
    resamples = int(settings["bootstrap_resamples"])
    base_seed = int(settings["bootstrap_seed"])
    improvement_margin = float(settings["minimum_worthwhile_improvement_absolute"])
    l1_margin = float(criteria["analytical_agreement"]["maximum_l1_upper_95ci"])
    moment_margins = {
        metric: float(criteria["analytical_agreement"][margin_key])
        for metric, (margin_key, _) in MOMENT_METRICS.items()
    }

    resolutions = sorted({int(row["max_superdroplets"]) for row in matrix_rows})
    available_members_by_resolution = {
        resolution: sorted(
            int(row["member_index"])
            for row in matrix_rows
            if int(row["max_superdroplets"]) == resolution
        )
        for resolution in resolutions
    }
    if member_counts_by_resolution is None:
        requested_member_counts = {resolution: member_count for resolution in resolutions}
    else:
        requested_member_counts = {
            int(resolution): int(count) for resolution, count in member_counts_by_resolution.items()
        }
        if set(requested_member_counts) != set(resolutions):
            raise ValueError("targeted member counts must cover exactly the analyzed resolutions")
        if any(count < 2 for count in requested_member_counts.values()):
            raise ValueError("targeted member counts must be at least two")
    members_by_resolution = {
        resolution: available_members_by_resolution[resolution][
            : requested_member_counts[resolution]
        ]
        for resolution in resolutions
    }
    for resolution, members in members_by_resolution.items():
        requested = requested_member_counts[resolution]
        if len(members) != requested:
            raise ValueError(f"member prefix {requested} is unavailable at resolution {resolution}")
    design_token = ";".join(
        f"{resolution}:{requested_member_counts[resolution]}" for resolution in resolutions
    )
    matrix_lookup = {
        (int(row["max_superdroplets"]), int(row["member_index"])): row for row in matrix_rows
    }
    keyed = decision_rows_by_key(rows, decision_times)

    resolution_pass = {resolution: True for resolution in resolutions}
    estimate_rows: list[dict[str, object]] = []
    estimates: dict[tuple[int, float, str], float] = {}
    bootstrap_draws: dict[tuple[int, float, str], np.ndarray] = {}

    for resolution in resolutions:
        members = members_by_resolution[resolution]
        selected_rows = [
            row
            for row in rows
            if int(row["max_superdroplets"]) == resolution and int(row["member_index"]) in members
        ]
        maximum_drift = max(abs(float(row["relative_liquid_mass_drift"])) for row in selected_rows)
        maximum_out_of_range = max(
            float(row["fixed_bin_mass_below_range_fraction"])
            + float(row["fixed_bin_mass_above_range_fraction"])
            for row in selected_rows
        )
        conservation_pass = maximum_drift <= float(criteria["maximum_relative_liquid_mass_drift"])
        range_pass = maximum_out_of_range <= float(criteria["maximum_out_of_range_mass_fraction"])
        resolution_pass[resolution] &= conservation_pass and range_pass

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
            rng = np.random.default_rng(
                derived_seed(base_seed, "l1", design_token, bin_count, resolution, time_s)
            )
            draw_indices = rng.integers(
                0,
                len(members),
                size=(resamples, len(members)),
            )
            draws = bootstrap_l1_values(stack, analytical, edges, draw_indices)
            ci_low, ci_high = percentile_interval(draws, confidence_level)
            passed = ci_high <= l1_margin
            resolution_pass[resolution] &= passed
            estimates[(resolution, time_s, L1_METRIC)] = point
            bootstrap_draws[(resolution, time_s, L1_METRIC)] = draws
            estimate_rows.append(
                {
                    "ensemble_size": member_count,
                    "n_members": len(members),
                    "log_radius_bins": bin_count,
                    "max_superdroplets": resolution,
                    "time_s": time_s,
                    "metric": L1_METRIC,
                    "estimate": point,
                    "95ci_low": ci_low,
                    "95ci_high": ci_high,
                    "analytical_margin": l1_margin,
                    "analytical_validity_pass": passed,
                    "maximum_absolute_liquid_mass_drift": maximum_drift,
                    "conservation_pass": conservation_pass,
                    "maximum_out_of_range_mass_fraction": maximum_out_of_range,
                    "range_coverage_pass": range_pass,
                }
            )

            for metric in MOMENT_METRICS:
                values = np.asarray(
                    [float(keyed[(resolution, member, time_s)][metric]) for member in members]
                )
                point, ci_low, ci_high = student_interval(values, confidence_level)
                margin = moment_margins[metric]
                passed = ci_low >= -margin and ci_high <= margin
                draws = bootstrap_mean_values(
                    values,
                    resamples=resamples,
                    seed=derived_seed(
                        base_seed,
                        "moment",
                        design_token,
                        bin_count,
                        resolution,
                        time_s,
                        metric,
                    ),
                )
                resolution_pass[resolution] &= passed
                estimates[(resolution, time_s, metric)] = point
                bootstrap_draws[(resolution, time_s, metric)] = draws
                estimate_rows.append(
                    {
                        "ensemble_size": member_count,
                        "n_members": len(members),
                        "log_radius_bins": bin_count,
                        "max_superdroplets": resolution,
                        "time_s": time_s,
                        "metric": metric,
                        "estimate": point,
                        "95ci_low": ci_low,
                        "95ci_high": ci_high,
                        "analytical_margin": margin,
                        "analytical_validity_pass": passed,
                        "maximum_absolute_liquid_mass_drift": maximum_drift,
                        "conservation_pass": conservation_pass,
                        "maximum_out_of_range_mass_fraction": maximum_out_of_range,
                        "range_coverage_pass": range_pass,
                    }
                )

    pair_pass: dict[tuple[int, int], bool] = {}
    change_rows: list[dict[str, object]] = []
    for lower, upper in zip(resolutions[:-1], resolutions[1:], strict=True):
        pair_pass[(lower, upper)] = True
        for time_s in decision_times:
            for metric in PRIMARY_METRICS:
                lower_point = estimates[(lower, time_s, metric)]
                upper_point = estimates[(upper, time_s, metric)]
                absolute_change = abs(lower_point - upper_point)
                absolute_draws = np.abs(
                    bootstrap_draws[(lower, time_s, metric)]
                    - bootstrap_draws[(upper, time_s, metric)]
                )
                upper_bound = float(np.quantile(absolute_draws, confidence_level))
                passed = upper_bound <= improvement_margin
                pair_pass[(lower, upper)] &= passed
                change_rows.append(
                    {
                        "ensemble_size": member_count,
                        "lower_n_members": len(members_by_resolution[lower]),
                        "upper_n_members": len(members_by_resolution[upper]),
                        "log_radius_bins": bin_count,
                        "lower_max_superdroplets": lower,
                        "upper_max_superdroplets": upper,
                        "time_s": time_s,
                        "metric": metric,
                        "lower_estimate": lower_point,
                        "upper_estimate": upper_point,
                        "absolute_change": absolute_change,
                        "one_sided_95_upper_bound": upper_bound,
                        "minimum_worthwhile_improvement": improvement_margin,
                        "diminishing_returns_pass": passed,
                    }
                )

    accepted: list[int] = []
    for index, resolution in enumerate(resolutions):
        if index + 2 >= len(resolutions):
            continue
        second = resolutions[index + 1]
        third = resolutions[index + 2]
        if (
            resolution_pass[resolution]
            and resolution_pass[second]
            and resolution_pass[third]
            and pair_pass[(resolution, second)]
            and pair_pass[(second, third)]
        ):
            accepted.append(resolution)

    selected = min(accepted) if accepted else None
    decision = {
        "ensemble_size": member_count,
        "members_by_resolution": {
            str(resolution): len(members) for resolution, members in members_by_resolution.items()
        },
        "log_radius_bins": bin_count,
        "selected_candidate": selected,
        "resolution_analytical_validity_pass": {
            str(key): bool(value) for key, value in resolution_pass.items()
        },
        "adjacent_pair_diminishing_returns_pass": {
            f"{lower}-{upper}": bool(value) for (lower, upper), value in pair_pass.items()
        },
    }
    return estimate_rows, change_rows, decision


def compare_final_prefixes(
    *,
    estimate_rows: list[dict[str, object]],
    decisions: list[dict[str, object]],
    config: dict[str, Any],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    settings = validate_settings(config)
    lower_prefix, upper_prefix = [int(value) for value in settings["final_prefixes_for_stability"]]
    primary_bins = int(settings["primary_log_radius_bins"])
    point_margin = float(settings["maximum_point_change_between_final_prefixes"])
    primary_rows = [
        row
        for row in estimate_rows
        if int(row["log_radius_bins"]) == primary_bins
        and int(row["ensemble_size"]) in (lower_prefix, upper_prefix)
    ]
    lookup = {
        (
            int(row["ensemble_size"]),
            int(row["max_superdroplets"]),
            float(row["time_s"]),
            str(row["metric"]),
        ): row
        for row in primary_rows
    }
    upper_keys = [key for key in lookup if key[0] == upper_prefix]
    stability_rows: list[dict[str, object]] = []
    for _, resolution, time_s, metric in sorted(upper_keys):
        lower = lookup[(lower_prefix, resolution, time_s, metric)]
        upper = lookup[(upper_prefix, resolution, time_s, metric)]
        change = abs(float(lower["estimate"]) - float(upper["estimate"]))
        stability_rows.append(
            {
                "lower_ensemble_size": lower_prefix,
                "upper_ensemble_size": upper_prefix,
                "max_superdroplets": resolution,
                "time_s": time_s,
                "metric": metric,
                "lower_estimate": float(lower["estimate"]),
                "upper_estimate": float(upper["estimate"]),
                "absolute_point_change": change,
                "maximum_allowed_point_change": point_margin,
                "point_stability_pass": change <= point_margin,
            }
        )

    decision_lookup = {
        int(row["ensemble_size"]): row
        for row in decisions
        if int(row["log_radius_bins"]) == primary_bins
    }
    lower_decision = decision_lookup[lower_prefix]
    upper_decision = decision_lookup[upper_prefix]
    analytical_unchanged = (
        lower_decision["resolution_analytical_validity_pass"]
        == upper_decision["resolution_analytical_validity_pass"]
    )
    diminishing_unchanged = (
        lower_decision["adjacent_pair_diminishing_returns_pass"]
        == upper_decision["adjacent_pair_diminishing_returns_pass"]
    )
    candidate_unchanged = (
        lower_decision["selected_candidate"] == upper_decision["selected_candidate"]
    )
    point_stability = all(bool(row["point_stability_pass"]) for row in stability_rows)
    summary = {
        "final_prefixes": [lower_prefix, upper_prefix],
        "analytical_validity_decision_unchanged": analytical_unchanged,
        "diminishing_returns_decision_unchanged": diminishing_unchanged,
        "selected_candidate_unchanged": candidate_unchanged,
        "all_primary_point_changes_within_margin": point_stability,
        "ensemble_sufficiency_pass": (
            analytical_unchanged
            and diminishing_unchanged
            and candidate_unchanged
            and point_stability
        ),
    }
    return stability_rows, summary


def summarize_bin_sensitivity(
    *,
    estimate_rows: list[dict[str, object]],
    decisions: list[dict[str, object]],
    config: dict[str, Any],
) -> list[dict[str, object]]:
    settings = validate_settings(config)
    full_size = max(int(value) for value in settings["ensemble_prefixes"])
    primary_bins = int(settings["primary_log_radius_bins"])
    resolutions = sorted(
        {
            int(row["max_superdroplets"])
            for row in estimate_rows
            if int(row["ensemble_size"]) == full_size
        }
    )
    full_decisions = {
        int(row["log_radius_bins"]): row
        for row in decisions
        if int(row["ensemble_size"]) == full_size
    }
    primary_candidate = full_decisions[primary_bins]["selected_candidate"]
    output: list[dict[str, object]] = []
    for bin_count in BIN_COUNTS:
        selected = [
            row
            for row in estimate_rows
            if int(row["ensemble_size"]) == full_size and int(row["log_radius_bins"]) == bin_count
        ]
        l1_rows = [row for row in selected if row["metric"] == L1_METRIC]
        analytical_failure = any(not bool(row["analytical_validity_pass"]) for row in l1_rows)
        point_lookup = {
            (int(row["max_superdroplets"]), float(row["time_s"])): float(row["estimate"])
            for row in l1_rows
        }
        ordering_reversal = any(
            point_lookup[(upper, time_s)] > point_lookup[(lower, time_s)]
            for lower, upper in zip(resolutions[:-1], resolutions[1:], strict=True)
            for time_s in sorted({float(row["time_s"]) for row in l1_rows})
        )
        range_failure = any(not bool(row["range_coverage_pass"]) for row in selected)
        candidate = full_decisions[bin_count]["selected_candidate"]
        candidate_disagreement = (candidate is None) != (primary_candidate is None)
        candidate_step_shift = False
        if candidate is not None and primary_candidate is not None:
            candidate_step_shift = (
                abs(resolutions.index(int(candidate)) - resolutions.index(int(primary_candidate)))
                > 1
            )
        requires_investigation = (
            analytical_failure
            or ordering_reversal
            or range_failure
            or candidate_disagreement
            or candidate_step_shift
        )
        output.append(
            {
                "ensemble_size": full_size,
                "log_radius_bins": bin_count,
                "role": "primary" if bin_count == primary_bins else "sensitivity",
                "selected_candidate": candidate,
                "l1_analytical_failure": analytical_failure,
                "l1_resolution_ordering_reversal": ordering_reversal,
                "range_coverage_failure": range_failure,
                "candidate_none_disagreement_with_primary": candidate_disagreement,
                "candidate_shift_more_than_one_doubling": candidate_step_shift,
                "requires_investigation": requires_investigation,
                "automatic_veto": False,
            }
        )
    return output


def analyze_practical_convergence(
    *,
    rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    config: dict[str, Any],
    archives: dict[str, dict[str, np.ndarray]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    validate_inputs(rows, matrix_rows, config)
    settings = validate_settings(config)
    prefixes = [int(value) for value in settings["ensemble_prefixes"]]
    primary_bins = int(settings["primary_log_radius_bins"])
    sensitivity_bins = [int(value) for value in settings["sensitivity_log_radius_bins"]]
    full_size = prefixes[-1]

    estimate_rows: list[dict[str, object]] = []
    change_rows: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    for prefix in prefixes:
        estimates, changes, decision = evaluate_prefix(
            rows=rows,
            matrix_rows=matrix_rows,
            config=config,
            archives=archives,
            member_count=prefix,
            bin_count=primary_bins,
        )
        estimate_rows.extend(estimates)
        change_rows.extend(changes)
        decisions.append(decision)
    for bin_count in sensitivity_bins:
        estimates, changes, decision = evaluate_prefix(
            rows=rows,
            matrix_rows=matrix_rows,
            config=config,
            archives=archives,
            member_count=full_size,
            bin_count=bin_count,
        )
        estimate_rows.extend(estimates)
        change_rows.extend(changes)
        decisions.append(decision)

    stability_rows, stability = compare_final_prefixes(
        estimate_rows=estimate_rows,
        decisions=decisions,
        config=config,
    )
    sensitivity_rows = summarize_bin_sensitivity(
        estimate_rows=estimate_rows,
        decisions=decisions,
        config=config,
    )
    full_primary = next(
        row
        for row in decisions
        if int(row["ensemble_size"]) == full_size and int(row["log_radius_bins"]) == primary_bins
    )
    candidate = full_primary["selected_candidate"]
    if candidate is not None and stability["ensemble_sufficiency_pass"]:
        status = "selected_practical_resolution"
        selected = candidate
    elif candidate is not None:
        status = "candidate_requires_more_members"
        selected = None
    else:
        status = "no_practical_resolution_selected"
        selected = None
    prospective_fixed_design = settings["status"] in {
        "researcher_approved_prospective_fixed_design",
        "researcher_approved_same_rule_as_frozen_experiment",
    }
    final_decision = {
        "schema": "golovin_practical_convergence_decision_v1",
        "status": status,
        "selected_max_superdroplets": selected,
        "full_ensemble_candidate_before_stability_gate": candidate,
        "tested_resolutions": sorted({int(row["max_superdroplets"]) for row in matrix_rows}),
        "primary_log_radius_bins": primary_bins,
        "sensitivity_log_radius_bins": sensitivity_bins,
        "minimum_worthwhile_improvement_absolute": float(
            settings["minimum_worthwhile_improvement_absolute"]
        ),
        "minimum_worthwhile_improvement_percentage_points": (
            float(settings["minimum_worthwhile_improvement_absolute"]) * 100.0
        ),
        "diminishing_returns_confidence_bound": (
            "one-sided percentile-bootstrap upper bound on the absolute independent-ensemble change"
        ),
        "requires_two_successive_doublings": True,
        "ensemble_stability": stability,
        "full_primary_decision": full_primary,
        "bin_sensitivity_requires_investigation": any(
            bool(row["requires_investigation"]) for row in sensitivity_rows
        ),
        "sensitivity_bins_are_diagnostic_only": True,
        "prospective_scope": (
            "prospectively frozen before the fixed-50 model data are inspected"
            if prospective_fixed_design
            else (
                "prospective for future model data; transparent reanalysis of an already "
                "inspected 100-member matrix"
            )
        ),
        "clara_review_status": (
            "researcher proceeding under supervisor-granted freedom to explore"
            if prospective_fixed_design
            else "pending"
        ),
        "independent_ensemble_warning": (
            "Different resolutions use independent collision ensembles; "
            "member indices are reproducible prefixes, not paired histories."
        ),
    }
    return estimate_rows, change_rows, stability_rows, sensitivity_rows, final_decision


def plot_diminishing_returns(
    change_rows: list[dict[str, object]],
    config: dict[str, Any],
    output: Path,
) -> None:
    settings = validate_settings(config)
    full_size = max(int(value) for value in settings["ensemble_prefixes"])
    primary_bins = int(settings["primary_log_radius_bins"])
    margin = float(settings["minimum_worthwhile_improvement_absolute"]) * 100.0
    selected = [
        row
        for row in change_rows
        if int(row["ensemble_size"]) == full_size and int(row["log_radius_bins"]) == primary_bins
    ]
    pairs = sorted(
        {
            (int(row["lower_max_superdroplets"]), int(row["upper_max_superdroplets"]))
            for row in selected
        }
    )
    colors = plt.get_cmap("viridis")(np.linspace(0.08, 0.92, len(pairs)))
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0), sharex=True)
    for axis, metric in zip(axes, PRIMARY_METRICS, strict=True):
        for color, (lower, upper) in zip(colors, pairs, strict=True):
            rows = sorted(
                [
                    row
                    for row in selected
                    if row["metric"] == metric
                    and int(row["lower_max_superdroplets"]) == lower
                    and int(row["upper_max_superdroplets"]) == upper
                ],
                key=lambda row: float(row["time_s"]),
            )
            times = np.asarray([float(row["time_s"]) / 60.0 for row in rows])
            points = np.asarray([float(row["absolute_change"]) * 100.0 for row in rows])
            uppers = np.asarray([float(row["one_sided_95_upper_bound"]) * 100.0 for row in rows])
            axis.plot(times, uppers, marker="o", color=color, label=f"{lower:,}→{upper:,}")
            axis.scatter(times, points, marker="x", color=color, zorder=3)
        axis.axhspan(0.0, margin, color="#58a65c", alpha=0.13)
        axis.axhline(margin, color="#3a9147", linewidth=1.0)
        axis.set_title(METRIC_LABELS[metric], fontsize=12)
        axis.set_xlabel("time / min", fontsize=10)
        axis.tick_params(labelsize=9)
        axis.grid(alpha=0.2)
    axes[0].set_ylabel("absolute change / pp", fontsize=10)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle(
        "Golovin diminishing returns: point changes (×) and one-sided 95% upper bounds",
        y=0.98,
        fontsize=14,
    )
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.89),
        ncol=3,
        fontsize=9,
    )
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.15, top=0.72, wspace=0.25)
    fig.savefig(output, dpi=300, facecolor="white")
    plt.close(fig)


def plot_prefix_stability(
    change_rows: list[dict[str, object]],
    config: dict[str, Any],
    output: Path,
) -> None:
    settings = validate_settings(config)
    primary_bins = int(settings["primary_log_radius_bins"])
    margin = float(settings["minimum_worthwhile_improvement_absolute"]) * 100.0
    selected = [row for row in change_rows if int(row["log_radius_bins"]) == primary_bins]
    pairs = sorted(
        {
            (int(row["lower_max_superdroplets"]), int(row["upper_max_superdroplets"]))
            for row in selected
        }
    )
    prefixes = sorted({int(row["ensemble_size"]) for row in selected})
    colors = plt.get_cmap("viridis")(np.linspace(0.08, 0.92, len(pairs)))
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0), sharex=True)
    for axis, metric in zip(axes, PRIMARY_METRICS, strict=True):
        for color, (lower, upper) in zip(colors, pairs, strict=True):
            worst_bounds = []
            for prefix in prefixes:
                values = [
                    float(row["one_sided_95_upper_bound"]) * 100.0
                    for row in selected
                    if row["metric"] == metric
                    and int(row["ensemble_size"]) == prefix
                    and int(row["lower_max_superdroplets"]) == lower
                    and int(row["upper_max_superdroplets"]) == upper
                ]
                worst_bounds.append(max(values))
            axis.plot(
                prefixes,
                worst_bounds,
                marker="o",
                color=color,
                label=f"{lower:,}→{upper:,}",
            )
        axis.axhspan(0.0, margin, color="#58a65c", alpha=0.13)
        axis.axhline(margin, color="#3a9147", linewidth=1.0)
        axis.set_title(METRIC_LABELS[metric], fontsize=12)
        axis.set_xlabel("ensemble members", fontsize=10)
        axis.tick_params(labelsize=9)
        axis.grid(alpha=0.2)
    axes[0].set_ylabel("worst all-time upper bound / pp", fontsize=10)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle(
        "Ensemble-prefix stability of the diminishing-returns decision",
        y=0.98,
        fontsize=14,
    )
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.89),
        ncol=3,
        fontsize=9,
    )
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.15, top=0.72, wspace=0.25)
    fig.savefig(output, dpi=300, facecolor="white")
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
    estimates, changes, stability, sensitivity, decision = analyze_practical_convergence(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )

    output_directory.mkdir(parents=True)
    write_csv(output_directory / "analytical_validity_by_prefix.csv", estimates)
    write_csv(output_directory / "diminishing_returns_by_prefix.csv", changes)
    write_csv(output_directory / "final_prefix_point_stability.csv", stability)
    write_csv(output_directory / "bin_sensitivity_summary.csv", sensitivity)
    plot_diminishing_returns(
        changes,
        config,
        output_directory / "diminishing_returns.png",
    )
    plot_prefix_stability(
        changes,
        config,
        output_directory / "ensemble_prefix_stability.png",
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
    (output_directory / "practical_convergence_decision.json").write_text(
        json.dumps(decision, indent=2) + "\n",
        encoding="utf-8",
    )
    print("GOLOVIN_PRACTICAL_CONVERGENCE_PASS=1")
    print(f"status={decision['status']}")
    print(f"selected_max_superdroplets={decision['selected_max_superdroplets']}")
    print(
        "full_ensemble_candidate_before_stability_gate="
        f"{decision['full_ensemble_candidate_before_stability_gate']}"
    )
    print(f"output_directory={output_directory}")


if __name__ == "__main__":
    main()
