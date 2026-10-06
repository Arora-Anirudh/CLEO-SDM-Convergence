#!/usr/bin/env python3
"""Exploratory, member-wise validation of a 2-D CLEO stochastic emulator.

This is *not* a CLEO member generator.  Samples in the output are conditional
model draws and must never enter the original convergence bootstrap as new runs.

The compact member cache is represented by six complete diagnostic trajectories
and a 25-bin mass-DSD shape at every stored time.  Separate PCA reductions are
followed by either a regularized asymptotic mean model or a small neural mean
model, with a shrinkage-covariance stochastic latent residual.  One latent draw
generates an entire member trajectory, preserving learned time correlations.

The two tests are distinct: (1) unseen members at resolutions used in training;
(2) an entirely unseen *higher* resolution under the same initial-radius support.
The 8192 cohort is excluded from the clean extrapolation test because its
initial-radius support differs from that of the 128--4096 cohorts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
# The available macOS Anaconda Python 3.12 has an older setuptools/joblib
# combination that still imports the removed stdlib distutils module.  This
# compatibility shim only affects this process; no installed package is edited.
try:
    import distutils  # noqa: F401
except ModuleNotFoundError:
    import pkgutil
    import zipimport

    if not hasattr(pkgutil, "ImpImporter"):
        pkgutil.ImpImporter = zipimport.zipimporter
    import setuptools._distutils as distutils

    sys.modules["distutils"] = distutils
from sklearn.covariance import LedoitWolf
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "results/cache/constthermo2d_fixedgrid_production_v1"
DEFAULT_OUTPUT = ROOT / "results/analysis/constthermo2d_stochastic_emulator_v1"
RESOLUTIONS = (128, 256, 512, 1024, 2048, 4096)
METRICS = (
    "lambda0_m3",
    "lambda2_um2_m3",
    "lambda3_um3_m3",
    "lambda6_um6_m3",
    "mass_weighted_terminal_speed_ms",
    "mass_weighted_r90_um",
)
METRIC_LABELS = (
    r"$\lambda_0$",
    r"$\lambda_2$",
    r"$\lambda_3$",
    r"$\lambda_6$",
    "mass-weighted fall speed",
    r"mass-weighted $r_{90}$",
)
N_FINE, N_COARSE = 500, 25
N_TIME = 61
SEED = 20261001


@dataclass
class Data:
    ncell: np.ndarray
    member: np.ndarray
    metrics: np.ndarray  # member, diagnostic, time
    fractions: np.ndarray  # member, time, coarse mass-DSD bin
    time_min: np.ndarray
    coarse_edges_um: np.ndarray
    input_hashes: dict[str, str]


def load_data(cache: Path) -> Data:
    cells, members, metrics, fractions = [], [], [], []
    hashes: dict[str, str] = {}
    time_ref = edges_ref = None
    for n in RESOLUTIONS:
        for member in range(1, 21):
            path = cache / f"ncell{n:04d}" / f"member{member:03d}.npz"
            if not path.is_file():
                raise FileNotFoundError(path)
            hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
            with np.load(path) as z:
                time = np.asarray(z["time_min"], dtype=float)
                edges = np.asarray(z["radius_edges_500_um"], dtype=float)
                if time.shape != (N_TIME,) or edges.shape != (N_FINE + 1,):
                    raise ValueError(f"Unexpected cache geometry: {path}")
                if time_ref is None:
                    time_ref, edges_ref = time.copy(), edges.copy()
                elif not (np.array_equal(time, time_ref) and np.array_equal(edges, edges_ref)):
                    raise ValueError(f"Mismatched time or radius grid: {path}")
                obs = np.stack([z[key] for key in METRICS]).astype(float)
                density = np.asarray(z["mass_dsd_500_g_m3"], dtype=float)
                if obs.shape != (len(METRICS), N_TIME) or density.shape != (N_TIME, N_FINE):
                    raise ValueError(f"Unexpected diagnostic shape: {path}")
                if not (np.isfinite(obs).all() and np.isfinite(density).all()):
                    raise ValueError(f"Nonfinite diagnostic: {path}")
                if np.any(obs <= 0) or np.any(density < 0):
                    raise ValueError(f"Nonpositive physical diagnostic: {path}")
                mass = density * np.diff(np.log(edges))[None, :]
                mass25 = mass.reshape(N_TIME, N_COARSE, N_FINE // N_COARSE).sum(axis=2)
                denom = mass25.sum(axis=1, keepdims=True)
                if np.any(denom <= 0):
                    raise ValueError(f"Empty DSD: {path}")
                cells.append(n)
                members.append(member)
                metrics.append(obs)
                fractions.append(mass25 / denom)
    return Data(
        np.asarray(cells), np.asarray(members), np.asarray(metrics),
        np.asarray(fractions), time_ref, edges_ref[:: N_FINE // N_COARSE], hashes,
    )


class Representation:
    def __init__(self, n_components: int = 24):
        self.n_components = n_components

    def fit(self, metrics: np.ndarray, fractions: np.ndarray) -> "Representation":
        logm = np.log10(metrics)
        self.mean = logm.mean(axis=(0, 2), keepdims=True)
        self.scale = np.maximum(logm.std(axis=(0, 2), keepdims=True), 1e-5)
        a = ((logm - self.mean) / self.scale).reshape(len(metrics), -1)
        b = np.sqrt(fractions).reshape(len(metrics), -1)
        self.pca_metrics = PCA(n_components=min(self.n_components, len(metrics) - 1), svd_solver="randomized", random_state=SEED).fit(a)
        self.pca_dsd = PCA(n_components=min(self.n_components, len(metrics) - 1), svd_solver="randomized", random_state=SEED).fit(b)
        return self

    def transform(self, metrics: np.ndarray, fractions: np.ndarray) -> np.ndarray:
        a = ((np.log10(metrics) - self.mean) / self.scale).reshape(len(metrics), -1)
        b = np.sqrt(fractions).reshape(len(metrics), -1)
        return np.column_stack((self.pca_metrics.transform(a), self.pca_dsd.transform(b)))

    def inverse(self, latent: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        latent = np.atleast_2d(latent)
        p = self.pca_metrics.n_components_
        a = self.pca_metrics.inverse_transform(latent[:, :p]).reshape(-1, len(METRICS), N_TIME)
        # Guard numerical overflow in an unsupported extrapolation, but record the
        # frequency separately in validation rather than accepting it as physics.
        metrics = 10.0 ** np.clip(a * self.scale + self.mean, -30, 30)
        b = self.pca_dsd.inverse_transform(latent[:, p:]).reshape(-1, N_TIME, N_COARSE)
        b = np.maximum(b, 0.0) ** 2
        fractions = b / np.maximum(b.sum(axis=2, keepdims=True), 1e-30)
        return metrics, fractions

    def explained(self) -> dict[str, float]:
        return {
            "diagnostic_pca_variance_fraction": float(self.pca_metrics.explained_variance_ratio_.sum()),
            "dsd_pca_variance_fraction": float(self.pca_dsd.explained_variance_ratio_.sum()),
        }


def input_features(ncell: np.ndarray) -> np.ndarray:
    n = np.asarray(ncell, dtype=float)
    return np.column_stack((np.log2(n / 128.0), np.sqrt(128.0 / n)))


class ConditionalEmulator:
    def __init__(self, method: str):
        if method not in ("ridge", "neural"):
            raise ValueError(method)
        self.method = method

    def fit(self, ncell: np.ndarray, latent: np.ndarray) -> "ConditionalEmulator":
        x = input_features(ncell)
        self.xmean = x.mean(axis=0)
        self.xstd = np.maximum(x.std(axis=0), 1e-9)
        x = (x - self.xmean) / self.xstd
        self.ymean = latent.mean(axis=0)
        self.ystd = np.maximum(latent.std(axis=0), 1e-8)
        y = (latent - self.ymean) / self.ystd
        if self.method == "ridge":
            design = np.column_stack((x, x[:, 1] ** 2))
            self.model = Ridge(alpha=15.0).fit(design, y)
        else:
            self.model = MLPRegressor(
                hidden_layer_sizes=(12, 12), activation="tanh", solver="adam",
                alpha=0.5, learning_rate_init=0.002, max_iter=1200,
                early_stopping=True, validation_fraction=0.2,
                n_iter_no_change=60, random_state=SEED,
            ).fit(x, y)

        # Separate within-resolution member variability from mean-model bias.
        residual = np.empty_like(latent)
        levels = np.unique(ncell)
        rms = []
        for level in levels:
            sel = ncell == level
            residual[sel] = latent[sel] - latent[sel].mean(axis=0)
            rms.append(float(np.sqrt(np.mean(np.sum(residual[sel] ** 2, axis=1)))))
        self.levels = levels
        self.rms = np.asarray(rms)
        slope, intercept = np.polyfit(np.log2(levels), np.log(np.maximum(self.rms, 1e-8)), 1)
        # An unconstrained positive slope is a poor basis for high-N generation.
        self.slope = float(np.clip(slope, -1.0, 0.0))
        self.intercept = float(intercept)
        scaled = residual / np.maximum(self._scale(ncell), 1e-9)[:, None]
        self.cov = LedoitWolf().fit(scaled).covariance_
        return self

    def _scale(self, ncell: np.ndarray) -> np.ndarray:
        n = np.atleast_1d(np.asarray(ncell, dtype=float))
        return np.exp(self.intercept + self.slope * np.log2(n))

    def mean(self, ncell: np.ndarray) -> np.ndarray:
        x = (input_features(np.atleast_1d(ncell)) - self.xmean) / self.xstd
        if self.method == "ridge":
            x = np.column_stack((x, x[:, 1] ** 2))
        return self.model.predict(x) * self.ystd + self.ymean

    def sample(self, ncell: int, count: int, seed: int) -> np.ndarray:
        rng = np.random.default_rng(seed)
        noise = rng.multivariate_normal(np.zeros(len(self.ymean)), self.cov, size=count)
        return self.mean(np.full(count, ncell)) + self._scale(np.full(count, ncell))[:, None] * noise


def fit_model(data: Data, train_idx: np.ndarray, method: str) -> tuple[Representation, ConditionalEmulator]:
    rep = Representation().fit(data.metrics[train_idx], data.fractions[train_idx])
    latent = rep.transform(data.metrics[train_idx], data.fractions[train_idx])
    model = ConditionalEmulator(method).fit(data.ncell[train_idx], latent)
    return rep, model


def compare(data: Data, test_idx: np.ndarray, generated_m: np.ndarray, generated_f: np.ndarray,
            label: str, method: str, train_max: int, fold: int) -> list[dict]:
    rows: list[dict] = []
    test_m, test_f = data.metrics[test_idx], data.fractions[test_idx]
    sample_n = len(test_idx)
    assert sample_n > 0
    for j, name in enumerate(METRICS):
        for minute in (30, 60, 90, 120):
            tidx = int(np.argmin(abs(data.time_min - minute)))
            obs = test_m[:, j, tidx]
            synth = generated_m[:, j, tidx]
            obs_mean = float(obs.mean())
            synth_mean = float(synth.mean())
            lo, hi = np.quantile(synth, [0.05, 0.95])
            rows.append({
                "test": label, "method": method, "train_max_ncell": train_max,
                "fold": fold, "metric": name, "minute": minute,
                "n_heldout_members": sample_n,
                "mean_symmetric_error_percent": 200 * abs(synth_mean - obs_mean) / max(abs(synth_mean) + abs(obs_mean), 1e-30),
                "observed_member_fraction_in_90pct_predictive_interval": float(np.mean((obs >= lo) & (obs <= hi))),
                "observed_mean": obs_mean, "generated_mean": synth_mean,
                "observed_member_std": float(obs.std(ddof=1)) if sample_n > 1 else 0.0,
                "generated_member_std": float(synth.std(ddof=1)),
            })
    for minute in (30, 60, 90, 120):
        tidx = int(np.argmin(abs(data.time_min - minute)))
        p = test_f[:, tidx].mean(axis=0)
        q = generated_f[:, tidx].mean(axis=0)
        tv = 50.0 * float(np.abs(p - q).sum())
        rows.append({
            "test": label, "method": method, "train_max_ncell": train_max,
            "fold": fold, "metric": "mass_dsd_25_tv_percent", "minute": minute,
            "n_heldout_members": sample_n, "mean_symmetric_error_percent": tv,
            "observed_member_fraction_in_90pct_predictive_interval": "",
            "observed_mean": "", "generated_mean": "",
            "observed_member_std": "", "generated_member_std": "",
        })
    return rows


def compare_alltime(data: Data, test_idx: np.ndarray, generated_m: np.ndarray,
                    generated_f: np.ndarray, label: str, method: str) -> list[dict]:
    """Descriptive all-postinitial checks; time points are not independent cases."""
    test_m, test_f = data.metrics[test_idx], data.fractions[test_idx]
    rows = []
    for j, name in enumerate(METRICS):
        observed = test_m[:, j, 1:]
        generated = generated_m[:, j, 1:]
        om, gm = observed.mean(axis=0), generated.mean(axis=0)
        error = 200 * np.abs(om - gm) / np.maximum(np.abs(om) + np.abs(gm), 1e-30)
        lo, hi = np.quantile(generated, [0.05, 0.95], axis=0)
        rows.append({
            "test": label, "method": method, "metric": name,
            "max_postinitial_mean_symmetric_error_percent": float(error.max()),
            "time_of_max_error_min": float(data.time_min[1:][error.argmax()]),
            "alltime_90pct_member_coverage_descriptive": float(np.mean((observed >= lo) & (observed <= hi))),
        })
    p = test_f[:, 1:].mean(axis=0)
    q = generated_f[:, 1:].mean(axis=0)
    tv = 50 * np.abs(p - q).sum(axis=1)
    rows.append({
        "test": label, "method": method, "metric": "mass_dsd_25_tv_percent",
        "max_postinitial_mean_symmetric_error_percent": float(tv.max()),
        "time_of_max_error_min": float(data.time_min[1:][tv.argmax()]),
        "alltime_90pct_member_coverage_descriptive": "",
    })
    return rows


def empirical_baseline(data: Data, train_idx: np.ndarray, test_n: int, count: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    levels = np.unique(data.ncell[train_idx])
    nearest = int(levels[np.argmin(np.abs(np.log2(levels) - np.log2(test_n)))])
    pool = train_idx[data.ncell[train_idx] == nearest]
    rng = np.random.default_rng(seed)
    choose = rng.choice(pool, size=count, replace=True)
    return data.metrics[choose], data.fractions[choose]


def summarize(rows: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = (row["test"], row["method"], row["metric"])
        groups.setdefault(key, []).append(row)
    out = []
    for (test, method, metric), group in groups.items():
        out.append({
            "test": test, "method": method, "metric": metric,
            "median_mean_error_percent": float(np.median([r["mean_symmetric_error_percent"] for r in group])),
            "max_mean_error_percent": float(np.max([r["mean_symmetric_error_percent"] for r in group])),
            "mean_90pct_member_coverage": ("" if metric.startswith("mass_dsd") else float(np.mean([r["observed_member_fraction_in_90pct_predictive_interval"] for r in group]))),
        })
    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def plot_diagnostics(data: Data, rows: list[dict], output: Path) -> None:
    summary = summarize(rows)
    tests = ("seen_members", "extrapolate_2048", "extrapolate_4096")
    methods = ("empirical", "ridge", "neural")
    display_metrics = ("lambda0_m3", "lambda6_um6_m3", "mass_weighted_terminal_speed_ms", "mass_weighted_r90_um", "mass_dsd_25_tv_percent")
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.4), sharey=True, constrained_layout=True)
    colors = {"empirical": "#65748b", "ridge": "#157f7c", "neural": "#b36319"}
    ceiling = 0.0
    for ax, test in zip(axes, tests):
        for k, method in enumerate(methods):
            vals = []
            for metric in display_metrics:
                found = [r for r in summary if r["test"] == test and r["method"] == method and r["metric"] == metric]
                vals.append(found[0]["median_mean_error_percent"] if found else np.nan)
            ceiling = max(ceiling, float(np.nanmax(vals)))
            ax.plot(np.arange(len(vals)) + (k - 1) * 0.08, vals, marker="o", ms=5, lw=1.5, color=colors[method], label=method)
        ax.set_title(test.replace("_", " "))
        ax.set_xticks(range(len(display_metrics)), [r"$\lambda_0$", r"$\lambda_6$", "fall speed", r"$r_{90}$", "25-bin DSD TV"], rotation=35, ha="right")
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylim(0, ceiling * 1.15)
    axes[0].set_ylabel("Median held-out mean discrepancy (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.06))
    fig.suptitle("Exploratory emulator validation: independent held-out CLEO members", y=1.12, fontsize=13)
    fig.savefig(output / "01_heldout_validation.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_coverage(rows: list[dict], output: Path) -> None:
    summary = summarize(rows)
    tests = ("seen_members", "extrapolate_2048", "extrapolate_4096")
    methods = ("empirical", "ridge", "neural")
    display_metrics = ("lambda0_m3", "lambda6_um6_m3", "mass_weighted_terminal_speed_ms", "mass_weighted_r90_um")
    colors = {"empirical": "#65748b", "ridge": "#157f7c", "neural": "#b36319"}
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.3), sharey=True, constrained_layout=True)
    for ax, test in zip(axes, tests):
        ax.axhline(0.9, color="#aa3344", ls="--", lw=1.3, label="nominal 90%")
        for k, method in enumerate(methods):
            vals = []
            for metric in display_metrics:
                found = [r for r in summary if r["test"] == test and r["method"] == method and r["metric"] == metric]
                vals.append(found[0]["mean_90pct_member_coverage"] if found else np.nan)
            ax.plot(np.arange(len(vals)) + (k - 1) * 0.08, vals, marker="o", ms=5, lw=1.5, color=colors[method], label=method)
        ax.set_title(test.replace("_", " "))
        ax.set_xticks(range(len(display_metrics)), [r"$\lambda_0$", r"$\lambda_6$", "fall speed", r"$r_{90}$"], rotation=30, ha="right")
        ax.set_ylim(0, 1.03)
        ax.grid(axis="y", alpha=0.25)
    axes[0].set_ylabel("Fraction of withheld CLEO values inside model 90% interval")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(0.5, 1.06))
    fig.suptitle("The neural ensemble is under-dispersed at unseen resolutions", y=1.12, fontsize=13)
    fig.savefig(output / "03_predictive_coverage.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_backtest(data: Data, saved: dict, output: Path) -> None:
    n = 4096
    obs = data.metrics[data.ncell == n]
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 7.8), constrained_layout=True)
    indices = (0, 3, 4, 5)
    colors = {"empirical": "#65748b", "ridge": "#157f7c", "neural": "#b36319"}
    for ax, j in zip(axes.flat, indices):
        mean = obs[:, j].mean(axis=0)
        lo, hi = np.quantile(obs[:, j], [0.05, 0.95], axis=0)
        ax.fill_between(data.time_min, 100 * (lo / mean - 1), 100 * (hi / mean - 1), color="#1d3354", alpha=0.14, label="CLEO 5–95% member range")
        ax.axhline(0, color="#1d3354", lw=1.5, label="held-out CLEO mean")
        for method in ("empirical", "ridge", "neural"):
            arr = saved[method][0][:, j]
            ax.plot(data.time_min, 100 * (arr.mean(axis=0) / mean - 1), color=colors[method], lw=1.45, label=f"{method} mean")
        ax.set_title(METRIC_LABELS[j], fontsize=11)
        ax.set_xlabel("time (min)")
        ax.set_ylabel("difference from held-out CLEO mean (%)")
        ax.grid(alpha=0.22)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.04))
    fig.suptitle("Blind 4,096-SDs-per-cell backtest (trained through 2,048)", y=1.11, fontsize=14)
    fig.savefig(output / "02_resolution_backtest_4096.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--draws", type=int, default=300)
    args = parser.parse_args()
    if args.draws < 50:
        raise ValueError("At least 50 model draws needed for interval diagnostics")
    args.output.mkdir(parents=True, exist_ok=True)
    data = load_data(args.cache)
    raw_rows: list[dict] = []
    alltime_rows: list[dict] = []
    representation_stats: list[dict] = []
    backtest_4096: dict = {}

    # Four deterministic member folds: no member's time slices appear in both
    # training and test sets.  Across folds, each member is tested exactly once.
    for fold in range(4):
        test = (data.member - 1) // 5 == fold
        train_idx, test_idx = np.flatnonzero(~test), np.flatnonzero(test)
        for method in ("ridge", "neural"):
            rep, model = fit_model(data, train_idx, method)
            representation_stats.append({"test": "seen_members", "fold": fold, **rep.explained(), "residual_scale_slope_per_doubling": model.slope})
            for n in RESOLUTIONS:
                target_idx = test_idx[data.ncell[test_idx] == n]
                synth = rep.inverse(model.sample(n, args.draws, SEED + 100 * fold + n))
                raw_rows.extend(compare(data, target_idx, *synth, "seen_members", method, 4096, fold))
                empirical = empirical_baseline(data, train_idx, n, args.draws, SEED + 200 * fold + n)
                if method == "ridge":
                    raw_rows.extend(compare(data, target_idx, *empirical, "seen_members", "empirical", 4096, fold))

    # Leave a whole higher resolution unseen.  The 8192 run has a different
    # initial-radius support, so 4096 is the highest clean test of this kind.
    for heldout_n in (2048, 4096):
        train_idx = np.flatnonzero(data.ncell < heldout_n)
        test_idx = np.flatnonzero(data.ncell == heldout_n)
        for method in ("ridge", "neural"):
            rep, model = fit_model(data, train_idx, method)
            representation_stats.append({"test": f"extrapolate_{heldout_n}", "fold": 0, **rep.explained(), "residual_scale_slope_per_doubling": model.slope})
            synth = rep.inverse(model.sample(heldout_n, args.draws, SEED + 1000 + heldout_n))
            raw_rows.extend(compare(data, test_idx, *synth, f"extrapolate_{heldout_n}", method, int(data.ncell[train_idx].max()), 0))
            alltime_rows.extend(compare_alltime(data, test_idx, *synth, f"extrapolate_{heldout_n}", method))
            if heldout_n == 4096:
                backtest_4096[method] = synth
            if method == "ridge":
                empirical = empirical_baseline(data, train_idx, heldout_n, args.draws, SEED + 2000 + heldout_n)
                raw_rows.extend(compare(data, test_idx, *empirical, f"extrapolate_{heldout_n}", "empirical", int(data.ncell[train_idx].max()), 0))
                alltime_rows.extend(compare_alltime(data, test_idx, *empirical, f"extrapolate_{heldout_n}", "empirical"))
                if heldout_n == 4096:
                    backtest_4096["empirical"] = empirical

    write_csv(args.output / "heldout_scores_all.csv", raw_rows)
    summary = summarize(raw_rows)
    write_csv(args.output / "heldout_scores_summary.csv", summary)
    write_csv(args.output / "alltime_resolution_backtest.csv", alltime_rows)
    write_csv(args.output / "representation_checks.csv", representation_stats)
    plot_diagnostics(data, raw_rows, args.output)
    plot_backtest(data, backtest_4096, args.output)
    plot_coverage(raw_rows, args.output)

    # Generate separately labelled planning samples at a *seen* resolution.
    # Higher-resolution files are only written after inspecting the blind
    # backtest.  This script never auto-promotes extrapolation to evidence.
    train_idx = np.arange(len(data.ncell))
    rep, model = fit_model(data, train_idx, "neural")
    generated_m, generated_f = rep.inverse(model.sample(1024, args.draws, SEED + 1024))
    np.savez_compressed(
        args.output / "synthetic_1024_neural_exploratory_not_CLEO.npz",
        ncell=np.int32(1024), time_min=data.time_min, metric_names=np.asarray(METRICS),
        metric_trajectories=generated_m, coarse_radius_edges_um=data.coarse_edges_um,
        mass_dsd_25_bin_fractions=generated_f,
        interpretation="Model-generated planning samples; not independent CLEO members",
    )
    manifest = {
        "status": "exploratory_emulator_not_CLEO",
        "source": "2-D constthermo2d fixed-grid normal-sampling compact member cache",
        "resolutions": list(RESOLUTIONS), "members_per_resolution": 20,
        "observations_are_whole_member_trajectories": True,
        "timepoints_per_member": N_TIME, "mass_dsd_bins_generated": N_COARSE,
        "clean_resolution_backtests": [2048, 4096],
        "8192_excluded_from_clean_backtest": "different initial-radius support (4 nm–2 um vs 3 nm–3 um)",
        "higher_resolution_samples_written": False,
        "reason": "inspect held-out extrapolation performance before scenario generation",
        "seed": SEED, "draws_per_prediction": args.draws,
        "input_sha256": data.input_hashes,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(args.output), "validation_rows": len(raw_rows),
                      "summary_rows": len(summary), "higher_resolution_samples_written": False}, indent=2))


if __name__ == "__main__":
    main()
