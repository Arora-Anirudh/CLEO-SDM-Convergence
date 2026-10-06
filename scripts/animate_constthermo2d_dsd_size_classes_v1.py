#!/usr/bin/env python3
"""Create DSD size-class animations from the audited fixed-20 2-D cache."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter
from matplotlib.colors import LogNorm
from matplotlib.lines import Line2D
import numpy as np

RESOLUTIONS = (2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192)
MEMBERS = tuple(range(1, 21))
SELECTED = (2, 512, 1024, 8192)
CLASSES = (
    ("cloud", 0.002, 50.0, "#3b82c4", "cloud: D < 0.1 mm"),
    ("drizzle", 50.0, 250.0, "#e7952e", "drizzle-sized: 0.1 <= D < 0.5 mm"),
    ("rain_sized", 250.0, 1000.0, "#c44e8b", "rain-sized: D >= 0.5 mm"),
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=5)
    return parser.parse_args()


def load(cache):
    masses, numbers, spatial = [], [], []
    time = number_edges = mass_edges = spatial_time = None
    for ncell in RESOLUTIONS:
        mrows, nrows, srows = [], [], []
        for member in MEMBERS:
            path = cache / f"ncell{ncell:04d}" / f"member{member:03d}.npz"
            with np.load(path) as raw:
                candidate_time = np.asarray(raw["time_min"], dtype=float)
                if time is None:
                    time = candidate_time
                    number_edges = np.asarray(raw["radius_edges_500_um"], dtype=float)
                    mass_edges = np.asarray(raw["radius_edges_1000_um"], dtype=float)
                    spatial_time = np.asarray(raw["spatial_selected_minutes"], dtype=float)
                elif not np.allclose(time, candidate_time, rtol=0, atol=1.0e-8):
                    raise ValueError(f"time mismatch: {path}")
                mrows.append(np.asarray(raw["mass_dsd_1000_g_m3"], dtype=float))
                nrows.append(np.asarray(raw["number_dsd_500_m3"], dtype=float))
                srows.append(np.asarray(raw["spatial_mass_selected_g_m3"], dtype=float))
        masses.append(np.stack(mrows))
        numbers.append(np.stack(nrows))
        spatial.append(np.stack(srows))
    return {
        "time": np.asarray(time), "number_edges": np.asarray(number_edges),
        "mass_edges": np.asarray(mass_edges), "mass": np.stack(masses),
        "number": np.stack(numbers), "spatial": np.stack(spatial),
        "spatial_time": np.asarray(spatial_time),
    }


def centres(edges):
    return np.sqrt(edges[:-1] * edges[1:])


def masks(radius):
    return {
        name: (radius >= lo) & ((radius < hi) if name != "rain_sized" else radius >= lo)
        for name, lo, hi, _, _ in CLASSES
    }


def fractions(mass, edges):
    widths = np.diff(np.log(edges))
    perbin = mass * widths[None, None, None, :]
    total = perbin.sum(axis=-1)
    return {
        name: np.divide(perbin[..., masks(centres(edges))[name]].sum(axis=-1), total,
                        out=np.zeros_like(total), where=total > 0)
        for name, *_ in CLASSES
    }


def limit(values):
    valid = values[np.isfinite(values) & (values > 0)]
    return np.percentile(valid, .1), np.percentile(valid, 99.9) * 1.25


def decorate(ax):
    for _, lo, hi, colour, _ in CLASSES:
        ax.axvspan(lo, hi, color=colour, alpha=.10, zorder=0)
    for boundary in (50, 250):
        ax.axvline(boundary, color="#5f6770", ls="--", lw=.8)
    ax.set(xscale="log", yscale="log", xlim=(.002, 1000))
    ax.grid(alpha=.22, which="both")


def draw_coloured(ax, radius, values, holder):
    for line in holder:
        line.remove()
    holder.clear()
    for name, _, _, colour, _ in CLASSES:
        mask = masks(radius)[name]
        holder.extend(ax.plot(radius[mask], values[mask], color=colour, lw=2.2))


def primary_animation(data, frac, output, fps):
    ridx = RESOLUTIONS.index(1024)
    time = data["time"]
    nr, mr = centres(data["number_edges"]), centres(data["mass_edges"])
    number, mass = data["number"][ridx].mean(axis=0), data["mass"][ridx].mean(axis=0)
    fig = plt.figure(figsize=(13, 8.8))
    grid = fig.add_gridspec(2, 2, height_ratios=(1, .9), hspace=.33, wspace=.24)
    axn, axm = fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])
    axf = fig.add_subplot(grid[1, :])
    for ax, title, ylabel, ylimits in (
        (axn, "Number DSD", r"$dN/d\ln r$ (m$^{-3}$)", limit(number)),
        (axm, "Liquid-mass DSD", r"$dM/d\ln r$ (g m$^{-3}$)", limit(mass)),
    ):
        decorate(ax)
        ax.set(title=title, xlabel=r"wet radius, $r$ ($\mu$m)", ylabel=ylabel, ylim=ylimits)
    meanfrac = {name: values[ridx].mean(axis=0) for name, values in frac.items()}
    for name, _, _, colour, label in CLASSES:
        axf.plot(time, meanfrac[name], color=colour, lw=2.4, label=label)
    axf.set(xlim=(0, 120), ylim=(0, 1), xlabel="time (min)", ylabel="liquid-mass fraction",
            title="Liquid mass in each size class")
    axf.grid(alpha=.25)
    axf.legend(ncol=3, loc="upper center", frameon=False)
    fig.suptitle(r"2-D fixed-20 DSD evolution: $N_{\rm cell}=1{,}024$", weight="bold", fontsize=16)
    fig.text(.5, .012, "Rain-sized is a radius class only. This null-boundary configuration does not measure surface rainfall.", ha="center", fontsize=9.2)
    lines_n, lines_m = [], []
    marker = axf.axvline(0, color="#222", ls="--", lw=1.2)
    stamp = fig.text(.5, .93, "", ha="center", weight="bold", fontsize=11)

    def update(frame):
        draw_coloured(axn, nr, number[frame], lines_n)
        draw_coloured(axm, mr, mass[frame], lines_m)
        marker.set_xdata([time[frame], time[frame]])
        stamp.set_text(f"stored time: {time[frame]:.0f} min")
        return lines_n + lines_m + [marker, stamp]

    animation = FuncAnimation(fig, update, frames=len(time), interval=1000/fps, blit=False)
    animation.save(output / "01_size_class_dsd_evolution_Ncell1024.gif", writer=PillowWriter(fps=fps), dpi=110)
    animation.save(
        output / "01_size_class_dsd_evolution_Ncell1024.mp4",
        writer=FFMpegWriter(
            fps=fps, bitrate=1800,
            extra_args=["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-pix_fmt", "yuv420p"],
        ),
        dpi=145,
    )
    plt.close(fig)


def comparison_animation(data, output, fps):
    time, radius = data["time"], centres(data["mass_edges"])
    fig, axes = plt.subplots(2, 2, figsize=(14.5, 10.0), sharex=True, sharey=True)
    ymin, ymax = limit(data["mass"])
    holders = [[] for _ in SELECTED]
    for ax, ncell in zip(axes.flat, SELECTED):
        decorate(ax)
        ax.set(title=fr"$N_{{cell}}={ncell:,}$", ylim=(ymin, ymax))
    for ax in axes[-1]:
        ax.set_xlabel(r"wet radius, $r$ ($\mu$m)")
    for ax in axes[:, 0]:
        ax.set_ylabel(r"$dM/d\ln r$ (g m$^{-3}$)")
    fig.suptitle("Mass-DSD evolution across representative resolutions", weight="bold", fontsize=17, y=.985)
    handles = [Line2D([], [], color=colour, lw=2.4, label=label) for _, _, _, colour, label in CLASSES]
    fig.legend(handles=handles, ncol=3, loc="upper center", bbox_to_anchor=(.5, .93), frameon=False, fontsize=9)
    fig.text(.5, .030, "Every curve is a 20-member mean. Colours identify contiguous size classes of one DSD.", ha="center", fontsize=10)
    stamp = fig.text(.5, .855, "", ha="center", weight="bold", fontsize=11)

    def update(frame):
        artists = []
        for ax, ncell, holder in zip(axes.flat, SELECTED, holders):
            profile = data["mass"][RESOLUTIONS.index(ncell)].mean(axis=0)[frame]
            draw_coloured(ax, radius, profile, holder)
            artists.extend(holder)
        stamp.set_text(f"stored time: {time[frame]:.0f} min")
        return artists + [stamp]

    animation = FuncAnimation(fig, update, frames=len(time), interval=1000/fps, blit=False)
    animation.save(output / "02_size_class_dsd_resolution_comparison.gif", writer=PillowWriter(fps=fps), dpi=105)
    animation.save(
        output / "02_size_class_dsd_resolution_comparison.mp4",
        writer=FFMpegWriter(
            fps=fps, bitrate=1800,
            extra_args=["-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-pix_fmt", "yuv420p"],
        ),
        dpi=140,
    )
    plt.close(fig)


def static_figures(data, frac, output):
    ridx = RESOLUTIONS.index(1024)
    time, edges = data["time"], data["mass_edges"]
    values = data["mass"][ridx].mean(axis=0).T
    positive = values[values > 0]
    time_edges = np.concatenate((
        [time[0] - 0.5 * (time[1] - time[0])],
        0.5 * (time[:-1] + time[1:]),
        [time[-1] + 0.5 * (time[-1] - time[-2])],
    ))
    fig, ax = plt.subplots(figsize=(13.5, 7.0))
    image = ax.pcolormesh(time_edges, edges, np.ma.masked_less_equal(values, 0), shading="flat",
                          norm=LogNorm(vmin=np.percentile(positive, .5), vmax=np.percentile(positive, 99.8)),
                          cmap="magma_r")
    for _, lo, hi, colour, _ in CLASSES:
        ax.axhspan(lo, hi, color=colour, alpha=.12)
    ax.axhline(50, color="white", ls="--", lw=1.1)
    ax.axhline(250, color="white", ls="--", lw=1.1)
    ax.text(2, 9, "cloud", color="white", weight="bold")
    ax.text(2, 110, "drizzle-sized", color="white", weight="bold")
    ax.text(2, 500, "rain-sized", color="white", weight="bold")
    ax.set(yscale="log", ylim=(.002, 1000), xlim=(0, 120), xlabel="time (min)",
           ylabel=r"wet radius, $r$ ($\mu$m)", title=r"Mass-DSD time–radius evolution: $N_{\rm cell}=1{,}024$")
    fig.colorbar(image, ax=ax, label=r"ensemble-mean $dM/d\ln r$ (g m$^{-3}$)")
    fig.subplots_adjust(top=.94, bottom=.13, left=.09, right=.90)
    fig.savefig(output / "03_mass_dsd_time_radius_Ncell1024.png", dpi=260, bbox_inches="tight", pad_inches=.10)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(18, 6.3), sharex=True, sharey=False)
    colours = plt.cm.viridis(np.linspace(.05, .96, len(SELECTED)))
    for ax, (name, _, _, _, label) in zip(axes, CLASSES):
        for ncell, colour in zip(SELECTED, colours):
            ax.plot(time, frac[name][RESOLUTIONS.index(ncell)].mean(axis=0), color=colour, lw=2, label=f"{ncell:,}")
        ax.set(title=label, xlabel="time (min)", ylabel="liquid-mass fraction")
        if name == "rain_sized":
            ax.set(yscale="symlog", ylim=(0, .1))
            ax.text(.5, .04, "expanded low-fraction scale", transform=ax.transAxes,
                    ha="center", fontsize=8.5, color="#59636e")
        else:
            ax.set(ylim=(0, 1))
        ax.grid(alpha=.25)
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.suptitle("Liquid-mass transfer between size classes", weight="bold", fontsize=17, y=.985)
    fig.legend(handles, labels, title=r"$N_{\rm cell}$", ncol=7, loc="upper center", bbox_to_anchor=(.5, .93), frameon=False, fontsize=8.5, title_fontsize=9)
    fig.subplots_adjust(top=.80, bottom=.14, left=.065, right=.985, wspace=.25)
    fig.savefig(output / "04_size_class_mass_fractions.png", dpi=260, bbox_inches="tight", pad_inches=.10)
    plt.close(fig)

    spatial = data["spatial"][ridx].mean(axis=0)
    pos = spatial[spatial > 0]
    xedges = zedges = np.linspace(0, 1500, 21)
    fig, axes = plt.subplots(1, 3, figsize=(17, 6.6), sharex=True, sharey=True)
    image = None
    norm = LogNorm(vmin=np.percentile(pos, 1), vmax=np.percentile(pos, 99.5))
    for ax, field, minute in zip(axes, spatial, data["spatial_time"]):
        image = ax.pcolormesh(xedges, zedges, np.ma.masked_less_equal(field, 0), shading="flat",
                              norm=norm, cmap="magma_r", edgecolors=(1, 1, 1, .22), linewidth=.28)
        ax.set(title=f"{minute:.0f} min", xlabel="horizontal distance, x (m)", aspect="equal")
    axes[0].set_ylabel("height, z (m)")
    fig.colorbar(image, ax=axes, pad=.02, shrink=.88, label=r"total-droplet mass concentration (g m$^{-3}$)")
    fig.suptitle(r"Native spatial grid: $N_{\rm cell}=1{,}024$ full-20 mean", weight="bold", fontsize=17, y=.975)
    fig.text(.5, .030, "Each tile is one 75 m × 75 m grid box. The cell edges show the actual spatial resolution.", ha="center", fontsize=10)
    fig.subplots_adjust(top=.88, bottom=.13, left=.065, right=.88, wspace=.15)
    fig.savefig(output / "05_native_grid_cell_mass_fields_Ncell1024.png", dpi=260, bbox_inches="tight", pad_inches=.10)
    plt.close(fig)


def write_readme(data, output):
    text = """# DSD size-class visualisation

