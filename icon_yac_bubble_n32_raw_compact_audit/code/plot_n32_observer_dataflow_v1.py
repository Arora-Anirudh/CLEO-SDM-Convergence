#!/usr/bin/env python3
"""Create a source-backed explanation of N=32 compact versus ragged CLEO outputs."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "results"


def box(ax, xy, width, height, title, body, *, face, edge="#334155", title_colour="#102a43"):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y), width, height, boxstyle="round,pad=0.012,rounding_size=0.018",
        facecolor=face, edgecolor=edge, linewidth=1.4,
    )
    ax.add_patch(patch)
    ax.text(x + 0.018, y + height - 0.042, title, ha="left", va="top", fontsize=12,
            fontweight="bold", color=title_colour)
    ax.text(x + 0.018, y + height - 0.088, body, ha="left", va="top", fontsize=9.3,
            color="#1f2937", linespacing=1.35)


def arrow(ax, start, end, text=None, *, colour="#334155", text_offset=(0.0, 0.0)):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=15,
                                 linewidth=1.6, color=colour))
    if text:
        mid = ((start[0] + end[0]) / 2 + text_offset[0], (start[1] + end[1]) / 2 + text_offset[1])
        ax.text(*mid, text, ha="center", va="center", fontsize=8.6, color=colour,
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.3})


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(15.5, 10.2), constrained_layout=False)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    fig.text(0.5, 0.965, "N=32 ICON–YAC–CLEO: compact and ragged outputs are independent observer paths",
             ha="center", va="top", fontsize=18, fontweight="bold", color="#102a43")
    fig.text(0.5, 0.932,
             "Source traced in the exact CLEO bubble code used on Levante; 241 stored states at a 30 s observation interval.",
             ha="center", va="top", fontsize=10.5, color="#334155")

    box(
        ax, (0.34, 0.755), 0.32, 0.125,
        "Live CLEO model state at an observation time",
        "d_supers: superdroplet attributes in memory\n"
        "(id, gridbox membership, coordinates, multiplicity ξ, radius r, solute mass)\n"
        "d_gbxs: thermodynamics and wind state in memory",
        face="#e7f0f7",
    )
    ax.text(0.50, 0.905, "OBSTSTEP = 30 s", ha="center", va="center", fontsize=10,
            fontweight="bold", color="#0f5f74")

    box(
        ax, (0.055, 0.475), 0.39, 0.205,
        "Compact observer path — direct in-memory reductions",
        "MassMomentsObserver: Kokkos reduction separately in every gridbox\n"
        "M₀ = Σξ;  M₁ = Σξm;  M₂ = Σξm², using each live drop.mass()\n"
        "StateObserver: live T, p, qᵥ, u, v, w gridbox state\n"
        "MonitorPrecipitationObserver: live boundary-crossing monitor\n\n"
        "No saved ragged array is read in this calculation.",
        face="#e7f6ec", edge="#198754", title_colour="#14532d",
    )
    box(
        ax, (0.555, 0.475), 0.39, 0.205,
        "Ragged particle-output path — attribute copies then serialization",
        "SuperdropsObserver: loops over all live d_supers and copies attributes\n"
        "sdId, coord1/2/3, ξ, r, msol → one concatenated ‘superdroplets’ axis\n"
        "raggedcount(time) marks the number of records in each saved state\n\n"
        "sdgbxindex was commented out in this bubble executable.",
        face="#fff3e5", edge="#b7791f", title_colour="#7c2d12",
    )
    arrow(ax, (0.405, 0.755), (0.255, 0.681), "same live state", colour="#198754", text_offset=(-0.02, 0.02))
    arrow(ax, (0.595, 0.755), (0.745, 0.681), "same live state", colour="#b7791f", text_offset=(0.02, 0.02))

    box(
        ax, (0.055, 0.230), 0.39, 0.165,
        "Compact arrays stored in bubble3d_sol.zarr",
        "massmom0/1/2, massmom*_raindrops, temp, press, qvap, uvel, vvel, wvel, precip\n"
        "Each dense field: (time, gbxindex) = (241, 768)\n"
        "These are the appropriate source for gridded mass, thermodynamic, wind, and boundary-flux diagnostics.",
        face="#e7f6ec", edge="#198754", title_colour="#14532d",
    )
    box(
        ax, (0.555, 0.230), 0.39, 0.165,
        "Ragged arrays stored in the same Zarr group",
        "sdId, coord1/2/3, ξ, radius, msol: each (superdroplets) = (5,339,479)\n"
        "raggedcount and totnsupers: each (time) = (241,)\n"
        "Useful for particle snapshots, but any reconstructed bulk statistic must agree with the compact observer before use.",
        face="#fff3e5", edge="#b7791f", title_colour="#7c2d12",
    )
    arrow(ax, (0.25, 0.475), (0.25, 0.396), colour="#198754")
    arrow(ax, (0.75, 0.475), (0.75, 0.396), colour="#b7791f")

    box(
        ax, (0.105, 0.033), 0.79, 0.163,
        "N=32 all-time consistency result and inference",
        "The audit uses CLEO’s total-mass definition: m = 4πρₗr³/3 + mₛₒₗ(1 − ρₗ/ρₛₒₗ).\n"
        "At t = 0: raw/compact M₁ = 0.99999994. At 59 min: raw/compact M₁ = 1.9007 while water-only/compact = 1.9001;\n"
        "the aerosol term is only 0.03% of raw mass. Aerosol accounting therefore cannot explain the discrepancy.\n"
        "The mismatch proves separate output paths, makes raw-derived bulk diagnostics provisional, and does not itself identify the cause.",
        face="#fef2f2", edge="#b91c1c", title_colour="#991b1b",
    )
    arrow(ax, (0.25, 0.230), (0.37, 0.198), colour="#64748b")
    arrow(ax, (0.75, 0.230), (0.63, 0.198), colour="#64748b")

    for extension in ("png", "pdf"):
        fig.savefig(OUTDIR / f"02_n32_compact_ragged_observer_paths.{extension}", dpi=220, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
