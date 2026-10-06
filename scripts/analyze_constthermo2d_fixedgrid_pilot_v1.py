#!/usr/bin/env python3
"""Analyse the accepted 16-thread `constthermo2d` small pilot locally.

This is intentionally a pilot diagnostic workflow.  It neither estimates a
convergence resolution nor treats the null-boundary 2-D configuration as a
surface-precipitation experiment.  It reconstructs domain moments and DSDs
directly from the stored SD attributes, checks them against the native CLEO
mass-moment observer, and reports member-to-member variation transparently.
"""

from __future__ import annotations

import argparse
import json
import warnings
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
import pandas as pd
import xarray as xr


DOMAIN_X_M = 1500.0
DOMAIN_Z_M = 1500.0
DOMAIN_Y_M = 20.0
DOMAIN_VOLUME_M3 = DOMAIN_X_M * DOMAIN_Z_M * DOMAIN_Y_M
CELL_VOLUME_M3 = (DOMAIN_X_M / 20.0) * (DOMAIN_Z_M / 20.0) * DOMAIN_Y_M
RHO_WATER_KG_M3 = 1000.0
RHO_LIQUID_KG_M3 = 998.203
RHO_SOLUTE_KG_M3 = 2016.5
RESOLUTIONS = (8, 32, 128, 512)
MEMBERS = (1, 2, 3)
SELECTED_MINUTES = (0, 30, 60, 90, 120)
SPATIAL_MINUTES = (0, 60, 120)
ALTITUDE_EDGES_M = np.array((0, 250, 500, 750, 1000, 1250, 1500), dtype=float)
# A 100-bin presentation mesh is used for the pilot DSD figures.  The raw
# particle data and all moment diagnostics remain unbinned.  Finer bins make
# the sparse tail appear as vertical sampling spikes rather than a legible DSD.
RADIUS_EDGES_UM = np.geomspace(0.002, 100.0, 101)


def total_droplet_mass_g(radius_um: np.ndarray, msol_g: np.ndarray) -> np.ndarray:
    """CLEO's exact ``Superdrop::mass`` in grams.

    The mass observer counts water plus the density-corrected dry-solute term.
    Reconstructing it this way allows the particle diagnostic to be checked
    against CLEO's native `massmom1` output rather than merely approximately
    compared using a pure-water sphere.
    """
    liquid_term = (4.0 / 3.0) * np.pi * RHO_LIQUID_KG_M3 * (radius_um * 1.0e-6) ** 3 * 1.0e3
    solute_term = np.asarray(msol_g) * (1.0 - RHO_LIQUID_KG_M3 / RHO_SOLUTE_KG_M3)
    return liquid_term + solute_term


def rogers_gk_terminal_speed_ms(radius_um: np.ndarray) -> np.ndarray:
    """Rogers et al. (1993) Gunn--Kinzer fit used by CLEO's motion operator.

    The source implements the fit in terms of diameter D in mm: V=4D(1-exp(-12D))
    for D<0.3725 mm, otherwise V=9.65-10.43exp(-0.6D).
    """
    diameter_mm = 2.0 * np.asarray(radius_um, dtype=float) / 1000.0
    return np.where(
        diameter_mm < 0.3725,
        4.0 * diameter_mm * (1.0 - np.exp(-12.0 * diameter_mm)),
        9.65 - 10.43 * np.exp(-0.6 * diameter_mm),
    )


def nearest_indices(time_minutes: np.ndarray, requested: tuple[int, ...]) -> dict[int, int]:
    return {minute: int(np.argmin(np.abs(time_minutes - minute))) for minute in requested}


def dsd_number(radius_um: np.ndarray, xi: np.ndarray) -> np.ndarray:
    """Number DSD dN/dln(r), in m^-3, using the common fixed 500-bin mesh."""
    weighted, _ = np.histogram(radius_um, bins=RADIUS_EDGES_UM, weights=xi)
    return weighted / DOMAIN_VOLUME_M3 / np.diff(np.log(RADIUS_EDGES_UM))


