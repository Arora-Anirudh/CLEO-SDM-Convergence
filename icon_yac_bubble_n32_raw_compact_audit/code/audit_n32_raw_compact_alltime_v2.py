#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr


RHO_WATER = 998.203
RHO_SOLUTE = 2016.5


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    return parser.parse_args()


def row_for_time(
    ds: xr.Dataset, time_starts: np.ndarray, time_ends: np.ndarray, index: int
) -> dict[str, float | int]:
    # The ragged arrays have no time dimension. They are laid out as one
    # concatenation of complete output states: [all particles at t0]
    # [all particles at t1] ... . These offsets select one saved time, not one
    # gridbox or a cumulative set of gridboxes.
    start, end = int(time_starts[index]), int(time_ends[index])
    selection = {"superdroplets": slice(start, end)}
    ids = np.asarray(ds["sdId"].isel(selection).values)
    xi = np.asarray(ds["xi"].isel(selection).values, dtype=float)
    radius_m = np.asarray(ds["radius"].isel(selection).values, dtype=float) * 1e-6
    msol_kg = np.asarray(ds["msol"].isel(selection).values, dtype=float) / 1000.0
    water_g = RHO_WATER * 4.0 * np.pi * radius_m**3 / 3.0 * 1000.0
    solute_g = msol_kg * (1.0 - RHO_WATER / RHO_SOLUTE) * 1000.0
    mass_g = water_g + solute_g
    represented_mass_g = xi * mass_g
    # This first audit deliberately compares domain totals. The raw stream
    # does not save CLEO's sdgbxindex, although a later audit can reconstruct
    # a provisional cell assignment from coord1/2/3 and the grid-boundary
    # file. Here the compact values are therefore summed over every gridbox at
    # the same saved time.
    compact0 = float(np.sum(np.asarray(ds["massmom0"].isel(time=index).values, dtype=float)))
    compact1 = float(np.sum(np.asarray(ds["massmom1"].isel(time=index).values, dtype=float)))
    compact2 = float(np.sum(np.asarray(ds["massmom2"].isel(time=index).values, dtype=float)))
    raw0 = float(np.sum(xi))
    raw1 = float(np.sum(represented_mass_g))
    raw2 = float(np.sum(xi * mass_g**2))
    delta0 = raw0 - compact0
    delta1 = raw1 - compact1
    delta2 = raw2 - compact2
    unique = int(np.unique(ids).size)
    return {
        "time_min": float(ds["time"].isel(time=index).values) / 60.0,
        "record_count": int(end - start),
        "raggedcount": int(ds["raggedcount"].isel(time=index).values),
        "totnsupers": int(ds["totnsupers"].isel(time=index).values),
        "unique_sdid": unique,
        "duplicate_sdid": int((end - start) - unique),
        "duplicate_fraction_pct": float(100.0 * ((end - start) - unique) / max(end - start, 1)),
        "raw_sum_xi": raw0,
        "compact_massmom0": compact0,
        "raw_minus_compact_mom0": delta0,
        "abs_raw_minus_compact_mom0": abs(delta0),
        "ratio_mom0": raw0 / compact0 if compact0 > 0 else np.nan,
        "raw_mass_g": raw1,
        "compact_massmom1_g": compact1,
        "raw_minus_compact_mom1_g": delta1,
        "abs_raw_minus_compact_mom1_g": abs(delta1),
        "ratio_mom1": raw1 / compact1 if compact1 > 0 else np.nan,
        "raw_massmom2_g2": raw2,
        "compact_massmom2_g2": compact2,
        "raw_minus_compact_mom2_g2": delta2,
        "abs_raw_minus_compact_mom2_g2": abs(delta2),
        "ratio_mom2": raw2 / compact2 if compact2 > 0 else np.nan,
        "raw_water_mass_g": float(np.sum(xi * water_g)),
        "raw_effective_solute_mass_g": float(np.sum(xi * solute_g)),
        "xi_nonfinite": int(np.count_nonzero(~np.isfinite(xi))),
        "radius_nonfinite": int(np.count_nonzero(~np.isfinite(radius_m))),
        "msol_nonfinite": int(np.count_nonzero(~np.isfinite(msol_kg))),
        "xi_nonpositive": int(np.count_nonzero(xi <= 0.0)),
        "radius_nonpositive": int(np.count_nonzero(radius_m <= 0.0)),
        "msol_negative": int(np.count_nonzero(msol_kg < 0.0)),
        "radius_max_um": float(np.nanmax(radius_m) * 1e6),
        "xi_max": float(np.nanmax(xi)),
        "largest_particle_mass_fraction": float(np.nanmax(represented_mass_g) / raw1) if raw1 > 0 else np.nan,
    }


