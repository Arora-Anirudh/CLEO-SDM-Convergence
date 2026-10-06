#!/usr/bin/env python3
"""Mac-only calibration experiment for the 2-D stochastic-emulator pilot.

Use the v1 neural conditional mean, but replace its Gaussian latent residual
with a *whole-member* residual resampled from the nearest training resolution.
For an unseen doubled resolution, the residual is scaled by the median of the
last three adjacent-resolution RMS ratios estimated strictly from training.

The 2048/4096 evaluations have already been inspected in v1.  They are now
retrospective checks, not fresh blind validation.  This script generates no
new CLEO data and no above-training-resolution scenario cohort.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import explore_constthermo2d_stochastic_emulator_v1 as base


OUT = base.ROOT / "results/analysis/constthermo2d_stochastic_emulator_calibration_v2"
SEED = 20261002


def sample_member_residuals(
    data: base.Data,
    train_idx: np.ndarray,
    rep: base.Representation,
    model: base.ConditionalEmulator,
    target_n: int,
    draws: int,
    seed: int,
) -> tuple[np.ndarray, float, int]:
    """Draw complete latent member residuals, never individual time slices."""
    train_n = data.ncell[train_idx]
    levels = np.unique(train_n)
    if target_n in levels:
        source_n, factor = target_n, 1.0
    else:
        lower = levels[levels < target_n]
        if not len(lower) or target_n != 2 * lower[-1]:
            raise ValueError("Only one tested doubling beyond training is allowed")
        source_n = int(lower[-1])
        latent_all = rep.transform(data.metrics[train_idx], data.fractions[train_idx])
        rms = []
        for n in levels:
            z = latent_all[train_n == n]
            rms.append(np.sqrt(np.mean(np.sum((z - z.mean(axis=0)) ** 2, axis=1))))
        ratios = np.asarray(rms[1:]) / np.maximum(rms[:-1], 1e-12)
        # This formula is fixed before viewing target-resolution outcomes.
        factor = float(np.median(ratios[-min(3, len(ratios)):]))
    source_idx = train_idx[train_n == source_n]
    latent = rep.transform(data.metrics[source_idx], data.fractions[source_idx])
    residual = latent - latent.mean(axis=0)
    rng = np.random.default_rng(seed)
    choose = rng.integers(0, len(source_idx), size=draws)
    synthetic = model.mean(np.full(draws, target_n)) + factor * residual[choose]
    return synthetic, factor, source_n


def plot_coverage(rows: list[dict], output: Path) -> None:
    v1_path = base.DEFAULT_OUTPUT / "alltime_resolution_backtest.csv"
    with v1_path.open(newline="") as f:
        old = list(csv.DictReader(f))
    data = []
    for row in old:
        if row["method"] in ("neural", "empirical"):
            data.append({**row, "method": "v1 Gaussian" if row["method"] == "neural" else "nearest real members"})
    for row in rows:
        data.append({**row, "method": "v2 neural + member residual"})
    tests = ("extrapolate_2048", "extrapolate_4096")
    metrics = ("lambda0_m3", "lambda6_um6_m3", "mass_weighted_terminal_speed_ms", "mass_weighted_r90_um")
    methods = ("nearest real members", "v1 Gaussian", "v2 neural + member residual")
    colors = ("#63738b", "#b36319", "#167b7e")
    fig, axes = plt.subplots(1, 2, figsize=(12.7, 4.8), sharey=True, constrained_layout=True)
    for ax, test in zip(axes, tests):
        for k, method in enumerate(methods):
            values = []
            for metric in metrics:
                matches = [r for r in data if r["test"] == test and r["method"] == method and r["metric"] == metric]
                values.append(float(matches[0]["alltime_90pct_member_coverage_descriptive"]))
            ax.plot(np.arange(len(metrics)) + (k - 1) * 0.08, values, color=colors[k], marker="o", lw=1.6, label=method)
        ax.axhline(0.9, color="#a53b42", ls="--", lw=1.3, label="nominal 90%")
        ax.set_xticks(range(len(metrics)), [r"$\lambda_0$", r"$\lambda_6$", "fall speed", r"$r_{90}$"])
        ax.set_ylim(0.55, 1.03)
        ax.set_title(test.replace("extrapolate_", "withheld ") + " SDs/cell")
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("Held-out member/time values inside 90% interval")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=4, loc="upper center", frameon=False, bbox_to_anchor=(0.5, 1.05))
    fig.suptitle("Retrospective calibration check — time points are correlated", y=1.14)
    fig.savefig(output / "01_calibration_comparison.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--draws", type=int, default=300)
    args = parser.parse_args()
    if args.draws < 100:
        raise ValueError("At least 100 draws required for predictive intervals")
    args.output.mkdir(parents=True, exist_ok=True)
    data = base.load_data(base.CACHE)
    selected_rows: list[dict] = []
    alltime_rows: list[dict] = []
    scale_rows: list[dict] = []

    # Complete-member folds at known resolutions.
    for fold in range(4):
        is_test = (data.member - 1) // 5 == fold
        train_idx, test_idx = np.flatnonzero(~is_test), np.flatnonzero(is_test)
        assert not set(train_idx).intersection(test_idx)
        rep, model = base.fit_model(data, train_idx, "neural")
        for n in base.RESOLUTIONS:
            target_idx = test_idx[data.ncell[test_idx] == n]
            latent, factor, source_n = sample_member_residuals(data, train_idx, rep, model, n, args.draws, SEED + 100 * fold + n)
            synth = rep.inverse(latent)
            selected_rows.extend(base.compare(data, target_idx, *synth, "seen_members", "neural_member_residual", 4096, fold))
            scale_rows.append({"test": "seen_members", "fold": fold, "target_ncell": n, "source_ncell": source_n, "residual_factor": factor})

    # These resolutions were examined in v1, so this is a retrospective test.
    for target_n in (2048, 4096):
        train_idx = np.flatnonzero(data.ncell < target_n)
        test_idx = np.flatnonzero(data.ncell == target_n)
        assert not set(train_idx).intersection(test_idx)
        rep, model = base.fit_model(data, train_idx, "neural")
        latent, factor, source_n = sample_member_residuals(data, train_idx, rep, model, target_n, args.draws, SEED + target_n)
        synth = rep.inverse(latent)
        label = f"extrapolate_{target_n}"
        selected_rows.extend(base.compare(data, test_idx, *synth, label, "neural_member_residual", source_n, 0))
        alltime_rows.extend(base.compare_alltime(data, test_idx, *synth, label, "neural_member_residual"))
        scale_rows.append({"test": label, "fold": 0, "target_ncell": target_n, "source_ncell": source_n, "residual_factor": factor})

    base.write_csv(args.output / "selected_time_scores.csv", selected_rows)
    base.write_csv(args.output / "selected_time_summary.csv", base.summarize(selected_rows))
    base.write_csv(args.output / "alltime_resolution_backtest.csv", alltime_rows)
    base.write_csv(args.output / "training_only_residual_scales.csv", scale_rows)
    plot_coverage(alltime_rows, args.output)
    manifest = {
        "status": "retrospective_calibration_experiment_not_CLEO",
        "training_member_count_per_resolution": 20,
        "seen_member_fold_count": 4,
        "clean_extrapolation_checks": [2048, 4096],
        "fresh_blind_extrapolation_validation": False,
        "training_only_scale_rule": "median of last up to three adjacent-resolution latent RMS ratios",
        "timepoints_are_correlated": True,
        "generated_higher_resolution_cohort": False,
        "draws_per_prediction": args.draws,
        "seed": SEED,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "retrospective_validation_only": True,
                      "higher_resolution_cohort_generated": False}, indent=2))


if __name__ == "__main__":
    main()
