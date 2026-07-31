"""Plan the next Golovin convergence step from retained compact results.

This script does two deliberately separate things:

1. It projects how the existing adjacent-resolution L1 confidence intervals
   would contract if both independent resolution ensembles were enlarged.
   The projection preserves the observed point estimate and applies the
   standard asymptotic 1/sqrt(n) scaling to each side of the current interval.
   It is a planning calculation, not new convergence evidence.
2. It plots the earlier 20-member resolution screen alongside the current
   100-member high-resolution experiment. The two experiments remain visually
   distinct and their independent 16,384-SD results are both retained.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

L1_PREFIX = "ensemble_mean_l1_bins_"
MOMENT0 = "golovin_relative_error_radius_moment_0_m3"
MOMENT6 = "golovin_relative_error_radius_moment_6_um6_m3"
DEFAULT_PROJECTED_MEMBERS = (100, 150, 200, 300, 400, 600, 800, 1000, 1500, 2000, 2500)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-adjacent", required=True, type=Path)
    parser.add_argument("--earlier-analytical", required=True, type=Path)
    parser.add_argument("--current-analytical", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument(
        "--projected-members",
        nargs="+",
        type=int,
        default=list(DEFAULT_PROJECTED_MEMBERS),
    )
    return parser.parse_args()


def read_csv(filename: Path) -> list[dict[str, str]]:
    with filename.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(filename: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {filename}")
    with filename.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def projected_interval(
    row: dict[str, str],
    projected_members: int,
) -> tuple[float, float, float]:
    """Scale one balanced two-ensemble interval to a projected member count."""
    lower_members = int(row["lower_n_members"])
    upper_members = int(row["upper_n_members"])
    if lower_members != upper_members:
        raise ValueError("projection requires balanced current resolution ensembles")
    if projected_members < lower_members:
        raise ValueError("projected member count cannot be below the observed member count")
    estimate = float(row["estimated_difference_lower_minus_upper"])
    current_low = float(row["95ci_low"])
    current_high = float(row["95ci_high"])
    if not current_low <= estimate <= current_high:
        raise ValueError("current interval does not contain its point estimate")
    scale = math.sqrt(lower_members / projected_members)
    return (
        estimate,
        estimate + (current_low - estimate) * scale,
        estimate + (current_high - estimate) * scale,
    )


def required_balanced_members(row: dict[str, str]) -> int | None:
    """Return the asymptotic balanced member count needed for containment.

    ``None`` means that interval contraction around the unchanged point
    estimate can never satisfy the registered margin.
    """
    lower_members = int(row["lower_n_members"])
    upper_members = int(row["upper_n_members"])
    if lower_members != upper_members:
        raise ValueError("projection requires balanced current resolution ensembles")
    estimate = float(row["estimated_difference_lower_minus_upper"])
    current_low = float(row["95ci_low"])
    current_high = float(row["95ci_high"])
    margin = float(row["equivalence_margin"])
    if abs(estimate) >= margin:
        return None

    ratios = [1.0]
    if current_high > estimate:
        ratios.append((current_high - estimate) / (margin - estimate))
    if current_low < estimate:
        ratios.append((estimate - current_low) / (margin + estimate))
    return max(lower_members, math.ceil(lower_members * max(ratios) ** 2))


def build_sample_size_projection(
    adjacent_rows: list[dict[str, str]],
    projected_members: list[int],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if projected_members != sorted(set(projected_members)):
        raise ValueError("projected member counts must be unique and sorted")
    l1_rows = [row for row in adjacent_rows if row["metric"].startswith(L1_PREFIX)]
    if not l1_rows:
        raise ValueError("adjacent table contains no fixed-bin L1 rows")
    observed_members = {int(row["lower_n_members"]) for row in l1_rows} | {
        int(row["upper_n_members"]) for row in l1_rows
    }
    if len(observed_members) != 1:
        raise ValueError("all projected L1 rows must use one balanced observed member count")
    base_members = observed_members.pop()
    if not projected_members or projected_members[0] != base_members:
        raise ValueError("projected member grid must begin at the observed member count")

    projection_rows: list[dict[str, object]] = []
    requirement_rows: list[dict[str, object]] = []
    for row in l1_rows:
        required = required_balanced_members(row)
        requirement_rows.append(
            {
                "lower_max_superdroplets": int(row["lower_max_superdroplets"]),
                "upper_max_superdroplets": int(row["upper_max_superdroplets"]),
                "time_s": float(row["time_s"]),
                "log_radius_bins": int(row["metric"].removeprefix(L1_PREFIX)),
                "observed_members_each_resolution": base_members,
                "observed_estimate": float(row["estimated_difference_lower_minus_upper"]),
                "observed_95ci_low": float(row["95ci_low"]),
                "observed_95ci_high": float(row["95ci_high"]),
                "equivalence_margin": float(row["equivalence_margin"]),
                "observed_equivalence_pass": row["equivalence_pass"] == "True",
                "projected_required_members_each_resolution": (
                    required if required is not None else "unattainable_at_fixed_estimate"
                ),
                "projection_method": "observed_95ci_scaled_by_sqrt_100_over_n",
            }
        )
        for members in projected_members:
            estimate, low, high = projected_interval(row, members)
            margin = float(row["equivalence_margin"])
            projection_rows.append(
                {
                    "lower_max_superdroplets": int(row["lower_max_superdroplets"]),
                    "upper_max_superdroplets": int(row["upper_max_superdroplets"]),
                    "time_s": float(row["time_s"]),
                    "log_radius_bins": int(row["metric"].removeprefix(L1_PREFIX)),
                    "projected_members_each_resolution": members,
                    "estimate_held_fixed": estimate,
                    "projected_95ci_low": low,
                    "projected_95ci_high": high,
                    "projected_largest_absolute_interval_edge": max(abs(low), abs(high)),
                    "equivalence_margin": margin,
                    "projected_equivalence_pass": low >= -margin and high <= margin,
                    "projection_method": "observed_95ci_scaled_by_sqrt_100_over_n",
                }
            )
    return projection_rows, requirement_rows


def summarize_pair_requirements(
    requirement_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[tuple[int, int], list[dict[str, object]]] = defaultdict(list)
    for row in requirement_rows:
        grouped[
            (
                int(row["lower_max_superdroplets"]),
                int(row["upper_max_superdroplets"]),
            )
        ].append(row)

    summaries: list[dict[str, object]] = []
    for (lower, upper), rows in sorted(grouped.items()):
        if any(
            row["projected_required_members_each_resolution"] == "unattainable_at_fixed_estimate"
            for row in rows
        ):
            required: int | str = "unattainable_at_fixed_estimate"
            limiting = next(
                row
                for row in rows
                if row["projected_required_members_each_resolution"]
                == "unattainable_at_fixed_estimate"
            )
        else:
            limiting = max(
                rows,
                key=lambda row: int(row["projected_required_members_each_resolution"]),
            )
            required = int(limiting["projected_required_members_each_resolution"])
        summaries.append(
            {
                "lower_max_superdroplets": lower,
                "upper_max_superdroplets": upper,
                "all_registered_rows_observed_pass": all(
                    bool(row["observed_equivalence_pass"]) for row in rows
                ),
                "projected_members_each_resolution_for_all_rows": required,
                "limiting_time_s": float(limiting["time_s"]),
                "limiting_log_radius_bins": int(limiting["log_radius_bins"]),
                "limiting_observed_estimate": float(limiting["observed_estimate"]),
                "limiting_observed_95ci_high": float(limiting["observed_95ci_high"]),
                "equivalence_margin": float(limiting["equivalence_margin"]),
                "projection_method": "observed_95ci_scaled_by_sqrt_100_over_n",
            }
        )
    return summaries


def plot_sample_size_projection(
    projection_rows: list[dict[str, object]],
    output: Path,
) -> None:
    grouped: dict[tuple[int, int, int], list[dict[str, object]]] = defaultdict(list)
    for row in projection_rows:
        grouped[
            (
                int(row["lower_max_superdroplets"]),
                int(row["upper_max_superdroplets"]),
                int(row["projected_members_each_resolution"]),
            )
        ].append(row)
    pairs = sorted({(key[0], key[1]) for key in grouped})
    member_counts = sorted({key[2] for key in grouped})
    margin = float(projection_rows[0]["equivalence_margin"]) * 100.0

    fig, axis = plt.subplots(figsize=(9.5, 5.5))
    colors = plt.cm.viridis(np.linspace(0.12, 0.82, len(pairs)))
    for color, pair in zip(colors, pairs, strict=True):
        worst_edges = [
            max(
                float(row["projected_largest_absolute_interval_edge"])
                for row in grouped[(pair[0], pair[1], members)]
            )
            * 100.0
            for members in member_counts
        ]
        axis.plot(
            member_counts,
            worst_edges,
            marker="o",
            linewidth=2.0,
            color=color,
            label=f"{pair[0] // 1024}k→{pair[1] // 1024}k",
        )

    axis.axhline(margin, color="#3a9147", linewidth=1.4)
    axis.set_xscale("log")
    axis.set_xticks(member_counts, [str(value) for value in member_counts])
    axis.set_xlabel("projected independent members per resolution")
    axis.set_ylabel("worst projected 95% interval edge / percentage points")
    axis.set_title("Planning projection for adjacent-resolution L1 equivalence")
    axis.grid(alpha=0.22)
    axis.legend(title="resolution doubling", frameon=False)
    fig.tight_layout()
    fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _analytical_series(
    rows: list[dict[str, str]],
    metric: str,
) -> dict[tuple[int, float], dict[str, float]]:
    grouped: dict[tuple[int, float], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if metric == "distribution":
            if row["metric"].startswith(L1_PREFIX):
                grouped[(int(row["max_superdroplets"]), float(row["time_s"]))].append(row)
        elif row["metric"] == metric:
            grouped[(int(row["max_superdroplets"]), float(row["time_s"]))].append(row)
    result: dict[tuple[int, float], dict[str, float]] = {}
    for key, selected in grouped.items():
        if metric == "distribution":
            worst = max(selected, key=lambda row: float(row["95ci_high"]))
            result[key] = {
                "estimate": float(worst["95ci_high"]),
                "low": float(worst["95ci_high"]),
                "high": float(worst["95ci_high"]),
            }
        else:
            if len(selected) != 1:
                raise ValueError(f"expected one analytical moment row for {key}")
            row = selected[0]
            result[key] = {
                "estimate": float(row["estimate"]),
                "low": float(row["95ci_low"]),
                "high": float(row["95ci_high"]),
            }
    if not result:
        raise ValueError(f"no analytical rows found for {metric}")
    return result


def plot_resolution_history(
    earlier_rows: list[dict[str, str]],
    current_rows: list[dict[str, str]],
    output: Path,
) -> None:
    experiments = (
        ("earlier screen: 20 members", earlier_rows, "o", ":", "none", 0.985),
        ("current study: 100 members", current_rows, "s", "-", None, 1.015),
    )
    metric_settings = (
        ("distribution", "Distribution: worst bin grid", "L1 upper 95% bound / %", 0.05, False),
        (MOMENT0, r"$M_0$: droplet number", "relative bias / %", 0.05, True),
        (MOMENT6, r"$M_6$: large-drop tail", "relative bias / %", 0.05, True),
    )
    times = sorted({float(row["time_s"]) for rows in (earlier_rows, current_rows) for row in rows})
    colors = plt.cm.viridis(np.linspace(0.08, 0.92, len(times)))
    color_by_time = dict(zip(times, colors, strict=True))
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.7), sharex=True)

    for axis, (metric, title, ylabel, margin, signed) in zip(
        axes,
        metric_settings,
        strict=True,
    ):
        all_y: list[float] = []
        for _, rows, marker, linestyle, marker_face, x_factor in experiments:
            series = _analytical_series(rows, metric)
            resolutions = sorted({key[0] for key in series})
            for time_s in times:
                selected = [
                    (resolution, series[(resolution, time_s)])
                    for resolution in resolutions
                    if (resolution, time_s) in series
                ]
                if not selected:
                    continue
                x = np.asarray([resolution * x_factor for resolution, _ in selected])
                estimate = np.asarray([values["estimate"] for _, values in selected]) * 100.0
                low = np.asarray([values["low"] for _, values in selected]) * 100.0
                high = np.asarray([values["high"] for _, values in selected]) * 100.0
                all_y.extend(low)
                all_y.extend(high)
                if metric == "distribution":
                    axis.plot(
                        x,
                        estimate,
                        color=color_by_time[time_s],
                        marker=marker,
                        markerfacecolor=(
                            marker_face if marker_face is not None else color_by_time[time_s]
                        ),
                        linestyle=linestyle,
                        linewidth=1.4,
                        markersize=5.0,
                    )
                else:
                    axis.errorbar(
                        x,
                        estimate,
                        yerr=np.vstack((estimate - low, high - estimate)),
                        color=color_by_time[time_s],
                        marker=marker,
                        markerfacecolor=(
                            marker_face if marker_face is not None else color_by_time[time_s]
                        ),
                        linestyle=linestyle,
                        linewidth=1.2,
                        elinewidth=0.8,
                        capsize=1.5,
                        markersize=4.5,
                    )
        if signed:
            axis.axhspan(-margin * 100.0, margin * 100.0, color="#d8f0dc", zorder=0)
            axis.axhline(0.0, color="black", linewidth=0.7)
            limit = 1.1 * max(margin * 100.0, max(abs(value) for value in all_y))
            axis.set_ylim(-limit, limit)
        else:
            axis.axhspan(0.0, margin * 100.0, color="#d8f0dc", zorder=0)
            axis.set_ylim(0.0, 1.1 * max(margin * 100.0, max(all_y)))
        axis.set_xscale("log", base=2)
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.grid(alpha=0.2)

    resolutions = sorted(
        {int(row["max_superdroplets"]) for rows in (earlier_rows, current_rows) for row in rows}
    )
    labels = [
        f"{resolution // 1024}k" if resolution >= 1024 else str(resolution)
        for resolution in resolutions
    ]
    for axis in axes:
        axis.set_xticks(resolutions, labels, rotation=30)
        axis.set_xlabel(r"$N_\mathrm{SD}$")

    time_handles = [
        Line2D([0], [0], color=color_by_time[time_s], marker="o", label=f"{time_s / 60:g} min")
        for time_s in times
    ]
    experiment_handles = [
        Line2D(
            [0],
            [0],
            color="black",
            marker=marker,
            markerfacecolor=marker_face if marker_face is not None else "black",
            linestyle=linestyle,
            label=label,
        )
        for label, _, marker, linestyle, marker_face, _ in experiments
    ]
    fig.suptitle("Golovin analytical accuracy across both controlled experiments", y=0.99)
    fig.legend(
        handles=[*time_handles, *experiment_handles],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.925),
        ncol=4,
        frameon=False,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.80))
    fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    output_directory = args.output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"refusing to overwrite: {output_directory}")
    projected_members = [int(value) for value in args.projected_members]
    adjacent_rows = read_csv(args.current_adjacent.resolve())
    earlier_rows = read_csv(args.earlier_analytical.resolve())
    current_rows = read_csv(args.current_analytical.resolve())

    projection_rows, requirement_rows = build_sample_size_projection(
        adjacent_rows,
        projected_members,
    )
    pair_summaries = summarize_pair_requirements(requirement_rows)

    output_directory.mkdir(parents=True)
    write_csv(output_directory / "adjacent_l1_sample_size_projection.csv", projection_rows)
    write_csv(output_directory / "adjacent_l1_required_members.csv", requirement_rows)
    write_csv(output_directory / "adjacent_l1_pair_summary.csv", pair_summaries)
    plot_sample_size_projection(
        projection_rows,
        output_directory / "adjacent_l1_sample_size_projection.png",
    )
    plot_resolution_history(
        earlier_rows,
        current_rows,
        output_directory / "resolution_history_context.png",
    )
    summary = {
        "status": "planning_projection_complete",
        "projection_is_new_convergence_evidence": False,
        "projection_assumption": (
            "Observed 100-member point estimates remain fixed and each side of the "
            "95% interval contracts in proportion to 1/sqrt(n)."
        ),
        "earlier_experiment_warning": (
            "The 20-member and 100-member experiments are independent and are plotted "
            "as separate series; they are not pooled."
        ),
        "pair_summaries": pair_summaries,
    }
    (output_directory / "followup_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    print("GOLOVIN_FOLLOWUP_ANALYSIS_PASS=1")
    print(f"output_directory={output_directory}")


if __name__ == "__main__":
    main()