def dsd_mass(radius_um: np.ndarray, xi: np.ndarray, msol_g: np.ndarray) -> np.ndarray:
    """Total droplet-mass DSD dM/dln(r), in g m^-3, matching CLEO massmom1."""
    weighted, _ = np.histogram(radius_um, bins=RADIUS_EDGES_UM, weights=xi * total_droplet_mass_g(radius_um, msol_g))
    return weighted / DOMAIN_VOLUME_M3 / np.diff(np.log(RADIUS_EDGES_UM))


def member_paths(cache_root: Path, ncell: int, member: int) -> tuple[Path, Path]:
    member_dir = cache_root / f"ncell{ncell:04d}" / f"member{member:03d}"
    return member_dir / "bin" / "const2d_sol.zarr", member_dir


def analyse_member(dataset_path: Path, member_dir: Path, ncell: int, member: int) -> tuple[pd.DataFrame, dict, dict]:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Object at .* is not recognized")
        ds = xr.open_dataset(dataset_path, engine="zarr", consolidated=False)

    time_min = np.asarray(ds["time"].values, dtype=float) / 60.0
    counts = np.asarray(ds["raggedcount"].values, dtype=int)
    offsets = np.concatenate(([0], np.cumsum(counts)))
    radius = np.asarray(ds["radius"].values, dtype=float)
    xi = np.asarray(ds["xi"].values, dtype=np.float64)
    msol_g = np.asarray(ds["msol"].values, dtype=float)
    xcoord = np.asarray(ds["coord1"].values, dtype=float)
    zcoord = np.asarray(ds["coord3"].values, dtype=float)
    stored_mom0 = np.asarray(ds["massmom0"].values, dtype=np.float64).sum(axis=1)
    stored_mom1_g = np.asarray(ds["massmom1"].values, dtype=float).sum(axis=1)
    selected = nearest_indices(time_min, SELECTED_MINUTES)
    spatial = nearest_indices(time_min, SPATIAL_MINUTES)

    rows: list[dict] = []
    selected_data: dict[int, dict[str, np.ndarray]] = {}
    for ti, minute in enumerate(time_min):
        begin, end = offsets[ti], offsets[ti + 1]
        r = radius[begin:end]
        multiplicity = xi[begin:end]
        mass_g = total_droplet_mass_g(r, msol_g[begin:end])
        weighted_mass_g = multiplicity * mass_g
        lambda_values = {
            p: float(np.sum(multiplicity * r**p) / DOMAIN_VOLUME_M3)
            for p in (0, 2, 3, 6)
        }
        total_mass_g = float(np.sum(weighted_mass_g))
        lower_fraction = float(np.sum(weighted_mass_g[zcoord[begin:end] < 150.0]) / total_mass_g) if total_mass_g else np.nan
        vterminal = rogers_gk_terminal_speed_ms(r)
        mass_weighted_vterminal = float(np.sum(weighted_mass_g * vterminal) / total_mass_g) if total_mass_g else np.nan
        rows.append(
            {
                "ncell": ncell,
                "member": member,
                "time_min": float(minute),
                "active_sds": int(end - begin),
                "lambda0_m3": lambda_values[0],
                "lambda2_um2_m3": lambda_values[2],
                "lambda3_um3_m3": lambda_values[3],
                "lambda6_um6_m3": lambda_values[6],
                "total_droplet_mass_g_m3": total_mass_g / DOMAIN_VOLUME_M3,
                "mass_weighted_terminal_speed_ms": mass_weighted_vterminal,
                "lower150m_total_droplet_mass_fraction": lower_fraction,
                "stored_lambda0_m3": stored_mom0[ti] / DOMAIN_VOLUME_M3,
                "stored_total_droplet_mass_g_m3": stored_mom1_g[ti] / DOMAIN_VOLUME_M3,
            }
        )
        chosen_minutes = [m for m, idx in selected.items() if idx == ti]
        if chosen_minutes:
            selected_data[chosen_minutes[0]] = {
                "radius_um": r.copy(), "xi": multiplicity.copy(), "msol_g": msol_g[begin:end].copy(), "z_m": zcoord[begin:end].copy(), "x_m": xcoord[begin:end].copy()
            }

    receipt = json.loads((member_dir / "trajectory_integrity.json").read_text())
    if receipt.get("status") != "passed_trajectory_integrity_no_convergence_claim":
        raise RuntimeError(f"Unaccepted trajectory: {member_dir}")
    member_meta = {
        "ncell": ncell,
        "member": member,
        "dataset": str(dataset_path),
        "noutputs": int(len(time_min)),
        "trajectory_status": receipt["status"],
        "max_abs_lambda0_relative_observer_difference": float(
            np.max(np.abs(np.asarray([r["lambda0_m3"] for r in rows]) / np.asarray([r["stored_lambda0_m3"] for r in rows]) - 1.0))
        ),
        "max_abs_total_droplet_mass_relative_observer_difference": float(
            np.max(np.abs(np.asarray([r["total_droplet_mass_g_m3"] for r in rows]) / np.asarray([r["stored_total_droplet_mass_g_m3"] for r in rows]) - 1.0))
        ),
    }
    return pd.DataFrame(rows), selected_data, member_meta


