#!/usr/bin/env python3
"""Render the one-realization Ncell=512 Kokkos Threads timing trade-off."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "analysis" / "constthermo2d_thread_benchmark_v1"


def main() -> None:
    with (RESULTS / "thread_benchmark.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    threads = [int(row["threads"]) for row in rows]
    wall = [float(row["model_wall_seconds"]) for row in rows]
    cpu_hours = [float(row["allocated_cpu_hours"]) for row in rows]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 4.2), constrained_layout=True)
    for axis, values, ylabel, optimum, note in (
        (axes[0], wall, "model-only wall time (s)", 64, "fastest"),
        (axes[1], cpu_hours, "allocated CPU-hours", 16, "lowest measured cost"),
    ):
        axis.plot(threads, values, color="#1b6f8a", marker="o", lw=2.2, ms=6)
        axis.scatter([optimum], [values[threads.index(optimum)]], s=88, zorder=3, color="#dc8c1d")
        axis.annotate(
            f"{optimum} threads\n{note}",
            (optimum, values[threads.index(optimum)]), xytext=(7, 13),
            textcoords="offset points", fontsize=9, color="#7a4300",
        )
        axis.set_xscale("log", base=2)
        axis.set_xticks(threads, labels=[str(value) for value in threads])
        axis.set_xlabel("Kokkos Threads host threads")
        axis.set_ylabel(ylabel)
        axis.spines[["top", "right"]].set_visible(False)
    axes[0].set_title("Time-to-solution")
    axes[1].set_title("Scheduler allocation cost")
    fig.suptitle(
        "2-D constthermo2d, $N_{cell}=512$: one-input Kokkos thread-scaling check",
        fontsize=13, fontweight="bold",
    )
    fig.text(
        0.5, -0.02,
        "One full 0–7200 s realization per thread count; same accepted native input. "
        "Operational timing only, not a physical comparison.",
        ha="center", fontsize=8.5,
    )
    fig.savefig(RESULTS / "thread_scaling_tradeoff.png", dpi=220, bbox_inches="tight")


if __name__ == "__main__":
    main()
