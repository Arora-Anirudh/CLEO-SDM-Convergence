#!/usr/bin/env python3
"""Stream one accepted 2-D ``constthermo2d`` member into compact diagnostics.

The raw trajectory remains authoritative in its original Zarr store.  This
extractor reads one member at a time, checks its integrity receipt, reconstructs
particle moments and exact CLEO droplet mass, and writes a non-overwriting NPZ
summary.  The summary retains DSDs on 250/500/1000-bin fixed log-radius meshes,
so later convergence analysis can test representation sensitivity without
re-reading every raw trajectory.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import xarray as xr


DOMAIN_VOLUME_M3 = 1500.0 * 1500.0 * 20.0
CELL_VOLUME_M3 = 75.0 * 75.0 * 20.0
RHO_LIQUID_KG_M3 = 998.203
RHO_SOLUTE_KG_M3 = 2016.5
BIN_COUNTS = (250, 500, 1000)
RADIUS_MIN_UM = 0.002
RADIUS_MAX_UM = 1000.0
SPATIAL_MINUTES = (0.0, 60.0, 120.0)


def droplet_mass_g(radius_um: np.ndarray, msol_g: np.ndarray) -> np.ndarray:
    """CLEO ``Superdrop::mass`` in grams, including the solute correction."""
    liquid = (4.0 / 3.0) * np.pi * RHO_LIQUID_KG_M3 * (radius_um * 1.0e-6) ** 3 * 1.0e3
    solute = np.asarray(msol_g) * (1.0 - RHO_LIQUID_KG_M3 / RHO_SOLUTE_KG_M3)
    return liquid + solute


def rogers_gk_terminal_speed_ms(radius_um: np.ndarray) -> np.ndarray:
    """The diameter-based Rogers--Gunn--Kinzer terminal-speed fit in CLEO."""
    diameter_mm = 2.0 * np.asarray(radius_um, dtype=float) / 1000.0
    return np.where(
        diameter_mm < 0.3725,
        4.0 * diameter_mm * (1.0 - np.exp(-12.0 * diameter_mm)),
        9.65 - 10.43 * np.exp(-0.6 * diameter_mm),
    )


def weighted_quantile_from_hist(weights: np.ndarray, edges: np.ndarray, probability: float) -> float:
    total = float(np.sum(weights))
    if not np.isfinite(total) or total <= 0.0:
        return float("nan")
    index = int(np.searchsorted(np.cumsum(weights), probability * total, side="left"))
    index = min(max(index, 0), len(edges) - 2)
    return float(np.sqrt(edges[index] * edges[index + 1]))


def selected_time_indices(time_min: np.ndarray) -> list[int]:
    return [int(np.argmin(np.abs(time_min - minute))) for minute in SPATIAL_MINUTES]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--ncell", required=True, type=int)
    parser.add_argument("--member", required=True, type=int)
    args = parser.parse_args()

    member_dir = args.raw_root / f"ncell{args.ncell:04d}" / f"member{args.member:03d}"
    dataset_path = member_dir / "bin" / "const2d_sol.zarr"
    receipt_path = member_dir / "trajectory_integrity.json"
    output_dir = args.output_root / f"ncell{args.ncell:04d}"
    output_path = output_dir / f"member{args.member:03d}.npz"
    audit_path = output_dir / f"member{args.member:03d}.json"
    if output_path.exists() or audit_path.exists():
        raise FileExistsError(f"refusing to overwrite aggregate: {output_path}")
    if not dataset_path.is_dir() or not receipt_path.is_file():
        raise FileNotFoundError(member_dir)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "passed_trajectory_integrity_no_convergence_claim":
        raise RuntimeError(f"unaccepted trajectory: {member_dir}")

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Object at .* is not recognized")
        ds = xr.open_dataset(dataset_path, engine="zarr", consolidated=False)
    time_min = np.asarray(ds["time"].values, dtype=float) / 60.0
    counts = np.asarray(ds["raggedcount"].values, dtype=np.int64)
    offsets = np.concatenate(([0], np.cumsum(counts)))
    radius = np.asarray(ds["radius"].values, dtype=np.float64)
    xi = np.asarray(ds["xi"].values, dtype=np.float64)
    msol_g = np.asarray(ds["msol"].values, dtype=np.float64)
    coord_x = np.asarray(ds["coord1"].values, dtype=np.float64)
    coord_z = np.asarray(ds["coord3"].values, dtype=np.float64)
    observer_lambda0 = np.asarray(ds["massmom0"].values, dtype=np.float64).sum(axis=1) / DOMAIN_VOLUME_M3
    observer_mass_g_m3 = np.asarray(ds["massmom1"].values, dtype=np.float64).sum(axis=1) / DOMAIN_VOLUME_M3

    edges = {count: np.geomspace(RADIUS_MIN_UM, RADIUS_MAX_UM, count + 1) for count in BIN_COUNTS}
    number_dsd = {count: np.zeros((len(time_min), count), dtype=np.float64) for count in BIN_COUNTS}
    mass_dsd = {count: np.zeros((len(time_min), count), dtype=np.float64) for count in BIN_COUNTS}
    moment = {power: np.zeros(len(time_min), dtype=np.float64) for power in (0, 1, 2, 3, 6)}
    mass_g_m3 = np.zeros(len(time_min), dtype=np.float64)
    speed_ms = np.zeros(len(time_min), dtype=np.float64)
    lower150_fraction = np.zeros(len(time_min), dtype=np.float64)
    mass_q50_um = np.zeros(len(time_min), dtype=np.float64)
    mass_q90_um = np.zeros(len(time_min), dtype=np.float64)
    mass_q99_um = np.zeros(len(time_min), dtype=np.float64)
    selected_maps: list[np.ndarray] = []
    selected_indices = set(selected_time_indices(time_min))

    for tidx in range(len(time_min)):
        begin, end = int(offsets[tidx]), int(offsets[tidx + 1])
        r = radius[begin:end]
        multiplicity = xi[begin:end]
        mass = droplet_mass_g(r, msol_g[begin:end])
        weighted_mass = multiplicity * mass
        for power in moment:
            moment[power][tidx] = np.sum(multiplicity * r**power) / DOMAIN_VOLUME_M3
        total_mass = float(np.sum(weighted_mass))
        mass_g_m3[tidx] = total_mass / DOMAIN_VOLUME_M3
        lower150_fraction[tidx] = np.sum(weighted_mass[coord_z[begin:end] < 150.0]) / total_mass if total_mass else np.nan
        speed_ms[tidx] = np.sum(weighted_mass * rogers_gk_terminal_speed_ms(r)) / total_mass if total_mass else np.nan
        for count, mesh in edges.items():
            logwidth = np.diff(np.log(mesh))
            number_weights, _ = np.histogram(r, bins=mesh, weights=multiplicity)
            mass_weights, _ = np.histogram(r, bins=mesh, weights=weighted_mass)
            number_dsd[count][tidx] = number_weights / DOMAIN_VOLUME_M3 / logwidth
            mass_dsd[count][tidx] = mass_weights / DOMAIN_VOLUME_M3 / logwidth
            if count == 1000:
                mass_q50_um[tidx] = weighted_quantile_from_hist(mass_weights, mesh, 0.50)
                mass_q90_um[tidx] = weighted_quantile_from_hist(mass_weights, mesh, 0.90)
                mass_q99_um[tidx] = weighted_quantile_from_hist(mass_weights, mesh, 0.99)
        if tidx in selected_indices:
            spatial_mass, _, _ = np.histogram2d(
                coord_z[begin:end], coord_x[begin:end], bins=(20, 20),
                range=((0.0, 1500.0), (0.0, 1500.0)), weights=weighted_mass,
            )
            selected_maps.append(spatial_mass / CELL_VOLUME_M3)

    output_dir.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, np.ndarray] = {
        "time_min": time_min, "active_sds": counts, "lambda0_m3": moment[0],
        "lambda1_um_m3": moment[1], "lambda2_um2_m3": moment[2],
        "lambda3_um3_m3": moment[3], "lambda6_um6_m3": moment[6],
        "total_droplet_mass_g_m3": mass_g_m3,
        "mass_weighted_terminal_speed_ms": speed_ms,
        "lower150m_total_droplet_mass_fraction": lower150_fraction,
        "mass_weighted_r50_um": mass_q50_um, "mass_weighted_r90_um": mass_q90_um,
        "mass_weighted_r99_um": mass_q99_um, "observer_lambda0_m3": observer_lambda0,
        "observer_total_droplet_mass_g_m3": observer_mass_g_m3,
        "spatial_mass_selected_g_m3": np.asarray(selected_maps, dtype=np.float64),
        "spatial_selected_minutes": time_min[selected_time_indices(time_min)],
    }
    for count, mesh in edges.items():
        arrays[f"radius_edges_{count}_um"] = mesh
        arrays[f"number_dsd_{count}_m3"] = number_dsd[count]
        arrays[f"mass_dsd_{count}_g_m3"] = mass_dsd[count]
    np.savez_compressed(output_path, **arrays)

    audit = {
        "status": "passed_member_aggregation_no_convergence_claim",
        "ncell": args.ncell, "member": args.member,
        "raw_zarr": str(dataset_path), "trajectory_receipt": str(receipt_path),
        "stored_times": int(len(time_min)), "initial_active_sds": int(counts[0]),
        "max_abs_lambda0_relative_native_difference": float(np.max(np.abs(moment[0] / observer_lambda0 - 1.0))),
        "max_abs_mass_relative_native_difference": float(np.max(np.abs(mass_g_m3 / observer_mass_g_m3 - 1.0))),
        "radius_support_um": [RADIUS_MIN_UM, RADIUS_MAX_UM], "dsd_bin_counts": list(BIN_COUNTS),
    }
    audit_path.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"CONSTTHERMO2D_PRODUCTION_MEMBER_AGGREGATION_PASS ncell={args.ncell} member={args.member}")


if __name__ == "__main__":
    main()
