#!/usr/bin/env python3
"""Bounded Mac-only 1000-bin DSD-first stochastic-emulator test.

Whole member trajectories are the statistical observations.  A conditional
neural mean of a cumulative-mass-DSD PCA is combined with *raw* whole-member
CDF residuals from the nearest training resolution.  The 1000-bin mass-DSD and
its histogram-midpoint r90 are then derived from each generated CDF.

This is exploratory emulation, not generation of independent CLEO members.
The 2048/4096 resolution tests have already been inspected in earlier pilots
and are retrospective.  No above-training-resolution scenario is written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import explore_constthermo2d_stochastic_emulator_v1 as base


OUT = base.ROOT / "results/analysis/constthermo2d_dsd_first_emulator_v3"
SEED = 20261001
N_TIME, N_BINS, N_COMPONENTS = 61, 1000, 48


@dataclass
class DSDData:
    ncell: np.ndarray
    member: np.ndarray
    cdf: np.ndarray  # whole member, saved time, 1000 mass bins
    r90_um: np.ndarray
    time_min: np.ndarray
    radius_edges_um: np.ndarray
    input_hashes: dict[str, str]


def load_data(cache: Path) -> DSDData:
    cdfs, r90, cells, members = [], [], [], []
    time_ref = edges_ref = None
    input_hashes = {}
    for n in base.RESOLUTIONS:
        for member in range(1, 21):
            path = cache / f"ncell{n:04d}" / f"member{member:03d}.npz"
            input_hashes[str(path.relative_to(base.ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
            with np.load(path) as z:
                time = np.asarray(z["time_min"], dtype=float)
                edges = np.asarray(z["radius_edges_1000_um"], dtype=float)
                density = np.asarray(z["mass_dsd_1000_g_m3"], dtype=float)
                stored_r90 = np.asarray(z["mass_weighted_r90_um"], dtype=float)
            if time.shape != (N_TIME,) or edges.shape != (N_BINS + 1,) or density.shape != (N_TIME, N_BINS):
                raise ValueError(f"Unexpected DSD cache geometry: {path}")
            if not (np.isfinite(density).all() and np.all(density >= 0)):
                raise ValueError(f"Invalid DSD: {path}")
            if time_ref is None:
                time_ref, edges_ref = time.copy(), edges.copy()
            elif not (np.array_equal(time, time_ref) and np.array_equal(edges, edges_ref)):
                raise ValueError(f"Inconsistent time or radius edges: {path}")
            bin_mass = density * np.diff(np.log(edges))[None, :]
            total_mass = bin_mass.sum(axis=1, keepdims=True)
            if np.any(total_mass <= 0):
                raise ValueError(f"Empty mass DSD: {path}")
            mass_fraction = bin_mass / total_mass
            cdf = np.cumsum(mass_fraction, axis=1)
            cdf[:, -1] = 1.0
            if not np.allclose(quantile_from_cdf(cdf, edges), stored_r90, rtol=1e-11, atol=1e-11):
                raise ValueError(f"Derived r90 does not reproduce saved diagnostic: {path}")
            cdfs.append(cdf)
            r90.append(stored_r90)
            cells.append(n)
            members.append(member)
    return DSDData(np.asarray(cells), np.asarray(members), np.asarray(cdfs),
                   np.asarray(r90), time_ref, edges_ref, input_hashes)


def enforce_cdf(values: np.ndarray) -> np.ndarray:
    cdf = np.maximum.accumulate(np.clip(values, 0.0, 1.0), axis=-1)
    cdf[..., -1] = 1.0
    return cdf


def fractions_from_cdf(cdf: np.ndarray) -> np.ndarray:
    return np.diff(np.pad(cdf, [(0, 0)] * (cdf.ndim - 1) + [(1, 0)]), axis=-1)


def quantile_bin(cdf: np.ndarray, probability: float = 0.9) -> np.ndarray:
    return np.argmax(cdf >= probability, axis=-1)


def quantile_from_cdf(cdf: np.ndarray, edges: np.ndarray) -> np.ndarray:
    midpoint = np.sqrt(edges[:-1] * edges[1:])
    return midpoint[quantile_bin(cdf)]


def fit_representation_and_mean(data: DSDData, train_idx: np.ndarray):
    # Import sklearn after the compatibility shim in the v1 module has run.
    from sklearn.decomposition import PCA

    flat = data.cdf[train_idx].reshape(len(train_idx), -1)
    pca = PCA(n_components=min(N_COMPONENTS, len(train_idx) - 1),
              svd_solver="randomized", random_state=SEED).fit(flat)
    latent = pca.transform(flat)
    model = base.ConditionalEmulator("neural").fit(data.ncell[train_idx], latent)
    return pca, model


def predict_cdf(data: DSDData, train_idx: np.ndarray, target_n: int,
                pca, model, draws: int, seed: int) -> tuple[np.ndarray, float, int]:
    levels = np.unique(data.ncell[train_idx])
    if target_n in levels:
        source_n, factor = target_n, 1.0
    else:
        lower = levels[levels < target_n]
        if not len(lower) or target_n != 2 * lower[-1]:
            raise ValueError("Only one untrained resolution doubling is evaluated")
        source_n = int(lower[-1])
        rms = []
        for n in levels:
            a = data.cdf[train_idx[data.ncell[train_idx] == n]]
            rms.append(np.sqrt(np.mean(np.sum((a - a.mean(axis=0)) ** 2, axis=(1, 2)))))
        ratios = np.asarray(rms[1:]) / np.maximum(rms[:-1], 1e-12)
        factor = float(np.median(ratios[-min(3, len(ratios)):]))

    source_idx = train_idx[data.ncell[train_idx] == source_n]
    source = data.cdf[source_idx]
    source_residual = source - source.mean(axis=0, keepdims=True)
    mean_flat = pca.inverse_transform(model.mean(np.asarray([target_n])))[0]
    mean_cdf = mean_flat.reshape(N_TIME, N_BINS)
    rng = np.random.default_rng(seed)
    choose = rng.integers(0, len(source_idx), size=draws)
    generated = enforce_cdf(mean_cdf[None, :, :] + factor * source_residual[choose])
    return generated, factor, source_n


def empirical_baseline(data: DSDData, train_idx: np.ndarray,
                       target_n: int, draws: int, seed: int) -> np.ndarray:
    levels = np.unique(data.ncell[train_idx])
    source_n = int(levels[np.argmin(np.abs(np.log2(levels) - np.log2(target_n)))])
    source_idx = train_idx[data.ncell[train_idx] == source_n]
    rng = np.random.default_rng(seed)
    return data.cdf[rng.choice(source_idx, size=draws, replace=True)]


def compare(data: DSDData, true_idx: np.ndarray, generated: np.ndarray,
            test: str, method: str) -> tuple[dict, dict[str, np.ndarray]]:
    true = data.cdf[true_idx]
    true_fraction = fractions_from_cdf(true)
    gen_fraction = fractions_from_cdf(generated)
    dsd_tv = 50.0 * np.abs(true_fraction.mean(axis=0) - gen_fraction.mean(axis=0)).sum(axis=1)
    true_bin = quantile_bin(true)
    gen_bin = quantile_bin(generated)
    bin_tv = []
    true_prob = []
    gen_prob = []
    for t in range(N_TIME):
        a = np.bincount(true_bin[:, t], minlength=N_BINS) / len(true_idx)
        b = np.bincount(gen_bin[:, t], minlength=N_BINS) / len(generated)
        bin_tv.append(50.0 * np.abs(a - b).sum())
        true_prob.append(a)
        gen_prob.append(b)
    bin_tv = np.asarray(bin_tv)
    mean_r_true = quantile_from_cdf(true, data.radius_edges_um).mean(axis=0)
    mean_r_gen = quantile_from_cdf(generated, data.radius_edges_um).mean(axis=0)
    r_true = quantile_from_cdf(true, data.radius_edges_um)
    r_gen = quantile_from_cdf(generated, data.radius_edges_um)
    sd_r_true = r_true.std(axis=0, ddof=1)
    sd_r_gen = r_gen.std(axis=0, ddof=1)
    r90_mean_sym = 200.0 * np.abs(mean_r_true - mean_r_gen) / np.maximum(mean_r_true + mean_r_gen, 1e-30)
    tail_edge = np.searchsorted(data.radius_edges_um, 100.0, side="left") - 1
    tail_true = 1.0 - true[:, :, tail_edge].mean(axis=0)
    tail_gen = 1.0 - generated[:, :, tail_edge].mean(axis=0)
    row = {
        "test": test, "method": method, "heldout_members": len(true_idx),
        "max_postinitial_mass_dsd_tv_1000_percent": float(dsd_tv[1:].max()),
        "median_postinitial_mass_dsd_tv_1000_percent": float(np.median(dsd_tv[1:])),
        "max_postinitial_r90_bin_distribution_tv_percent": float(bin_tv[1:].max()),
        "median_postinitial_r90_bin_distribution_tv_percent": float(np.median(bin_tv[1:])),
        "max_postinitial_r90_mean_symmetric_error_percent": float(r90_mean_sym[1:].max()),
        "r90_120min_mean_true_um": float(mean_r_true[-1]),
        "r90_120min_mean_generated_um": float(mean_r_gen[-1]),
        "r90_120min_sd_true_um": float(sd_r_true[-1]),
        "r90_120min_sd_generated_um": float(sd_r_gen[-1]),
        "max_postinitial_tail100_mass_fraction_difference_percentage_points": float(100 * np.max(np.abs(tail_true[1:] - tail_gen[1:]))),
    }
    return row, {"dsd_tv": dsd_tv, "r90_bin_tv": bin_tv,
                 "r90_mean_true": mean_r_true, "r90_mean_generated": mean_r_gen,
                 "r90_sd_true": sd_r_true, "r90_sd_generated": sd_r_gen,
                 "r90_true_probs": np.asarray(true_prob), "r90_generated_probs": np.asarray(gen_prob)}


def representation_check(data: DSDData, true_idx: np.ndarray, pca, test: str) -> dict:
    flat = data.cdf[true_idx].reshape(len(true_idx), -1)
    reconstructed = enforce_cdf(pca.inverse_transform(pca.transform(flat)).reshape(-1, N_TIME, N_BINS))
    true_bins = quantile_bin(data.cdf[true_idx])
    rebuilt_bins = quantile_bin(reconstructed)
    score, _ = compare(data, true_idx, reconstructed, test, "oracle_test_latent_reconstruction")
    return {
        "test": test,
        "training_pca_variance_fraction": float(pca.explained_variance_ratio_.sum()),
        "heldout_exact_r90_bin_fraction_postinitial": float(np.mean(true_bins[:, 1:] == rebuilt_bins[:, 1:])),
        "heldout_exact_r90_bin_fraction_120min": float(np.mean(true_bins[:, -1] == rebuilt_bins[:, -1])),
        "max_postinitial_mass_dsd_tv_1000_percent": score["max_postinitial_mass_dsd_tv_1000_percent"],
    }


def plot_retro(data: DSDData, curves: dict, output: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(13.4, 7.8), sharex=True, constrained_layout=True)
    colors = {"nearest_real_members": "#61718a", "neural_dsd_first": "#147c79"}
    for row, n in enumerate((2048, 4096)):
        for method in ("nearest_real_members", "neural_dsd_first"):
            result = curves[(n, method)]
            axes[row, 0].plot(data.time_min, result["dsd_tv"], color=colors[method], lw=1.8, label=method.replace("_", " "))
            axes[row, 1].plot(data.time_min, result["r90_bin_tv"], color=colors[method], lw=1.8, label=method.replace("_", " "))
        axes[row, 0].set_ylabel(f"{n:,} SDs/cell\nDSD TV (%)")
        axes[row, 1].set_ylabel(f"{n:,} SDs/cell\nr₉₀-bin TV (%)")
        for ax in axes[row]:
            ax.grid(alpha=0.22)
            ax.set_ylim(bottom=0)
    axes[0, 0].set_title("1,000-bin mean mass-DSD discrepancy")
    axes[0, 1].set_title("Distribution of exact r₉₀ bins across members")
    for ax in axes[-1]:
        ax.set_xlabel("saved time (min)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=2, loc="upper center", frameon=False, bbox_to_anchor=(0.5, 1.05))
    fig.suptitle("DSD-first retrospective resolution tests (not a fresh blind test)", y=1.10, fontsize=14)
    fig.savefig(output / "01_dsd_first_resolution_tests.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(12.8, 7.1), sharex=True, constrained_layout=True)
    for row, n in enumerate((2048, 4096)):
        observed = curves[(n, "neural_dsd_first")]
        for col, key in enumerate(("r90_mean", "r90_sd")):
            ax = axes[row, col]
            ax.plot(data.time_min, observed[f"{key}_true"], color="black", lw=2.0,
                    label="20 held-out CLEO members")
            for method in ("nearest_real_members", "neural_dsd_first"):
                ax.plot(data.time_min, curves[(n, method)][f"{key}_generated"],
                        color=colors[method], lw=1.6, label=method.replace("_", " "))
            ax.set_ylabel(f"{n:,} SDs/cell\n{key[4:]} r₉₀ (µm)")
            ax.grid(alpha=0.22)
            ax.set_ylim(bottom=0)
    axes[0, 0].set_title("Mean of member r₉₀ values")
    axes[0, 1].set_title("Member-to-member SD of r₉₀")
    for ax in axes[-1]:
        ax.set_xlabel("saved time (min)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=3, loc="upper center", frameon=False,
               bbox_to_anchor=(0.5, 1.04))
    fig.suptitle("r₉₀ derived from the 1,000-bin DSD (retrospective tests)", y=1.10, fontsize=14)
    fig.savefig(output / "02_r90_mean_spread.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--draws", type=int, default=300)
    args = parser.parse_args()
    if args.draws < 100:
        raise ValueError("At least 100 synthetic draws needed for bin-distribution comparison")
    args.output.mkdir(parents=True, exist_ok=True)
    data = load_data(base.CACHE)
    rows, representation, scales = [], [], []
    curves = {}

    # Whole-member cross-validation at known resolutions. Five members are
    # held out per resolution per fold; no time slice enters training alone.
    for fold in range(4):
        test_mask = (data.member - 1) // 5 == fold
        train_idx, test_idx = np.flatnonzero(~test_mask), np.flatnonzero(test_mask)
        assert not set(train_idx).intersection(test_idx)
        pca, model = fit_representation_and_mean(data, train_idx)
        for n in base.RESOLUTIONS:
            target_idx = test_idx[data.ncell[test_idx] == n]
            predicted, factor, source = predict_cdf(data, train_idx, n, pca, model, args.draws, SEED + 100 * fold + n)
            empirical = empirical_baseline(data, train_idx, n, args.draws, SEED + 200 * fold + n)
            for method, sample in (("neural_dsd_first", predicted), ("nearest_real_members", empirical)):
                row, _ = compare(data, target_idx, sample, "seen_members", method)
                rows.append({**row, "fold": fold, "target_ncell": n})
            scales.append({"test": "seen_members", "fold": fold, "target_ncell": n, "source_ncell": source, "factor": factor})

    # Already-inspected target resolutions: strictly retrospective comparisons.
    for n in (2048, 4096):
        train_idx = np.flatnonzero(data.ncell < n)
        test_idx = np.flatnonzero(data.ncell == n)
        pca, model = fit_representation_and_mean(data, train_idx)
        label = f"retrospective_extrapolate_{n}"
        representation.append(representation_check(data, test_idx, pca, label))
        predicted, factor, source = predict_cdf(data, train_idx, n, pca, model, args.draws, SEED + n)
        empirical = empirical_baseline(data, train_idx, n, args.draws, SEED + 1000 + n)
        for method, sample in (("neural_dsd_first", predicted), ("nearest_real_members", empirical)):
            row, curve = compare(data, test_idx, sample, label, method)
            rows.append({**row, "fold": 0, "target_ncell": n})
            curves[(n, method)] = curve
        scales.append({"test": label, "fold": 0, "target_ncell": n, "source_ncell": source, "factor": factor})

    base.write_csv(args.output / "scores.csv", rows)
    base.write_csv(args.output / "representation_gate.csv", representation)
    base.write_csv(args.output / "training_only_residual_scales.csv", scales)
    plot_retro(data, curves, args.output)
    manifest = {
        "status": "exploratory_dsd_first_not_CLEO",
        "training_members_per_resolution": 20,
        "memberwise_seen_resolution_folds": 4,
        "retrospective_resolution_checks": [2048, 4096],
        "fresh_blind_resolution_validation": False,
        "dsd_bins": 1000,
        "cdf_pca_components": N_COMPONENTS,
        "r90_definition": "first 1000-bin CDF crossing 0.9; geometric radius-bin midpoint",
        "above_training_resolution_cohort_written": False,
        "seed": SEED,
        "draws_per_prediction": args.draws,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "input_files_sha256": data.input_hashes,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "score_rows": len(rows),
                      "above_training_resolution_cohort_written": False}, indent=2))


if __name__ == "__main__":
    main()
