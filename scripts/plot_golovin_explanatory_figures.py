#!/usr/bin/env python3
"""Create explanatory figures for the final controlled Golovin experiment.

The script is deliberately analysis-only. It reads archived Stage-0 arrays and
the final fixed-50 decision tables; it does not run CLEO. The figures separate
formal ensemble-mean convergence statistics from descriptive member-level
variability.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch, Rectangle  # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator  # noqa: E402


COLORS = {
    "blue": "#2166AC",
    "sky": "#67A9CF",
    "orange": "#D95F02",
    "gold": "#E6AB02",
    "green": "#1B9E77",
    "purple": "#7570B3",
    "red": "#B2182B",
    "gray": "#5F6974",
    "light_gray": "#E9EEF3",
    "dark": "#0B2545",
}
METRIC_LABELS = {
    "ensemble_mean_l1_bins_500": r"DSD $L_1$ error",
    "golovin_relative_error_radius_moment_0_m3": r"$M_0$ bias",
    "golovin_relative_error_radius_moment_6_um6_m3": r"$M_6$ bias",
}
MOMENT_COLUMNS = {
    "golovin_relative_error_radius_moment_0_m3": "M0",
    "golovin_relative_error_radius_moment_3_um3_m3": "M3",
    "golovin_relative_error_radius_moment_6_um6_m3": "M6",
}
RESOLUTION_RE = re.compile(r"_N(?P<n>\d+)_dt[^_]+_m(?P<m>\d+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixed50-analysis", required=True, type=Path)
    parser.add_argument("--fixed50-tables", required=True, type=Path)
    parser.add_argument("--selected-npz-root", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    return parser.parse_args()


def set_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": COLORS["dark"],
            "axes.labelcolor": COLORS["dark"],
            "axes.titlecolor": COLORS["dark"],
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.color": COLORS["dark"],
            "ytick.color": COLORS["dark"],
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "font.family": "DejaVu Sans",
            "font.size": 9.5,
            "legend.fontsize": 8.5,
            "legend.frameon": False,
            "grid.color": "#CBD5E1",
            "grid.linewidth": 0.6,
            "grid.alpha": 0.65,
            "lines.linewidth": 2.0,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
        }
    )


def save_figure(fig: plt.Figure, output: Path) -> None:
    fig.savefig(output, dpi=300, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def format_resolution(value: float, _position: int | None = None) -> str:
    value = int(round(value))
    if value >= 1_048_576:
        return f"{value / 1_048_576:g}M"
    if value >= 1024:
        return f"{value / 1024:g}k"
    return str(value)


def add_panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.16,
        1.06,
        label,
        transform=ax.transAxes,
        fontsize=11,
        fontweight="bold",
        color=COLORS["dark"],
        va="top",
    )


def source_footer(fig: plt.Figure, text: str) -> None:
    fig.text(0.01, 0.005, text, ha="left", va="bottom", fontsize=6.8, color=COLORS["gray"])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_archives(root: Path) -> dict[tuple[int, int], dict[str, np.ndarray]]:
    archives: dict[tuple[int, int], dict[str, np.ndarray]] = {}
    for path in sorted(root.rglob("fixed_bin_distributions.npz")):
        run_label = path.parents[1].name
        match = RESOLUTION_RE.search(run_label)
        if not match:
            raise ValueError(f"cannot parse resolution/member from {run_label}")
        key = (int(match.group("n")), int(match.group("m")))
        with np.load(path, allow_pickle=False) as source:
            archives[key] = {name: np.asarray(source[name]) for name in source.files}
    return archives


def nominal_time_index(archive: dict[str, np.ndarray], time_s: float) -> int:
    index = np.flatnonzero(np.isclose(archive["time_s"], time_s, atol=1e-3, rtol=0.0))
    if index.size != 1:
        raise ValueError(f"expected one archive time match for {time_s}, found {index.size}")
    return int(index[0])


def bin_centers(edges: np.ndarray) -> np.ndarray:
    return np.sqrt(edges[:-1] * edges[1:])


def relative_l1(numerical: np.ndarray, analytical: np.ndarray, edges: np.ndarray) -> float:
    widths = np.diff(np.log(edges))
    return float(np.sum(np.abs(numerical - analytical) * widths) / np.sum(analytical * widths))


def derived_seed(base_seed: int, *parts: object) -> int:
    payload = "|".join([str(base_seed), *(str(part) for part in parts)]).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def plot_dsd_evolution(
    archives: dict[tuple[int, int], dict[str, np.ndarray]], output: Path
) -> None:
    resolution = 131_072
    members = sorted(member for n, member in archives if n == resolution)
    if len(members) != 50:
        raise ValueError(f"expected 50 selected-resolution archives, found {len(members)}")
    times = [0.0, 1200.0, 2400.0, 3600.0]
    fig, axes = plt.subplots(2, 4, figsize=(13.2, 6.2), sharex="col")
    for column, time_s in enumerate(times):
        numerical = []
        analytical = None
        edges = None
        for member in members:
            archive = archives[(resolution, member)]
            idx = nominal_time_index(archive, time_s)
            numerical.append(archive["numerical_gm3_per_ln_radius_500"][idx])
            if analytical is None:
                analytical = archive["analytical_gm3_per_ln_radius_500"][idx]
                edges = archive["edges_um_500"]
        stack = np.stack(numerical)
        mean = np.mean(stack, axis=0)
        low, high = np.quantile(stack, [0.05, 0.95], axis=0)
        centers = bin_centers(edges)
        ax = axes[0, column]
        ax.fill_between(centers, low, high, color=COLORS["sky"], alpha=0.26, linewidth=0)
        ax.plot(centers, mean, color=COLORS["blue"], label="ensemble mean")
        ax.plot(centers, analytical, color=COLORS["dark"], linestyle="--", label="analytical")
        ax.set_xscale("log")
        ax.set_title(f"t = {time_s / 60:.0f} min")
        ax.grid(True, which="major")
        ax.set_xlim(1, 5000)
        if column == 0:
            ax.set_ylabel(r"mass density / g m$^{-3}$ per unit ln $r$")
        residual = mean - analytical
        member_residual = stack - analytical
        residual_low, residual_high = np.quantile(member_residual, [0.05, 0.95], axis=0)
        axr = axes[1, column]
        axr.axhline(0, color=COLORS["dark"], linewidth=0.9)
        axr.fill_between(
            centers, residual_low, residual_high, color=COLORS["sky"], alpha=0.26, linewidth=0
        )
        axr.plot(centers, residual, color=COLORS["blue"])
        axr.set_xscale("log")
        axr.set_xlim(1, 5000)
        axr.grid(True, which="major")
        axr.set_xlabel(r"radius $r$ / $\mu$m")
        if column == 0:
            axr.set_ylabel("numerical − analytical\n" + r"/ g m$^{-3}$ per unit ln $r$")
        l1_percent = 100 * relative_l1(mean, analytical, edges)
        axr.text(
            0.97,
            0.92,
            rf"ensemble-mean $L_1$ = {l1_percent:.2f}%",
            transform=axr.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color=COLORS["dark"],
        )
    axes[0, 0].legend(
        handles=[
            Line2D([], [], color=COLORS["blue"], label="50-member ensemble mean"),
            Line2D([], [], color=COLORS["dark"], linestyle="--", label="Golovin analytical"),
            Patch(facecolor=COLORS["sky"], alpha=0.26, label="5–95% member envelope"),
        ],
        loc="upper left",
    )
    add_panel_label(axes[0, 0], "a")
    add_panel_label(axes[1, 0], "b")
    fig.suptitle(
        r"How the droplet mass distribution evolves at the selected resolution ($N_{SD}=131{,}072$)",
        fontsize=15,
        fontweight="bold",
        color=COLORS["dark"],
        y=0.995,
    )
    source_footer(
        fig,
        "Controlled Golovin fixed-50 experiment; 500 fixed logarithmic bins. Shading is member spread, not a confidence interval.",
    )
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    save_figure(fig, output)


def plot_decision_matrix(decision: dict[str, object], output: Path) -> None:
    tested = [int(value) for value in decision["tested_resolutions"]]
    candidates = [value for value in tested if 4 * value in tested]
    analytical = {int(key): bool(value) for key, value in decision["resolution_analytical_and_precision_pass"].items()}
    adjacent = {
        tuple(int(part) for part in key.split("-")): bool(value)
        for key, value in decision["adjacent_pair_equivalence_pass"].items()
    }
    rows = [
        r"$N$ analytical + precision",
        r"$2N$ analytical + precision",
        r"$4N$ analytical + precision",
        r"$N \rightarrow 2N$ equivalence",
        r"$2N \rightarrow 4N$ equivalence",
        "all five gates",
    ]
    matrix = np.zeros((len(rows), len(candidates)), dtype=int)
    for column, value in enumerate(candidates):
        checks = [
            analytical[value],
            analytical[2 * value],
            analytical[4 * value],
            adjacent[(value, 2 * value)],
            adjacent[(2 * value, 4 * value)],
        ]
        matrix[:5, column] = checks
        matrix[5, column] = all(checks)
    fig, ax = plt.subplots(figsize=(11.4, 4.7))
    ax.imshow(matrix, aspect="auto", cmap=ListedColormap(["#D95F5F", "#2E8B57"]), vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(candidates)), [format_resolution(value) for value in candidates])
    ax.set_yticks(np.arange(len(rows)), rows)
    ax.set_xlabel(r"candidate $N_{SD}$")
    ax.set_xticks(np.arange(-0.5, len(candidates), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(rows), 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", bottom=False, left=False)
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            ax.text(
                column,
                row,
                "PASS" if matrix[row, column] else "FAIL",
                ha="center",
                va="center",
                color="white",
                fontweight="bold",
                fontsize=8,
            )
    selected = int(decision["selected_max_superdroplets"])
    selected_column = candidates.index(selected)
    ax.add_patch(
        Rectangle(
            (selected_column - 0.48, -0.48),
            0.96,
            len(rows) - 0.04,
            fill=False,
            edgecolor=COLORS["gold"],
            linewidth=3.2,
        )
    )
    ax.annotate(
        "first candidate satisfying\nall registered gates",
        xy=(selected_column, len(rows) - 0.35),
        xytext=(selected_column + 1.5, len(rows) + 0.45),
        arrowprops=dict(arrowstyle="->", color=COLORS["gold"], linewidth=1.5),
        color=COLORS["dark"],
        ha="center",
        fontsize=9,
        annotation_clip=False,
    )
    ax.set_title(
        "Formal convergence decision matrix",
        loc="left",
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.125,
        0.90,
        r"A candidate passes only if $N$, $2N$, and $4N$ are analytically valid and both doublings are equivalent.",
        fontsize=9,
        color=COLORS["gray"],
    )
    source_footer(fig, "Registered fixed-50 resolution decision; 50 independent collision members at every resolution.")
    fig.tight_layout(rect=[0, 0.06, 1, 0.88])
    save_figure(fig, output)


def plot_confirmation(analytical: pd.DataFrame, output: Path) -> None:
    resolutions = [131_072, 262_144, 524_288]
    metrics = list(METRIC_LABELS)
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.2), sharex=True)
    palette = [COLORS["blue"], COLORS["orange"], COLORS["green"]]
    for ax, metric in zip(axes, metrics):
        selected = analytical[
            (analytical["metric"] == metric)
            & (analytical["max_superdroplets"].isin(resolutions))
        ].copy()
        for resolution, color in zip(resolutions, palette):
            values = selected[selected["max_superdroplets"] == resolution].sort_values("time_s")
            time_min = values["time_s"].to_numpy() / 60.0
            estimate = 100 * values["estimate"].to_numpy()
            low = 100 * values["95ci_low"].to_numpy()
            high = 100 * values["95ci_high"].to_numpy()
            if metric == "ensemble_mean_l1_bins_500":
                ax.plot(time_min, high, color=color, marker="o", label=format_resolution(resolution))
            else:
                ax.errorbar(
                    time_min,
                    estimate,
                    yerr=np.vstack([estimate - low, high - estimate]),
                    color=color,
                    marker="o",
                    capsize=2,
                    label=format_resolution(resolution),
                )
        ax.axhspan(-5, 5, color="#D9F0D3", alpha=0.75, zorder=0)
        ax.axhline(0, color=COLORS["dark"], linewidth=0.8)
        ax.grid(True)
        ax.set_xlabel("simulation time / min")
        ax.set_title(METRIC_LABELS[metric])
        if metric == "ensemble_mean_l1_bins_500":
            ax.set_ylabel("upper 95% confidence bound / %")
            ax.set_ylim(bottom=0)
        else:
            ax.set_ylabel("relative bias / %")
        ax.legend(title=r"$N_{SD}$", ncol=1, loc="best")
    add_panel_label(axes[0], "a")
    add_panel_label(axes[1], "b")
    add_panel_label(axes[2], "c")
    fig.suptitle(
        r"Registered $N$–$2N$–$4N$ confirmation across the full 60-minute window",
        fontsize=15,
        fontweight="bold",
        color=COLORS["dark"],
    )
    source_footer(
        fig,
        "Green band: ±5% analytical-accuracy margin. For L1, the plotted quantity is the upper 95% bound and only the positive half applies.",
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.93])
    save_figure(fig, output)


def compute_five_member_sensitivity(
    archives: dict[tuple[int, int], dict[str, np.ndarray]], diagnostics: pd.DataFrame
) -> list[dict[str, float | str | int]]:
    resolution = 131_072
    members = sorted(member for n, member in archives if n == resolution)
    archive_list = [archives[(resolution, member)] for member in members]
    idx = nominal_time_index(archive_list[0], 3600.0)
    stack = np.stack([archive["numerical_gm3_per_ln_radius_500"][idx] for archive in archive_list])
    analytical = archive_list[0]["analytical_gm3_per_ln_radius_500"][idx]
    edges = archive_list[0]["edges_um_500"]
    selected = diagnostics[
        (diagnostics["max_superdroplets"] == resolution)
        & np.isclose(diagnostics["time_s"], 3600.0, atol=1e-3)
    ].sort_values("member_index")
    if selected.shape[0] != 50:
        raise ValueError("expected 50 final-time diagnostics for selected resolution")
    moment_values = {
        metric: selected[metric].to_numpy(dtype=float)
        for metric in [
            "golovin_relative_error_radius_moment_0_m3",
            "golovin_relative_error_radius_moment_6_um6_m3",
        ]
    }
    rng = np.random.default_rng(derived_seed(2026073102, "ensemble_size", resolution, 5))
    random_keys = rng.random((2000, 50))
    draw_indices = np.argpartition(random_keys, 4, axis=1)[:, :5]
    sampled_mean = np.mean(stack[draw_indices], axis=1)
    l1_values = np.asarray([relative_l1(value, analytical, edges) for value in sampled_mean])
    values_by_metric = {
        "ensemble_mean_l1_bins_500": l1_values,
        **{metric: np.mean(values[draw_indices], axis=1) for metric, values in moment_values.items()},
    }
    full_estimates = {
        "ensemble_mean_l1_bins_500": relative_l1(np.mean(stack, axis=0), analytical, edges),
        **{metric: float(np.mean(values)) for metric, values in moment_values.items()},
    }
    output = []
    for metric, values in values_by_metric.items():
        low, median, high = np.quantile(values, [0.025, 0.5, 0.975])
        output.append(
            {
                "max_superdroplets": resolution,
                "time_s": 3600.0,
                "metric": metric,
                "ensemble_size": 5,
                "full_ensemble_estimate": full_estimates[metric],
                "subset_median": float(median),
                "subset_95pct_low": float(low),
                "subset_95pct_high": float(high),
            }
        )
    return output


def plot_ensemble_stability(
    sensitivity: pd.DataFrame,
    five_rows: list[dict[str, float | str | int]],
    output: Path,
) -> None:
    selected = sensitivity[sensitivity["max_superdroplets"] == 131_072].copy()
    selected = pd.concat([pd.DataFrame(five_rows), selected], ignore_index=True)
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.2))
    for ax, metric in zip(axes, METRIC_LABELS):
        values = selected[selected["metric"] == metric].sort_values("ensemble_size")
        x = values["ensemble_size"].to_numpy()
        median = 100 * values["subset_median"].to_numpy()
        low = 100 * values["subset_95pct_low"].to_numpy()
        high = 100 * values["subset_95pct_high"].to_numpy()
        full = 100 * float(values["full_ensemble_estimate"].iloc[0])
        ax.fill_between(x, low, high, color=COLORS["sky"], alpha=0.28, label="95% subset range")
        ax.plot(x, median, color=COLORS["blue"], marker="o", label="subset median")
        ax.axhline(full, color=COLORS["dark"], linestyle="--", label="full 50-member estimate")
        ax.axhspan(-5, 5, color="#D9F0D3", alpha=0.55, zorder=0)
        ax.axhline(0, color=COLORS["dark"], linewidth=0.8)
        ax.set_xticks([5, 10, 20, 30, 40, 50])
        ax.set_xlabel("members retained from the same 50-member pool")
        ax.set_title(METRIC_LABELS[metric])
        ax.grid(True)
        if metric == "ensemble_mean_l1_bins_500":
            ax.set_ylim(bottom=0)
            ax.set_ylabel("ensemble-mean error / %")
        else:
            ax.set_ylabel("ensemble-mean relative bias / %")
    axes[0].legend(loc="upper right")
    add_panel_label(axes[0], "a")
    add_panel_label(axes[1], "b")
    add_panel_label(axes[2], "c")
    fig.suptitle(
        r"What ensemble size changes at the selected resolution ($N_{SD}=131{,}072$, t = 60 min)",
        fontsize=15,
        fontweight="bold",
        color=COLORS["dark"],
    )
    source_footer(
        fig,
        "Random subsets without replacement from the completed 50-member pool (2,000 draws; n=5 added post hoc for explanation). Descriptive, not a new formal decision.",
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.93])
    save_figure(fig, output)


def worst_bound_by_resolution(analytical: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (resolution, metric), values in analytical.groupby(["max_superdroplets", "metric"]):
        if metric == "ensemble_mean_l1_bins_500":
            bound = float(values["95ci_high"].max())
        elif metric in {
            "golovin_relative_error_radius_moment_0_m3",
            "golovin_relative_error_radius_moment_6_um6_m3",
        }:
            bound = float(np.maximum(np.abs(values["95ci_low"]), np.abs(values["95ci_high"])).max())
        else:
            continue
        rows.append({"max_superdroplets": int(resolution), "metric": metric, "worst_bound": bound})
    return pd.DataFrame(rows)


def plot_accuracy_cost(
    analytical: pd.DataFrame, inventory: dict[str, object], output: Path
) -> None:
    worst = worst_bound_by_resolution(analytical)
    resolutions = sorted(worst["max_superdroplets"].unique())
    durations: dict[int, list[float]] = defaultdict(list)
    for member in inventory["members"]:
        durations[int(member["max_superdroplets"])].append(float(member["job_wall_seconds"]))
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.6))
    palette = [COLORS["blue"], COLORS["orange"], COLORS["green"]]
    for metric, color in zip(METRIC_LABELS, palette):
        values = worst[worst["metric"] == metric].sort_values("max_superdroplets")
        work = values["max_superdroplets"].to_numpy()
        axes[0].plot(
            work,
            100 * values["worst_bound"].to_numpy(),
            marker="o",
            color=color,
            label=METRIC_LABELS[metric],
        )
    axes[0].axhspan(0, 5, color="#D9F0D3", alpha=0.70, zorder=0)
    axes[0].axvline(131_072, color=COLORS["gold"], linestyle="--")
    axes[0].set_xscale("log", base=2)
    axes[0].set_yscale("log")
    axes[0].set_xticks(resolutions)
    axes[0].xaxis.set_major_formatter(FuncFormatter(format_resolution))
    axes[0].set_xlabel(r"$N_{SD}$ (50 members fixed; proportional-work axis)")
    axes[0].set_ylabel("worst all-time 95% error bound / %")
    axes[0].grid(True, which="both")
    axes[0].legend()
    axes[0].set_title("Accuracy gained as represented particles increase")
    medians = np.asarray([np.median(durations[value]) for value in resolutions])
    lows = np.asarray([np.quantile(durations[value], 0.25) for value in resolutions])
    highs = np.asarray([np.quantile(durations[value], 0.75) for value in resolutions])
    axes[1].fill_between(resolutions, lows, highs, color=COLORS["sky"], alpha=0.30, label="member IQR")
    axes[1].plot(resolutions, medians, color=COLORS["blue"], marker="o", label="member median")
    axes[1].axvline(131_072, color=COLORS["gold"], linestyle="--", label="selected resolution")
    axes[1].set_xscale("log", base=2)
    axes[1].set_yscale("log")
    axes[1].xaxis.set_major_formatter(FuncFormatter(format_resolution))
    axes[1].set_xlabel(r"$N_{SD}$")
    axes[1].set_ylabel("archived operational wall time / s per member")
    axes[1].grid(True, which="both")
    axes[1].legend()
    axes[1].set_title("Observed operational cost (not a benchmark)")
    add_panel_label(axes[0], "a")
    add_panel_label(axes[1], "b")
    fig.suptitle(
        "Accuracy–cost trade-off in the fixed-50 experiment",
        fontsize=15,
        fontweight="bold",
        color=COLORS["dark"],
    )
    source_footer(
        fig,
        "Left: hardware-independent work proxy. Right: archived per-member wall times include operational variability and must not be interpreted as a CLEO scaling benchmark.",
    )
    fig.tight_layout(rect=[0, 0.05, 1, 0.92])
    save_figure(fig, output)


def plot_initialization_fidelity(
    archives: dict[tuple[int, int], dict[str, np.ndarray]], diagnostics: pd.DataFrame, output: Path
) -> None:
    resolutions = [4096, 131_072, 1_048_576]
    colors = [COLORS["orange"], COLORS["blue"], COLORS["green"]]
    fig = plt.figure(figsize=(12.8, 7.2))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.05, 0.95], width_ratios=[1.35, 1])
    ax_distribution = fig.add_subplot(grid[0, :])
    ax_residual = fig.add_subplot(grid[1, 0])
    ax_moments = fig.add_subplot(grid[1, 1])
    analytical = None
    edges = None
    for resolution, color in zip(resolutions, colors):
        archive = archives[(resolution, 0)]
        idx = nominal_time_index(archive, 0.0)
        numerical = archive["numerical_gm3_per_ln_radius_500"][idx]
        if analytical is None:
            analytical = archive["analytical_gm3_per_ln_radius_500"][idx]
            edges = archive["edges_um_500"]
        centers = bin_centers(edges)
        ax_distribution.plot(centers, numerical, color=color, label=format_resolution(resolution))
        total_mass = np.sum(analytical * np.diff(np.log(edges)))
        ax_residual.plot(
            centers,
            100 * (numerical - analytical) / total_mass,
            color=color,
            label=format_resolution(resolution),
        )
    ax_distribution.plot(
        centers, analytical, color=COLORS["dark"], linestyle="--", linewidth=2.3, label="target"
    )
    ax_distribution.set_xscale("log")
    ax_distribution.set_xlim(1, 100)
    ax_distribution.set_ylabel(r"mass density / g m$^{-3}$ per unit ln $r$")
    ax_distribution.set_xlabel(r"initial radius $r$ / $\mu$m")
    ax_distribution.set_title("Frozen controlled initialization versus its analytical target")
    ax_distribution.grid(True)
    ax_distribution.legend(title=r"$N_{SD}$", ncol=4)
    ax_residual.axhline(0, color=COLORS["dark"], linewidth=0.8)
    ax_residual.set_xscale("log")
    ax_residual.set_xlim(1, 100)
    ax_residual.set_xlabel(r"initial radius $r$ / $\mu$m")
    ax_residual.set_ylabel("signed bin difference / % of total mass")
    ax_residual.set_title("Where discretization leaves small binwise residuals")
    ax_residual.grid(True)
    init = diagnostics[np.isclose(diagnostics["time_s"], 0.0, atol=1e-3)]
    x = np.arange(len(resolutions))
    width = 0.23
    moment_colors = [COLORS["blue"], COLORS["orange"], COLORS["green"]]
    for offset, (column, short), color in zip([-width, 0, width], MOMENT_COLUMNS.items(), moment_colors):
        values = []
        for resolution in resolutions:
            selected = init[init["max_superdroplets"] == resolution][column]
            values.append(100 * float(selected.iloc[0]))
        ax_moments.bar(x + offset, values, width=width, label=short, color=color)
    ax_moments.axhline(0, color=COLORS["dark"], linewidth=0.8)
    ax_moments.set_xticks(x, [format_resolution(value) for value in resolutions])
    ax_moments.set_xlabel(r"$N_{SD}$")
    ax_moments.set_ylabel("initial relative moment error / %")
    ax_moments.set_title("Matched bulk moments remain essentially exact")
    ax_moments.grid(True, axis="y")
    ax_moments.legend(ncol=3)
    add_panel_label(ax_distribution, "a")
    add_panel_label(ax_residual, "b")
    add_panel_label(ax_moments, "c")
    fig.suptitle(
        "Initialization fidelity before any collision is enacted",
        fontsize=15,
        fontweight="bold",
        color=COLORS["dark"],
    )
    source_footer(
        fig,
        "The initialization is deterministic within each resolution and reused across its 50 collision members; M0 and M3 are constrained, while M6 is audited.",
    )
    fig.tight_layout(rect=[0, 0.04, 1, 0.94])
    save_figure(fig, output)


def plot_integrity_qa(diagnostics: pd.DataFrame, output: Path) -> None:
    resolutions = sorted(int(value) for value in diagnostics["max_superdroplets"].unique())
    max_drift, p95_drift, max_radius, max_range = [], [], [], []
    for resolution in resolutions:
        values = diagnostics[diagnostics["max_superdroplets"] == resolution]
        drift = np.abs(values["relative_liquid_mass_drift"].to_numpy())
        max_drift.append(float(np.max(drift)))
        p95_drift.append(float(np.quantile(drift, 0.95)))
        max_radius.append(float(values["max_radius_um"].max()))
        outside = values["fixed_bin_mass_below_range_fraction"] + values[
            "fixed_bin_mass_above_range_fraction"
        ]
        max_range.append(float(outside.max()))
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.2))
    axes[0].plot(resolutions, max_drift, color=COLORS["red"], marker="o", label="maximum")
    axes[0].plot(resolutions, p95_drift, color=COLORS["blue"], marker="s", label="95th percentile")
    axes[0].axhline(1e-7, color=COLORS["green"], linestyle="--", label=r"registered limit $10^{-7}$")
    axes[0].set_yscale("log")
    axes[0].set_xscale("log", base=2)
    axes[0].xaxis.set_major_formatter(FuncFormatter(format_resolution))
    axes[0].set_xlabel(r"$N_{SD}$")
    axes[0].set_ylabel("absolute relative liquid-mass drift")
    axes[0].set_title("Mass conservation")
    axes[0].grid(True, which="both")
    axes[0].legend()
    axes[1].plot(resolutions, max_radius, color=COLORS["blue"], marker="o")
    axes[1].axhline(5000, color=COLORS["green"], linestyle="--", label=r"diagnostic ceiling 5000 $\mu$m")
    axes[1].set_xscale("log", base=2)
    axes[1].xaxis.set_major_formatter(FuncFormatter(format_resolution))
    axes[1].set_xlabel(r"$N_{SD}$")
    axes[1].set_ylabel(r"largest recorded radius / $\mu$m")
    axes[1].set_title("Radius-range coverage")
    axes[1].grid(True)
    axes[1].legend()
    axes[2].plot(resolutions, max_range, color=COLORS["blue"], marker="o")
    axes[2].axhline(1e-6, color=COLORS["green"], linestyle="--", label=r"registered limit $10^{-6}$")
    axes[2].set_xscale("log", base=2)
    axes[2].xaxis.set_major_formatter(FuncFormatter(format_resolution))
    axes[2].set_ylim(-0.05e-6, 1.1e-6)
    axes[2].set_xlabel(r"$N_{SD}$")
    axes[2].set_ylabel("maximum mass fraction outside [1, 5000] μm")
    axes[2].set_title("No mass escapes the diagnostic range")
    axes[2].grid(True)
    axes[2].legend()
    add_panel_label(axes[0], "a")
    add_panel_label(axes[1], "b")
    add_panel_label(axes[2], "c")
    fig.suptitle(
        "Numerical-integrity checks across all 450 members and seven output times",
        fontsize=15,
        fontweight="bold",
        color=COLORS["dark"],
    )
    source_footer(fig, "Quality-control gates are prerequisites: passing them does not by itself establish convergence.")
    fig.tight_layout(rect=[0, 0.05, 1, 0.92])
    save_figure(fig, output)


def plot_member_variability(diagnostics: pd.DataFrame, output: Path) -> None:
    resolutions = sorted(
        int(value) for value in diagnostics["max_superdroplets"].unique()
    )
    if len(resolutions) != 9:
        raise ValueError(
            f"expected nine fixed-50 resolutions, found {len(resolutions)}"
        )
    selected = diagnostics[
        diagnostics["max_superdroplets"].isin(resolutions)
        & np.isclose(diagnostics["time_s"], 3600.0, atol=1e-3)
    ]
    member_counts = selected.groupby("max_superdroplets")["member_index"].nunique()
    if set(member_counts.index.astype(int)) != set(resolutions) or not np.all(
        member_counts.to_numpy() == 50
    ):
        raise ValueError("expected 50 independent members at every resolution")
    columns = [
        "golovin_fixed_bin_l1_relative_bins_500",
        "golovin_relative_error_radius_moment_0_m3",
        "golovin_relative_error_radius_moment_6_um6_m3",
    ]
    titles = [r"member-level DSD $L_1$ mismatch", r"member $M_0$ bias", r"member $M_6$ bias"]
    positions = np.arange(len(resolutions))
    fig, axes = plt.subplots(1, 3, figsize=(15.8, 4.9))
    for ax, column, title in zip(axes, columns, titles):
        data = [
            100
            * selected[selected["max_superdroplets"] == resolution][column].to_numpy(dtype=float)
            for resolution in resolutions
        ]
        parts = ax.violinplot(
            data,
            positions=positions,
            widths=0.82,
            showmeans=False,
            showextrema=False,
        )
        for body in parts["bodies"]:
            body.set_facecolor(COLORS["sky"])
            body.set_edgecolor(COLORS["blue"])
            body.set_alpha(0.65)
        ax.boxplot(
            data,
            positions=positions,
            widths=0.14,
            showfliers=False,
            patch_artist=True,
            boxprops=dict(facecolor="white", edgecolor=COLORS["dark"]),
            medianprops=dict(color=COLORS["red"], linewidth=1.7),
            whiskerprops=dict(color=COLORS["dark"]),
            capprops=dict(color=COLORS["dark"]),
        )
        ax.axhline(0, color=COLORS["dark"], linewidth=0.8)
        ax.set_xticks(
            positions,
            [format_resolution(value) for value in resolutions],
            rotation=38,
            ha="right",
        )
        ax.set_xlim(-0.65, len(resolutions) - 0.35)
        ax.set_xlabel(r"$N_{SD}$")
        ax.set_ylabel("member diagnostic / %")
        ax.set_title(title)
        ax.grid(True, axis="y")
    add_panel_label(axes[0], "a")
    add_panel_label(axes[1], "b")
    add_panel_label(axes[2], "c")
    fig.suptitle(
        "Collision-realization variability at 60 minutes",
        fontsize=15,
        fontweight="bold",
        color=COLORS["dark"],
    )
    source_footer(
        fig,
        "All nine tested resolutions are shown; each violin contains 50 independent collision members. Panel a is a member-level diagnostic and is not the formal L1 of the ensemble-mean distribution.",
    )
    fig.tight_layout(rect=[0, 0.06, 1, 0.92])
    save_figure(fig, output)


def plot_bin_sensitivity(
    analytical: pd.DataFrame, adjacent: pd.DataFrame, output: Path
) -> None:
    bin_counts = [250, 500, 1000]
    colors = [COLORS["orange"], COLORS["blue"], COLORS["green"]]
    fig, axes = plt.subplots(1, 2, figsize=(12.8, 4.7))
    for bins, color in zip(bin_counts, colors):
        metric = f"ensemble_mean_l1_bins_{bins}"
        selected = analytical[analytical["metric"] == metric]
        worst = selected.groupby("max_superdroplets")["95ci_high"].max().sort_index()
        axes[0].plot(worst.index, 100 * worst.values, color=color, marker="o", label=f"{bins} bins")
        pairs = adjacent[adjacent["metric"] == metric].copy()
        pairs["worst_edge"] = np.maximum(np.abs(pairs["95ci_low"]), np.abs(pairs["95ci_high"]))
        pair_worst = pairs.groupby("lower_max_superdroplets")["worst_edge"].max().sort_index()
        axes[1].plot(
            pair_worst.index,
            100 * pair_worst.values,
            color=color,
            marker="o",
            label=f"{bins} bins",
        )
    for ax in axes:
        ax.axhspan(0, 5, color="#D9F0D3", alpha=0.70, zorder=0)
        ax.axhline(5, color=COLORS["green"], linestyle="--")
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.xaxis.set_major_formatter(FuncFormatter(format_resolution))
        ax.set_xlabel(r"$N_{SD}$" if ax is axes[0] else r"lower $N_{SD}$ in adjacent pair")
        ax.set_ylabel("worst all-time 95% bound / %")
        ax.grid(True, which="both")
        ax.legend()
    axes[0].set_title("Analytical DSD accuracy")
    axes[1].set_title("Adjacent-resolution DSD equivalence")
    add_panel_label(axes[0], "a")
    add_panel_label(axes[1], "b")
    fig.suptitle(
        "Sensitivity of the distribution conclusion to 250, 500, or 1000 fixed log-radius bins",
        fontsize=14,
        fontweight="bold",
        color=COLORS["dark"],
    )
    source_footer(
        fig,
        "The 500-bin statistic is primary. The 250- and 1000-bin results diagnose estimator sensitivity and do not retroactively redefine the selected resolution.",
    )
    fig.tight_layout(rect=[0, 0.06, 1, 0.91])
    save_figure(fig, output)


def write_manifest(
    output_directory: Path,
    input_paths: list[tuple[str, Path]],
    outputs: list[Path],
) -> None:
    manifest = {
        "schema": "golovin_explanatory_figure_manifest_v1",
        "scientific_scope": "analysis-only figures from archived fixed-50 Golovin products",
        "formal_result_unchanged": "131072 SDs with the prospectively fixed 50-member ensembles",
        "inputs": [
            {"path": label, "sha256": sha256_file(path)}
            for label, path in input_paths
            if path.is_file()
        ],
        "outputs": [
            {"path": output.name, "sha256": sha256_file(output)} for output in outputs
        ],
        "notes": [
            "No CLEO model run was performed by this script.",
            "Member-level L1 variability is explicitly separated from the formal ensemble-mean L1 estimand.",
            "The n=5 ensemble-size point is a post-hoc descriptive subset diagnostic and does not alter the registered decision.",
        ],
    }
    (output_directory / "figure_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    set_style()
    args.output_directory.mkdir(parents=True, exist_ok=True)
    diagnostics_path = args.fixed50_analysis / "all_member_time_diagnostics.csv"
    sensitivity_path = args.fixed50_analysis / "ensemble_size_sensitivity.csv"
    inventory_path = args.fixed50_analysis / "model_inventory.json"
    analytical_path = args.fixed50_tables / "analytical_agreement.csv"
    adjacent_path = args.fixed50_tables / "adjacent_resolution_equivalence.csv"
    decision_path = args.fixed50_tables / "resolution_decision.json"
    diagnostics = pd.read_csv(diagnostics_path)
    sensitivity = pd.read_csv(sensitivity_path)
    analytical = pd.read_csv(analytical_path)
    adjacent = pd.read_csv(adjacent_path)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    archives = load_archives(args.selected_npz_root)

    outputs = [
        args.output_directory / "golovin_dsd_evolution_selected.png",
        args.output_directory / "golovin_formal_decision_matrix.png",
        args.output_directory / "golovin_n2n4n_confirmation.png",
        args.output_directory / "golovin_ensemble_size_selected.png",
        args.output_directory / "golovin_accuracy_cost_tradeoff.png",
        args.output_directory / "golovin_initialization_fidelity.png",
        args.output_directory / "golovin_integrity_qa.png",
        args.output_directory / "golovin_member_variability.png",
        args.output_directory / "golovin_bin_sensitivity.png",
    ]
    plot_dsd_evolution(archives, outputs[0])
    plot_decision_matrix(decision, outputs[1])
    plot_confirmation(analytical, outputs[2])
    five_rows = compute_five_member_sensitivity(archives, diagnostics)
    plot_ensemble_stability(sensitivity, five_rows, outputs[3])
    plot_accuracy_cost(analytical, inventory, outputs[4])
    plot_initialization_fidelity(archives, diagnostics, outputs[5])
    plot_integrity_qa(diagnostics, outputs[6])
    plot_member_variability(diagnostics, outputs[7])
    plot_bin_sensitivity(analytical, adjacent, outputs[8])
    write_manifest(
        args.output_directory,
        [
            ("fixed50-analysis/all_member_time_diagnostics.csv", diagnostics_path),
            ("fixed50-analysis/ensemble_size_sensitivity.csv", sensitivity_path),
            ("fixed50-analysis/model_inventory.json", inventory_path),
            ("fixed50-tables/analytical_agreement.csv", analytical_path),
            ("fixed50-tables/adjacent_resolution_equivalence.csv", adjacent_path),
            ("fixed50-tables/resolution_decision.json", decision_path),
            *[
                (
                    "selected-stage0/" + path.relative_to(args.selected_npz_root).as_posix(),
                    path,
                )
                for path in sorted(args.selected_npz_root.rglob("fixed_bin_distributions.npz"))
            ],
        ],
        outputs,
    )
    with (args.output_directory / "figure_index.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["figure", "purpose"])
        writer.writerows(
            [
                [outputs[0].name, "selected-resolution DSD evolution and residuals"],
                [outputs[1].name, "formal five-gate candidate decision matrix"],
                [outputs[2].name, "selected N-2N-4N analytical confirmation over time"],
                [outputs[3].name, "descriptive selected-resolution ensemble-size stability"],
                [outputs[4].name, "accuracy versus work and operational wall time"],
                [outputs[5].name, "controlled initialization fidelity"],
                [outputs[6].name, "mass-conservation and diagnostic-range quality control"],
                [outputs[7].name, "member-level collision-realization variability"],
                [outputs[8].name, "fixed-bin sensitivity of DSD conclusions"],
            ]
        )


if __name__ == "__main__":
    main()
