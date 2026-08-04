"""Estimate the observed Golovin error-convergence law.

This is a supporting diagnostic, not a resolution-selection rule.  For each
registered metric and decision time it fits

    E(N) = E_inf + a * (N / N_min)**(-p)

over several windows ending at the highest tested resolution.  Independent
member bootstraps propagate stochastic ensemble uncertainty into E_inf, p and
the projected gain from one additional doubling.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import json
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
    read_csv,
    validate_inputs,
    write_csv,
)
from golovin_stage0 import fixed_bin_relative_l1

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
    settings = config["convergence_law"]
    registered_prospective_statuses = {
        "researcher_approved_prospective_supporting_diagnostic",
        "supporting_non_selection_diagnostic",
    }
    if settings["status"] not in registered_prospective_statuses:
        raise ValueError("convergence-law diagnostic is not prospectively approved")
    if settings["selection_gate"] is not False:
        raise ValueError("convergence-law fit must remain a supporting non-selection diagnostic")
    if settings["model"] != "error_floor_plus_power_law":
        raise ValueError("unsupported convergence-law model")
    window_sizes = [int(value) for value in settings["highest_resolution_window_sizes"]]
    minimum_levels = int(settings["minimum_levels_per_fit"])
    if window_sizes != sorted(set(window_sizes)) or window_sizes[0] < minimum_levels:
        raise ValueError("fit windows must be unique, increasing and sufficiently long")
    exponent = settings["exponent_grid"]
    p_min = float(exponent["minimum"])
    p_max = float(exponent["maximum"])
    p_step = float(exponent["spacing"])
    if not 0.0 < p_min < p_max or p_step <= 0.0:
        raise ValueError("invalid exponent grid")
    if int(settings["bootstrap_resamples"]) < 100:
        raise ValueError("at least 100 convergence-law bootstrap resamples are required")
    if int(settings["primary_log_radius_bins"]) != int(
        config["diagnostics"]["primary_log_radius_bins"]
    ):
        raise ValueError("convergence-law and primary diagnostic bin counts differ")
    expected_transforms = {
        L1_METRIC: "identity",
        PRIMARY_METRICS[1]: "absolute_value",
        PRIMARY_METRICS[2]: "absolute_value",
    }
    if settings["metric_error_transform"] != expected_transforms:
        raise ValueError("unexpected metric error transformations")
    return settings


def exponent_grid(settings: dict[str, Any]) -> np.ndarray:
    parameters = settings["exponent_grid"]
    p_min = float(parameters["minimum"])
    p_max = float(parameters["maximum"])
    spacing = float(parameters["spacing"])
    count = int(np.floor((p_max - p_min) / spacing + 0.5))
    return p_min + spacing * np.arange(count + 1)


def fit_floor_power_law_grid(
    resolutions: np.ndarray,
    errors: np.ndarray,
    p_values: np.ndarray,
) -> dict[str, np.ndarray]:
    """Fit non-negative floor-plus-power-law curves on a fixed p grid.

    ``errors`` may have shape ``(levels,)`` or ``(draws, levels)``.  For each
    exponent the amplitude and floor are linear least-squares parameters.  If
    the unconstrained floor is negative, the boundary solution E_inf=0 is
    evaluated instead.  Negative amplitudes are excluded because they would
    describe error increasing with resolution.
    """
    resolutions = np.asarray(resolutions, dtype=float)
    values = np.asarray(errors, dtype=float)
    p_values = np.asarray(p_values, dtype=float)
    squeeze = values.ndim == 1
    if squeeze:
        values = values[None, :]
    if resolutions.ndim != 1 or values.ndim != 2:
        raise ValueError("resolutions and errors must be one- or two-dimensional")
    if values.shape[1] != resolutions.size or resolutions.size < 4:
        raise ValueError("at least four matching resolution levels are required")
    if np.any(~np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("errors must be finite and non-negative")
    if np.any(np.diff(resolutions) <= 0.0):
        raise ValueError("resolutions must be strictly increasing")
    if np.any(~np.isfinite(p_values)) or np.any(p_values <= 0.0):
        raise ValueError("exponents must be finite and positive")

    scaled = resolutions / resolutions[0]
    draw_count = values.shape[0]
    best_sse = np.full(draw_count, np.inf)
    best_floor = np.full(draw_count, np.nan)
    best_amplitude = np.full(draw_count, np.nan)
    best_exponent = np.full(draw_count, np.nan)

    y_mean = np.mean(values, axis=1)
    for exponent in p_values:
        x = scaled ** (-exponent)
        x_mean = float(np.mean(x))
        centered = x - x_mean
        denominator = float(np.dot(centered, centered))
        amplitude = (values @ centered) / denominator
        floor = y_mean - amplitude * x_mean

        on_floor_boundary = floor < 0.0
        if np.any(on_floor_boundary):
            amplitude_boundary = (values[on_floor_boundary] @ x) / float(np.dot(x, x))
            amplitude[on_floor_boundary] = amplitude_boundary
            floor[on_floor_boundary] = 0.0

        valid = amplitude >= 0.0
        if not np.any(valid):
            continue
        prediction = floor[:, None] + amplitude[:, None] * x[None, :]
        sse = np.sum((values - prediction) ** 2, axis=1)
        improve = valid & (sse < best_sse)
        best_sse[improve] = sse[improve]
        best_floor[improve] = floor[improve]
        best_amplitude[improve] = amplitude[improve]
        best_exponent[improve] = exponent

    # Independent-member bootstrap draws can contain a locally increasing
    # error sequence. Such a draw genuinely has no admissible fit under the
    # registered non-negative, decreasing power-law model. It is evidence that
    # this supporting model is not applicable to that draw, not a reason to
    # abort the complete resolution analysis.
    fit_valid = np.isfinite(best_sse)
    best_sse[~fit_valid] = np.nan
    fitted = {
        "floor": best_floor,
        "amplitude": best_amplitude,
        "exponent": best_exponent,
        "sse": best_sse,
        "rmse": np.sqrt(best_sse / resolutions.size),
        "fit_valid": fit_valid,
    }
    if squeeze:
        return {key: value[0] for key, value in fitted.items()}
    return fitted


def transformed_metric_values(
    *,
    metric: str,
    resolution: int,
    members: list[int],
    time_s: float,
    bin_count: int,
    matrix_lookup: dict[tuple[int, int], dict[str, str]],
    diagnostic_lookup: dict[tuple[int, int, float], dict[str, str]],
    archives: dict[str, dict[str, np.ndarray]],
    resamples: int,
    seed: int,
) -> tuple[float, np.ndarray]:
    if metric == L1_METRIC:
        stack, analytical, edges = distribution_stack(
            resolution=resolution,
            members=members,
            time_s=time_s,
            bin_count=bin_count,
            matrix_lookup=matrix_lookup,
            archives=archives,
        )
        point = fixed_bin_relative_l1(np.mean(stack, axis=0), analytical, edges)
        rng = np.random.default_rng(seed)
        indices = rng.integers(0, len(members), size=(resamples, len(members)))
        draws = bootstrap_l1_values(stack, analytical, edges, indices)
        return point, draws

    values = np.asarray(
        [float(diagnostic_lookup[(resolution, member, time_s)][metric]) for member in members]
    )
    draws = bootstrap_mean_values(values, resamples=resamples, seed=seed)
    return abs(float(np.mean(values))), np.abs(draws)


def quantile_interval(values: np.ndarray, confidence_level: float) -> tuple[float, float]:
    alpha = (1.0 - confidence_level) / 2.0
    low, high = np.quantile(np.asarray(values, dtype=float), [alpha, 1.0 - alpha])
    return float(low), float(high)


def analyze_convergence_law(
    *,
    rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
    config: dict[str, Any],
    archives: dict[str, dict[str, np.ndarray]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    validate_inputs(rows, matrix_rows, config)
    settings = validate_settings(config)
    resolutions = sorted({int(row["max_superdroplets"]) for row in matrix_rows})
    window_sizes = [int(value) for value in settings["highest_resolution_window_sizes"]]
    if window_sizes[-1] > len(resolutions):
        raise ValueError("convergence-law window exceeds the resolution ladder")
    members_by_resolution = {
        resolution: sorted(
            int(row["member_index"])
            for row in matrix_rows
            if int(row["max_superdroplets"]) == resolution
        )
        for resolution in resolutions
    }
    expected_members = int(config["matrix"]["members_per_cell"])
    if any(len(members) != expected_members for members in members_by_resolution.values()):
        raise ValueError("every resolution must contain the registered fixed member count")

    decision_times = [float(value) for value in config["diagnostics"]["decision_times_s"]]
    confidence_level = float(config["diagnostics"]["confidence_level"])
    bin_count = int(settings["primary_log_radius_bins"])
    resamples = int(settings["bootstrap_resamples"])
    base_seed = int(settings["bootstrap_seed"])
    p_values = exponent_grid(settings)
    diagnostic_lookup = decision_rows_by_key(rows, decision_times)
    matrix_lookup = {
        (int(row["max_superdroplets"]), int(row["member_index"])): row for row in matrix_rows
    }

    points: dict[tuple[int, float, str], float] = {}
    bootstrap_draws: dict[tuple[int, float, str], np.ndarray] = {}
    for resolution in resolutions:
        members = members_by_resolution[resolution]
        for time_s in decision_times:
            for metric in PRIMARY_METRICS:
                point, draws = transformed_metric_values(
                    metric=metric,
                    resolution=resolution,
                    members=members,
                    time_s=time_s,
                    bin_count=bin_count,
                    matrix_lookup=matrix_lookup,
                    diagnostic_lookup=diagnostic_lookup,
                    archives=archives,
                    resamples=resamples,
                    seed=derived_seed(
                        base_seed,
                        "convergence_law",
                        resolution,
                        time_s,
                        metric,
                    ),
                )
                points[(resolution, time_s, metric)] = point
                bootstrap_draws[(resolution, time_s, metric)] = draws

    output_rows: list[dict[str, object]] = []
    for time_s in decision_times:
        for metric in PRIMARY_METRICS:
            for window_size in window_sizes:
                selected = resolutions[-window_size:]
                resolution_values = np.asarray(selected, dtype=float)
                point_errors = np.asarray(
                    [points[(resolution, time_s, metric)] for resolution in selected]
                )
                draw_errors = np.column_stack(
                    [bootstrap_draws[(resolution, time_s, metric)] for resolution in selected]
                )
                point_fit = fit_floor_power_law_grid(
                    resolution_values,
                    point_errors,
                    p_values,
                )
                bootstrap_fit = fit_floor_power_law_grid(
                    resolution_values,
                    draw_errors,
                    p_values,
                )

                point_fit_valid = bool(point_fit["fit_valid"])
                bootstrap_fit_valid = np.asarray(bootstrap_fit["fit_valid"], dtype=bool)
                bootstrap_fit_count = int(np.count_nonzero(bootstrap_fit_valid))
                bootstrap_fit_fraction = bootstrap_fit_count / bootstrap_fit_valid.size
                next_resolution = 2 * selected[-1]

                # Do not calculate confidence intervals conditional on only
                # the admissible bootstrap draws. That would hide the model
                # failure and overstate uncertainty precision. A complete
                # bootstrap fit is required for uncertainty to be reported.
                uncertainty_estimable = point_fit_valid and bool(np.all(bootstrap_fit_valid))
                if point_fit_valid:
                    next_scale = next_resolution / selected[0]
                    predicted_next = float(
                        point_fit["floor"]
                        + point_fit["amplitude"] * next_scale ** (-point_fit["exponent"])
                    )
                    predicted_gain = max(point_errors[-1] - predicted_next, 0.0)
                else:
                    predicted_next = float("nan")
                    predicted_gain = float("nan")

                if uncertainty_estimable:
                    predicted_next_draws = bootstrap_fit["floor"] + bootstrap_fit[
                        "amplitude"
                    ] * next_scale ** (-bootstrap_fit["exponent"])
                    predicted_gain_draws = np.maximum(
                        draw_errors[:, -1] - predicted_next_draws,
                        0.0,
                    )
                    floor_low, floor_high = quantile_interval(
                        bootstrap_fit["floor"],
                        confidence_level,
                    )
                    exponent_low, exponent_high = quantile_interval(
                        bootstrap_fit["exponent"],
                        confidence_level,
                    )
                    next_low, next_high = quantile_interval(
                        predicted_next_draws,
                        confidence_level,
                    )
                    gain_low, gain_high = quantile_interval(
                        predicted_gain_draws,
                        confidence_level,
                    )
                else:
                    floor_low = floor_high = float("nan")
                    exponent_low = exponent_high = float("nan")
                    next_low = next_high = float("nan")
                    gain_low = gain_high = float("nan")
                output_rows.append(
                    {
                        "time_s": time_s,
                        "metric": metric,
                        "log_radius_bins": bin_count,
                        "member_count": expected_members,
                        "window_size": window_size,
                        "window_min_superdroplets": selected[0],
                        "window_max_superdroplets": selected[-1],
                        "window_resolutions_json": json.dumps(selected),
                        "window_observed_errors_json": json.dumps(point_errors.tolist()),
                        "observed_error_at_window_max": point_errors[-1],
                        "point_fit_status": (
                            "admissible" if point_fit_valid else "no_nonnegative_decay_fit"
                        ),
                        "bootstrap_fit_count": bootstrap_fit_count,
                        "bootstrap_fit_fraction": bootstrap_fit_fraction,
                        "uncertainty_status": (
                            "estimable_all_bootstrap_draws_admissible"
                            if uncertainty_estimable
                            else "not_estimable_some_bootstrap_draws_unfittable"
                        ),
                        "fitted_error_floor": float(point_fit["floor"]),
                        "fitted_error_floor_95ci_low": floor_low,
                        "fitted_error_floor_95ci_high": floor_high,
                        "fitted_exponent": float(point_fit["exponent"]),
                        "fitted_exponent_95ci_low": exponent_low,
                        "fitted_exponent_95ci_high": exponent_high,
                        "fitted_amplitude": float(point_fit["amplitude"]),
                        "fit_rmse": float(point_fit["rmse"]),
                        "next_doubling_superdroplets": next_resolution,
                        "predicted_next_error": predicted_next,
                        "predicted_next_error_95ci_low": next_low,
                        "predicted_next_error_95ci_high": next_high,
                        "predicted_next_improvement": predicted_gain,
                        "predicted_next_improvement_95ci_low": gain_low,
                        "predicted_next_improvement_95ci_high": gain_high,
                        "floor_strictly_positive_at_95pct": bool(
                            uncertainty_estimable and floor_low > 0.0
                        ),
                        "selection_gate": False,
                    }
                )

    point_fit_count = sum(row["point_fit_status"] == "admissible" for row in output_rows)
    full_bootstrap_fit_count = sum(
        row["uncertainty_status"] == "estimable_all_bootstrap_draws_admissible"
        for row in output_rows
    )
    decision = {
        "schema": "golovin_convergence_law_diagnostic_v1",
        "status": "supporting_diagnostic_only",
        "selection_gate": False,
        "tested_resolutions": resolutions,
        "members_per_resolution": expected_members,
        "decision_times_s": decision_times,
        "primary_log_radius_bins": bin_count,
        "model": settings["formula"],
        "highest_resolution_window_sizes": window_sizes,
        "bootstrap_resamples": resamples,
        "interpretation": (
            "Use window-to-window stability and bootstrap uncertainty to distinguish "
            "continuing power-law-like error reduction from an identifiable residual floor. "
            "Do not select a practical resolution from this fit alone."
        ),
        "fit_admissibility": {
            "total_fit_rows": len(output_rows),
            "point_fit_rows_admissible": point_fit_count,
            "rows_with_all_bootstrap_draws_admissible": full_bootstrap_fit_count,
            "uncertainty_policy": (
                "Intervals are not reported when any bootstrap draw has no admissible "
                "non-negative decreasing floor-plus-power-law fit; no conditional "
                "interval is substituted."
            ),
        },
        "successive_improvement_ratio_included": False,
    }
    return output_rows, decision


def plot_late_time_fits(
    fit_rows: list[dict[str, object]],
    output: Path,
) -> None:
    time_s = max(float(row["time_s"]) for row in fit_rows)
    selected = [row for row in fit_rows if float(row["time_s"]) == time_s]
    window_sizes = sorted({int(row["window_size"]) for row in selected})
    colors = plt.get_cmap("viridis")(np.linspace(0.12, 0.88, len(window_sizes)))
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0))
    for axis, metric in zip(axes, PRIMARY_METRICS, strict=True):
        rows = [row for row in selected if row["metric"] == metric]
        for color, window_size in zip(colors, window_sizes, strict=True):
            row = next(value for value in rows if int(value["window_size"]) == window_size)
            if row["point_fit_status"] != "admissible":
                continue
            minimum = int(row["window_min_superdroplets"])
            maximum = int(row["window_max_superdroplets"])
            grid = np.geomspace(minimum, 2 * maximum, 200)
            scaled = grid / minimum
            fitted = float(row["fitted_error_floor"]) + float(row["fitted_amplitude"]) * scaled ** (
                -float(row["fitted_exponent"])
            )
            axis.plot(grid, fitted, color=color, label=f"highest {window_size} levels")
            observed_resolutions = np.asarray(
                json.loads(str(row["window_resolutions_json"])),
                dtype=float,
            )
            observed_errors = np.asarray(
                json.loads(str(row["window_observed_errors_json"])),
                dtype=float,
            )
            axis.scatter(
                observed_resolutions,
                observed_errors,
                color=color,
                marker="o",
                zorder=3,
            )
        axis.set_xscale("log", base=2)
        axis.set_yscale("log")
        axis.set_title(METRIC_LABELS[metric], fontsize=12)
        axis.set_xlabel(r"$N_{\mathrm{SD}}$", fontsize=10)
        axis.grid(alpha=0.2)
        axis.tick_params(labelsize=9)
    axes[0].set_ylabel("absolute analytical error", fontsize=10)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle(
        f"Golovin error-law fits at {time_s / 60.0:g} min (supporting diagnostic)",
        fontsize=14,
    )
    if handles:
        fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.88), ncol=3)
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.16, top=0.72, wspace=0.27)
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
    fit_rows, decision = analyze_convergence_law(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )

    output_directory.mkdir(parents=True)
    write_csv(output_directory / "convergence_law_fits.csv", fit_rows)
    plot_late_time_fits(fit_rows, output_directory / "late_time_convergence_law.png")
    (output_directory / "convergence_law_decision.json").write_text(
        json.dumps(decision, indent=2) + "\n",
        encoding="utf-8",
    )
    print("GOLOVIN_CONVERGENCE_LAW_DIAGNOSTIC_PASS=1")
    print("selection_gate=false")
    print(f"output_directory={output_directory}")


if __name__ == "__main__":
    main()
