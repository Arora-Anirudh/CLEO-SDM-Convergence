"""Analyze one CLEO collision-only box-model run.

The distribution figure follows CLEO's ``shima2009_plotting.py`` and
``plotcleo.shima2009fig`` implementation at the repository's pinned CLEO
commit. A separate project-owned figure reports bulk and conservation
diagnostics without changing CLEO's validation plot.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import warnings
from pathlib import Path
from typing import Any

import awkward as ak
import matplotlib
import numpy as np
from ruamel.yaml import YAML

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cleo-source",
        required=True,
        type=Path,
        help="pinned CLEO source containing cleopy and plotcleo",
    )
    parser.add_argument(
        "--run-directory",
        required=True,
        type=Path,
        help="completed run containing config.yaml, inputs/ and output/",
    )
    parser.add_argument(
        "--kernel",
        required=True,
        choices=("golovin", "long"),
        help="collision kernel used by the completed run",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=None,
        help="fresh output directory; default RUN_DIRECTORY/analysis_v1",
    )
    parser.add_argument(
        "--times",
        nargs="+",
        type=float,
        default=(0.0, 1200.0, 2400.0, 3600.0),
        help="exact output times in seconds for distribution curves",
    )
    return parser.parse_args()


def load_yaml(filename: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    with filename.open("r", encoding="utf-8") as stream:
        return yaml.load(stream)


def validate_paths(cleo_source: Path, run_directory: Path, output_directory: Path) -> None:
    required = (
        cleo_source / "cleopy" / "__init__.py",
        cleo_source / "examples" / "exampleplotting" / "plotcleo" / "plotcleo" / "shima2009fig.py",
        run_directory / "config.yaml",
        run_directory / "inputs" / "grid.dat",
        run_directory / "output" / "collisions0d_setup.txt",
        run_directory / "output" / "collisions0d_solution.zarr",
        run_directory / "manifest.txt",
    )
    for required_path in required:
        if not required_path.exists():
            raise FileNotFoundError(f"required input is missing: {required_path}")
    if output_directory.exists():
        raise FileExistsError(
            f"refusing to overwrite existing diagnostic directory: {output_directory}"
        )


def import_cleo_plotting(cleo_source: Path):
    sys.path.insert(0, str(cleo_source))
    sys.path.insert(
        0,
        str(cleo_source / "examples" / "exampleplotting" / "plotcleo"),
    )

    from cleopy.sdmout_src import pygbxsdat, pysetuptxt, pyzarr  # noqa: PLC0415
    from plotcleo import shima2009fig  # noqa: PLC0415

    return pygbxsdat, pysetuptxt, pyzarr, shima2009fig


def require_exact_times(
    available: np.ndarray,
    requested: list[float],
    *,
    absolute_tolerance_s: float = 1.0e-3,
) -> None:
    """Require each nominal time to match a stored output within float tolerance."""
    for requested_time in requested:
        if not np.any(
            np.isclose(
                available,
                requested_time,
                rtol=0.0,
                atol=absolute_tolerance_s,
            )
        ):
            raise ValueError(
                f"requested time {requested_time:g} s is not an exact dataset output; "
                f"available times are {available.tolist()}"
            )


def calculate_bulk_row(
    *,
    time_s: float,
    radius_um: np.ndarray,
    multiplicity: np.ndarray,
    water_mass_g: np.ndarray,
    domain_volume_m3: float,
    initial_liquid_water_gm3: float,
) -> dict[str, float | int]:
    if radius_um.shape != multiplicity.shape or radius_um.shape != water_mass_g.shape:
        raise ValueError("radius, multiplicity and water mass must have identical shapes")
    if domain_volume_m3 <= 0:
        raise ValueError("domain volume must be positive")

    represented_mass_g = multiplicity * water_mass_g
    liquid_water_gm3 = float(np.sum(represented_mass_g) / domain_volume_m3)
    if initial_liquid_water_gm3 <= 0:
        relative_drift = 0.0
    else:
        relative_drift = liquid_water_gm3 / initial_liquid_water_gm3 - 1.0

    total_mass = float(np.sum(represented_mass_g))

    def mass_fraction_at_or_above(threshold_um: float) -> float:
        if total_mass <= 0:
            return float("nan")
        return float(np.sum(represented_mass_g[radius_um >= threshold_um]) / total_mass)

    return {
        "time_s": float(time_s),
        "n_superdroplet_records": int(radius_um.size),
        "number_concentration_cm3": float(np.sum(multiplicity) / domain_volume_m3 / 1.0e6),
        "liquid_water_gm3": liquid_water_gm3,
        "relative_liquid_mass_drift": relative_drift,
        "max_radius_um": float(np.max(radius_um)),
        "mass_fraction_r_ge_40um": mass_fraction_at_or_above(40.0),
        "mass_fraction_r_ge_1000um": mass_fraction_at_or_above(1000.0),
    }


def relative_l1_error(
    numerical: np.ndarray,
    reference: np.ndarray,
    radius_centres_um: np.ndarray,
) -> float:
    if numerical.shape != reference.shape or numerical.shape != radius_centres_um.shape:
        raise ValueError("distribution arrays must have identical shapes")
    log_radius = np.log(radius_centres_um)
    reference_integral = np.trapezoid(np.abs(reference), x=log_radius)
    if reference_integral <= 0:
        return float("nan")
    return float(np.trapezoid(np.abs(numerical - reference), x=log_radius) / reference_integral)


def calculate_diagnostics(
    *,
    time,
    superdrops,
    domain_volume_m3: float,
    kernel: str,
    number_concentration_m3: float,
    volume_exponential_scale_m: float,
    max_superdroplets: int,
    shima2009fig,
) -> list[dict[str, float | int]]:
    radii = superdrops["radius"]
    multiplicities = superdrops["xi"]
    solute_masses = superdrops["msol"]
    all_radii = np.asarray(ak.to_numpy(ak.flatten(radii)), dtype=float)
    radius_span_um = [float(np.nanmin(all_radii)), float(np.nanmax(all_radii))]
    smooth_sigma = 0.62 * max_superdroplets ** (-1.0 / 5.0)

    rows: list[dict[str, float | int]] = []
    initial_liquid_water_gm3: float | None = None
    for index, time_s in enumerate(np.asarray(time.secs, dtype=float)):
        radius_um = np.asarray(ak.to_numpy(radii[index]), dtype=float)
        multiplicity = np.asarray(ak.to_numpy(multiplicities[index]), dtype=float)
        solute_mass_g = np.asarray(ak.to_numpy(solute_masses[index]), dtype=float)
        water_mass_g = np.asarray(superdrops.m_water(radius_um, solute_mass_g), dtype=float)

        if initial_liquid_water_gm3 is None:
            initial_liquid_water_gm3 = float(np.sum(multiplicity * water_mass_g) / domain_volume_m3)

        row = calculate_bulk_row(
            time_s=time_s,
            radius_um=radius_um,
            multiplicity=multiplicity,
            water_mass_g=water_mass_g,
            domain_volume_m3=domain_volume_m3,
            initial_liquid_water_gm3=initial_liquid_water_gm3,
        )

        if kernel == "golovin":
            numerical, radius_centres_um = shima2009fig.calc_massdens_distrib(
                radius_span_um,
                500,
                domain_volume_m3,
                multiplicity,
                radius_um,
                superdrops,
                smooth_sigma,
            )
            analytical, _ = shima2009fig.golovin_analytical(
                radius_span_um,
                float(time_s),
                500,
                number_concentration_m3,
                volume_exponential_scale_m,
                superdrops.RHO_L(),
            )
            # Preserve CLEO's validation-error convention: corresponding numerical
            # and analytical bins are subtracted by index. Their reported centres
            # differ slightly because plotcleo uses an arithmetic midpoint for the
            # numerical bins and a geometric midpoint for the analytical bins.
            row["golovin_l1_relative"] = relative_l1_error(
                numerical,
                analytical,
                radius_centres_um,
            )
        else:
            row["golovin_l1_relative"] = float("nan")

        rows.append(row)

    return rows


def write_diagnostics_csv(filename: Path, rows: list[dict[str, float | int]]) -> None:
    with filename.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_bulk_diagnostics(
    rows: list[dict[str, float | int]],
    *,
    kernel: str,
    savename: Path,
) -> None:
    time_minutes = np.asarray([float(row["time_s"]) for row in rows]) / 60.0

    def values(key: str) -> np.ndarray:
        return np.asarray([float(row[key]) for row in rows], dtype=float)

    fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(13, 7), sharex=True)
    fig.suptitle(f"CLEO collisions0d bulk diagnostics — {kernel.capitalize()} kernel")

    axes[0, 0].plot(time_minutes, values("number_concentration_cm3"), marker="o")
    axes[0, 0].set_ylabel("droplet concentration /cm$^{-3}$")

    axes[0, 1].plot(time_minutes, values("liquid_water_gm3"), marker="o")
    axes[0, 1].set_ylabel("liquid water /g m$^{-3}$")

    axes[0, 2].plot(time_minutes, values("relative_liquid_mass_drift"), marker="o")
    axes[0, 2].axhline(0.0, color="k", linewidth=0.8)
    axes[0, 2].set_ylabel("relative liquid-mass drift")
    axes[0, 2].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))

    axes[1, 0].plot(time_minutes, values("max_radius_um"), marker="o")
    axes[1, 0].set_yscale("log")
    axes[1, 0].set_ylabel("maximum radius /μm")

    axes[1, 1].plot(
        time_minutes,
        values("mass_fraction_r_ge_40um"),
        marker="o",
        label="$r\\geq40$ μm",
    )
    axes[1, 1].plot(
        time_minutes,
        values("mass_fraction_r_ge_1000um"),
        marker="o",
        label="$r\\geq1000$ μm",
    )
    axes[1, 1].set_ylim(-0.02, 1.02)
    axes[1, 1].set_ylabel("liquid-mass fraction")
    axes[1, 1].legend()

    if kernel == "golovin":
        axes[1, 2].plot(time_minutes, values("golovin_l1_relative"), marker="o")
        axes[1, 2].set_ylabel("relative Golovin L1 error")
    else:
        axes[1, 2].plot(
            time_minutes,
            values("n_superdroplet_records"),
            marker="o",
        )
        axes[1, 2].set_ylabel("stored superdroplet records")

    for axis in axes[-1, :]:
        axis.set_xlabel("time /min")
    for axis in axes.flat:
        axis.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(savename, dpi=400, bbox_inches="tight", facecolor="w", format="png")
    plt.close(fig)
    print(f"Figure .png saved as: {savename}")


def main() -> None:
    args = parse_args()
    cleo_source = args.cleo_source.resolve()
    run_directory = args.run_directory.resolve()
    output_directory = (
        args.output_directory.resolve()
        if args.output_directory is not None
        else run_directory / "analysis_v1"
    )
    validate_paths(cleo_source, run_directory, output_directory)

    pygbxsdat, pysetuptxt, pyzarr, shima2009fig = import_cleo_plotting(cleo_source)

    runtime_config = load_yaml(run_directory / "config.yaml")
    setup_filename = run_directory / "output" / "collisions0d_setup.txt"
    grid_filename = run_directory / "inputs" / "grid.dat"
    dataset = run_directory / "output" / "collisions0d_solution.zarr"

    setup_config = pysetuptxt.get_config(setup_filename, nattrs=3, isprint=True)
    consts = pysetuptxt.get_consts(setup_filename, isprint=True)
    gridboxes = pygbxsdat.get_gridboxes(
        grid_filename,
        consts["COORD0"],
        isprint=True,
    )
    time = pyzarr.get_time(dataset)
    superdrops = pyzarr.get_supers(dataset, consts)

    requested_times = [float(value) for value in args.times]
    require_exact_times(np.asarray(time.secs, dtype=float), requested_times)
    output_directory.mkdir(parents=True)

    super_config = runtime_config["python_initconds"]["supers"]
    number_concentration_m3 = float(super_config["numconc"])
    volume_exponential_scale_m = float(super_config["volexpr0"])
    max_superdroplets = int(setup_config["maxnsupers"])
    if max_superdroplets != int(runtime_config["domain"]["maxnsupers"]):
        raise RuntimeError("setup record and runtime YAML disagree on maxnsupers")
    if int(setup_config["ntime"]) != len(time.secs):
        raise RuntimeError("setup record and Zarr dataset disagree on output count")
    domain_volume_m3 = float(gridboxes["domainvol"])
    smooth_sigma = 0.62 * max_superdroplets ** (-1.0 / 5.0)

    distribution_figure = output_directory / f"{args.kernel}_mass_distribution.png"
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="invalid value encountered in multiply",
            category=RuntimeWarning,
        )
        shima2009fig.plot_validation_figure(
            args.kernel == "golovin",
            time,
            superdrops,
            requested_times,
            domain_volume_m3,
            number_concentration_m3,
            volume_exponential_scale_m,
            smooth_sigma,
            xlims=[10, 5000],
            savename=distribution_figure,
            withgol=args.kernel == "golovin",
        )
    plt.close("all")

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="invalid value encountered in multiply",
            category=RuntimeWarning,
        )
        rows = calculate_diagnostics(
            time=time,
            superdrops=superdrops,
            domain_volume_m3=domain_volume_m3,
            kernel=args.kernel,
            number_concentration_m3=number_concentration_m3,
            volume_exponential_scale_m=volume_exponential_scale_m,
            max_superdroplets=max_superdroplets,
            shima2009fig=shima2009fig,
        )
    diagnostics_csv = output_directory / "bulk_diagnostics.csv"
    write_diagnostics_csv(diagnostics_csv, rows)

    bulk_figure = output_directory / f"{args.kernel}_bulk_diagnostics.png"
    plot_bulk_diagnostics(rows, kernel=args.kernel, savename=bulk_figure)

    metadata = {
        "status": "completed",
        "kernel": args.kernel,
        "run_directory": str(run_directory),
        "cleo_source": str(cleo_source),
        "dataset": str(dataset),
        "setup_filename": str(setup_filename),
        "grid_filename": str(grid_filename),
        "requested_distribution_times_s": requested_times,
        "domain_volume_m3": domain_volume_m3,
        "number_concentration_m3": number_concentration_m3,
        "volume_exponential_scale_m": volume_exponential_scale_m,
        "max_superdroplets": max_superdroplets,
        "smoothing_sigma_ln_radius": smooth_sigma,
        "maximum_absolute_relative_mass_drift": max(
            abs(float(row["relative_liquid_mass_drift"])) for row in rows
        ),
        "outputs": {
            "bulk_csv": diagnostics_csv.name,
            "distribution_figure": distribution_figure.name,
            "bulk_figure": bulk_figure.name,
        },
    }
    metadata_filename = output_directory / "diagnostic_metadata.json"
    metadata_filename.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print("DIAGNOSTIC_PASS=1")
    print(f"output_directory={output_directory}")
    print(
        f"maximum_absolute_relative_mass_drift={metadata['maximum_absolute_relative_mass_drift']:.8e}"
    )


if __name__ == "__main__":
    main()
