"""Check the ensemble-size scaling assumed by the Golovin extension planner.

The completed 100-member matrix is reused without launching CLEO. For each
registered member prefix, this script bootstraps the actual nonlinear L1
estimator and the scalar moment estimators, then records

    Var(q_hat_n) and n * Var(q_hat_n).

If the planner's Var(q_hat_n) = a / n approximation is adequate, the fitted
log-variance slope should be near -1 and the coefficient n * Var(q_hat_n)
should not move strongly as the member prefix grows. These are diagnostics,
not universal pass/fail thresholds and not new convergence evidence.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
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
    decision_rows_by_key,
)
from analyze_golovin_resolution_convergence import (
    bootstrap_l1_values,
    derived_seed,
    distribution_stack,
    load_archives,
    load_yaml,
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
    parser.add_argument("--output-directory", required=True, type=Path)
    return parser.parse_args()


def validate_settings(config: dict[str, Any]) -> dict[str, Any]:
    settings = config["variance_scaling_validation"]
    active = [int(value) for value in settings["active_max_superdroplets"]]
    prefixes = [int(value) for value in settings["ensemble_prefixes"]]
    available = int(settings["available_members_per_resolution"])
    if settings["status"] != "researcher_authorized_existing_data_analysis_only":
        raise ValueError("variance-scaling analysis has not been authorized")
    if len(active) < 2 or active != sorted(set(active)):
        raise ValueError("active resolutions must be unique and increasing")
    if prefixes != sorted(set(prefixes)) or prefixes[0] < 2 or prefixes[-1] != available:
        raise ValueError("prefixes must be unique, increasing and end at the available pool")
    if available != int(config["matrix"]["members_per_cell"]):
        raise ValueError("available member count does not match the reviewed matrix")
    if int(settings["primary_log_radius_bins"]) != int(
        config["diagnostics"]["primary_log_radius_bins"]
    ):
        raise ValueError("variance scaling must use the registered primary bin count")
    if int(settings["bootstrap_resamples"]) < 100:
        raise ValueError("variance scaling requires at least 100 bootstrap resamples")
    if not 0.0 < float(settings["confidence_level"]) < 1.0:
        raise ValueError("confidence level must lie between zero and one")
    if settings["formal_pass_fail_gate"] is not False:
        raise ValueError("variance scaling is diagnostic and must not be a formal gate")
    return settings


def variance_row(
    *,
    resolution: int,
    time_s: float,
    metric: str,
    member_count: int,
    point: float,
    draws: np.ndarray,
) -> dict[str, object]:
    draws = np.asarray(draws, dtype=float)
    variance = float(np.var(draws, ddof=1))
    coefficient = variance * member_count
    if not np.isfinite(variance) or variance < 0.0:
        raise ValueError("bootstrap variance is invalid")
    return {
        "max_superdroplets": resolution,
        "time_s": time_s,
        "metric": metric,
        "ensemble_members": member_count,
        "point_estimate": point,
        "bootstrap_variance_of_estimate": variance,
        "variance_coefficient_n_times_variance": coefficient,
    }


def summarize_variance_rows(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[int, float, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                int(row["max_superdroplets"]),
                float(row["time_s"]),
                str(row["metric"]),
            )
        ].append(row)

    output: list[dict[str, object]] = []
    for (resolution, time_s, metric), group in sorted(grouped.items()):
        ordered = sorted(group, key=lambda row: int(row["ensemble_members"]))
        member_counts = np.asarray([int(row["ensemble_members"]) for row in ordered], dtype=float)
        variances = np.asarray(
            [float(row["bootstrap_variance_of_estimate"]) for row in ordered],
            dtype=float,
        )
        coefficients = np.asarray(
            [float(row["variance_coefficient_n_times_variance"]) for row in ordered],
            dtype=float,
        )
        if np.any(variances <= 0.0):
            slope = float("nan")
            r_squared = float("nan")
        else:
            slope, intercept = np.polyfit(np.log(member_counts), np.log(variances), 1)
            fitted = intercept + slope * np.log(member_counts)
            residual = float(np.sum((np.log(variances) - fitted) ** 2))
            total = float(np.sum((np.log(variances) - np.mean(np.log(variances))) ** 2))
            r_squared = 1.0 if total == 0.0 else 1.0 - residual / total
        output.append(
            {
                "max_superdroplets": resolution,
                "time_s": time_s,
                "metric": metric,
                "minimum_members": int(member_counts[0]),
                "maximum_members": int(member_counts[-1]),
                "fitted_log_variance_slope": float(slope),
                "slope_deviation_from_minus_one": float(slope + 1.0),
                "fitted_log_variance_r_squared": r_squared,
                "minimum_variance_coefficient": float(np.min(coefficients)),
                "maximum_variance_coefficient": float(np.max(coefficients)),
                "coefficient_max_to_min_ratio": (
                    float(np.max(coefficients) / np.min(coefficients))
                    if np.min(coefficients) > 0.0
                    else float("inf")
                ),
                "coefficient_relative_range": float(
                    (np.max(coefficients) - np.min(coefficients)) / np.mean(coefficients)
                ),
                "point_estimate_range": float(
                    max(float(row["point_estimate"]) for row in ordered)
                    - min(float(row["point_estimate"]) for row in ordered)
                ),
            }
        )
    return output


def adjacent_calibration_rows(
    *,
    variance_rows: list[dict[str, object]],
    bootstrap_draws: dict[tuple[int, float, str, int], np.ndarray],
    active_resolutions: list[int],
    prefixes: list[int],
    decision_times: list[float],
    confidence_level: float,
) -> list[dict[str, object]]:
    lookup = {
        (
            int(row["max_superdroplets"]),
            float(row["time_s"]),
            str(row["metric"]),
            int(row["ensemble_members"]),
        ): row
        for row in variance_rows
    }
    z_value = float(norm.ppf(confidence_level))
    output: list[dict[str, object]] = []
    for lower, upper in zip(active_resolutions[:-1], active_resolutions[1:], strict=True):
        for time_s in decision_times:
            for metric in PRIMARY_METRICS:
                for member_count in prefixes:
                    lower_row = lookup[(lower, time_s, metric, member_count)]
                    upper_row = lookup[(upper, time_s, metric, member_count)]
                    point_change = abs(
                        float(lower_row["point_estimate"]) - float(upper_row["point_estimate"])
                    )
                    absolute_draws = np.abs(
                        bootstrap_draws[(lower, time_s, metric, member_count)]
                        - bootstrap_draws[(upper, time_s, metric, member_count)]
                    )
                    percentile_bound = float(np.quantile(absolute_draws, confidence_level))
                    normal_standard_error = float(
                        np.sqrt(
                            float(lower_row["bootstrap_variance_of_estimate"])
                            + float(upper_row["bootstrap_variance_of_estimate"])
                        )
                    )
                    normal_bound = point_change + z_value * normal_standard_error
                    output.append(
                        {
                            "lower_max_superdroplets": lower,
                            "upper_max_superdroplets": upper,
                            "time_s": time_s,
                            "metric": metric,
                            "ensemble_members_each": member_count,
                            "absolute_point_change": point_change,
                            "percentile_bootstrap_one_sided_upper_bound": percentile_bound,
                            "normal_approximation_one_sided_upper_bound": normal_bound,
                            "normal_minus_percentile_bound": normal_bound - percentile_bound,
                        }
                    )
    return output


def analyze(
    *,
    rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    config: dict[str, Any],
    archives: dict[str, dict[str, np.ndarray]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    validate_inputs(rows, matrix_rows, config)
    settings = validate_settings(config)
    active = [int(value) for value in settings["active_max_superdroplets"]]
    prefixes = [int(value) for value in settings["ensemble_prefixes"]]
    bin_count = int(settings["primary_log_radius_bins"])
    resamples = int(settings["bootstrap_resamples"])
    base_seed = int(settings["bootstrap_seed"])
    confidence_level = float(settings["confidence_level"])
    decision_times = [float(value) for value in config["diagnostics"]["decision_times_s"]]
    keyed = decision_rows_by_key(rows, decision_times)
    matrix_lookup = {
        (int(row["max_superdroplets"]), int(row["member_index"])): row for row in matrix_rows
    }

    output: list[dict[str, object]] = []
    draws_by_key: dict[tuple[int, float, str, int], np.ndarray] = {}
    for resolution in active:
        all_members = sorted(
            int(row["member_index"])
            for row in matrix_rows
            if int(row["max_superdroplets"]) == resolution
        )
        if len(all_members) != int(settings["available_members_per_resolution"]):
            raise ValueError(f"resolution {resolution} does not have the complete member pool")
        for time_s in decision_times:
            full_stack, analytical, edges = distribution_stack(
                resolution=resolution,
                members=all_members,
                time_s=time_s,
                bin_count=bin_count,
                matrix_lookup=matrix_lookup,
                archives=archives,
            )
            for member_count in prefixes:
                members = all_members[:member_count]
                stack = full_stack[:member_count]
                point = fixed_bin_relative_l1(np.mean(stack, axis=0), analytical, edges)
                rng = np.random.default_rng(
                    derived_seed(
                        base_seed,
                        "variance-scaling-l1",
                        resolution,
                        time_s,
                        member_count,
                    )
                )
                indices = rng.integers(0, member_count, size=(resamples, member_count))
                l1_draws = bootstrap_l1_values(stack, analytical, edges, indices)
                draws_by_key[(resolution, time_s, L1_METRIC, member_count)] = l1_draws
                output.append(
                    variance_row(
                        resolution=resolution,
                        time_s=time_s,
                        metric=L1_METRIC,
                        member_count=member_count,
                        point=point,
                        draws=l1_draws,
                    )
                )

                for metric in PRIMARY_METRICS[1:]:
                    values = np.asarray(
                        [float(keyed[(resolution, member, time_s)][metric]) for member in members],
                        dtype=float,
                    )
                    moment_draws = bootstrap_mean_values(
                        values,
                        resamples=resamples,
                        seed=derived_seed(
                            base_seed,
                            "variance-scaling-moment",
                            resolution,
                            time_s,
                            metric,
                            member_count,
                        ),
                    )
                    draws_by_key[(resolution, time_s, metric, member_count)] = moment_draws
                    output.append(
                        variance_row(
                            resolution=resolution,
                            time_s=time_s,
                            metric=metric,
                            member_count=member_count,
                            point=float(np.mean(values)),
                            draws=moment_draws,
                        )
                    )

    summary_rows = summarize_variance_rows(output)
    calibration_rows = adjacent_calibration_rows(
        variance_rows=output,
        bootstrap_draws=draws_by_key,
        active_resolutions=active,
        prefixes=prefixes,
        decision_times=decision_times,
        confidence_level=confidence_level,
    )
    decision = {
        "schema": "golovin_variance_scaling_validation_v1",
        "status": "existing_data_variance_scaling_diagnostic_complete",
        "active_max_superdroplets": active,
        "ensemble_prefixes": prefixes,
        "primary_log_radius_bins": bin_count,
        "bootstrap_resamples": resamples,
        "confidence_level": confidence_level,
        "variance_model_under_review": "variance_of_estimate_equals_coefficient_over_member_count",
        "interpretation": (
            "Inspect fitted slopes, coefficient stability and normal-versus-percentile "
            "calibration. No universal pass threshold is imposed."
        ),
        "formal_pass_fail_gate": False,
        "new_model_compute_authorized": False,
        "long_kernel_compute_authorized": False,
    }
    return output, summary_rows, calibration_rows, decision


def plot_scaling(
    rows: list[dict[str, object]],
    output: Path,
    *,
    coefficient: bool,
) -> None:
    time_s = max(float(row["time_s"]) for row in rows)
    selected = [row for row in rows if float(row["time_s"]) == time_s]
    resolutions = sorted({int(row["max_superdroplets"]) for row in selected})
    colors = dict(zip(resolutions, ("#2468a2", "#d95f02", "#3a9147"), strict=False))
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.1))
    for axis, metric in zip(axes, PRIMARY_METRICS, strict=True):
        for resolution in resolutions:
            group = sorted(
                (
                    row
                    for row in selected
                    if int(row["max_superdroplets"]) == resolution and row["metric"] == metric
                ),
                key=lambda row: int(row["ensemble_members"]),
            )
            x = np.asarray([int(row["ensemble_members"]) for row in group])
            if coefficient:
                y = np.asarray(
                    [float(row["variance_coefficient_n_times_variance"]) for row in group]
                )
            else:
                y = np.asarray([float(row["bootstrap_variance_of_estimate"]) for row in group])
            axis.plot(x, y, marker="o", color=colors[resolution], label=f"{resolution:,} SDs")
            if not coefficient:
                reference = y[-1] * x[-1] / x
                axis.plot(x, reference, linestyle=":", color=colors[resolution], alpha=0.55)
        axis.set_title(METRIC_LABELS[metric])
        axis.set_xlabel("members in nested prefix")
        axis.set_yscale("log")
        axis.grid(alpha=0.2)
    axes[0].set_ylabel(
        r"$n\,\mathrm{Var}(\hat q_n)$" if coefficient else r"$\mathrm{Var}(\hat q_n)$"
    )
    handles, labels = axes[0].get_legend_handles_labels()
    title = (
        f"Variance-coefficient stability at {time_s / 60.0:g} min"
        if coefficient
        else f"Bootstrap variance scaling at {time_s / 60.0:g} min"
    )
    fig.suptitle(title, y=1.02)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.985), ncol=3)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_calibration(rows: list[dict[str, object]], output: Path) -> None:
    time_s = max(float(row["time_s"]) for row in rows)
    selected = [row for row in rows if float(row["time_s"]) == time_s]
    pairs = sorted(
        {
            (int(row["lower_max_superdroplets"]), int(row["upper_max_superdroplets"]))
            for row in selected
        }
    )
    colors = dict(zip(pairs, ("#6a51a3", "#e6550d"), strict=False))
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.1))
    for axis, metric in zip(axes, PRIMARY_METRICS, strict=True):
        for pair in pairs:
            group = sorted(
                (
                    row
                    for row in selected
                    if (
                        int(row["lower_max_superdroplets"]),
                        int(row["upper_max_superdroplets"]),
                    )
                    == pair
                    and row["metric"] == metric
                ),
                key=lambda row: int(row["ensemble_members_each"]),
            )
            x = [int(row["ensemble_members_each"]) for row in group]
            y = [100.0 * float(row["normal_minus_percentile_bound"]) for row in group]
            axis.plot(
                x,
                y,
                marker="o",
                color=colors[pair],
                label=f"{pair[0]:,}–{pair[1]:,}",
            )
        axis.axhline(0.0, color="black", linewidth=0.8)
        axis.set_title(METRIC_LABELS[metric])
        axis.set_xlabel("members per resolution")
        axis.grid(alpha=0.2)
    axes[0].set_ylabel("normal minus percentile upper bound / percentage points")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle(f"Normal-approximation calibration at {time_s / 60.0:g} min", y=1.02)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.985), ncol=2)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    for filename in (args.combined_member_time, args.matrix_file, args.config):
        if not filename.is_file():
            raise FileNotFoundError(filename)
    if not args.run_root.is_dir():
        raise NotADirectoryError(args.run_root)
    if args.output_directory.exists():
        raise FileExistsError(args.output_directory)

    rows = read_csv(args.combined_member_time)
    matrix_rows = read_csv(args.matrix_file, delimiter="\t")
    config = load_yaml(args.config)
    settings = validate_settings(config)
    active = [int(value) for value in settings["active_max_superdroplets"]]
    active_matrix_rows = [row for row in matrix_rows if int(row["max_superdroplets"]) in active]
    archives = load_archives(args.run_root, active_matrix_rows)
    variance_rows, summary_rows, calibration_rows, decision = analyze(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )

    args.output_directory.mkdir(parents=True)
    write_csv(args.output_directory / "variance_scaling_by_prefix.csv", variance_rows)
    write_csv(args.output_directory / "variance_scaling_summary.csv", summary_rows)
    write_csv(args.output_directory / "normal_percentile_calibration.csv", calibration_rows)
    plot_scaling(
        variance_rows,
        args.output_directory / "bootstrap_variance_scaling.png",
        coefficient=False,
    )
    plot_scaling(
        variance_rows,
        args.output_directory / "variance_coefficient_stability.png",
        coefficient=True,
    )
    plot_calibration(
        calibration_rows,
        args.output_directory / "normal_percentile_calibration.png",
    )
    decision.update(
        {
            "combined_member_time": portable_artifact_path(
                args.combined_member_time,
                analysis_root=args.output_directory.parent,
            ),
            "combined_member_time_path_base": "analysis_root",
            "combined_member_time_sha256": sha256_file(args.combined_member_time),
            "matrix_file": str(args.matrix_file.resolve()),
            "matrix_sha256": sha256_file(args.matrix_file),
            "config": str(args.config.resolve()),
            "config_sha256": sha256_file(args.config),
        }
    )
    (args.output_directory / "variance_scaling_decision.json").write_text(
        json.dumps(decision, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