def line_with_member_range(ax, data: pd.DataFrame, ycol: str, ylabel: str, title: str, log: bool = False) -> None:
    colors = {8: "#440154", 32: "#31688e", 128: "#35b779", 512: "#fde725"}
    for ncell in RESOLUTIONS:
        subset = data[data.ncell == ncell]
        grouped = subset.groupby("time_min")[ycol]
        mean = grouped.mean()
        lower = grouped.min()
        upper = grouped.max()
        ax.fill_between(mean.index, lower, upper, color=colors[ncell], alpha=0.14, linewidth=0)
        ax.plot(mean.index, mean, color=colors[ncell], linewidth=2.2, label=fr"$N_{{cell}}={ncell}$")
        for member in MEMBERS:
            member_data = subset[subset.member == member]
            ax.plot(member_data.time_min, member_data[ycol], color=colors[ncell], alpha=0.28, linewidth=0.7)
    if log:
        ax.set_yscale("log")
    ax.set_title(title, fontsize=12, weight="bold")
    ax.set_xlabel("time (min)")
    ax.set_ylabel(ylabel)
    ax.grid(True, which="both", alpha=0.2)


def make_domain_figure(data: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), sharex=True)
    line_with_member_range(axes[0, 0], data, "lambda0_m3", r"$\lambda_0$ (m$^{-3}$)", r"Number moment $\lambda_0$", log=True)
    line_with_member_range(axes[0, 1], data, "lambda2_um2_m3", r"$\lambda_2$ ($\mu$m$^2$ m$^{-3}$)", r"Area-related moment $\lambda_2$", log=True)
    line_with_member_range(axes[1, 0], data, "total_droplet_mass_g_m3", r"total droplet mass (g m$^{-3}$)", r"Mass concentration (native $\lambda_3$-related observer)", log=True)
    line_with_member_range(axes[1, 1], data, "lambda6_um6_m3", r"$\lambda_6$ ($\mu$m$^6$ m$^{-3}$)", r"Radar-weighted moment proxy $\lambda_6$", log=True)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, bbox_to_anchor=(0.5, 0.948), loc="upper center", ncol=4, frameon=False)
    fig.suptitle("2-D constthermo2d pilot: domain moment evolution", fontsize=16, weight="bold", y=0.995)
    fig.text(0.5, 0.01, "Solid lines: three-member mean; faint lines and shading: individual members and their full range. Pilot evidence only.", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, 0.04, 1, 0.87))
    fig.savefig(out, dpi=220)
    plt.close(fig)


