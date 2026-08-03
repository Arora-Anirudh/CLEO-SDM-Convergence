#!/usr/bin/env python3
"""Compare paired frozen and operational Golovin fixed-50 experiments.

The experiments share the same collision seed for a given resolution/member
index but use different initial populations.  Pairing reduces comparison noise;
it does not imply that the realized collision events remain identical after the
different initial states begin to evolve.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
import numpy as np
from ruamel.yaml import YAML

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

METRICS = (
    "golovin_fixed_bin_l1_relative_bins_500",
    "golovin_relative_error_radius_moment_0_m3",
    "golovin_relative_error_radius_moment_3_um3_m3",
    "golovin_relative_error_radius_moment_6_um6_m3",
)
PLOT_METRICS = (
    "golovin_fixed_bin_l1_relative_bins_500",
    "golovin_relative_error_radius_moment_0_m3",
    "golovin_relative_error_radius_moment_6_um6_m3",
)
LABELS = {
    "golovin_fixed_bin_l1_relative_bins_500": "member DSD L1 mismatch",
    "golovin_relative_error_radius_moment_0_m3": r"$M_0$ relative bias",
    "golovin_relative_error_radius_moment_3_um3_m3": r"$M_3$ relative bias",
    "golovin_relative_error_radius_moment_6_um6_m3": r"$M_6$ relative bias",
    "ensemble_mean_l1_bins_500": "ensemble-mean DSD L1",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--frozen-cases", required=True, type=Path)
    parser.add_argument("--operational-cases", required=True, type=Path)
    parser.add_argument("--frozen-member-time", required=True, type=Path)
    parser.add_argument("--operational-member-time", required=True, type=Path)
    parser.add_argument("--frozen-resolution-directory", required=True, type=Path)
    parser.add_argument("--operational-resolution-directory", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    return parser.parse_args()


def read_csv(path: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source, delimiter=delimiter))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {path}")
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        return YAML(typ="safe").load(source)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def derived_seed(base: int, *parts: object) -> int:
    payload = "|".join([str(base), *(str(part) for part in parts)])
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big")


def bootstrap_mean_interval(
    values: np.ndarray,
    *,
    resamples: int,
    seed: int,
    confidence_level: float,
) -> tuple[float, float, float]:
    values = np.asarray(values, dtype=float)
    if values.size < 2 or np.any(~np.isfinite(values)):
        raise ValueError("paired bootstrap requires at least two finite differences")
    generator = np.random.default_rng(seed)
    indices = generator.integers(0, values.size, size=(resamples, values.size))
    draws = np.mean(values[indices], axis=1)
    alpha = (1.0 - confidence_level) / 2.0
    low, high = np.quantile(draws, [alpha, 1.0 - alpha])
    return float(np.mean(values)), float(low), float(high)


def bootstrap_spread_ratio(
    frozen: np.ndarray,
    operational: np.ndarray,
    *,
    resamples: int,
    seed: int,
    confidence_level: float,
) -> tuple[float, float, float]:
    frozen = np.asarray(frozen, dtype=float)
    operational = np.asarray(operational, dtype=float)
    if frozen.shape != operational.shape or frozen.size < 3:
        raise ValueError("spread-ratio inputs must be paired arrays with at least three values")
    frozen_sd = float(np.std(frozen, ddof=1))
    operational_sd = float(np.std(operational, ddof=1))
    if frozen_sd == 0.0:
        return float("inf"), float("inf"), float("inf")
    generator = np.random.default_rng(seed)
    indices = generator.integers(0, frozen.size, size=(resamples, frozen.size))
    frozen_draw_sd = np.std(frozen[indices], axis=1, ddof=1)
    operational_draw_sd = np.std(operational[indices], axis=1, ddof=1)
    finite = frozen_draw_sd > 0.0
    ratios = operational_draw_sd[finite] / frozen_draw_sd[finite]
    if ratios.size < resamples // 2:
        raise RuntimeError("too few finite spread-ratio bootstrap draws")
    alpha = (1.0 - confidence_level) / 2.0
    low, high = np.quantile(ratios, [alpha, 1.0 - alpha])
    return operational_sd / frozen_sd, float(low), float(high)


def validate_case_pairing(
    frozen_cases: list[dict[str, str]],
    operational_cases: list[dict[str, str]],
) -> list[tuple[int, int]]:
    if len(frozen_cases) != 450 or len(operational_cases) != 450:
        raise ValueError("both protocols must contain exactly 450 cases")
    frozen = {
        (int(row["max_superdroplets"]), int(row["member_index"])): row for row in frozen_cases
    }
    operational = {
        (int(row["max_superdroplets"]), int(row["member_index"])): row for row in operational_cases
    }
    if set(frozen) != set(operational):
        raise ValueError("protocol matrices do not contain identical resolution/member keys")
    if {row["initialization_family"] for row in frozen.values()} != {"controlled"}:
        raise ValueError("frozen matrix is not controlled")
    if {row["initialization_family"] for row in operational.values()} != {"operational_stochastic"}:
        raise ValueError("operational matrix has the wrong initialization family")
    initialization_seeds = [int(row["initialization_seed"]) for row in operational.values()]
    if len(initialization_seeds) != len(set(initialization_seeds)):
        raise ValueError("operational initialization seeds are not unique")
    for key in frozen:
        if frozen[key]["collision_seed"] != operational[key]["collision_seed"]:
            raise ValueError(f"collision seed does not pair at {key}")
    return sorted(frozen)


def diagnostic_lookup(
    rows: list[dict[str, str]],
) -> dict[tuple[int, int, float], dict[str, str]]:
    output: dict[tuple[int, int, float], dict[str, str]] = {}
    for row in rows:
        key = (
            int(row["max_superdroplets"]),
            int(row["member_index"]),
            round(float(row["time_s"]), 3),
        )
        if key in output:
            raise ValueError(f"duplicate member diagnostic: {key}")
        output[key] = row
    return output


def analyze_member_pairs(
    *,
    keys: list[tuple[int, int]],
    frozen_rows: list[dict[str, str]],
    operational_rows: list[dict[str, str]],
    times: list[float],
    confidence_level: float,
    resamples: int,
    base_seed: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    frozen = diagnostic_lookup(frozen_rows)
    operational = diagnostic_lookup(operational_rows)
    member_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    spread_rows: list[dict[str, object]] = []
    resolutions = sorted({resolution for resolution, _ in keys})
    for resolution in resolutions:
        members = sorted(member for candidate, member in keys if candidate == resolution)
        for time in times:
            nominal = round(time, 3)
            for metric in METRICS:
                frozen_values = np.asarray(
                    [float(frozen[(resolution, member, nominal)][metric]) for member in members]
                )
                operational_values = np.asarray(
                    [
                        float(operational[(resolution, member, nominal)][metric])
                        for member in members
                    ]
                )
                differences = operational_values - frozen_values
                for member, frozen_value, operational_value, difference in zip(
                    members,
                    frozen_values,
                    operational_values,
                    differences,
                    strict=True,
                ):
                    member_rows.append(
                        {
                            "max_superdroplets": resolution,
                            "member_index": member,
                            "time_s": time,
                            "metric": metric,
                            "frozen_value": frozen_value,
                            "operational_value": operational_value,
                            "operational_minus_frozen": difference,
                        }
                    )
                estimate, low, high = bootstrap_mean_interval(
                    differences,
                    resamples=resamples,
                    seed=derived_seed(base_seed, "paired_mean", resolution, time, metric),
                    confidence_level=confidence_level,
                )
                summary_rows.append(
                    {
                        "max_superdroplets": resolution,
                        "time_s": time,
                        "metric": metric,
                        "n_pairs": len(members),
                        "mean_operational_minus_frozen": estimate,
                        "paired_bootstrap_95ci_low": low,
                        "paired_bootstrap_95ci_high": high,
                    }
                )
                ratio, low, high = bootstrap_spread_ratio(
                    frozen_values,
                    operational_values,
                    resamples=resamples,
                    seed=derived_seed(base_seed, "spread_ratio", resolution, time, metric),
                    confidence_level=confidence_level,
                )
                spread_rows.append(
                    {
                        "max_superdroplets": resolution,
                        "time_s": time,
                        "metric": metric,
                        "n_pairs": len(members),
                        "frozen_sample_sd": float(np.std(frozen_values, ddof=1)),
                        "operational_sample_sd": float(np.std(operational_values, ddof=1)),
                        "operational_to_frozen_sd_ratio": ratio,
                        "paired_bootstrap_95ci_low": low,
                        "paired_bootstrap_95ci_high": high,
                    }
                )
    return member_rows, summary_rows, spread_rows


def compare_formal_outputs(
    frozen_directory: Path,
    operational_directory: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    frozen_rows = read_csv(frozen_directory / "analytical_agreement.csv")
    operational_rows = read_csv(operational_directory / "analytical_agreement.csv")
    frozen = {
        (int(row["max_superdroplets"]), float(row["time_s"]), row["metric"]): row
        for row in frozen_rows
    }
    operational = {
        (int(row["max_superdroplets"]), float(row["time_s"]), row["metric"]): row
        for row in operational_rows
    }
    if set(frozen) != set(operational):
        raise ValueError("formal analytical tables do not have identical keys")
    rows = []
    for key in sorted(frozen):
        frozen_row = frozen[key]
        operational_row = operational[key]
        rows.append(
            {
                "max_superdroplets": key[0],
                "time_s": key[1],
                "metric": key[2],
                "frozen_estimate": float(frozen_row["estimate"]),
                "operational_estimate": float(operational_row["estimate"]),
                "operational_minus_frozen": float(operational_row["estimate"])
                - float(frozen_row["estimate"]),
                "frozen_95ci_low": float(frozen_row["95ci_low"]),
                "frozen_95ci_high": float(frozen_row["95ci_high"]),
                "operational_95ci_low": float(operational_row["95ci_low"]),
                "operational_95ci_high": float(operational_row["95ci_high"]),
            }
        )
    frozen_decision_path = frozen_directory / "resolution_decision.json"
    operational_decision_path = operational_directory / "resolution_decision.json"
    frozen_decision = json.loads(frozen_decision_path.read_text(encoding="utf-8"))
    operational_decision = json.loads(operational_decision_path.read_text(encoding="utf-8"))
    decision = {
        "schema": "golovin_initialization_protocol_comparison_v1",
        "status": "comparison_completed",
        "frozen_selected_max_superdroplets": frozen_decision["selected_max_superdroplets"],
        "operational_selected_max_superdroplets": operational_decision[
            "selected_max_superdroplets"
        ],
        "same_formal_selection": frozen_decision["selected_max_superdroplets"]
        == operational_decision["selected_max_superdroplets"],
        "frozen_decision_sha256": sha256(frozen_decision_path),
        "operational_decision_sha256": sha256(operational_decision_path),
        "interpretation_boundary": (
            "The operational ensemble combines initialization, collision and "
            "interaction variability. Paired differences use common collision seeds "
            "but do not imply identical realized collision events."
        ),
    }
    return rows, decision


def plot_initialization_variability(
    member_rows: list[dict[str, object]],
    output: Path,
) -> None:
    rows = [row for row in member_rows if float(row["time_s"]) == 0.0]
    resolutions = sorted({int(row["max_superdroplets"]) for row in rows})
    fig, axes = plt.subplots(2, 2, figsize=(12.0, 7.6), sharex=True)
    for axis, metric in zip(axes.flat, METRICS, strict=True):
        values = [
            [
                float(row["operational_value"])
                for row in rows
                if int(row["max_superdroplets"]) == resolution and row["metric"] == metric
            ]
            for resolution in resolutions
        ]
        frozen = [
            np.mean(
                [
                    float(row["frozen_value"])
                    for row in rows
                    if int(row["max_superdroplets"]) == resolution and row["metric"] == metric
                ]
            )
            for resolution in resolutions
        ]
        positions = np.arange(len(resolutions))
        parts = axis.violinplot(values, positions=positions, showextrema=False)
        for body in parts["bodies"]:
            body.set_facecolor("#66A9D9")
            body.set_edgecolor("#1D5D8F")
            body.set_alpha(0.65)
        axis.scatter(positions, frozen, color="#D1495B", marker="_", s=140, label="frozen")
        axis.axhline(0.0, color="#20344A", linewidth=0.8)
        axis.set_title(LABELS[metric])
        axis.grid(axis="y", alpha=0.25)
        axis.set_xticks(positions, [f"{value // 1024}k" for value in resolutions], rotation=35)
    axes[0, 0].legend(frameon=False)
    fig.suptitle("Time-zero member variability introduced by operational initialization")
    fig.supxlabel(r"$N_{SD}$")
    fig.tight_layout()
    fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_paired_summary(
    rows: list[dict[str, object]],
    output: Path,
    *,
    value_key: str,
    low_key: str,
    high_key: str,
    title: str,
    reference: float,
) -> None:
    selected = [row for row in rows if float(row["time_s"]) == 3600.0]
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.8), sharex=True)
    for axis, metric in zip(axes, PLOT_METRICS, strict=True):
        metric_rows = sorted(
            (row for row in selected if row["metric"] == metric),
            key=lambda row: int(row["max_superdroplets"]),
        )
        x = np.arange(len(metric_rows))
        values = np.asarray([float(row[value_key]) for row in metric_rows])
        lows = np.asarray([float(row[low_key]) for row in metric_rows])
        highs = np.asarray([float(row[high_key]) for row in metric_rows])
        finite = np.isfinite(values) & np.isfinite(lows) & np.isfinite(highs)
        axis.errorbar(
            x[finite],
            values[finite],
            yerr=np.vstack([values[finite] - lows[finite], highs[finite] - values[finite]]),
            color="#1D5D8F",
            marker="o",
            capsize=3,
        )
        axis.axhline(reference, color="#D1495B", linewidth=1.0)
        axis.set_title(LABELS[metric])
        axis.grid(axis="y", alpha=0.25)
        axis.set_xticks(
            x,
            [f"{int(row['max_superdroplets']) // 1024}k" for row in metric_rows],
            rotation=40,
        )
    fig.suptitle(title)
    fig.supxlabel(r"$N_{SD}$")
    fig.tight_layout()
    fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_formal_comparison(rows: list[dict[str, object]], output: Path) -> None:
    metrics = (
        "ensemble_mean_l1_bins_500",
        "golovin_relative_error_radius_moment_0_m3",
        "golovin_relative_error_radius_moment_6_um6_m3",
    )
    selected = [row for row in rows if float(row["time_s"]) == 3600.0]
    fig, axes = plt.subplots(1, 3, figsize=(12.0, 3.8), sharex=True)
    for axis, metric in zip(axes, metrics, strict=True):
        metric_rows = sorted(
            (row for row in selected if row["metric"] == metric),
            key=lambda row: int(row["max_superdroplets"]),
        )
        x = np.arange(len(metric_rows))
        axis.plot(
            x,
            [float(row["frozen_estimate"]) for row in metric_rows],
            color="#D1495B",
            marker="o",
            label="frozen",
        )
        axis.plot(
            x,
            [float(row["operational_estimate"]) for row in metric_rows],
            color="#1D5D8F",
            marker="o",
            label="operational",
        )
        axis.axhline(0.0, color="#20344A", linewidth=0.8)
        axis.set_title(LABELS[metric])
        axis.grid(axis="y", alpha=0.25)
        axis.set_xticks(
            x,
            [f"{int(row['max_superdroplets']) // 1024}k" for row in metric_rows],
            rotation=40,
        )
    axes[0].legend(frameon=False)
    fig.suptitle("Frozen versus operational formal estimates at 60 minutes")
    fig.supxlabel(r"$N_{SD}$")
    fig.tight_layout()
    fig.savefig(output, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    output = args.output_directory.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite: {output}")
    config = load_yaml(args.config.resolve())
    settings = config["paired_protocol_comparison"]
    times = [float(value) for value in settings["comparison_times_s"]]
    confidence = float(settings["confidence_level"])
    resamples = int(settings["bootstrap_resamples"])
    base_seed = int(settings["bootstrap_seed"])

    frozen_cases = read_csv(args.frozen_cases.resolve(), delimiter="\t")
    operational_cases = read_csv(args.operational_cases.resolve(), delimiter="\t")
    keys = validate_case_pairing(frozen_cases, operational_cases)
    member_rows, summary_rows, spread_rows = analyze_member_pairs(
        keys=keys,
        frozen_rows=read_csv(args.frozen_member_time.resolve()),
        operational_rows=read_csv(args.operational_member_time.resolve()),
        times=times,
        confidence_level=confidence,
        resamples=resamples,
        base_seed=base_seed,
    )
    formal_rows, decision = compare_formal_outputs(
        args.frozen_resolution_directory.resolve(),
        args.operational_resolution_directory.resolve(),
    )
    decision.update(
        {
            "paired_case_count": len(keys),
            "confidence_level": confidence,
            "bootstrap_resamples": resamples,
            "frozen_cases_sha256": sha256(args.frozen_cases.resolve()),
            "operational_cases_sha256": sha256(args.operational_cases.resolve()),
            "frozen_member_time_sha256": sha256(args.frozen_member_time.resolve()),
            "operational_member_time_sha256": sha256(args.operational_member_time.resolve()),
        }
    )

    output.mkdir(parents=True)
    write_csv(output / "paired_member_differences.csv", member_rows)
    write_csv(output / "paired_mean_difference_intervals.csv", summary_rows)
    write_csv(output / "protocol_spread_ratios.csv", spread_rows)
    write_csv(output / "formal_estimate_comparison.csv", formal_rows)
    (output / "initialization_protocol_comparison.json").write_text(
        json.dumps(decision, indent=2) + "\n",
        encoding="utf-8",
    )
    plot_initialization_variability(
        member_rows,
        output / "time_zero_initialization_variability.png",
    )
    plot_paired_summary(
        summary_rows,
        output / "paired_protocol_differences_3600s.png",
        value_key="mean_operational_minus_frozen",
        low_key="paired_bootstrap_95ci_low",
        high_key="paired_bootstrap_95ci_high",
        title="Paired operational-minus-frozen differences at 60 minutes",
        reference=0.0,
    )
    plot_paired_summary(
        spread_rows,
        output / "protocol_spread_ratios_3600s.png",
        value_key="operational_to_frozen_sd_ratio",
        low_key="paired_bootstrap_95ci_low",
        high_key="paired_bootstrap_95ci_high",
        title="Operational-to-frozen member spread ratio at 60 minutes",
        reference=1.0,
    )
    plot_formal_comparison(
        formal_rows,
        output / "formal_estimate_comparison_3600s.png",
    )
    print("GOLOVIN_INITIALIZATION_PROTOCOL_COMPARISON_PASS=1")
    print(f"paired_case_count={len(keys)}")
    print(f"output_directory={output}")


if __name__ == "__main__":
    main()
