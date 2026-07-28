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
import hashlib
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

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from golovin_stage0 import (  # noqa: E402
    first_threshold_crossing,
    fixed_bin_mass_density,
    fixed_bin_relative_l1,
    golovin_analytical_mass_density,
    golovin_analytical_radius_moments,
    logarithmic_radius_edges,
    mass_fraction_at_or_above,
    mass_weighted_radius_quantile,
    radius_moment,
    relative_error,
    water_equivalent_droplet_mass_g,
)


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
        help="fresh output directory; default RUN_DIRECTORY/analysis_stage0_v1",
    )
    parser.add_argument(
        "--stage0-config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "config" / "golovin_stage0_development.yaml",
        help="registered fixed-bin, threshold and statistical settings",
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


def sha256_file(filename: Path) -> str:
    digest = hashlib.sha256()
    with filename.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_key_value_manifest(filename: Path) -> dict[str, str]:
    """Read the ``key=value`` records and ignore following checksum lines."""
    records: dict[str, str] = {}
    for line in filename.read_text(encoding="utf-8").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        if key and key.replace("_", "").isalnum():
            records[key] = value
    return records


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
    large_drop_threshold_um: float = 1000.0,
    mass_quantile: float = 0.99,
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

    return {
        "time_s": float(time_s),
        "n_superdroplet_records": int(radius_um.size),
        "number_concentration_cm3": float(np.sum(multiplicity) / domain_volume_m3 / 1.0e6),
        "liquid_water_gm3": liquid_water_gm3,
        "relative_liquid_mass_drift": relative_drift,
        "radius_moment_0_m3": radius_moment(
            order=0,
            radius_um=radius_um,
            multiplicity=multiplicity,
            domain_volume_m3=domain_volume_m3,
        ),
        "radius_moment_3_um3_m3": radius_moment(
            order=3,
            radius_um=radius_um,
            multiplicity=multiplicity,
            domain_volume_m3=domain_volume_m3,
        ),
        "radius_moment_6_um6_m3": radius_moment(
            order=6,
            radius_um=radius_um,
            multiplicity=multiplicity,
            domain_volume_m3=domain_volume_m3,
        ),
        "max_radius_um": float(np.max(radius_um)),
        "mass_fraction_r_ge_40um": mass_fraction_at_or_above(
            radius_um,
            represented_mass_g,
            40.0,
        ),
        "mass_fraction_r_ge_large_threshold": mass_fraction_at_or_above(
            radius_um,
            represented_mass_g,
            large_drop_threshold_um,
        ),
        # Retained for compatibility while the registered development
        # threshold is 1000 um.
        "mass_fraction_r_ge_1000um": mass_fraction_at_or_above(
            radius_um,
            represented_mass_g,
            1000.0,
        ),
        "mass_weighted_radius_q99_um": mass_weighted_radius_quantile(
            radius_um,
            represented_mass_g,
            mass_quantile,
        ),
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
    fixed_edges_um: np.ndarray,
    large_drop_threshold_um: float,
    mass_quantile: float,
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
            large_drop_threshold_um=large_drop_threshold_um,
            mass_quantile=mass_quantile,
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

            wet_mass_g = water_equivalent_droplet_mass_g(
                radius_um,
                superdrops.RHO_L(),
            )
            fixed_numerical = fixed_bin_mass_density(
                radius_um=radius_um,
                multiplicity=multiplicity,
                droplet_mass_g=wet_mass_g,
                domain_volume_m3=domain_volume_m3,
                edges_um=fixed_edges_um,
            )
            fixed_analytical = golovin_analytical_mass_density(
                edges_um=fixed_edges_um,
                time_s=float(time_s),
                initial_number_concentration_m3=number_concentration_m3,
                volume_exponential_scale_radius_m=volume_exponential_scale_m,
                liquid_water_density_kgm3=superdrops.RHO_L(),
            )
            row["golovin_fixed_bin_l1_relative"] = fixed_bin_relative_l1(
                fixed_numerical.mass_density_gm3_per_ln_radius,
                fixed_analytical,
                fixed_edges_um,
            )
            row["fixed_bin_mass_below_range_fraction"] = fixed_numerical.mass_below_range_fraction
            row["fixed_bin_mass_above_range_fraction"] = fixed_numerical.mass_above_range_fraction

            analytical_moments = golovin_analytical_radius_moments(
                time_s=float(time_s),
                initial_number_concentration_m3=number_concentration_m3,
                volume_exponential_scale_radius_m=volume_exponential_scale_m,
            )
            for order, column in (
                (0, "radius_moment_0_m3"),
                (3, "radius_moment_3_um3_m3"),
                (6, "radius_moment_6_um6_m3"),
            ):
                row[f"golovin_analytical_{column}"] = analytical_moments[order]
                row[f"golovin_relative_error_{column}"] = relative_error(
                    float(row[column]),
                    analytical_moments[order],
                )
        else:
            row["golovin_l1_relative"] = float("nan")
            row["golovin_fixed_bin_l1_relative"] = float("nan")
            row["fixed_bin_mass_below_range_fraction"] = float("nan")
            row["fixed_bin_mass_above_range_fraction"] = float("nan")
            for column in (
                "radius_moment_0_m3",
                "radius_moment_3_um3_m3",
                "radius_moment_6_um6_m3",
            ):
                row[f"golovin_analytical_{column}"] = float("nan")
                row[f"golovin_relative_error_{column}"] = float("nan")

        rows.append(row)

    return rows


def write_diagnostics_csv(filename: Path, rows: list[dict[str, object]]) -> None:
    with filename.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_bulk_diagnostics(
    rows: list[dict[str, float | int]],
    *,
    kernel: str,
    large_drop_threshold_um: float,
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
    axes[0, 1].ticklabel_format(axis="y", style="plain", useOffset=False)

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
        values("mass_fraction_r_ge_large_threshold"),
        marker="o",
        label=rf"$r\geq{large_drop_threshold_um:g}$ μm",
    )
    axes[1, 1].set_ylim(-0.02, 1.02)
    axes[1, 1].set_ylabel("liquid-mass fraction")
    axes[1, 1].legend()

    if kernel == "golovin":
        axes[1, 2].plot(
            time_minutes,
            values("golovin_fixed_bin_l1_relative"),
            marker="o",
        )
        axes[1, 2].set_ylabel("fixed-bin relative Golovin L1 error")
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
        else run_directory / "analysis_stage0_v1"
    )
    stage0_config_filename = args.stage0_config.resolve()
    validate_paths(cleo_source, run_directory, output_directory)
    if not stage0_config_filename.is_file():
        raise FileNotFoundError(f"Stage-0 configuration is missing: {stage0_config_filename}")

    pygbxsdat, pysetuptxt, pyzarr, shima2009fig = import_cleo_plotting(cleo_source)

    runtime_config = load_yaml(run_directory / "config.yaml")
    run_manifest = load_key_value_manifest(run_directory / "manifest.txt")
    stage0_config = load_yaml(stage0_config_filename)
    diagnostic_config = stage0_config["diagnostics"]
    fixed_edges_um = logarithmic_radius_edges(
        float(diagnostic_config["radius_minimum_um"]),
        float(diagnostic_config["radius_maximum_um"]),
        int(diagnostic_config["number_of_log_radius_bins"]),
    )
    large_drop_threshold_um = float(diagnostic_config["large_drop_threshold_um"])
    mass_quantile = float(diagnostic_config["mass_weighted_radius_quantile"])
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
            fixed_edges_um=fixed_edges_um,
            large_drop_threshold_um=large_drop_threshold_um,
            mass_quantile=mass_quantile,
        )
    member_identifiers: dict[str, str | int | float] = {
        "run_label": run_manifest.get("run_label", run_directory.name),
        "kernel": args.kernel,
        "matrix_stage": run_manifest.get("matrix_stage", "single_run"),
        "initialization_family": run_manifest.get(
            "initialization_family",
            "unspecified",
        ),
        "matrix_case_index": int(run_manifest.get("matrix_case_index", -1)),
        "member_index": int(run_manifest.get("member_index", -1)),
        "initialization_seed": run_manifest.get("initialization_seed", "unknown"),
        "collision_seed": run_manifest.get("collision_seed", "unknown"),
        "max_superdroplets": max_superdroplets,
        "collision_timestep_s": float(runtime_config["timesteps"]["COLLTSTEP"]),
        "observation_timestep_s": float(runtime_config["timesteps"]["OBSTSTEP"]),
        "end_time_s": float(runtime_config["timesteps"]["T_END"]),
    }
    rows = [{**member_identifiers, **row} for row in rows]
    diagnostics_csv = output_directory / "member_time_diagnostics.csv"
    write_diagnostics_csv(diagnostics_csv, rows)

    crossing = first_threshold_crossing(
        np.asarray([float(row["time_s"]) for row in rows]),
        np.asarray([float(row["mass_fraction_r_ge_40um"]) for row in rows]),
        float(diagnostic_config["onset_mass_fraction"]),
    )
    member_summary = {
        **member_identifiers,
        "t10_status": crossing.status,
        "t10_lower_bound_s": crossing.lower_bound_s,
        "t10_upper_bound_s": crossing.upper_bound_s,
        "t10_first_recorded_crossing_s": crossing.first_recorded_crossing_s,
        "maximum_absolute_liquid_mass_drift": float(
            np.max(
                np.abs(
                    np.asarray(
                        [float(row["relative_liquid_mass_drift"]) for row in rows],
                        dtype=float,
                    )
                )
            )
        ),
        "large_drop_threshold_um": large_drop_threshold_um,
        "mass_weighted_radius_quantile": mass_quantile,
    }
    write_diagnostics_csv(output_directory / "member_summary.csv", [member_summary])

    bulk_figure = output_directory / f"{args.kernel}_bulk_diagnostics.png"
    plot_bulk_diagnostics(
        rows,
        kernel=args.kernel,
        large_drop_threshold_um=large_drop_threshold_um,
        savename=bulk_figure,
    )

    metadata = {
        "status": "completed",
        "kernel": args.kernel,
        "run_directory": str(run_directory),
        "cleo_source": str(cleo_source),
        "dataset": str(dataset),
        "stage0_config": str(stage0_config_filename),
        "stage0_config_sha256": sha256_file(stage0_config_filename),
        "stage0_experiment_status": stage0_config["experiment"]["status"],
        "fixed_bin_radius_minimum_um": float(fixed_edges_um[0]),
        "fixed_bin_radius_maximum_um": float(fixed_edges_um[-1]),
        "fixed_bin_count": int(fixed_edges_um.size - 1),
        "fixed_bin_smoothing": None,
        "large_drop_threshold_um": large_drop_threshold_um,
        "t10_definition": (
            "first stored time with mass_fraction_r_ge_40um >= "
            f"{float(diagnostic_config['onset_mass_fraction']):g}; interval-censored"
        ),
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