def make_transport_figure(data: pd.DataFrame, out: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.3), sharex=True)
    line_with_member_range(axes[0], data, "lower150m_total_droplet_mass_fraction", "fraction", "Lower-150 m total-droplet-mass fraction")
    axes[0].set_ylim(bottom=0)
    line_with_member_range(axes[1], data, "mass_weighted_terminal_speed_ms", "m s$^{-1}$", "Mass-weighted terminal fall speed")
    axes[1].set_ylim(bottom=0)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, bbox_to_anchor=(0.5, 0.948), loc="upper center", ncol=4, frameon=False)
    fig.suptitle("Boundary-aware transport diagnostics", fontsize=16, weight="bold", y=0.995)
    fig.text(0.5, 0.015, "The left panel is an in-domain proximity diagnostic, not surface precipitation: this pilot uses NullBoundaryConditions.", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, 0.05, 1, 0.86))
    fig.savefig(out, dpi=220)
    plt.close(fig)


def aggregate_dsd(selected: dict[tuple[int, int], dict], ncell: int, minute: int, kind: str) -> np.ndarray:
    curves = []
    for member in MEMBERS:
        entry = selected[(ncell, member)][minute]
        if kind == "number":
            curves.append(dsd_number(entry["radius_um"], entry["xi"]))
        else:
            curves.append(dsd_mass(entry["radius_um"], entry["xi"], entry["msol_g"]))
    return np.mean(curves, axis=0)


def make_dsd_evolution(selected: dict[tuple[int, int], dict], out: Path, kind: str) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), sharex=True, sharey=True)
    colors = plt.cm.viridis(np.linspace(0.08, 0.95, len(SELECTED_MINUTES)))
    centers = np.sqrt(RADIUS_EDGES_UM[:-1] * RADIUS_EDGES_UM[1:])
    curves = {(ncell, minute): aggregate_dsd(selected, ncell, minute, kind) for ncell in RESOLUTIONS for minute in SELECTED_MINUTES}
    shared_peak = max(float(np.max(curve)) for curve in curves.values())
    display_floor = shared_peak * 1.0e-6
    for ax, ncell in zip(axes.flat, RESOLUTIONS):
        for color, minute in zip(colors, SELECTED_MINUTES):
            curve = curves[(ncell, minute)]
            ax.plot(centers, np.where(curve >= display_floor, curve, np.nan), color=color, linewidth=1.7, label=f"{minute} min")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_ylim(display_floor, shared_peak * 1.4)
        ax.set_title(fr"$N_{{cell}}={ncell}$ ({120*ncell:,} initial SDs)", weight="bold")
        ax.grid(True, which="both", alpha=0.18)
    ylabel = r"$dN/d\ln r$ (m$^{-3}$)" if kind == "number" else r"$dL/d\ln r$ (g m$^{-3}$)"
    for ax in axes[:, 0]:
        ax.set_ylabel(ylabel)
    for ax in axes[-1, :]:
        ax.set_xlabel(r"wet radius $r$ ($\mu$m)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, title="stored time", bbox_to_anchor=(0.5, 0.948), loc="upper center", ncol=5, frameon=False)
    descriptor = "number" if kind == "number" else "total droplet mass"
    fig.suptitle(f"2-D constthermo2d pilot: {descriptor} DSD evolution", fontsize=16, weight="bold", y=0.995)
    fig.text(0.5, 0.012, "Each curve is the mean across three accepted members on a fixed 100-bin radius grid. Values below 10$^{-6}$ of the shared peak are omitted for legibility.", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, 0.05, 1, 0.86))
    fig.savefig(out, dpi=220)
    plt.close(fig)