def write_csv(path: Path, rows: list[dict[str, float | int]]) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def print_absolute_difference_summary(rows: list[dict[str, float | int]]) -> None:
    """Print physical-unit differences so rounding can be assessed directly."""
    metrics = (
        ("M0", "raw_minus_compact_mom0", "abs_raw_minus_compact_mom0", "represented droplets"),
        ("M1", "raw_minus_compact_mom1_g", "abs_raw_minus_compact_mom1_g", "g"),
        ("M2", "raw_minus_compact_mom2_g2", "abs_raw_minus_compact_mom2_g2", "g^2"),
    )
    print("Absolute-difference audit: raw reconstruction minus compact diagnostic")
    for name, signed_key, absolute_key, unit in metrics:
        signed0 = float(rows[0][signed_key])
        finite = [row for row in rows if np.isfinite(float(row[absolute_key]))]
        largest = max(finite, key=lambda row: float(row[absolute_key]))
        nonfinite = len(rows) - len(finite)
        print(
            f"{name}: t=0 signed difference = {signed0:.12g} {unit}; "
            f"max finite absolute difference = {float(largest[absolute_key]):.12g} {unit} "
            f"at {float(largest['time_min']):.6g} min "
            f"(signed {float(largest[signed_key]):.12g}); "
            f"non-finite differences = {nonfinite}"
        )


def make_plot(rows: list[dict[str, float | int]], outdir: Path) -> None:
    t = np.array([float(r["time_min"]) for r in rows])
    fig, axes = plt.subplots(2, 2, figsize=(12.2, 8.2), sharex=True, constrained_layout=True)
    for axis, key, label in [
        (axes[0, 0], "ratio_mom0", r"raw $\sum\xi$ / compact $M_0$"),
        (axes[0, 1], "ratio_mom1", r"raw $\sum\xi m$ / compact $M_1$"),
        (axes[1, 0], "ratio_mom2", r"raw $\sum\xi m^2$ / compact $M_2$"),
    ]:
        y = np.array([float(r[key]) for r in rows])
        axis.plot(t, y, color="#234f81", lw=1.2)
        axis.axhline(1.0, color="0.25", lw=1)
        axis.set(yscale="log", ylabel=label)
        axis.grid(alpha=0.25)
    axes[1, 0].set_xlabel("time (min)")
    axes[1, 1].plot(t, [float(r["duplicate_fraction_pct"]) for r in rows], label="within-state duplicate IDs")
    axes[1, 1].plot(t, [float(r["largest_particle_mass_fraction"]) * 100.0 for r in rows], label="largest raw mass share")
    axes[1, 1].set(xlabel="time (min)", ylabel="percent", title="Raw-record integrity indicators")
    axes[1, 1].grid(alpha=0.25)
    axes[1, 1].legend(frameon=False, fontsize=8)
    fig.suptitle("Ncell=32 raw-particle versus compact-diagnostic audit", weight="bold")
    fig.savefig(outdir / "01_n32_raw_compact_alltime.png", dpi=220)
    plt.close(fig)


def main() -> None:
    cfg = args()
    cfg.outdir.mkdir(parents=True, exist_ok=False)
    with xr.open_dataset(cfg.dataset, engine="zarr", consolidated=False) as ds:
        records_per_time = np.asarray(ds["raggedcount"].values, dtype=np.int64)
        # Convert per-time ragged record counts to exclusive offsets on the
        # one-dimensional ``superdroplets`` storage axis.
        time_ends = np.cumsum(records_per_time, dtype=np.int64)
        time_starts = np.insert(time_ends[:-1], 0, 0)
        rows = [
            row_for_time(ds, time_starts, time_ends, index)
            for index in range(records_per_time.size)
        ]
    write_csv(cfg.outdir / "n32_raw_compact_alltime.csv", rows)
    print_absolute_difference_summary(rows)
    make_plot(rows, cfg.outdir)
    with (cfg.outdir / "README.txt").open("w") as stream:
        stream.write(
            "Read-only all-time N32 integrity audit. Raw particle fields are never deduplicated, corrected, or rewritten.\n"
            "Ratios compare raw reconstructed moments with independently written compact massmom0--2.\n"
        )


if __name__ == "__main__":
    main()
