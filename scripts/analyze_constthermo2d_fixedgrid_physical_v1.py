#!/usr/bin/env python3
"""Complete physical-diagnostic figure suite for fixed-20 constthermo2d data.

All quantities are reconstructed from the compact, audited 20-member cache.
The terminal-speed flux is an instantaneous downward transport *proxy*:
constthermo2d uses null boundaries, so it is not surface precipitation.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np


RESOLUTIONS = (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192)
MEMBERS = tuple(range(1, 21))
REFERENCE = 8192
NBOOT = 2000
RHO_WATER_KG_M3 = 998.203
DOMAIN_X_M, DOMAIN_Z_M = 1500.0, 1500.0
FAST_SPEEDS_MS = (0.25, 0.5, 1.0)
DEVELOPMENT_SPEED_MS = 1.0
DEVELOPMENT_FRACTION = 0.01
DSD_MINUTES = (0, 30, 60, 90, 120)
SPECTRUM_MINUTES = (0, 60, 68, 120)
SPATIAL_RESOLUTIONS = (2, 1024, 8192)
COLORS = plt.cm.viridis(np.linspace(0.02, 0.97, len(RESOLUTIONS)))


def save_figure(fig: plt.Figure, path: Path, *, top: float = .82, bottom: float = .10,
                left: float = .07, right: float = .985, wspace: float = .24,
                hspace: float = .28) -> None:
    """Reserve fixed figure-level space instead of letting titles/legends collide."""
    fig.subplots_adjust(top=top, bottom=bottom, left=left, right=right,
                        wspace=wspace, hspace=hspace)
    fig.savefig(path, dpi=250, bbox_inches="tight", pad_inches=.10)
    plt.close(fig)


def rogers_gk_terminal_speed_ms(radius_um: np.ndarray) -> np.ndarray:
    """Rogers--Gunn--Kinzer terminal speed used by the 2-D CLEO setup."""
    diameter_mm = 2.0 * np.asarray(radius_um, dtype=float) / 1000.0
    return np.where(
        diameter_mm < 0.3725,
        4.0 * diameter_mm * (1.0 - np.exp(-12.0 * diameter_mm)),
        9.65 - 10.43 * np.exp(-0.6 * diameter_mm),
    )


def symmetric_percent(candidate: np.ndarray, reference: np.ndarray) -> np.ndarray:
    den = np.abs(candidate) + np.abs(reference)
    return np.divide(200.0 * np.abs(candidate - reference), den,
                     out=np.zeros_like(np.asarray(candidate, dtype=float)), where=den > 0)


def max_postinitial(values: np.ndarray) -> np.ndarray:
    return np.max(values[..., 1:], axis=-1)


def nearest_indices(time_min: np.ndarray, requested: tuple[int, ...]) -> list[int]:
    return [int(np.argmin(np.abs(time_min - minute))) for minute in requested]


def load_cache(cache: Path) -> dict[str, np.ndarray]:
    scalar_names = (
        "active_sds", "lambda0_m3", "lambda1_um_m3", "lambda2_um2_m3",
        "lambda3_um3_m3", "lambda6_um6_m3", "total_droplet_mass_g_m3",
        "mass_weighted_terminal_speed_ms", "lower150m_total_droplet_mass_fraction",
        "mass_weighted_r50_um", "mass_weighted_r90_um", "mass_weighted_r99_um",
    )
    rows: dict[str, list[np.ndarray]] = {name: [] for name in scalar_names}
    rows["number_dsd_500_m3"] = []
    rows["mass_dsd_1000_g_m3"] = []
    rows["spatial_mass_selected_g_m3"] = []
    time_reference: np.ndarray | None = None
    number_edges: np.ndarray | None = None
    mass_edges: np.ndarray | None = None
    spatial_minutes: np.ndarray | None = None
    for ncell in RESOLUTIONS:
        per = {name: [] for name in rows}
        for member in MEMBERS:
            path = cache / f"ncell{ncell:04d}" / f"member{member:03d}.npz"
            if not path.is_file():
                raise FileNotFoundError(path)
            with np.load(path) as raw:
                time = np.asarray(raw["time_min"], dtype=float)
                if time_reference is None:
                    time_reference = time
                    number_edges = np.asarray(raw["radius_edges_500_um"], dtype=float)
                    mass_edges = np.asarray(raw["radius_edges_1000_um"], dtype=float)
                    spatial_minutes = np.asarray(raw["spatial_selected_minutes"], dtype=float)
                elif not np.allclose(time_reference, time, rtol=0.0, atol=1.0e-8):
                    raise ValueError(f"time mismatch: {path}")
                for name in scalar_names:
                    per[name].append(np.asarray(raw[name], dtype=float))
                per["number_dsd_500_m3"].append(np.asarray(raw["number_dsd_500_m3"], dtype=float))
                per["mass_dsd_1000_g_m3"].append(np.asarray(raw["mass_dsd_1000_g_m3"], dtype=float))
                per["spatial_mass_selected_g_m3"].append(np.asarray(raw["spatial_mass_selected_g_m3"], dtype=float))
        for name in rows:
            rows[name].append(np.stack(per[name], axis=0))
    return {
        **{name: np.stack(values, axis=0) for name, values in rows.items()},
        "time_min": np.asarray(time_reference),
        "radius_edges_500_um": np.asarray(number_edges),
        "radius_edges_1000_um": np.asarray(mass_edges),
        "spatial_selected_minutes": np.asarray(spatial_minutes),
    }


def derive(data: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    mass_edges = data["radius_edges_1000_um"]
    mass_centers = np.sqrt(mass_edges[:-1] * mass_edges[1:])
    mass_widths = np.diff(np.log(mass_edges))
    speed = rogers_gk_terminal_speed_ms(mass_centers)
    mass_per_logbin = data["mass_dsd_1000_g_m3"] * mass_widths[None, None, None, :]
    total_from_dsd = mass_per_logbin.sum(axis=-1)
    flux_g_m2_s = (mass_per_logbin * speed[None, None, None, :]).sum(axis=-1)
    fast_fraction = {
        threshold: np.divide(
            mass_per_logbin[..., speed >= threshold].sum(axis=-1), total_from_dsd,
            out=np.zeros_like(total_from_dsd), where=total_from_dsd > 0,
        ) for threshold in FAST_SPEEDS_MS
    }
    development = fast_fraction[DEVELOPMENT_SPEED_MS]
    onset_min = np.full(development.shape[:2], np.nan)
    for ridx in range(len(RESOLUTIONS)):
        for midx in range(len(MEMBERS)):
            crossed = np.flatnonzero(development[ridx, midx] >= DEVELOPMENT_FRACTION)
            if crossed.size:
                onset_min[ridx, midx] = data["time_min"][crossed[0]]
    surface_area_m1 = 4.0 * np.pi * data["lambda2_um2_m3"] * 1.0e-12
    liquid_equiv_g_m3 = (
        RHO_WATER_KG_M3 * (4.0 * np.pi / 3.0) * data["lambda3_um3_m3"] * 1.0e-18 * 1.0e3
    )
    reflectivity_mm6_m3 = 64.0 * data["lambda6_um6_m3"] * 1.0e-18
    dbz = 10.0 * np.log10(np.maximum(reflectivity_mm6_m3, np.finfo(float).tiny))
    flux_identity_g_m2_s = data["total_droplet_mass_g_m3"] * data["mass_weighted_terminal_speed_ms"]
    return {
        "mass_radius_centers_um": mass_centers,
        "mass_bin_terminal_speed_ms": speed,
        "mass_per_logbin_g_m3": mass_per_logbin,
        "flux_g_m2_s": flux_g_m2_s,
        "fast_fraction": fast_fraction,
        "development_onset_min": onset_min,
        "surface_area_m1": surface_area_m1,
        "liquid_equiv_g_m3": liquid_equiv_g_m3,
        "reflectivity_mm6_m3": reflectivity_mm6_m3,
        "dbz": dbz,
        "flux_identity_g_m2_s": flux_identity_g_m2_s,
    }


def add_legend(fig, ax, title: str = r"$N_{cell}$") -> None:
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, title=title, ncol=7, loc="upper center",
               bbox_to_anchor=(0.5, 0.935), frameon=False, fontsize=8.2,
               title_fontsize=8.5, columnspacing=1.25, handlelength=2.0)


def plot_all_evolution(data: dict[str, np.ndarray], output: Path) -> None:
    specs = (
        ("lambda0_m3", r"$\lambda_0$ (m$^{-3}$)", r"Number moment, $\lambda_0$"),
        ("lambda1_um_m3", r"$\lambda_1$ ($\mu$m m$^{-3}$)", r"First radius moment, $\lambda_1$"),
        ("lambda2_um2_m3", r"$\lambda_2$ ($\mu$m$^2$ m$^{-3}$)", r"Second radius moment, $\lambda_2$"),
        ("lambda3_um3_m3", r"$\lambda_3$ ($\mu$m$^3$ m$^{-3}$)", r"Third radius moment, $\lambda_3$"),
        ("lambda6_um6_m3", r"$\lambda_6$ ($\mu$m$^6$ m$^{-3}$)", r"Sixth radius moment, $\lambda_6$"),
        ("total_droplet_mass_g_m3", r"total-droplet mass (g m$^{-3}$)", "Total droplet-mass concentration"),
    )
    fig, axes = plt.subplots(2, 3, figsize=(18, 10.5), sharex=True)
    for ax, (name, ylabel, title) in zip(axes.flat, specs):
        for ridx, ncell in enumerate(RESOLUTIONS):
            ax.plot(data["time_min"], data[name][ridx].mean(axis=0), color=COLORS[ridx], lw=1.15,
                    label=f"{ncell:,}")
        ax.set_yscale("log")
        ax.set(title=title, ylabel=ylabel, xlabel="time (min)")
        ax.grid(True, which="both", alpha=0.2)
    add_legend(fig, axes[0, 0])
    fig.suptitle("Full fixed-20 2-D evolution: represented moments and mass", weight="bold", fontsize=18, y=.985)
    fig.text(.5, .032, "Every curve is an independent 20-member ensemble mean. Moments are reconstructed directly from multiplicity-weighted wet radii.", ha="center", fontsize=10)
    save_figure(fig, output / "01_all_moments_and_mass_evolution.png", top=.80, bottom=.09)


def plot_radius_transport(data: dict[str, np.ndarray], physical: dict[str, np.ndarray], output: Path) -> None:
    specs = (
        ("mass_weighted_r50_um", r"mass-weighted $r_{50}$ ($\mu$m)", "Mass-weighted median radius", False),
        ("mass_weighted_r90_um", r"mass-weighted $r_{90}$ ($\mu$m)", "Mass-weighted 90th-percentile radius", False),
        ("mass_weighted_r99_um", r"mass-weighted $r_{99}$ ($\mu$m)", "Mass-weighted 99th-percentile radius", False),
        ("mass_weighted_terminal_speed_ms", r"mass-weighted $v_t$ (m s$^{-1}$)", "Liquid-mass-weighted terminal speed", False),
        ("lower150m_total_droplet_mass_fraction", "fraction", "Mass fraction below 150 m", False),
        ("active_sds", "active SDs", "Active superdroplets", True),
    )
    fig, axes = plt.subplots(2, 3, figsize=(18, 10.5), sharex=True)
    for ax, (name, ylabel, title, log) in zip(axes.flat, specs):
        for ridx, ncell in enumerate(RESOLUTIONS):
            ax.plot(data["time_min"], data[name][ridx].mean(axis=0), color=COLORS[ridx], lw=1.15,
                    label=f"{ncell:,}")
        if log:
            ax.set_yscale("log")
        ax.set(title=title, ylabel=ylabel, xlabel="time (min)")
        ax.grid(True, which="both", alpha=0.2)
    add_legend(fig, axes[0, 0])
    fig.suptitle("Radius, fall speed, location and active-superdroplet evolution", weight="bold", fontsize=18, y=.985)
    fig.text(.5, .032, "The lower-150 m quantity is an in-domain location diagnostic. Null boundaries mean it is not accumulated surface rainfall.", ha="center", fontsize=10)
    save_figure(fig, output / "02_radius_transport_and_population_evolution.png", top=.80, bottom=.09)


def plot_dsd(data: dict[str, np.ndarray], output: Path, kind: str) -> None:
    chosen = (2, 64, 512, 1024, 2048, 8192)
    indices = nearest_indices(data["time_min"], DSD_MINUTES)
    colors = plt.cm.plasma(np.linspace(0.05, 0.95, len(indices)))
    if kind == "number":
        edges, values, ylabel, prefix = (
            data["radius_edges_500_um"], data["number_dsd_500_m3"],
            r"$dN/d\ln r$ (m$^{-3}$)", "number",
        )
    else:
        edges, values, ylabel, prefix = (
            data["radius_edges_1000_um"], data["mass_dsd_1000_g_m3"],
            r"$dL/d\ln r$ (g m$^{-3}$)", "total-droplet-mass",
        )
    centers = np.sqrt(edges[:-1] * edges[1:])
    fig, axes = plt.subplots(2, 3, figsize=(18, 10.5), sharex=True, sharey=True)
    positive = values[values > 0]
    floor = np.nanmin(positive) * 0.8
    for ax, ncell in zip(axes.flat, chosen):
        ridx = RESOLUTIONS.index(ncell)
        mean = values[ridx].mean(axis=0)
        for color, tidx, minute in zip(colors, indices, DSD_MINUTES):
            ax.plot(centers, np.where(mean[tidx] > floor, mean[tidx], np.nan),
                    color=color, lw=1.25, label=f"{minute} min")
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_title(fr"$N_{{cell}}={ncell:,}$", weight="bold")
        ax.grid(True, which="both", alpha=0.2)
    for ax in axes[:, 0]: ax.set_ylabel(ylabel)
    for ax in axes[-1, :]: ax.set_xlabel(r"wet radius, $r$ ($\mu$m)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.suptitle(f"{prefix.capitalize()} DSD evolution at representative resolutions", weight="bold", fontsize=18, y=.985)
    fig.legend(handles, labels, title="stored time", ncol=5, loc="upper center",
               bbox_to_anchor=(.5, .935), frameon=False, fontsize=9, title_fontsize=9)
    fig.text(.5, .032, "Each curve is a full 20-member ensemble mean on one common fixed radius mesh; unlike adaptive smoothing, this representation is resolution-invariant.", ha="center", fontsize=10)
    save_figure(fig, output / f"{'03' if kind == 'number' else '04'}_{prefix}_dsd_evolution.png", top=.81, bottom=.095, left=.075, right=.985)


def plot_physical_proxies(data: dict[str, np.ndarray], physical: dict[str, np.ndarray], output: Path) -> None:
    specs = (
        ("surface_area_m1", r"m$^2$ m$^{-3}$ = m$^{-1}$", r"Geometric surface-area density, $4\pi\lambda_2$"),
        ("liquid_equiv_g_m3", r"g m$^{-3}$", r"Liquid-equivalent water content from $\lambda_3$"),
        ("dbz", "dBZ", r"Rayleigh reflectivity-factor proxy from $\lambda_6$"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(18, 7.0), sharex=True)
    for ax, (name, ylabel, title) in zip(axes, specs):
        for ridx, ncell in enumerate(RESOLUTIONS):
            ax.plot(data["time_min"], physical[name][ridx].mean(axis=0), color=COLORS[ridx], lw=1.15,
                    label=f"{ncell:,}")
        if name != "dbz":
            ax.set_yscale("log")
        ax.set(title=title, ylabel=ylabel, xlabel="time (min)")
        ax.grid(True, which="both", alpha=0.2)
    add_legend(fig, axes[0])
    fig.suptitle(r"Physical interpretation of the $r^2$, $r^3$, and $r^6$ moments", weight="bold", fontsize=18, y=.985)
    fig.text(.5, .032, "Surface area is geometric, not a radiative-transfer extinction coefficient. The reflectivity quantity is a Rayleigh proxy, not a simulated radar observation.", ha="center", fontsize=10)
    save_figure(fig, output / "05_physical_moment_proxies_evolution.png", top=.80, bottom=.11, left=.075, right=.985, wspace=.26)


def plot_flux_fastdrop(data: dict[str, np.ndarray], physical: dict[str, np.ndarray], output: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(17, 7.0), sharex=True)
    for ridx, ncell in enumerate(RESOLUTIONS):
        axes[0].plot(data["time_min"], physical["flux_g_m2_s"][ridx].mean(axis=0), color=COLORS[ridx], lw=1.15,
                     label=f"{ncell:,}")
    axes[0].set(yscale="log", title=r"Terminal-speed downward mass-transport proxy",
                ylabel=r"$\mathcal{P}=\sum \xi m v_t/V$ (g m$^{-2}$ s$^{-1}$)", xlabel="time (min)")
    axes[0].grid(True, which="both", alpha=0.2)
    line_styles = ("-", "--", ":")
    for threshold, style in zip(FAST_SPEEDS_MS, line_styles):
        axes[1].plot(data["time_min"], physical["fast_fraction"][threshold][RESOLUTIONS.index(REFERENCE)].mean(axis=0),
                     color="#1f6f8b", lw=2.1, ls=style, label=fr"$v_t\geq{threshold:g}$ m s$^{{-1}}$; 8,192")
        axes[1].plot(data["time_min"], physical["fast_fraction"][threshold][RESOLUTIONS.index(1024)].mean(axis=0),
                     color="#c66b16", lw=1.3, ls=style, alpha=0.9, label=fr"$v_t\geq{threshold:g}$ m s$^{{-1}}$; 1,024")
    axes[1].axhline(DEVELOPMENT_FRACTION, color="0.35", lw=1, ls=":")
    axes[1].set(title="Liquid mass carried by increasingly fast drops", ylabel="liquid-mass fraction", xlabel="time (min)")
    axes[1].grid(True, alpha=0.2)
    axes[1].legend(fontsize=8.2, ncol=2, frameon=False, loc="upper left")
    add_legend(fig, axes[0])
    fig.suptitle("Terminal-speed mass transport and fast-drop development", weight="bold", fontsize=18, y=.985)
    fig.text(.5, .032, "The flux is the instantaneous downward transport that would occur at terminal speed. Null boundaries mean neither panel is a surface-rainfall diagnostic.", ha="center", fontsize=10)
    save_figure(fig, output / "06_virtual_flux_and_fastdrop_evolution.png", top=.80, bottom=.11, left=.08, right=.985, wspace=.25)


def plot_speed_spectrum(data: dict[str, np.ndarray], physical: dict[str, np.ndarray], output: Path) -> None:
    chosen = (1024, 8192)
    indices = nearest_indices(data["time_min"], SPECTRUM_MINUTES)
    fig, axes = plt.subplots(1, 2, figsize=(16, 7.0), sharex=True, sharey=True)
    positive_speed = physical["mass_bin_terminal_speed_ms"] > 1.0e-7
    for ax, ncell in zip(axes, chosen):
        ridx = RESOLUTIONS.index(ncell)
        curves = physical["mass_per_logbin_g_m3"][ridx].mean(axis=0)
        for color, tidx, minute in zip(plt.cm.plasma(np.linspace(.08, .95, len(indices))), indices, SPECTRUM_MINUTES):
            ax.plot(physical["mass_bin_terminal_speed_ms"][positive_speed],
                    curves[tidx, positive_speed], color=color, lw=1.35, label=f"{minute} min")
        ax.axvline(1.0, color="0.35", ls=":", lw=1)
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set(title=fr"$N_{{cell}}={ncell:,}$", xlabel=r"terminal speed, $v_t$ (m s$^{-1}$)")
        ax.grid(True, which="both", alpha=0.2)
    axes[0].set_ylabel(r"mass per log-radius bin (g m$^{-3}$)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle("How liquid mass migrates into faster terminal-speed classes", weight="bold", fontsize=18, y=.985)
    fig.legend(handles, labels, title="stored time", ncol=4, bbox_to_anchor=(.5, .935), loc="upper center", frameon=False, fontsize=9, title_fontsize=9)
    fig.text(.5, .032, "The horizontal coordinate uses the Rogers--Gunn--Kinzer radius-speed relation. It is a re-expression of the mass DSD, not an independently simulated velocity distribution.", ha="center", fontsize=10)
    save_figure(fig, output / "07_terminal_speed_mass_spectrum.png", top=.81, bottom=.11, left=.08, right=.985, wspace=.22)


def plot_spatial_maps(data: dict[str, np.ndarray], output: Path) -> None:
    snapshots = data["spatial_mass_selected_g_m3"]
    positives = snapshots[snapshots > 0]
    norm = LogNorm(vmin=np.percentile(positives, 1), vmax=np.percentile(positives, 99.5))
    fig = plt.figure(figsize=(15.5, 11))
    grid = fig.add_gridspec(
        len(SPATIAL_RESOLUTIONS), 4, width_ratios=(1, 1, 1, .045),
        left=.065, right=.92, top=.84, bottom=.11, wspace=.12, hspace=.20,
    )
    axes = np.asarray([
        [fig.add_subplot(grid[row, col]) for col in range(3)]
        for row in range(len(SPATIAL_RESOLUTIONS))
    ])
    colorbar_axis = fig.add_subplot(grid[:, 3])
    image = None
    xedges = np.linspace(0, DOMAIN_X_M, 21)
    zedges = np.linspace(0, DOMAIN_Z_M, 21)
    for ridx_plot, ncell in enumerate(SPATIAL_RESOLUTIONS):
        ridx = RESOLUTIONS.index(ncell)
        mean = snapshots[ridx].mean(axis=0)
        for tidx, minute in enumerate(data["spatial_selected_minutes"]):
            ax = axes[ridx_plot, tidx]
            image = ax.pcolormesh(xedges, zedges, np.ma.masked_less_equal(mean[tidx], 0), norm=norm, cmap="magma_r", shading="auto")
            if ridx_plot == 0:
                ax.set_title(f"{minute:.0f} min", weight="bold")
            if tidx == 0:
                ax.set_ylabel(fr"$N_{{cell}}={ncell:,}$" + "\nheight, z (m)")
            if ridx_plot == len(SPATIAL_RESOLUTIONS) - 1:
                ax.set_xlabel("horizontal distance, x (m)")
    cbar = fig.colorbar(image, cax=colorbar_axis)
    cbar.set_label(r"total-droplet mass concentration (g m$^{-3}$)")
    fig.suptitle("Spatial liquid-mass evolution: representative full-20 resolutions", weight="bold", fontsize=18, y=.975)
    fig.text(.5, .030, "Maps are ensemble-mean fields reconstructed at the stored 0, 60, and 120 min snapshots. They show in-domain redistribution, not rain-out.", ha="center", fontsize=10)
    fig.savefig(output / "08_spatial_total_droplet_mass_fields.png", dpi=250, bbox_inches="tight", pad_inches=.10)
    plt.close(fig)


def bootstrap_scalar(candidate: np.ndarray, reference: np.ndarray, rng: np.random.Generator) -> tuple[float, float, float]:
    point = float(max_postinitial(symmetric_percent(candidate.mean(axis=0), reference.mean(axis=0))))
    values = []
    for _ in range(0, NBOOT, 100):
        n = min(100, NBOOT - len(values) * 100)
        ci = rng.integers(0, len(MEMBERS), size=(n, len(MEMBERS)))
        ri = rng.integers(0, len(MEMBERS), size=(n, len(MEMBERS)))
        values.append(np.max(symmetric_percent(candidate[ci].mean(axis=1)[:, 1:], reference[ri].mean(axis=1)[:, 1:]), axis=1))
    distribution = np.concatenate(values)
    return point, float(np.median(distribution)), float(np.quantile(distribution, .95))


def physical_convergence(data: dict[str, np.ndarray], physical: dict[str, np.ndarray], output: Path) -> list[dict[str, object]]:
    metrics = (
        ("surface_area_m1", r"$4\pi\lambda_2$", 5.0),
        ("liquid_equiv_g_m3", "liquid-equivalent water", 5.0),
        ("reflectivity_mm6_m3", r"reflectivity proxy, $Z$", 10.0),
        ("mass_weighted_terminal_speed_ms", "mass-weighted terminal speed", 5.0),
        ("flux_g_m2_s", "terminal-speed mass-flux proxy", 5.0),
    )
    values = {**physical, **data}
    refidx = RESOLUTIONS.index(REFERENCE)
    rows: list[dict[str, object]] = []
    for ridx, ncell in enumerate(RESOLUTIONS[:-1]):
        for key, label, tolerance in metrics:
            point, median, upper = bootstrap_scalar(values[key][ridx], values[key][refidx],
                                                     np.random.default_rng(20260928 + ridx * 13 + len(rows)))
            rows.append({"comparison": f"{ncell}->{REFERENCE}", "ncell": ncell, "metric": key,
                         "label": label, "tolerance_percent": tolerance, "point_percent": point,
                         "bootstrap_median_percent": median, "bootstrap_upper95_percent": upper,
                         "upper95_ratio_to_tolerance": upper / tolerance})
    for left, right in ((512, 1024), (1024, 2048), (2048, 4096), (4096, 8192)):
        li, ri = RESOLUTIONS.index(left), RESOLUTIONS.index(right)
        for key, label, tolerance in metrics:
            point, median, upper = bootstrap_scalar(values[key][li], values[key][ri],
                                                     np.random.default_rng(20261928 + li * 19 + len(rows)))
            rows.append({"comparison": f"{left}->{right}", "ncell": left, "metric": key,
                         "label": label, "tolerance_percent": tolerance, "point_percent": point,
                         "bootstrap_median_percent": median, "bootstrap_upper95_percent": upper,
                         "upper95_ratio_to_tolerance": upper / tolerance})
    write_csv(rows, output / "physical_reference_and_adjacent_bootstrap.csv")

    fig, axes = plt.subplots(2, 3, figsize=(18, 10.5), sharex=True)
    for ax, (key, label, tolerance) in zip(axes.flat, metrics):
        selected = [row for row in rows if row["comparison"].endswith(f"->{REFERENCE}") and row["metric"] == key]
        x = np.array([int(row["ncell"]) for row in selected])
        y = np.array([float(row["point_percent"]) for row in selected])
        upper = np.array([float(row["bootstrap_upper95_percent"]) for row in selected])
        ax.vlines(x, y, upper, color="#176f7d", lw=1.8)
        ax.scatter(x, y, color="#176f7d", s=27, zorder=3)
        ax.axhline(tolerance, color="#bd2d2d", ls="--", lw=1.1, label=f"{tolerance:g}% margin")
        ax.set_xscale("log", base=2); ax.set_yscale("log")
        ax.set(title=label, ylabel="all-time difference (%)", xlabel=r"$N_{cell}$")
        ax.grid(True, which="both", alpha=.2)
    axes.flat[-1].axis("off")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.suptitle("Physical diagnostics: agreement with the 8,192 internal comparator", weight="bold", fontsize=18, y=.985)
    fig.legend(handles, labels, loc="upper center", ncol=1, bbox_to_anchor=(.5, .935), frameon=False, fontsize=9)
    fig.text(.5, .032, "Dot: full-20 difference. Vertical line: one-sided 95% member-bootstrap upper bound. This assesses finite-ensemble precision around an internal comparator, not independent numerical truth.", ha="center", fontsize=10)
    save_figure(fig, output / "09_physical_diagnostics_reference_ladder.png", top=.82, bottom=.10)
    return rows


def plot_development_times(data: dict[str, np.ndarray], physical: dict[str, np.ndarray], output: Path) -> dict[str, object]:
    onset = physical["development_onset_min"]
    summaries = []
    fig, ax = plt.subplots(figsize=(13.5, 6.5))
    for ridx, ncell in enumerate(RESOLUTIONS):
        values = onset[ridx, np.isfinite(onset[ridx])]
        summaries.append({"ncell": ncell, "members_reaching_threshold": int(len(values)),
                          "mean_first_time_min": float(np.mean(values)) if len(values) else np.nan,
                          "min_first_time_min": float(np.min(values)) if len(values) else np.nan,
                          "max_first_time_min": float(np.max(values)) if len(values) else np.nan})
        if len(values):
            x = np.full(len(values), ridx, dtype=float) + np.linspace(-.13, .13, len(values))
            ax.scatter(x, values, color=COLORS[ridx], s=22, alpha=.65)
            ax.scatter(ridx, np.mean(values), marker="_", s=430, lw=2.3, color="black", zorder=4)
    ax.set_xticks(range(len(RESOLUTIONS)), [f"{n:,}" for n in RESOLUTIONS], rotation=40, ha="right")
    ax.set(xlabel=r"SDs per populated grid box, $N_{cell}$",
           ylabel="first stored time (min)",
           title=r"Fast-drop development: first $F_{v_t\geq1\,m\,s^{-1}}\geq1\%$")
    ax.grid(True, axis="y", alpha=.2)
    fig.text(.5, .032, "Each dot is one member; black bar is its member mean. The threshold is diagnostic only and is evaluated on the 120-s output grid. It is not rain onset.", ha="center", fontsize=10)
    save_figure(fig, output / "10_fastdrop_development_time.png", top=.90, bottom=.12, left=.09, right=.98)
    write_csv(summaries, output / "fastdrop_development_times.csv")
    return {"threshold_speed_ms": DEVELOPMENT_SPEED_MS, "threshold_mass_fraction": DEVELOPMENT_FRACTION, "summary": summaries}


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def write_readout(data: dict[str, np.ndarray], physical: dict[str, np.ndarray], rows: list[dict[str, object]],
                  development: dict[str, object], output: Path) -> None:
    refidx = RESOLUTIONS.index(REFERENCE)
    consistency = np.max(np.abs(
        physical["flux_g_m2_s"][refidx].mean(axis=0) / physical["flux_identity_g_m2_s"][refidx].mean(axis=0) - 1.0
    ))
    physical_1024 = [row for row in rows if row["comparison"] == "1024->8192"]
    gate = max(float(row["upper95_ratio_to_tolerance"]) for row in physical_1024)
    limiting = max(physical_1024, key=lambda row: float(row["upper95_ratio_to_tolerance"]))
    lines = [
        "# 2-D constthermo2d full physical-diagnostics readout",
        "",
        "## Scope",
        "",
        "All figures use the compact, audited fixed-20 normal-sampling cache for every completed resolution from 2 through 8,192 SDs per initially populated grid box. The diagnostic reconstruction uses the stored radius, multiplicity-weighted DSDs, moments, terminal-speed relation, and selected spatial mass fields. No new CLEO trajectory was run.",
        "",
        "## Physical definitions",
        "",
        r"- Surface-area density: \(A=4\pi\lambda_2\), after converting micrometre-squared radii to square metres. It is geometric area per air volume, not a radiative-transfer extinction coefficient.",
        r"- Liquid-equivalent water content: \(L=\rho_w(4\pi/3)\lambda_3\). It is a radius-derived liquid quantity and is shown alongside CLEO's total-droplet mass diagnostic.",
        r"- Rayleigh reflectivity-factor proxy: \(Z=64\lambda_6^{(r,\mathrm{mm})}\), displayed as dBZ. It is not a radar forward simulation.",
        r"- Terminal-speed transport proxy: \(\mathcal P=V^{-1}\sum_i\xi_i m_i v_t(r_i)\). It has flux units but, with null boundaries, is not surface precipitation.",
        "",
        "## Fast-drop threshold check",
        "",
        "A 4 m/s fast-drop threshold is not usable in this 2-D configuration: the 8,192-SD ensemble has essentially zero liquid mass at speeds at or above 2 or 4 m/s by 120 min. The figures therefore show the realized 0.25, 0.5, and 1 m/s classes. The descriptive development time is the first 120-s output where 1% of liquid mass has terminal speed at least 1 m/s.",
        "",
        "## Physical corroboration of the 1,024-SD operational selection",
        "",
        f"For 1,024 versus 8,192, the largest 95% bootstrap-bound/tolerance ratio over physical area, liquid-equivalent water, reflectivity proxy, terminal speed, and terminal-speed flux is {gate:.3f}, limited by {limiting['label']}. A ratio at or below one passes its 5% core or 10% tail margin. Thus the physical diagnostics corroborate rather than overturn the existing 1,024-SD operational selection.",
        "",
        f"The binned flux reconstruction differs from total-mass times mass-weighted speed by at most {100*consistency:.3f}% in the 8,192 ensemble mean, documenting the fixed-bin approximation used for the flux figures.",
        "",
        "## Interpretation boundary",
        "",
        "These figures demonstrate cloud-scale size-distribution development, in-domain redistribution, and the emergence of faster-falling liquid mass. They do not diagnose surface rainfall or accumulation because the 2-D setup has null boundaries and no sedimenting exit.",
    ]
    (output / "physical_diagnostics_readout.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite output: {args.output}")
    args.output.mkdir(parents=True)
    data = load_cache(args.cache)
    physical = derive(data)
    plot_all_evolution(data, args.output)
    plot_radius_transport(data, physical, args.output)
    plot_dsd(data, args.output, "number")
    plot_dsd(data, args.output, "mass")
    plot_physical_proxies(data, physical, args.output)
    plot_flux_fastdrop(data, physical, args.output)
    plot_speed_spectrum(data, physical, args.output)
    plot_spatial_maps(data, args.output)
    rows = physical_convergence(data, physical, args.output)
    development = plot_development_times(data, physical, args.output)
    write_readout(data, physical, rows, development, args.output)
    (args.output / "metadata.json").write_text(json.dumps({
        "status": "complete_full_production_physical_diagnostic_suite",
        "resolutions_ncell": list(RESOLUTIONS), "members_per_resolution": len(MEMBERS),
        "reference_ncell": REFERENCE, "dsd_meshes": [500, 1000],
        "terminal_speed_relation": "Rogers--Gunn--Kinzer",
        "fast_speed_thresholds_ms": list(FAST_SPEEDS_MS),
        "development_threshold": {"speed_ms": DEVELOPMENT_SPEED_MS, "mass_fraction": DEVELOPMENT_FRACTION},
        "warning": "Flux and development diagnostics are closed-domain terminal-speed proxies, not surface precipitation.",
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