def make_altitude_dsd(selected: dict[tuple[int, int], dict], out: Path) -> None:
    ncell = 512
    centers = np.sqrt(RADIUS_EDGES_UM[:-1] * RADIUS_EDGES_UM[1:])
    fig, axes = plt.subplots(1, 3, figsize=(16, 4.8), sharex=True, sharey=True)
    colors = plt.cm.cividis(np.linspace(0.05, 0.95, len(ALTITUDE_EDGES_M) - 1))
    for ax, minute in zip(axes, SPATIAL_MINUTES):
        for lo, hi, color in zip(ALTITUDE_EDGES_M[:-1], ALTITUDE_EDGES_M[1:], colors):
            curves = []
            for member in MEMBERS:
                entry = selected[(ncell, member)][minute]
                mask = (entry["z_m"] >= lo) & (entry["z_m"] < hi)
                weighted, _ = np.histogram(entry["radius_um"][mask], bins=RADIUS_EDGES_UM, weights=entry["xi"][mask] * total_droplet_mass_g(entry["radius_um"][mask], entry["msol_g"][mask]))
                layer_volume = DOMAIN_X_M * DOMAIN_Y_M * (hi - lo)
                curves.append(weighted / layer_volume / np.diff(np.log(RADIUS_EDGES_UM)))
            curve = np.mean(curves, axis=0)
            ax.plot(centers, np.where(curve >= 1e-7, curve, np.nan), color=color, linewidth=1.45, label=f"{lo:.0f}–{hi:.0f} m")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(f"{minute} min", weight="bold")
        ax.set_ylim(1e-7, 1.0)
        ax.grid(True, which="both", alpha=0.18)
        ax.set_xlabel(r"wet radius $r$ ($\mu$m)")
    axes[0].set_ylabel(r"$dL/d\ln r$ (g m$^{-3}$)")
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(handles, labels, title="altitude layer", bbox_to_anchor=(0.5, 0.93), loc="upper center", ncol=3, frameon=False)
    fig.suptitle(r"Spatial mass-DSD evolution: $N_{cell}=512$ pilot mean", fontsize=16, weight="bold", y=0.995)
    fig.text(0.5, 0.015, "Each line is a local layer concentration, averaged across three members; it is not a domain-wide DSD.", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, 0.06, 1, 0.80))
    fig.savefig(out, dpi=220)
    plt.close(fig)


def make_spatial_mass_maps(selected: dict[tuple[int, int], dict], out: Path) -> None:
    ncell = 512
    maps = []
    for minute in SPATIAL_MINUTES:
        member_maps = []
        for member in MEMBERS:
            entry = selected[(ncell, member)][minute]
            mass, zedges, xedges = np.histogram2d(
                entry["z_m"], entry["x_m"], bins=(20, 20), range=((0, DOMAIN_Z_M), (0, DOMAIN_X_M)),
                weights=entry["xi"] * total_droplet_mass_g(entry["radius_um"], entry["msol_g"]),
            )
            member_maps.append(mass / CELL_VOLUME_M3)
        maps.append(np.mean(member_maps, axis=0))
    positives = np.concatenate([m[m > 0] for m in maps])
    norm = LogNorm(vmin=max(np.nanpercentile(positives, 2), 1e-8), vmax=np.nanpercentile(positives, 99.5))
    fig = plt.figure(figsize=(17, 5.2))
    grid = fig.add_gridspec(1, 4, width_ratios=(1, 1, 1, 0.05), left=0.055, right=0.94, top=0.83, bottom=0.16, wspace=0.14)
    axes = [fig.add_subplot(grid[0, idx]) for idx in range(3)]
    colorbar_axis = fig.add_subplot(grid[0, 3])
    image = None
    for ax, minute, mcon in zip(axes, SPATIAL_MINUTES, maps):
        image = ax.pcolormesh(xedges, zedges, np.ma.masked_less_equal(mcon, 0), shading="auto", cmap="magma_r", norm=norm)
        ax.set_title(f"{minute} min", weight="bold")
        ax.set_xlabel("x (m)")
    axes[0].set_ylabel("z (m)")
    cbar = fig.colorbar(image, cax=colorbar_axis)
    cbar.set_label(r"total droplet-mass concentration (g m$^{-3}$)")
    fig.suptitle(r"Spatial total-droplet-mass field: $N_{cell}=512$ pilot mean", fontsize=16, weight="bold", y=0.99)
    fig.text(0.5, 0.015, "Horizontal–vertical map formed directly from particle positions and multiplicity-weighted droplet mass; mean of three members.", ha="center", fontsize=10)
    fig.savefig(out, dpi=220)
    plt.close(fig)


