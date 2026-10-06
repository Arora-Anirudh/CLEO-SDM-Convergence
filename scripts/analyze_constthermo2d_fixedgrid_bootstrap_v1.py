#!/usr/bin/env python3
"""Bootstrap uncertainty and adjacent-resolution stability for 2-D fixed-20 data.

This is deliberately a *precision analysis*, not a convergence selector.  It
quantifies the sampling uncertainty of the 20-member means for high-resolution
comparisons, while retaining the distinction between an internal highest-
resolution comparator (4096 SDs per populated cell) and an independent
numerical reference that has not yet been generated.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import analyze_constthermo2d_fixedgrid_production_descriptive_v1 as descriptive
from analyze_constthermo2d_fixedgrid_production_descriptive_v1 import (
    dsd_tv_percent, load_cohorts, max_postinitial, symmetric_percent,
)


MEMBERS = 20
NBOOT = 2000
# These transitions resolve the part of the ladder at which the descriptive
# deviations become small enough to be scientifically interesting.  Lower
# resolutions are already plainly separated in the descriptive ladder.
HIGH_RESOLUTION_TRANSITIONS = ((256, 512), (512, 1024), (1024, 2048), (2048, 4096))
INTERNAL_REFERENCE_CANDIDATES = (512, 1024, 2048)
SCALAR_METRICS = (
    ("lambda0_m3", r"$\lambda_0$"),
    ("lambda2_um2_m3", r"$\lambda_2$"),
    ("lambda3_um3_m3", r"$\lambda_3$"),
    ("lambda6_um6_m3", r"$\lambda_6$"),
    ("mass_weighted_terminal_speed_ms", "mass-weighted terminal speed"),
    ("mass_weighted_r90_um", r"mass-weighted $r_{90}$"),
)


def bootstrap_indices(rng: np.random.Generator, draws: int) -> np.ndarray:
    return rng.integers(0, MEMBERS, size=(draws, MEMBERS), endpoint=False)


def scalar_bootstrap(candidate: np.ndarray, reference: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    """All-time max symmetric difference: point, median, one-sided 95% bound."""
    point = float(max_postinitial(symmetric_percent(candidate.mean(axis=0), reference.mean(axis=0))))
    ci = bootstrap_indices(rng, NBOOT)
    ri = bootstrap_indices(rng, NBOOT)
    # Indexing produces (bootstrap, member, time), then each resample mean.
    cmean = candidate[ci].mean(axis=1)
    rmean = reference[ri].mean(axis=1)
    statistic = np.max(symmetric_percent(cmean[:, 1:], rmean[:, 1:]), axis=1)
    return point, float(np.quantile(statistic, 0.5)), float(np.quantile(statistic, 0.95))


def dsd_bootstrap(candidate: np.ndarray, reference: np.ndarray, widths: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    """All-time max DSD-TV bootstrap, evaluated in small batches to limit RAM."""
    point = float(max_postinitial(dsd_tv_percent(candidate.mean(axis=0), reference.mean(axis=0), widths)))
    values: list[np.ndarray] = []
    batch = 25
    for _ in range(0, NBOOT, batch):
        count = min(batch, NBOOT - len(values) * batch)
        ci = bootstrap_indices(rng, count)
        ri = bootstrap_indices(rng, count)
        cmean = candidate[ci].mean(axis=1)
        rmean = reference[ri].mean(axis=1)
        values.append(np.max(dsd_tv_percent(cmean[:, 1:], rmean[:, 1:], widths), axis=1))
    statistic = np.concatenate(values)
    return point, float(np.quantile(statistic, 0.5)), float(np.quantile(statistic, 0.95))


def evaluate_pair(data: dict[str, np.ndarray], nleft: int, nright: int, comparison: str, rng: np.random.Generator) -> list[dict[str, float | int | str]]:
    left = descriptive.RESOLUTIONS.index(nleft)
    right = descriptive.RESOLUTIONS.index(nright)
    rows: list[dict[str, float | int | str]] = []
    widths = np.diff(np.log(data["radius_edges_500_um"]))
    point, median, upper = dsd_bootstrap(data["mass_dsd_500_g_m3"][left], data["mass_dsd_500_g_m3"][right], widths, rng)
    rows.append({"comparison": comparison, "left_ncell": nleft, "right_ncell": nright,
                 "metric": "mass_dsd_tv_500", "point_percent": point, "bootstrap_median_percent": median,
                 "bootstrap_upper95_percent": upper, "bootstrap_replicates": NBOOT})
    for name, label in SCALAR_METRICS:
        point, median, upper = scalar_bootstrap(data[name][left], data[name][right], rng)
        rows.append({"comparison": comparison, "left_ncell": nleft, "right_ncell": nright,
                     "metric": name, "point_percent": point, "bootstrap_median_percent": median,
                     "bootstrap_upper95_percent": upper, "bootstrap_replicates": NBOOT})
    return rows


def dsd_bin_points(data: dict[str, np.ndarray], nleft: int, nright: int) -> list[dict[str, float | int]]:
    left, right = descriptive.RESOLUTIONS.index(nleft), descriptive.RESOLUTIONS.index(nright)
    out = []
    for bins in (250, 500, 1000):
        candidate = data[f"mass_dsd_{bins}_g_m3"][left].mean(axis=0)
        reference = data[f"mass_dsd_{bins}_g_m3"][right].mean(axis=0)
        widths = np.diff(np.log(data[f"radius_edges_{bins}_um"]))
        out.append({"left_ncell": nleft, "right_ncell": nright, "bins": bins,
                    "alltime_max_tv_percent": float(max_postinitial(dsd_tv_percent(candidate, reference, widths)))})
    return out


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def plot_bootstrap_bounds(rows: list[dict], output: Path) -> None:
    plot_metrics = (("mass_dsd_tv_500", "500-bin mass-DSD TV"),) + tuple((name, label) for name, label in SCALAR_METRICS)
    comparisons = ("vs_internal_comparator", "adjacent_doubling")
    titles = {"vs_internal_comparator": f"candidate vs {descriptive.REFERENCE:,} internal comparator",
              "adjacent_doubling": "adjacent doubling"}
    fig, axes = plt.subplots(2, 4, figsize=(21, 11), sharex=False)
    for ax, (metric, label) in zip(axes.flat, plot_metrics):
        all_labels: list[str] = []
        xpos = 0
        for comparison, color, marker in (("vs_internal_comparator", "#0f766e", "o"), ("adjacent_doubling", "#7c3f99", "s")):
            selected = [r for r in rows if r["comparison"] == comparison and r["metric"] == metric]
            x = np.arange(xpos, xpos + len(selected))
            point = [r["point_percent"] for r in selected]
            upper = [r["bootstrap_upper95_percent"] for r in selected]
            ax.vlines(x, point, upper, color=color, lw=2)
            ax.scatter(x, point, color=color, marker=marker, s=34,
                       label=titles[comparison] if metric == "mass_dsd_tv_500" else None, zorder=3)
            all_labels.extend([f"{r['left_ncell']:,}→{r['right_ncell']:,}" for r in selected])
            xpos += len(selected)
        ax.axvline(2.5, color="0.5", lw=0.8, ls=":")
        ax.set_xticks(np.arange(len(all_labels)), all_labels, rotation=35, ha="right", fontsize=8.5)
        ax.set_yscale("log")
        ax.set_title(label, weight="bold")
        ax.set_ylabel("all-time maximum difference (%)")
        ax.grid(True, which="both", axis="y", alpha=0.23)
    axes.flat[-1].axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.suptitle("High-resolution agreement: full-20 point estimates and member-bootstrap upper bounds", fontsize=18, weight="bold", y=.985)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(.5, .935), ncol=2, frameon=False, fontsize=9)
    fig.text(0.5, .032,
             "Dot: observed full-20 comparison. Vertical segment ends at its one-sided 95% member-bootstrap bound (2,000 resamples).\n"
             f"These quantify finite-ensemble uncertainty only. The {descriptive.REFERENCE:,} cohort is an internal comparator, not an independent numerical truth; no pass/fail threshold is imposed here.",
             ha="center", fontsize=10)
    fig.subplots_adjust(top=.82, bottom=.12, left=.055, right=.99, wspace=.34, hspace=.35)
    fig.savefig(output / "06_high_resolution_bootstrap_bounds.png", dpi=250, bbox_inches="tight", pad_inches=.10)
    plt.close(fig)


def plot_dsd_sensitivity(rows: list[dict], output: Path) -> None:
    transitions = HIGH_RESOLUTION_TRANSITIONS
    fig, ax = plt.subplots(figsize=(12.5, 7.2))
    markers = {250: "o", 500: "s", 1000: "^"}
    colors = {250: "#4d7c0f", 500: "#087e8b", 1000: "#9a3412"}
    x = np.arange(len(transitions))
    for bins in (250, 500, 1000):
        vals = [next(r["alltime_max_tv_percent"] for r in rows if r["left_ncell"] == left and r["right_ncell"] == right and r["bins"] == bins)
                for left, right in transitions]
        ax.plot(x, vals, marker=markers[bins], color=colors[bins], lw=1.8, label=f"{bins}-bin mass DSD")
    ax.set_xticks(x, [f"{a:,}→{b:,}" for a, b in transitions])
    ax.set_yscale("log")
    ax.set_ylabel("all-time maximum total variation (%)")
    ax.set_xlabel(r"adjacent resolution doubling, $N_{cell}$")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(frameon=False)
    ax.set_title("Mass-DSD comparison is sensitive to analysis-bin resolution", weight="bold")
    fig.text(0.5, .032,
             "The physical simulations are unchanged. This is a diagnostic-resolution sensitivity check: finer bins retain more shape detail,\n"
             "so a distribution can agree in broad structure while retaining a measurable fine-scale tail difference.", ha="center", fontsize=10)
    fig.subplots_adjust(top=.90, bottom=.14, left=.10, right=.97)
    fig.savefig(output / "07_adjacent_doubling_dsd_bin_sensitivity.png", dpi=250, bbox_inches="tight", pad_inches=.10)
    plt.close(fig)


def main() -> None:
    global HIGH_RESOLUTION_TRANSITIONS, INTERNAL_REFERENCE_CANDIDATES
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resolutions", nargs="+", type=int, default=list(descriptive.RESOLUTIONS))
    parser.add_argument("--reference", type=int, default=descriptive.REFERENCE)
    args = parser.parse_args()
    descriptive.RESOLUTIONS = tuple(args.resolutions)
    descriptive.REFERENCE = args.reference
    descriptive.COLORS = plt.cm.viridis(np.linspace(0.03, 0.96, len(descriptive.RESOLUTIONS)))
    if descriptive.REFERENCE not in descriptive.RESOLUTIONS:
        raise ValueError("--reference must be present in --resolutions")
    if tuple(sorted(set(descriptive.RESOLUTIONS))) != descriptive.RESOLUTIONS:
        raise ValueError("--resolutions must be unique and strictly ascending")
    HIGH_RESOLUTION_TRANSITIONS = tuple(zip(descriptive.RESOLUTIONS[-5:-1], descriptive.RESOLUTIONS[-4:]))
    INTERNAL_REFERENCE_CANDIDATES = tuple(descriptive.RESOLUTIONS[-4:-1])
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite output: {args.output}")
    args.output.mkdir(parents=True)
    data = load_cohorts(args.cache)
    rng = np.random.default_rng(20260925)
    bootstrap_rows: list[dict] = []
    for ncell in INTERNAL_REFERENCE_CANDIDATES:
        bootstrap_rows.extend(evaluate_pair(data, ncell, descriptive.REFERENCE, "vs_internal_comparator", rng))
    for left, right in HIGH_RESOLUTION_TRANSITIONS:
        bootstrap_rows.extend(evaluate_pair(data, left, right, "adjacent_doubling", rng))
    sensitivity_rows = [item for left, right in HIGH_RESOLUTION_TRANSITIONS for item in dsd_bin_points(data, left, right)]
    write_csv(bootstrap_rows, args.output / "high_resolution_bootstrap_bounds.csv")
    write_csv(sensitivity_rows, args.output / "adjacent_doubling_dsd_bin_sensitivity.csv")
    plot_bootstrap_bounds(bootstrap_rows, args.output)
    plot_dsd_sensitivity(sensitivity_rows, args.output)
    (args.output / "metadata.json").write_text(json.dumps({
        "status": "bootstrap_precision_and_adjacent_stability_no_convergence_selection",
        "members_per_resolution": MEMBERS, "bootstrap_replicates": NBOOT,
        "internal_comparator_ncell": descriptive.REFERENCE,
        "internal_reference_candidates": list(INTERNAL_REFERENCE_CANDIDATES),
        "adjacent_transitions": [list(pair) for pair in HIGH_RESOLUTION_TRANSITIONS],
        "warning": f"{descriptive.REFERENCE} is the highest tested resolution, not independent numerical reference; no post-hoc threshold or convergence number assigned",
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
