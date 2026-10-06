#!/usr/bin/env python3
"""Descriptive fixed-20 analysis of compact 2-D constthermo2d aggregates.

The 4096-SD-per-populated-cell cohort is an internal operational comparator,
not physical truth or an independent formal reference.  This script reports
full-20 ensemble-mean agreement and finite-ensemble precision descriptively;
it deliberately makes no convergence selection or rainfall claim.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np


RESOLUTIONS = (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096)
MEMBERS = tuple(range(1, 21))
REFERENCE = 4096
ENSEMBLE_SIZES = (1, 2, 3, 5, 10, 15, 20)
SELECTED_MINUTES = (0, 30, 60, 90, 120)
VIOLIN_MINUTES = (30, 60, 90, 120)
COLORS = plt.cm.viridis(np.linspace(0.03, 0.96, len(RESOLUTIONS)))


def save_figure(fig: plt.Figure, path: Path, *, top: float = .82, bottom: float = .10,
                left: float = .07, right: float = .985, wspace: float = .24,
                hspace: float = .28) -> None:
    """Save with explicit margins reserved for titles, legends, and captions.

    ``tight_layout`` does not reserve enough space for figure-level legends and
    titles in these dense multi-panel diagnostics.  The explicit geometry keeps
    the scientific labels separate from the plot axes at slide/report scale.
    """
    fig.subplots_adjust(top=top, bottom=bottom, left=left, right=right,
                        wspace=wspace, hspace=hspace)
    fig.savefig(path, dpi=240, bbox_inches="tight", pad_inches=.10)
    plt.close(fig)


def symmetric_percent(candidate: np.ndarray, reference: np.ndarray) -> np.ndarray:
    denominator = np.abs(candidate) + np.abs(reference)
    return np.divide(200.0 * np.abs(candidate - reference), denominator,
                     out=np.zeros_like(np.asarray(candidate, dtype=float)), where=denominator > 0)


def normalised_mass_distribution(dsd: np.ndarray, widths: np.ndarray) -> np.ndarray:
    weights = np.asarray(dsd, dtype=float) * widths
    integral = np.sum(weights, axis=-1, keepdims=True)
    return np.divide(weights, integral, out=np.zeros_like(weights), where=integral > 0)


def dsd_tv_percent(candidate: np.ndarray, reference: np.ndarray, widths: np.ndarray) -> np.ndarray:
    cand = normalised_mass_distribution(candidate, widths)
    ref = normalised_mass_distribution(reference, widths)
    return 50.0 * np.sum(np.abs(cand - ref), axis=-1)


def load_cohorts(cache: Path) -> dict[str, np.ndarray]:
    metric_names = (
        "lambda0_m3", "lambda1_um_m3", "lambda2_um2_m3", "lambda3_um3_m3", "lambda6_um6_m3",
        "total_droplet_mass_g_m3", "mass_weighted_terminal_speed_ms", "lower150m_total_droplet_mass_fraction",
        "mass_weighted_r50_um", "mass_weighted_r90_um", "mass_weighted_r99_um", "active_sds",
    )
    values: dict[str, list[np.ndarray]] = {name: [] for name in metric_names}
    values["mass_dsd_250_g_m3"] = []
    values["mass_dsd_500_g_m3"] = []
    values["mass_dsd_1000_g_m3"] = []
    values["number_dsd_500_m3"] = []
    time_reference: np.ndarray | None = None
    edges_reference: dict[int, np.ndarray] = {}
    for ncell in RESOLUTIONS:
        per_member: dict[str, list[np.ndarray]] = {name: [] for name in values}
        for member in MEMBERS:
            path = cache / f"ncell{ncell:04d}" / f"member{member:03d}.npz"
            if not path.is_file():
                raise FileNotFoundError(path)
            with np.load(path) as raw:
                time = np.asarray(raw["time_min"], dtype=float)
                if time_reference is None:
                    time_reference = time
                    for count in (250, 500, 1000):
                        edges_reference[count] = np.asarray(raw[f"radius_edges_{count}_um"], dtype=float)
                elif not np.allclose(time_reference, time, rtol=0.0, atol=1e-8):
                    raise ValueError(f"stored time mismatch: {path}")
                for name in metric_names:
                    per_member[name].append(np.asarray(raw[name], dtype=float))
                for name in ("mass_dsd_250_g_m3", "mass_dsd_500_g_m3", "mass_dsd_1000_g_m3", "number_dsd_500_m3"):
                    per_member[name].append(np.asarray(raw[name], dtype=float))
        for name in values:
            values[name].append(np.stack(per_member[name], axis=0))
    return {**{name: np.stack(rows, axis=0) for name, rows in values.items()},
            "time_min": np.asarray(time_reference),
            "radius_edges_250_um": edges_reference[250], "radius_edges_500_um": edges_reference[500],
            "radius_edges_1000_um": edges_reference[1000]}


def minute_indices(time_min: np.ndarray, requested: tuple[int, ...]) -> list[int]:
    return [int(np.argmin(np.abs(time_min - value))) for value in requested]


def max_postinitial(values: np.ndarray) -> np.ndarray:
    return np.max(values[..., 1:], axis=-1)


def ladder_rows(data: dict[str, np.ndarray]) -> list[dict[str, float | int]]:
    ref_index = RESOLUTIONS.index(REFERENCE)
    ref_metrics = {name: np.mean(data[name][ref_index], axis=0) for name in (
        "lambda0_m3", "lambda2_um2_m3", "lambda3_um3_m3", "lambda6_um6_m3",
        "mass_weighted_terminal_speed_ms", "mass_weighted_r90_um", "total_droplet_mass_g_m3",
    )}
    rows: list[dict[str, float | int]] = []
    for ridx, ncell in enumerate(RESOLUTIONS):
        row: dict[str, float | int] = {"ncell": ncell, "initial_domain_sds": 120 * ncell}
        candidate_dsd = np.mean(data["mass_dsd_500_g_m3"][ridx], axis=0)
        reference_dsd = np.mean(data["mass_dsd_500_g_m3"][ref_index], axis=0)
        widths = np.diff(np.log(data["radius_edges_500_um"]))
        row["max_mass_dsd_tv_500_percent"] = float(max_postinitial(dsd_tv_percent(candidate_dsd, reference_dsd, widths)))
        for name, reference in ref_metrics.items():
            candidate = np.mean(data[name][ridx], axis=0)
            row[f"max_{name}_symmetric_percent"] = float(max_postinitial(symmetric_percent(candidate, reference)))
        for bins in (250, 1000):
            candidate = np.mean(data[f"mass_dsd_{bins}_g_m3"][ridx], axis=0)
            reference = np.mean(data[f"mass_dsd_{bins}_g_m3"][ref_index], axis=0)
            widths = np.diff(np.log(data[f"radius_edges_{bins}_um"]))
            row[f"max_mass_dsd_tv_{bins}_percent"] = float(max_postinitial(dsd_tv_percent(candidate, reference, widths)))
        rows.append(row)
    return rows


def write_rows(rows: list[dict[str, float | int]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_moment_evolution(data: dict[str, np.ndarray], output: Path) -> None:
    specs = (
        ("lambda0_m3", r"$\lambda_0$ (m$^{-3}$)", r"Droplet-number moment $\lambda_0$", True),
        ("lambda2_um2_m3", r"$\lambda_2$ ($\mu$m$^2$ m$^{-3}$)", r"Area-related moment $\lambda_2$", True),
        ("lambda3_um3_m3", r"$\lambda_3$ ($\mu$m$^3$ m$^{-3}$)", r"Volume-related moment $\lambda_3$", True),
        ("lambda6_um6_m3", r"$\lambda_6$ ($\mu$m$^6$ m$^{-3}$)", r"Large-drop-sensitive moment $\lambda_6$", True),
        ("mass_weighted_terminal_speed_ms", "mass-weighted fall speed (m s$^{-1}$)", "Mass-weighted terminal speed", False),
        ("mass_weighted_r90_um", r"mass-weighted $r_{90}$ ($\mu$m)", "Mass-weighted 90th-percentile radius", False),
    )
    fig, axes = plt.subplots(2, 3, figsize=(18, 10.5), sharex=True)
    for ax, (name, ylabel, title, logscale) in zip(axes.flat, specs):
        for ridx, ncell in enumerate(RESOLUTIONS):
            mean = np.mean(data[name][ridx], axis=0)
            ax.plot(data["time_min"], mean, color=COLORS[ridx], lw=1.25, label=f"{ncell:,}")
        if logscale:
            ax.set_yscale("log")
        ax.set(title=title, ylabel=ylabel, xlabel="time (min)")
        ax.grid(True, which="both", alpha=0.2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.suptitle("2-D condensation-collision: full-20 ensemble mean evolution", fontsize=18, weight="bold", y=.985)
    fig.legend(handles, labels, title=r"$N_{cell}$", ncol=7, loc="upper center",
               bbox_to_anchor=(.5, .935), frameon=False, fontsize=8.2, title_fontsize=8.5,
               columnspacing=1.3, handlelength=2.1)
    fig.text(.5, .032, f"Each line is an independent 20-member ensemble mean. The {REFERENCE:,} line is an internal operational comparator, not physical truth.", ha="center", fontsize=10)
    save_figure(fig, output / "01_ensemble_moment_and_physical_evolution.png", top=.80, bottom=.09)


def plot_dsd_evolution(data: dict[str, np.ndarray], output: Path) -> None:
    chosen = (RESOLUTIONS[0], 32, 512, REFERENCE)
    indices = minute_indices(data["time_min"], SELECTED_MINUTES)
    colors = plt.cm.plasma(np.linspace(0.06, 0.93, len(indices)))
    edges = data["radius_edges_500_um"]
    centers = np.sqrt(edges[:-1] * edges[1:])
    fig, axes = plt.subplots(2, 2, figsize=(15.5, 10.8), sharex=True, sharey=True)
    for ax, ncell in zip(axes.flat, chosen):
        ridx = RESOLUTIONS.index(ncell)
        average = np.mean(data["mass_dsd_500_g_m3"][ridx], axis=0)
        positive = average[average > 0]
        floor = max(np.min(positive) * 0.8, 1e-18)
        for color, tidx, minute in zip(colors, indices, SELECTED_MINUTES):
            curve = average[tidx]
            ax.plot(centers, np.where(curve > floor, curve, np.nan), color=color, lw=1.5, label=f"{minute} min")
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_title(fr"$N_{{cell}}={ncell:,}$ ({120*ncell:,} initial SDs)", weight="bold")
        ax.grid(True, which="both", alpha=0.2)
    for ax in axes[:, 0]: ax.set_ylabel(r"total-droplet-mass DSD $dL/d\ln r$ (g m$^{-3}$)")
    for ax in axes[-1, :]: ax.set_xlabel(r"wet radius $r$ ($\mu$m)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.suptitle("Mass-DSD evolution at representative resolution levels", fontsize=18, weight="bold", y=.985)
    fig.legend(handles, labels, title="stored time", ncol=5, loc="upper center",
               bbox_to_anchor=(.5, .935), frameon=False, fontsize=9, title_fontsize=9)
    fig.text(.5, .032, "Fixed 500-bin radius representation; each curve is a 20-member ensemble mean. This figure shows evolution, not a convergence decision.", ha="center", fontsize=10)
    save_figure(fig, output / "02_mass_dsd_evolution_representative_resolutions.png", top=.82, bottom=.095, left=.075, right=.985, wspace=.16, hspace=.25)


def plot_reference_ladder(rows: list[dict[str, float | int]], output: Path) -> None:
    specs = (
        ("max_mass_dsd_tv_500_percent", "mass-DSD total variation (%)", "500-bin mass-DSD total variation", "#087e8b"),
        ("max_lambda0_m3_symmetric_percent", r"$\lambda_0$ symmetric difference (%)", r"$\lambda_0$", "#a16207"),
        ("max_lambda2_um2_m3_symmetric_percent", r"$\lambda_2$ symmetric difference (%)", r"$\lambda_2$", "#267c8c"),
        ("max_lambda3_um3_m3_symmetric_percent", r"$\lambda_3$ symmetric difference (%)", r"$\lambda_3$", "#458b5f"),
        ("max_lambda6_um6_m3_symmetric_percent", r"$\lambda_6$ symmetric difference (%)", r"$\lambda_6$", "#6d3fa0"),
        ("max_mass_weighted_terminal_speed_ms_symmetric_percent", "terminal-speed symmetric difference (%)", "Mass-weighted terminal speed", "#214a77"),
    )
    x = np.array([int(row["ncell"]) for row in rows[:-1]])
    fig, axes = plt.subplots(2, 3, figsize=(18, 10), sharex=True)
    for ax, (key, ylabel, title, colour) in zip(axes.flat, specs):
        y = np.array([float(row[key]) for row in rows[:-1]])
        ax.plot(x, y, marker="o", ms=4.8, lw=1.8, color=colour)
        ax.set_xscale("log", base=2)
        ax.set(title=title, ylabel=ylabel, xlabel=r"SDs per populated grid box, $N_{cell}$")
        ax.grid(True, which="both", alpha=0.2)
    fig.suptitle(f"Descriptive full-20 agreement with the {REFERENCE:,} internal comparator", fontsize=18, weight="bold", y=.985)
    fig.text(.5, .03, f"Value: maximum over post-initial stored times of the difference between full 20-member means. {REFERENCE:,} is omitted because self-comparison is identically zero.", ha="center", fontsize=10)
    save_figure(fig, output / "03_descriptive_full20_reference_ladder.png", top=.90, bottom=.10)


def member_deviations(data: dict[str, np.ndarray], metric: str, tidx: int) -> np.ndarray:
    refidx = RESOLUTIONS.index(REFERENCE)
    ref = np.mean(data[metric][refidx], axis=0)[tidx]
    return symmetric_percent(data[metric][:, :, tidx], ref)


def plot_member_violin(data: dict[str, np.ndarray], output: Path) -> None:
    metrics = (
        ("lambda0_m3", r"$\lambda_0$ member difference (%)"),
        ("lambda2_um2_m3", r"$\lambda_2$ member difference (%)"),
        ("lambda6_um6_m3", r"$\lambda_6$ member difference (%)"),
        ("mass_weighted_terminal_speed_ms", "terminal-speed member difference (%)"),
    )
    indices = minute_indices(data["time_min"], VIOLIN_MINUTES)

    # A single violin per resolution is intentionally used here. The earlier
    # version overlaid four times beside each other, which obscured both the
    # member spread and the resolution ordering. One familiar long-style
    # figure is written for every stored diagnostic time instead.
    for tidx, minute in zip(indices, VIOLIN_MINUTES):
        fig, axes = plt.subplots(2, 2, figsize=(14.8, 9.2), sharex=True)
        positions = np.arange(1, len(RESOLUTIONS) + 1)
        for ax, (metric, ylabel) in zip(axes.flat, metrics):
            vals = member_deviations(data, metric, tidx)
            shapes = ax.violinplot(
                [vals[ridx] for ridx in range(len(RESOLUTIONS))],
                positions=positions,
                widths=0.78,
                showmeans=False,
                showmedians=False,
                showextrema=True,
            )
            for body in shapes["bodies"]:
                body.set_facecolor("#a8d5f0")
                body.set_edgecolor("#1e5f91")
                body.set_linewidth(0.9)
                body.set_alpha(0.88)
            for name in ("cbars", "cmins", "cmaxes"):
                shapes[name].set_color("#173b63")
                shapes[name].set_linewidth(1.0)

            # The inset box carries the interquartile range; its red rule is
            # the member median. This is the same visual vocabulary as the
            # preceding Long-kernel variability figure.
            box = ax.boxplot(
                [vals[ridx] for ridx in range(len(RESOLUTIONS))],
                positions=positions,
                widths=0.24,
                patch_artist=True,
                showfliers=False,
                medianprops={"color": "#b44646", "linewidth": 1.35},
            )
            for patch in box["boxes"]:
                patch.set_facecolor("white")
                patch.set_edgecolor("#173b63")
                patch.set_linewidth(0.95)
            for name in ("whiskers", "caps"):
                for item in box[name]:
                    item.set_color("#173b63")
                    item.set_linewidth(0.9)
            ax.set_title(ylabel.replace(" member difference (%)", ""), fontsize=11, weight="bold", pad=8)
            ax.set_ylabel(ylabel)
            ax.grid(True, axis="y", alpha=0.20)
            ax.set_xticks(positions, [str(n) for n in RESOLUTIONS], rotation=42, ha="right", fontsize=8.3)
            ax.set_xlabel(r"SDs per populated grid box, $N_{cell}$")

        fig.suptitle(
            f"Collision-realization variability at {minute} min: member deviations from the full-20 {REFERENCE:,} comparator",
            fontsize=16,
            weight="bold",
            y=.975,
        )
        fig.text(
            .5,
            .035,
            "Each violin contains the 20 independently seeded members at one resolution. "
            "The white box is the interquartile range and the red rule is the member median. "
            "These are descriptive member spreads, not bootstrap confidence intervals; "
            f"the {REFERENCE:,} self-comparison is zero by construction.",
            ha="center",
            fontsize=9.4,
        )
        save_figure(
            fig,
            output / f"04_member_violin_diagnostics_{minute:03d}min_longstyle.png",
            top=.90,
            bottom=.12,
            left=.075,
            right=.985,
            wspace=.20,
            hspace=.34,
        )

    # Comparative small multiples retain the clean single-violin convention
    # while making the four stored times directly comparable. Every column
    # uses one fixed vertical scale across its four time rows.
    all_values = {
        metric: [member_deviations(data, metric, tidx) for tidx in indices]
        for metric, _ in metrics
    }
    column_upper = {
        metric: 1.06 * max(float(np.max(values)) for values in time_values)
        for metric, time_values in all_values.items()
    }
    fig, axes = plt.subplots(len(VIOLIN_MINUTES), len(metrics), figsize=(22.0, 15.8), sharex=True)
    positions = np.arange(1, len(RESOLUTIONS) + 1)
    for row, (minute, tidx) in enumerate(zip(VIOLIN_MINUTES, indices)):
        for col, (metric, ylabel) in enumerate(metrics):
            ax = axes[row, col]
            vals = member_deviations(data, metric, tidx)
            shapes = ax.violinplot(
                [vals[ridx] for ridx in range(len(RESOLUTIONS))],
                positions=positions,
                widths=0.78,
                showmeans=False,
                showmedians=False,
                showextrema=True,
            )
            for body in shapes["bodies"]:
                body.set_facecolor("#a8d5f0")
                body.set_edgecolor("#1e5f91")
                body.set_linewidth(0.8)
                body.set_alpha(0.88)
            for name in ("cbars", "cmins", "cmaxes"):
                shapes[name].set_color("#173b63")
                shapes[name].set_linewidth(0.85)
            box = ax.boxplot(
                [vals[ridx] for ridx in range(len(RESOLUTIONS))],
                positions=positions,
                widths=0.24,
                patch_artist=True,
                showfliers=False,
                medianprops={"color": "#b44646", "linewidth": 1.25},
            )
            for patch in box["boxes"]:
                patch.set_facecolor("white")
                patch.set_edgecolor("#173b63")
                patch.set_linewidth(0.85)
            for name in ("whiskers", "caps"):
                for item in box[name]:
                    item.set_color("#173b63")
                    item.set_linewidth(0.8)
            ax.set_ylim(0.0, column_upper[metric])
            ax.grid(True, axis="y", alpha=0.20)
            if row == 0:
                ax.set_title(ylabel.replace(" member difference (%)", ""), fontsize=12.5, weight="bold", pad=10)
            if col == 0:
                ax.set_ylabel("member difference (%)", fontsize=9.5)
                ax.text(-0.25, 0.50, f"{minute} min", transform=ax.transAxes,
                        rotation=90, ha="center", va="center", fontsize=12.5, weight="bold", color="#173b63")
            else:
                ax.set_ylabel("")
            if row == len(VIOLIN_MINUTES) - 1:
                ax.set_xticks(positions, [str(n) for n in RESOLUTIONS], rotation=42, ha="right", fontsize=7.5)
                ax.set_xlabel(r"$N_{cell}$", fontsize=10)
            else:
                ax.tick_params(axis="x", labelbottom=False)

    fig.suptitle(
        f"Member-level collision-realization variability through time: full-20 {REFERENCE:,} comparator",
        fontsize=18,
        weight="bold",
        y=.975,
    )
    fig.text(
        .5,
        .028,
        "Read down a column to compare 30, 60, 90, and 120 min on the same diagnostic scale. "
        "Each violin contains 20 independently seeded members at one resolution; the white box is the interquartile range and the red rule is the member median. "
        "These are descriptive member spreads, not bootstrap confidence intervals.",
        ha="center",
        fontsize=10.0,
    )
    save_figure(
        fig,
        output / "04_member_violin_diagnostics_multitime_longstyle.png",
        top=.92,
        bottom=.09,
        left=.095,
        right=.985,
        wspace=.20,
        hspace=.24,
    )


def subset_surface(data: dict[str, np.ndarray], output: Path, rng: np.random.Generator) -> list[dict[str, float | int | str]]:
    refidx = RESOLUTIONS.index(REFERENCE)
    ref_dsd = np.mean(data["mass_dsd_500_g_m3"][refidx], axis=0)
    ref_l0 = np.mean(data["lambda0_m3"][refidx], axis=0)
    ref_l6 = np.mean(data["lambda6_um6_m3"][refidx], axis=0)
    widths = np.diff(np.log(data["radius_edges_500_um"]))
    metrics = ("mass_dsd_tv_500_percent", "lambda0_symmetric_percent", "lambda6_symmetric_percent")
    rows: list[dict[str, float | int | str]] = []
    for ridx, ncell in enumerate(RESOLUTIONS):
        for k in ENSEMBLE_SIZES:
            values = {metric: [] for metric in metrics}
            draws = 1 if k == 20 else 200
            for _ in range(draws):
                choose = np.arange(20) if k == 20 else rng.choice(20, size=k, replace=False)
                dsd = np.mean(data["mass_dsd_500_g_m3"][ridx, choose], axis=0)
                l0 = np.mean(data["lambda0_m3"][ridx, choose], axis=0)
                l6 = np.mean(data["lambda6_um6_m3"][ridx, choose], axis=0)
                values["mass_dsd_tv_500_percent"].append(float(max_postinitial(dsd_tv_percent(dsd, ref_dsd, widths))))
                values["lambda0_symmetric_percent"].append(float(max_postinitial(symmetric_percent(l0, ref_l0))))
                values["lambda6_symmetric_percent"].append(float(max_postinitial(symmetric_percent(l6, ref_l6))))
            for metric in metrics:
                rows.append({"ncell": ncell, "ensemble_size": k, "metric": metric,
                             "median_percent": float(np.median(values[metric])), "draws": draws})
    fig, axes = plt.subplots(1, 3, figsize=(19, 7.2), sharey=True)
    titles = ("500-bin mass-DSD TV", r"$\lambda_0$ symmetric difference", r"$\lambda_6$ symmetric difference")
    for ax, metric, title in zip(axes, metrics, titles):
        matrix = np.array([[next(float(row["median_percent"]) for row in rows if row["ncell"] == n and row["ensemble_size"] == k and row["metric"] == metric)
                            for k in ENSEMBLE_SIZES] for n in RESOLUTIONS])
        masked = np.ma.masked_less_equal(matrix, 0.0)
        image = ax.pcolormesh(np.arange(len(ENSEMBLE_SIZES)+1), np.arange(len(RESOLUTIONS)+1), masked,
                              cmap="viridis", norm=LogNorm(vmin=max(masked.min(), 0.01), vmax=max(masked.max(), 0.02)), shading="auto")
        ax.set_xticks(np.arange(len(ENSEMBLE_SIZES))+0.5, [str(k) for k in ENSEMBLE_SIZES])
        ax.set_yticks(np.arange(len(RESOLUTIONS))+0.5, [f"{n:,}" for n in RESOLUTIONS])
        ax.set(title=title, xlabel="ensemble size, k members")
        if ax is axes[0]: ax.set_ylabel(r"SDs per populated grid box, $N_{cell}$")
        fig.colorbar(image, ax=ax, label="median all-time deviation (%)")
    fig.suptitle("Resolution and ensemble size jointly control internal-comparator deviation", fontsize=18, weight="bold", y=.985)
    fig.text(.5, .025, f"Each cell is the median across up to 200 without-replacement candidate subsets, compared with the fixed full-20 {REFERENCE:,} ensemble mean. Descriptive precision map only; not a bootstrap selection gate.", ha="center", fontsize=10)
    save_figure(fig, output / "05_resolution_ensemble_precision_surface.png", top=.90, bottom=.11, left=.065, right=.98, wspace=.30)
    return rows


def main() -> None:
    global RESOLUTIONS, REFERENCE, COLORS
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--resolutions", nargs="+", type=int, default=list(RESOLUTIONS),
                        help="Ordered SD-per-populated-cell ladder; default preserves the original v1 ladder.")
    parser.add_argument("--reference", type=int, default=REFERENCE,
                        help="Highest internal comparator within --resolutions; default preserves v1.")
    args = parser.parse_args()
    RESOLUTIONS = tuple(args.resolutions)
    REFERENCE = args.reference
    if REFERENCE not in RESOLUTIONS:
        raise ValueError("--reference must be present in --resolutions")
    if tuple(sorted(set(RESOLUTIONS))) != RESOLUTIONS:
        raise ValueError("--resolutions must be unique and strictly ascending")
    COLORS = plt.cm.viridis(np.linspace(0.03, 0.96, len(RESOLUTIONS)))
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite output: {args.output}")
    args.output.mkdir(parents=True)
    data = load_cohorts(args.cache)
    rows = ladder_rows(data)
    write_rows(rows, args.output / "descriptive_full20_reference_ladder.csv")
    surface_rows = subset_surface(data, args.output, np.random.default_rng(20260925))
    write_rows(surface_rows, args.output / "resolution_ensemble_precision_surface.csv")
    plot_moment_evolution(data, args.output)
    plot_dsd_evolution(data, args.output)
    plot_reference_ladder(rows, args.output)
    plot_member_violin(data, args.output)
    metadata = {
        "status": "descriptive_fixed20_internal_comparator_analysis_no_convergence_selection",
        "resolutions_ncell": list(RESOLUTIONS), "members_per_resolution": 20,
        "internal_comparator_ncell": REFERENCE,
        "dsd_bin_sensitivity_available": [250, 500, 1000],
        "surface_method": f"without-replacement candidate subsets compared with fixed full-20 {REFERENCE} ensemble mean",
        "high_resolution_protocol_note": (
            "When reference=8192, that cohort uses the separately audited 4 nm to 2 micrometre "
            "initial-radius support correction needed to avoid zero multiplicities. It trims an analytically "
            "estimated 0.000052 percent of initial number and 0.00205 percent of initial mass; it remains "
            "an internal support-corrected comparator, not identical-protocol numerical truth."
        ) if REFERENCE == 8192 else None,
    }
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