def make_final_spread(data: pd.DataFrame, out: Path) -> None:
    final_time = data.time_min.max()
    final = data[np.isclose(data.time_min, final_time)]
    specs = (
        ("lambda0_m3", r"$\lambda_0$ (m$^{-3}$)", r"Number moment $\lambda_0$", False),
        ("total_droplet_mass_g_m3", r"total droplet mass (g m$^{-3}$)", r"Total droplet-mass concentration", False),
        ("lambda6_um6_m3", r"$\lambda_6$ ($\mu$m$^6$ m$^{-3}$)", r"Radar-weighted moment proxy $\lambda_6$", True),
        ("mass_weighted_terminal_speed_ms", "mass-weighted fall speed (m s$^{-1}$)", "Mass-weighted terminal fall speed", False),
    )
    colors = {8: "#440154", 32: "#31688e", 128: "#35b779", 512: "#fde725"}
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.5))
    for ax, (column, ylabel, title, log) in zip(axes.flat, specs):
        for i, ncell in enumerate(RESOLUTIONS):
            vals = final[final.ncell == ncell][column].to_numpy()
            ax.vlines(i, vals.min(), vals.max(), color=colors[ncell], linewidth=2.2)
            ax.scatter(np.full_like(vals, i, dtype=float), vals, s=48, color=colors[ncell], edgecolor="white", linewidth=0.8, zorder=3)
            ax.scatter(i, vals.mean(), marker="_", s=360, color="black", linewidth=2.2, zorder=4)
        ax.set_xticks(range(len(RESOLUTIONS)), [str(v) for v in RESOLUTIONS])
        ax.set_xlabel(r"SDs per initially populated grid box, $N_{cell}$")
        ax.set_ylabel(ylabel)
        ax.set_title(title, weight="bold")
        ax.grid(True, axis="y", which="both", alpha=0.2)
        if log:
            ax.set_yscale("log")
    fig.suptitle("Member-to-member spread at 120 min", fontsize=16, weight="bold", y=0.98)
    fig.text(0.5, 0.01, "Three dots: the accepted members; coloured line: full member range; black bar: arithmetic member mean. This is not a confidence interval.", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    fig.savefig(out, dpi=220)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    tables = []
    selected: dict[tuple[int, int], dict] = {}
    audits = []
    for ncell in RESOLUTIONS:
        for member in MEMBERS:
            dataset, member_dir = member_paths(args.cache_root, ncell, member)
            if not dataset.exists():
                raise FileNotFoundError(dataset)
            table, snapshots, audit = analyse_member(dataset, member_dir, ncell, member)
            tables.append(table)
            selected[(ncell, member)] = snapshots
            audits.append(audit)
            print(f"analysed Ncell={ncell}, member={member}: {audit['noutputs']} outputs")
    data = pd.concat(tables, ignore_index=True)
    data.to_csv(args.output_dir / "pilot_domain_diagnostics.csv", index=False)
    (args.output_dir / "pilot_reconstruction_audit.json").write_text(json.dumps(audits, indent=2) + "\n")

    make_domain_figure(data, args.output_dir / "pilot_domain_lambda_evolution.png")
    make_transport_figure(data, args.output_dir / "pilot_transport_and_terminal_speed.png")
    make_dsd_evolution(selected, args.output_dir / "pilot_number_dsd_evolution.png", "number")
    make_dsd_evolution(selected, args.output_dir / "pilot_mass_dsd_evolution.png", "mass")
    make_altitude_dsd(selected, args.output_dir / "pilot_altitude_resolved_mass_dsd.png")
    make_spatial_mass_maps(selected, args.output_dir / "pilot_spatial_liquid_water_maps.png")
    make_final_spread(data, args.output_dir / "pilot_final_member_spread.png")
    (args.output_dir / "README.md").write_text(
        "# constthermo2d fixed-grid pilot analysis\n\n"
        "This directory contains local, read-only reconstruction of the accepted 16-thread pilot. "
        "No convergence number is inferred. The lower-150m fraction is an in-domain transport "
        "proxy, not surface precipitation, because the model uses `NullBoundaryConditions`.\n"
    )


if __name__ == "__main__":
    main()
