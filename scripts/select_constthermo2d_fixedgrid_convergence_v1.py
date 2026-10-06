#!/usr/bin/env python3
"""Apply a pre-declared-style operational convergence rule to constthermo2d.

This script deliberately distinguishes an internal high-resolution comparator
from independent numerical truth.  The decision is therefore an operational,
metric-scoped selection within the tested 20-member ladder, not a universal
claim of numerical convergence.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import analyze_constthermo2d_fixedgrid_production_descriptive_v1 as descriptive
import analyze_constthermo2d_fixedgrid_bootstrap_v1 as bootstrap


RESOLUTIONS = (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192)
REFERENCE = 8192
MEMBERS = 20
NBOOT = 2000
CANDIDATES = (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048)
CORE_METRICS = {
    "mass_dsd_tv_500": 5.0,
    "lambda0_m3": 5.0,
    "lambda2_um2_m3": 5.0,
    "lambda3_um3_m3": 5.0,
    "mass_weighted_terminal_speed_ms": 5.0,
}
TAIL_METRICS = {
    "lambda6_um6_m3": 10.0,
    "mass_weighted_r90_um": 10.0,
}
THRESHOLDS = {**CORE_METRICS, **TAIL_METRICS}


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def pair_rows(data: dict[str, np.ndarray], left: int, right: int, seed: int) -> list[dict[str, object]]:
    rows = bootstrap.evaluate_pair(data, left, right, "selection_pair", np.random.default_rng(seed))
    for row in rows:
        row["threshold_percent"] = THRESHOLDS[row["metric"]]
        row["upper95_ratio_to_threshold"] = float(row["bootstrap_upper95_percent"]) / THRESHOLDS[row["metric"]]
        row["criterion_pass"] = bool(row["upper95_ratio_to_threshold"] <= 1.0)
    return rows


def worst_pair(rows: list[dict[str, object]]) -> tuple[float, str, float, float]:
    worst = max(rows, key=lambda row: float(row["upper95_ratio_to_threshold"]))
    return (
        float(worst["upper95_ratio_to_threshold"]),
        str(worst["metric"]),
        float(worst["bootstrap_upper95_percent"]),
        float(worst["threshold_percent"]),
    )


def initial_support_audit(data: dict[str, np.ndarray]) -> dict[str, float]:
    left = RESOLUTIONS.index(4096)
    right = RESOLUTIONS.index(REFERENCE)
    output: dict[str, float] = {}
    for name in ("lambda0_m3", "lambda2_um2_m3", "lambda3_um3_m3", "lambda6_um6_m3", "total_droplet_mass_g_m3"):
        candidate = data[name][left].mean(axis=0)[0]
        reference = data[name][right].mean(axis=0)[0]
        output[f"initial_{name}_symmetric_percent"] = float(
            descriptive.symmetric_percent(np.asarray(candidate), np.asarray(reference))
        )
    for bins in (250, 500, 1000):
        candidate = data[f"mass_dsd_{bins}_g_m3"][left].mean(axis=0)[0:1]
        reference = data[f"mass_dsd_{bins}_g_m3"][right].mean(axis=0)[0:1]
        widths = np.diff(np.log(data[f"radius_edges_{bins}_um"]))
        output[f"initial_mass_dsd_tv_{bins}_percent"] = float(
            descriptive.dsd_tv_percent(candidate, reference, widths)[0]
        )
    return output


def selection_rows(data: dict[str, np.ndarray]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    pair_cache: dict[tuple[int, int], list[dict[str, object]]] = {}
    requested_pairs = {(candidate, REFERENCE) for candidate in CANDIDATES}
    requested_pairs |= {(candidate, 2 * candidate) for candidate in CANDIDATES}
    requested_pairs |= {(2 * candidate, 4 * candidate) for candidate in CANDIDATES}
    for index, (left, right) in enumerate(sorted(requested_pairs)):
        pair_cache[(left, right)] = pair_rows(data, left, right, 20260927 + index)

    diagnostic_rows: list[dict[str, object]] = []
    for pair, rows in pair_cache.items():
        for row in rows:
            diagnostic_rows.append({"comparison": f"{pair[0]}->{pair[1]}", **row})

    decisions: list[dict[str, object]] = []
    for candidate in CANDIDATES:
        gates = {
            "against_8192": worst_pair(pair_cache[(candidate, REFERENCE)]),
            "first_doubling": worst_pair(pair_cache[(candidate, 2 * candidate)]),
            "second_doubling": worst_pair(pair_cache[(2 * candidate, 4 * candidate)]),
        }
        decision = {
            "candidate_ncell": candidate,
            "initial_domain_sds": 120 * candidate,
            "against_8192_worst_ratio": gates["against_8192"][0],
            "against_8192_limiting_metric": gates["against_8192"][1],
            "against_8192_upper95_percent": gates["against_8192"][2],
            "against_8192_threshold_percent": gates["against_8192"][3],
            "first_doubling_worst_ratio": gates["first_doubling"][0],
            "first_doubling_limiting_metric": gates["first_doubling"][1],
            "first_doubling_upper95_percent": gates["first_doubling"][2],
            "first_doubling_threshold_percent": gates["first_doubling"][3],
            "second_doubling_worst_ratio": gates["second_doubling"][0],
            "second_doubling_limiting_metric": gates["second_doubling"][1],
            "second_doubling_upper95_percent": gates["second_doubling"][2],
            "second_doubling_threshold_percent": gates["second_doubling"][3],
        }
        decision["all_bootstrap_gates_pass"] = bool(max(gate[0] for gate in gates.values()) <= 1.0)
        decisions.append(decision)
    return decisions, diagnostic_rows


def plot_gate_matrix(decisions: list[dict[str, object]], output: Path) -> None:
    # The complete ladder is retained in selection_decisions.csv.  This plot
    # focuses on the scientifically relevant high-resolution decision edge.
    decisions = [row for row in decisions if int(row["candidate_ncell"]) >= 256]
    keys = ("against_8192", "first_doubling", "second_doubling")
    labels = (r"candidate vs 8,192", r"$N\rightarrow2N$", r"$2N\rightarrow4N$")
    matrix = np.array([[float(row[f"{key}_worst_ratio"]) for key in keys] for row in decisions])
    fig, ax = plt.subplots(figsize=(10.5, max(5.6, 1.48 * len(decisions))))
    image = ax.imshow(matrix, cmap="RdYlGn_r", vmin=0.0, vmax=max(1.2, matrix.max() * 1.05), aspect="auto")
    ax.set_xticks(range(len(keys)), labels)
    ax.set_yticks(range(len(decisions)), [f"{int(row['candidate_ncell']):,}" for row in decisions])
    ax.set_xlabel("required comparison gate")
    ax.set_ylabel(r"candidate SDs per populated grid box, $N_{cell}$")
    for i, row in enumerate(decisions):
        for j, key in enumerate(keys):
            ratio = float(row[f"{key}_worst_ratio"])
            metric = {
                "mass_dsd_tv_500": "DSD TV",
                "lambda0_m3": r"$\lambda_0$",
                "lambda2_um2_m3": r"$\lambda_2$",
                "lambda3_um3_m3": r"$\lambda_3$",
                "lambda6_um6_m3": r"$\lambda_6$",
                "mass_weighted_terminal_speed_ms": "terminal speed",
                "mass_weighted_r90_um": r"$r_{90}$",
            }[str(row[f"{key}_limiting_metric"])]
            value = float(row[f"{key}_upper95_percent"])
            threshold = float(row[f"{key}_threshold_percent"])
            ax.text(j, i, f"{ratio:.2f}x\n{metric}\n{value:.2f}/{threshold:.0f}%",
                    ha="center", va="center", fontsize=9.5, color="black")
    fig.colorbar(image, ax=ax, label="worst 95% upper bound / metric tolerance")
    ax.set_title("Operational convergence gate: maximum normalised uncertainty across required metrics", weight="bold", pad=14)
    fig.text(0.5, .032,
             "A cell passes when its ratio is at most 1. Core metrics use a 5% margin; sparse-tail metrics use 10%.\n"
             "This is an internal-comparator operational decision, not an independent-reference proof.",
             ha="center", fontsize=10)
    fig.subplots_adjust(top=.90, bottom=.14, left=.17, right=.92)
    fig.savefig(output / "01_operational_convergence_gate_matrix.png", dpi=260, bbox_inches="tight", pad_inches=.10)
    plt.close(fig)


def write_readout(decisions: list[dict[str, object]], support: dict[str, float], output: Path) -> None:
    accepted = [row for row in decisions if bool(row["all_bootstrap_gates_pass"])]
    selected = min(accepted, key=lambda row: int(row["candidate_ncell"])) if accepted else None
    lines = [
        "# 2-D constthermo2d: operational resolution-selection readout",
        "",
        "## Decision boundary",
        "",
        "This document applies a transparent operational rule to the completed fixed-20 normal-sampling ladder. "
        "It does not turn the 8,192-SD-per-populated-cell cohort into independent numerical truth. "
        "The resulting selection is configuration-, diagnostic-, and 20-member-ensemble-specific.",
        "",
        "## Declared criterion applied here",
        "",
        "For each candidate, every reported statistic is the maximum over post-initial stored times. "
        "The uncertainty value is a one-sided 95% member-bootstrap upper bound from 2,000 independent resamples of each 20-member cohort.",
        "",
        "- Core diagnostics: 500-bin mass-DSD total variation, lambda0, lambda2, lambda3, and mass-weighted terminal speed must each be at most 5%.",
        "- Tail diagnostics: lambda6 and mass-weighted r90 must each be at most 10%.",
        "- A candidate must pass against the 8,192 internal comparator and across two successive doublings: N to 2N and 2N to 4N.",
        "- The 250- and 1,000-bin DSD values remain sensitivity diagnostics; the 500-bin DSD is the primary decision statistic.",
        "",
        "## Result",
        "",
    ]
    if selected:
        lines += [
            f"The smallest tested candidate passing every stated bootstrap gate is **Ncell = {int(selected['candidate_ncell']):,} SDs per initially populated grid box** "
            f"({int(selected['initial_domain_sds']):,} initial domain SDs).",
            "",
            "It passes against the 8,192 comparator and the 1,024-to-2,048 and 2,048-to-4,096 adjacent-doubling confirmations. "
            "The next lower candidate, Ncell=512, fails the first-doubling gate because its 500-bin mass-DSD TV upper bound is just above the 5% core margin.",
        ]
    else:
        lines.append("No candidate passes every stated gate; no operational resolution is selected.")
    lines += [
        "",
        "## Protocol-comparability audit",
        "",
        "The 8,192 cohort used the separately audited 4 nm to 2 micrometre radius support because the original 3 nm to 3 micrometre support produces zero multiplicities at this resolution. "
        "The support scan estimated that this removes 0.000052% of initial number and 0.00205% of initial mass. "
        f"At t=0, the observed 4,096-versus-8,192 500-bin mass-DSD TV is {support['initial_mass_dsd_tv_500_percent']:.3f}% and total-mass symmetric difference is {support['initial_total_droplet_mass_g_m3_symmetric_percent']:.3f}%. "
        "These values are reported rather than treated as evidence that the two protocols are literally identical.",
        "",
        "## What the selection supports",
        "",
        "It supports Ncell=1,024 as the smallest tested operational resolution under this declared metric set, margins, compact 120-s output grid, and 20-member design. "
        "It does not establish universal SDM convergence, an arbitrary-member guarantee, an independently referenced numerical error, or a rainfall conclusion from this closed 2-D configuration.",
        "",
        "## Produced evidence",
        "",
        "- `selection_decisions.csv`: gate-level outcome for every candidate.",
        "- `selection_pair_diagnostics.csv`: every metric, point estimate, bootstrap upper bound, tolerance, and pass status.",
        "- `01_operational_convergence_gate_matrix.png`: compact graphical decision audit.",
    ]
    (output / "operational_convergence_selection_readout.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite output: {args.output}")
    args.output.mkdir(parents=True)
    descriptive.RESOLUTIONS = RESOLUTIONS
    descriptive.REFERENCE = REFERENCE
    bootstrap.NBOOT = NBOOT
    data = descriptive.load_cohorts(args.cache)
    decisions, diagnostics = selection_rows(data)
    support = initial_support_audit(data)
    write_csv(decisions, args.output / "selection_decisions.csv")
    write_csv(diagnostics, args.output / "selection_pair_diagnostics.csv")
    plot_gate_matrix(decisions, args.output)
    write_readout(decisions, support, args.output)
    selected = next((row for row in decisions if bool(row["all_bootstrap_gates_pass"])), None)
    (args.output / "metadata.json").write_text(json.dumps({
        "status": "provisional_operational_metric_scoped_resolution_selection",
        "resolutions_ncell": list(RESOLUTIONS), "members_per_resolution": MEMBERS,
        "bootstrap_replicates": NBOOT, "internal_comparator_ncell": REFERENCE,
        "core_tolerances_percent": CORE_METRICS, "tail_tolerances_percent": TAIL_METRICS,
        "candidate_rule": "comparator plus two successive adjacent doublings",
        "selected_ncell": selected["candidate_ncell"] if selected else None,
        "support_comparability_audit": support,
        "warning": "8192 cohort uses separately audited 4nm-to-2um support correction and is an internal comparator, not independent numerical truth.",
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