All products use the audited 2-D fixed-20 cache; no CLEO trajectory was rerun.

Size categories use wet diameter D=2r:

- cloud: D < 0.1 mm, equivalently r < 50 micrometres;
- drizzle-sized: 0.1 <= D < 0.5 mm, equivalently 50 <= r < 250 micrometres;
- rain-sized: D >= 0.5 mm, equivalently r >= 250 micrometres.

The rain-sized label is a size class only. The constthermo2d executable uses
NullBoundaryConditions, therefore these figures do not diagnose surface
rainfall, rain-out, or rainfall onset.

The spatial field is natively 20 by 20 cells over 1500 m by 1500 m. Each cell
is 75 m by 75 m. Its blocky appearance is the physical grid resolution, not
an image-resolution problem.
"""
    (output / "README.md").write_text(text)
    (output / "metadata.json").write_text(json.dumps({
        "source_cache": "constthermo2d_fixedgrid_production_v1",
        "members_per_resolution": 20,
        "stored_outputs": int(len(data["time"])),
        "output_cadence_seconds": 120,
        "size_class_boundaries_radius_um": [50, 250],
        "boundary_interpretation": "Null boundaries; no surface rainfall diagnostic."
    }, indent=2) + "\n")


def main():
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    data = load(args.cache)
    frac = fractions(data["mass"], data["mass_edges"])
    primary_animation(data, frac, args.output, args.fps)
    comparison_animation(data, args.output, args.fps)
    static_figures(data, frac, args.output)
    write_readme(data, args.output)


if __name__ == "__main__":
    main()
