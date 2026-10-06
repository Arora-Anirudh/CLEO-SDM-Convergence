#!/usr/bin/env python3
"""Render the native 2-D CLEO mass-moment field as an ensemble animation.

Inputs are compact ensemble means exported from the raw ``MassMomentsObserver``
at every stored 120-second model output.  No interpolation is used: every
frame is an actual CLEO observer time and each coloured square is one native
75 m by 75 m horizontal grid cell, vertically integrated over the 20 m depth.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
from matplotlib.colors import LogNorm


DOMAIN_M = 1500.0
GRID_N = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=5)
    return parser.parse_args()


def read_fields(paths: list[Path]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    time_ref: np.ndarray | None = None
    ncell_rows: list[np.ndarray] = []
    fields: list[np.ndarray] = []
    for path in paths:
        with np.load(path) as source:
            time = np.asarray(source["time_min"], dtype=float)
            if time_ref is None:
                time_ref = time
            elif not np.allclose(time_ref, time, rtol=0.0, atol=1.0e-8):
                raise ValueError(f"time mismatch: {path}")
            ncell_rows.append(np.asarray(source["ncell"], dtype=int))
            fields.append(np.asarray(source["ensemble_mean_mass_g_m3"], dtype=float))
    ncell = np.concatenate(ncell_rows)
    field = np.concatenate(fields, axis=0)
    order = np.argsort(ncell)
    return np.asarray(time_ref), ncell[order], field[order]


def make_animation(time_min: np.ndarray, ncell: np.ndarray, fields: np.ndarray, output: Path, fps: int) -> None:
    output.mkdir(parents=True, exist_ok=True)
    positive = fields[np.isfinite(fields) & (fields > 0)]
    # A common, fixed physical scale makes the three resolutions comparable.
    # The lower bound retains the initially uniform cloud; zero means no mass.
    norm = LogNorm(vmin=1.0e-8, vmax=np.percentile(positive, 99.9))
    cmap = plt.get_cmap("magma_r").copy()
    cmap.set_bad("#f7f7f7")
    xedges = np.linspace(0.0, DOMAIN_M, GRID_N + 1)
    zedges = np.linspace(0.0, DOMAIN_M, GRID_N + 1)

    # Keep explicit space for the figure-wide heading and explanatory footer.
    # ``tight_layout``/``constrained_layout`` do not reliably reserve space for
    # both a shared colourbar and figure-level text in the static first frame.
    fig, axes = plt.subplots(1, len(ncell), figsize=(15.6, 6.0), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.060, right=0.895, bottom=0.155, top=0.825, wspace=0.20)
    if len(ncell) == 1:
        axes = [axes]
    artists = []
    for axis, resolution, field in zip(axes, ncell, fields, strict=True):
        image = axis.pcolormesh(xedges, zedges, np.ma.masked_less_equal(field[0], 0.0), cmap=cmap, norm=norm, shading="flat")
        artists.append(image)
        axis.set_title(rf"$N_{{cell}}={resolution:,}$", weight="bold")
        axis.set_aspect("equal")
        axis.set_xlabel("horizontal distance, x (m)")
    axes[0].set_ylabel("height, z (m)")
    colorbar = fig.colorbar(artists[-1], ax=axes, shrink=0.89, pad=0.025)
    colorbar.set_label(r"total-droplet mass concentration (g m$^{-3}$)")
    title = fig.suptitle("2-D CLEO spatial liquid-mass evolution — 0 min", y=0.955, weight="bold", fontsize=15)
    subtitle = fig.text(
        0.5, 0.045,
        "Ensemble mean of 20 members; every frame is a stored 120 s CLEO output. "
        "Native 75 m × 75 m cells; colours share one fixed logarithmic physical scale.",
        ha="center", fontsize=9.3,
    )

    def update(frame: int):
        for artist, field in zip(artists, fields, strict=True):
            artist.set_array(np.ma.masked_less_equal(field[frame], 0.0).ravel())
        title.set_text(f"2-D CLEO spatial liquid-mass evolution — {time_min[frame]:.0f} min")
        return (*artists, title, subtitle)

    animation = FuncAnimation(fig, update, frames=len(time_min), interval=1000 / fps, blit=False)
    animation.save(output / "spatial_total_droplet_mass_evolution_Ncell2_1024_8192.mp4", writer=FFMpegWriter(fps=fps, bitrate=2200), dpi=160)
    animation.save(output / "spatial_total_droplet_mass_evolution_Ncell2_1024_8192.gif", writer=PillowWriter(fps=fps), dpi=120)
    update(0)
    fig.savefig(output / "spatial_total_droplet_mass_evolution_first_frame.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    time, ncell, fields = read_fields(args.input)
    make_animation(time, ncell, fields, args.output_dir, args.fps)
    print(f"SPATIAL_MASS_ANIMATION_PASS frames={len(time)} resolutions={','.join(map(str, ncell))}")


if __name__ == "__main__":
    main()
