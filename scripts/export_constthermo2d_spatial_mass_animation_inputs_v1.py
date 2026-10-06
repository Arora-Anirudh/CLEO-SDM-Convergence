#!/usr/bin/env python3
"""Compact the raw CLEO 2-D mass-moment fields for spatial animation.

This deliberately reads only the native ``massmom1`` observer field (not the
large superdroplet trajectory arrays).  It produces an ensemble-mean
time-by-z-by-x liquid-mass concentration array for selected resolutions.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr


GRID_N = 20
CELL_VOLUME_M3 = 75.0 * 75.0 * 20.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resolutions", type=int, nargs="+", default=(2, 1024, 8192))
    parser.add_argument("--members", type=int, default=20)
    return parser.parse_args()


def load_member(dataset: Path) -> tuple[np.ndarray, np.ndarray]:
    with xr.open_dataset(dataset, engine="zarr", consolidated=False) as source:
        minutes = np.asarray(source["time"].values, dtype=float) / 60.0
        # ``massmom1`` is total represented droplet mass [g] in each grid box.
        # Native gridbox order is x-major then z-major. Transpose to the
        # z-by-x layout used by the existing spatial-map diagnostic.
        mass_g = np.asarray(source["massmom1"].values, dtype=float)
    if mass_g.shape != (len(minutes), GRID_N * GRID_N):
        raise ValueError(f"unexpected massmom1 shape {mass_g.shape} in {dataset}")
    mass_g_zx = mass_g.reshape(len(minutes), GRID_N, GRID_N).transpose(0, 2, 1)
    return minutes, mass_g_zx / CELL_VOLUME_M3


def main() -> None:
    args = parse_args()
    all_fields: list[np.ndarray] = []
    minutes_reference: np.ndarray | None = None
    for ncell in args.resolutions:
        members: list[np.ndarray] = []
        for member in range(1, args.members + 1):
            path = args.raw_root / f"ncell{ncell:04d}" / f"member{member:03d}" / "bin" / "const2d_sol.zarr"
            minutes, field = load_member(path)
            if minutes_reference is None:
                minutes_reference = minutes
            elif not np.allclose(minutes_reference, minutes, rtol=0.0, atol=1e-8):
                raise ValueError(f"output-time mismatch: {path}")
            members.append(field)
        all_fields.append(np.mean(np.stack(members, axis=0), axis=0))
        print(f"SPATIAL_MASS_EXPORT_PASS ncell={ncell} members={args.members}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        time_min=minutes_reference,
        ncell=np.asarray(args.resolutions, dtype=int),
        ensemble_mean_mass_g_m3=np.stack(all_fields, axis=0),
        cell_volume_m3=np.asarray(CELL_VOLUME_M3),
    )
    print(f"SPATIAL_MASS_EXPORT_COMPLETE output={args.output}")


if __name__ == "__main__":
    main()
