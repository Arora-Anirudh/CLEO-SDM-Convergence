"""Analyze the predefined targeted high-resolution Golovin precision extension.

This is a follow-up calculation over a read-only analysis view. It uses 150,
150 and 50 independent members at 262144, 524288 and 1048576 SDs,
respectively. The unequal ensemble sizes are deliberate and recorded in every
result; the script does not relabel the original balanced fixed-50 result.

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
    METRIC_LABELS,
    PRIMARY_METRICS,
    evaluate_prefix,
    validate_settings,
)
from analyze_golovin_resolution_convergence import (
    load_archives,
    load_yaml,
    portable_artifact_path,
    read_csv,
    sha256_file,
    validate_inputs,
    write_csv,
)

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


def target_counts(config: dict[str, Any]) -> dict[int, int]:
    raw_counts = config["practical_convergence"].get("targeted_member_counts_by_resolution")
    if not isinstance(raw_counts, dict):
        raise ValueError("targeted_member_counts_by_resolution is required")
    counts = {int(resolution): int(member_count) for resolution, member_count in raw_counts.items()}
    if len(counts) != 3 or any(member_count < 2 for member_count in counts.values()):
        raise ValueError("targeted analysis requires three resolutions with at least two members")
    return counts


def bin_sensitivity_summary(
    decisions: list[dict[str, object]],
    *,
    primary_bin: int,
) -> list[dict[str, object]]:
    primary = next(row for row in decisions if int(row["log_radius_bins"]) == primary_bin)
    output: list[dict[str, object]] = []
    for decision in decisions:
        selected = decision["selected_candidate"]
        role = "primary" if int(decision["log_radius_bins"]) == primary_bin else "sensitivity"
        primary_selected = primary["selected_candidate"]
        output.append(
            {
                "log_radius_bins": int(decision["log_radius_bins"]),
                "role": role,
                "selected_candidate": selected,
                "candidate_none_disagreement_with_primary": (
                    (selected is None) != (primary_selected is None)
                ),
                "candidate_step_disagreement_with_primary": (
                    selected is not None
                    and primary_selected is not None
                    and int(selected) != int(primary_selected)
                ),
                "automatic_veto": False,
            }
        )
    return output


def plot_targeted_bounds(
    changes: list[dict[str, object]],
    config: dict[str, Any],
    output: Path,
) -> None:
    settings = config["practical_convergence"]
    primary_bin = int(settings["primary_log_radius_bins"])
    margin = float(settings["minimum_worthwhile_improvement_absolute"]) * 100.0
    selected = [row for row in changes if int(row["log_radius_bins"]) == primary_bin]
    pairs = sorted(
        {
            (int(row["lower_max_superdroplets"]), int(row["upper_max_superdroplets"]))
            for row in selected
        }
    )
    colors = plt.get_cmap("viridis")(np.linspace(0.15, 0.85, len(pairs)))
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.8), sharex=True)
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
            bounds = np.asarray([float(row["one_sided_95_upper_bound"]) * 100.0 for row in rows])
            axis.plot(
                times,
                bounds,
                marker="o",
                color=color,
                label=f"{lower // 1024}k→{upper // 1024}k",
            )
            axis.scatter(times, points, marker="x", color=color, zorder=3)
        axis.axhspan(0.0, margin, color="#58a65c", alpha=0.13)
        axis.axhline(margin, color="#3a9147", linewidth=1.0)
        axis.set_title(METRIC_LABELS[metric], fontsize=11)
        axis.set_xlabel("time / min")
        axis.grid(alpha=0.2)
    axes[0].set_ylabel("absolute change / pp")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle("Targeted Golovin high-resolution precision follow-up", y=0.99)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.90), ncol=2)
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.16, top=0.69, wspace=0.26)
    fig.savefig(output, dpi=300, facecolor="white")
    plt.close(fig)


def analyze_targeted_extension(
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
    counts = target_counts(config)
    resolutions = sorted({int(row["max_superdroplets"]) for row in matrix_rows})
    if set(counts) != set(resolutions):
        raise ValueError("target counts must exactly match the combined analysis resolutions")

    primary_bin = int(settings["primary_log_radius_bins"])
    bins = [primary_bin, *(int(value) for value in settings["sensitivity_log_radius_bins"])]
    estimates: list[dict[str, object]] = []
    changes: list[dict[str, object]] = []
    decisions: list[dict[str, object]] = []
    representative_size = max(counts.values())
    for bin_count in bins:
        bin_estimates, bin_changes, bin_decision = evaluate_prefix(
            rows=rows,
            matrix_rows=matrix_rows,
            config=config,
            archives=archives,
            member_count=representative_size,
            bin_count=bin_count,
            member_counts_by_resolution=counts,
        )
        estimates.extend(bin_estimates)
        changes.extend(bin_changes)
        decisions.append(bin_decision)

    primary = next(row for row in decisions if int(row["log_radius_bins"]) == primary_bin)
    candidate = primary["selected_candidate"]
    sensitivity = bin_sensitivity_summary(decisions, primary_bin=primary_bin)
    decision = {
        "schema": "golovin_targeted_high_resolution_precision_extension_v1",
        "status": (
            "targeted_precision_criterion_resolved"
            if candidate is not None
            else "targeted_precision_criterion_unresolved"
        ),
        "selected_candidate_within_targeted_followup": candidate,
        "formal_convergence_claim_permitted": False,
        "formal_claim_boundary": (
            "The original balanced fixed-50 selection is unchanged. This is a transparently "
            "conditioned, prospectively frozen follow-up for the late-time high-resolution "
            "practical-criterion uncertainty."
        ),
        "members_by_resolution": {str(key): value for key, value in counts.items()},
        "primary_log_radius_bins": primary_bin,
        "sensitivity_log_radius_bins": [
            int(value) for value in settings["sensitivity_log_radius_bins"]
        ],
        "minimum_worthwhile_improvement_absolute": float(
            settings["minimum_worthwhile_improvement_absolute"]
        ),
        "diminishing_returns_confidence_bound": (
            "one-sided percentile-bootstrap upper bound on the absolute independent-ensemble change"
        ),
        "requires_two_successive_doublings": True,
        "primary_decision": primary,
        "bin_sensitivity_requires_investigation": any(
            bool(row["candidate_none_disagreement_with_primary"])
            or bool(row["candidate_step_disagreement_with_primary"])
            for row in sensitivity
        ),
        "sensitivity_bins_are_diagnostic_only": True,
        "independent_ensemble_warning": (
            "Different resolutions use independent collision ensembles; member "
            "indices are not paired histories."
        ),
    }
    return estimates, changes, sensitivity, decision


def main() -> None:
    args = parse_args()
    output_directory = args.output_directory.resolve()
    if output_directory.exists():
        raise FileExistsError(f"refusing to overwrite: {output_directory}")
    rows = read_csv(args.combined_member_time.resolve())
    matrix_rows = read_csv(args.matrix_file.resolve(), delimiter="\t")
    config = load_yaml(args.config.resolve())
    archives = load_archives(args.run_root.resolve(), matrix_rows)
    estimates, changes, sensitivity, decision = analyze_targeted_extension(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )
    output_directory.mkdir(parents=True)
    write_csv(output_directory / "analytical_validity.csv", estimates)
    write_csv(output_directory / "diminishing_returns.csv", changes)
    write_csv(output_directory / "bin_sensitivity_summary.csv", sensitivity)
    plot_targeted_bounds(changes, config, output_directory / "targeted_diminishing_returns.png")
    decision.update(
        {
            "combined_member_time": portable_artifact_path(
                args.combined_member_time, analysis_root=output_directory.parent
            ),
            "combined_member_time_path_base": "analysis_root",
            "combined_member_time_sha256": sha256_file(args.combined_member_time.resolve()),
            "matrix_file": str(args.matrix_file.resolve()),
            "matrix_sha256": sha256_file(args.matrix_file.resolve()),
            "config": str(args.config.resolve()),
            "config_sha256": sha256_file(args.config.resolve()),
        }
    )
    (output_directory / "targeted_precision_decision.json").write_text(
        json.dumps(decision, indent=2) + "\n", encoding="utf-8"
    )
    print("GOLOVIN_TARGETED_PRECISION_ANALYSIS_PASS=1")
    print(f"status={decision['status']}")
    print(f"selected_candidate={decision['selected_candidate_within_targeted_followup']}")
    print(f"output_directory={output_directory}")


if __name__ == "__main__":
    main()
