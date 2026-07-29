"""Generate CLEO inputs for the reference collision-only box.

The radius and multiplicity construction follows
PerformanceTestingCLEO/src/collisions0d/initconds_colls0d.py by Clara Bayley,
ported from the legacy ``pySD`` API to current ``cleopy``.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from controlled_initialization import (
    ControlledAttrsGenerator,
    ControlledPopulation,
    build_controlled_population,
    controlled_audit,
    write_controlled_audit,
)
from ruamel.yaml import YAML

INITIALIZATION_FAMILIES = ("operational_stochastic", "controlled")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cleo-source",
        required=True,
        type=Path,
        help="CLEO source directory containing the cleopy package",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="collisions0d YAML configuration",
    )
    parser.add_argument(
        "--seed",
        default=None,
        type=int,
        help="NumPy seed in [0, 2**32) for operational_stochastic initialization",
    )
    parser.add_argument(
        "--initialization-family",
        choices=INITIALIZATION_FAMILIES,
        default="operational_stochastic",
        help="superdroplet initialization method",
    )
    parser.add_argument(
        "--controlled-config",
        default=None,
        type=Path,
        help="YAML containing controlled_initialization settings",
    )
    parser.add_argument(
        "--audit-file",
        default=None,
        type=Path,
        help="new JSON audit path for controlled initialization",
    )
    parser.add_argument("--show-figures", action="store_true")
    parser.add_argument("--save-figures", action="store_true")
    parser.add_argument(
        "--figure-directory",
        default=Path("build/bin"),
        type=Path,
    )
    return parser.parse_args()


def load_config(filename: Path) -> dict:
    yaml = YAML(typ="safe")
    with filename.open("r", encoding="utf-8") as stream:
        return yaml.load(stream)


def validate_inputs(
    cleo_source: Path,
    config: dict,
    seed: int | None,
    initialization_family: str,
    controlled_config: Path | None,
    audit_file: Path | None,
) -> None:
    if not (cleo_source / "cleopy" / "__init__.py").is_file():
        raise FileNotFoundError(f"CLEO cleopy package not found under {cleo_source}")

    if initialization_family not in INITIALIZATION_FAMILIES:
        raise ValueError(f"unsupported initialization family: {initialization_family}")
    if initialization_family == "operational_stochastic":
        if seed is not None and not 0 <= seed < 2**32:
            raise ValueError("seed must be in [0, 2**32)")
        if controlled_config is not None:
            raise ValueError("--controlled-config is only valid for controlled initialization")
        if audit_file is not None:
            raise ValueError("--audit-file is only valid for controlled initialization")
    else:
        if seed is not None:
            raise ValueError(
                "controlled initialization is deterministic and does not accept --seed"
            )
        if controlled_config is None or not controlled_config.is_file():
            raise FileNotFoundError(
                "controlled initialization requires an existing --controlled-config"
            )

    domain = config["domain"]
    if domain["ngbxs"] != 1:
        raise ValueError("the reference collisions0d setup requires exactly one grid box")
    if domain["nspacedims"] != 3:
        raise ValueError(
            "the reference PerformanceTestingCLEO initializer generates three coordinates"
        )
    if domain["maxnsupers"] <= 0:
        raise ValueError("maxnsupers must be positive")
    if initialization_family == "controlled":
        for axis in ("zgrid", "xgrid", "ygrid"):
            bounds = config["python_initconds"]["grid"][axis]
            if len(bounds) != 2 or bounds[1] <= bounds[0]:
                raise ValueError(
                    f"the one-box controlled initializer requires two increasing {axis} bounds"
                )


def build_operational_attrs_generator(super_config: dict, attrsgen, crdgens, probdists, rgens):
    """Return the stochastic PerformanceTestingCLEO-compatible generator."""
    rspan = super_config["rspan"]
    radiigen = rgens.SampleLog10RadiiGen(rspan)
    dryradiigen = rgens.MonoAttrGen(super_config["dryradius"])
    xiprobdist = probdists.VolExponential(super_config["volexpr0"], rspan)
    xiprobdist = probdists.MinXiDistrib(xiprobdist, super_config["xi_min"])

    coordinates = [crdgens.SampleCoordGen(True) for _ in range(3)]
    return attrsgen.AttrsGenerator(
        radiigen,
        dryradiigen,
        xiprobdist,
        coordinates[0],
        coordinates[1],
        coordinates[2],
    )


def build_controlled_attrs_generator(
    *,
    config: dict,
    controlled_config: dict,
    crdgens,
) -> tuple[ControlledAttrsGenerator, ControlledPopulation]:
    """Build the deterministic population and its CLEO writer adapter."""
    settings = controlled_config["controlled_initialization"]
    if settings["method"] != "deterministic_log_volume_bin_quadrature":
        raise ValueError("unsupported controlled-initialization method")
    if settings["integer_multiplicity_allocation"] != "largest_remainder":
        raise ValueError("unsupported integer multiplicity allocation")
    if settings["require_representative_inside_source_bin"] is not True:
        raise ValueError("controlled initialization requires source-bin containment")
    super_config = config["python_initconds"]["supers"]
    grid_config = config["python_initconds"]["grid"]
    configured_support_m = np.asarray(super_config["rspan"], dtype=float)
    controlled_support_m = np.asarray(settings["radius_support_um"], dtype=float) * 1.0e-6
    if not np.allclose(
        configured_support_m,
        controlled_support_m,
        rtol=1.0e-14,
        atol=0.0,
    ):
        raise ValueError("controlled radius support does not match python_initconds.supers.rspan")

    sample_volume_m3 = float(
        np.prod(
            [
                float(grid_config[axis][1]) - float(grid_config[axis][0])
                for axis in ("zgrid", "xgrid", "ygrid")
            ]
        )
    )
    population = build_controlled_population(
        number_of_superdroplets=int(config["domain"]["maxnsupers"]),
        sample_volume_m3=sample_volume_m3,
        number_concentration_m3=float(super_config["numconc"]),
        radius_minimum_m=float(controlled_support_m[0]),
        radius_maximum_m=float(controlled_support_m[1]),
        scale_radius_m=float(super_config["volexpr0"]),
        minimum_multiplicity=int(super_config["xi_min"]),
        maximum_relative_moment0_error=float(settings["maximum_relative_moment0_error"]),
        maximum_relative_moment3_error=float(settings["maximum_relative_moment3_error"]),
        maximum_relative_moment6_error=float(settings["maximum_relative_moment6_error"]),
    )
    coordinates = [crdgens.SampleCoordGen(False) for _ in range(3)]
    generator = ControlledAttrsGenerator(
        population,
        dry_radius_m=float(super_config["dryradius"]),
        coord3gen=coordinates[0],
        coord1gen=coordinates[1],
        coord2gen=coordinates[2],
    )
    return generator, population


def generate_inputs(
    cleo_source: Path,
    config_filename: Path,
    seed: int | None,
    show_figures: bool,
    save_figures: bool,
    figure_directory: Path,
    initialization_family: str = "operational_stochastic",
    controlled_config_filename: Path | None = None,
    audit_filename: Path | None = None,
) -> None:
    config = load_config(config_filename)
    validate_inputs(
        cleo_source,
        config,
        seed,
        initialization_family,
        controlled_config_filename,
        audit_filename,
    )

    sys.path.insert(0, str(cleo_source))
    from cleopy import cxx2py, geninitconds  # noqa: PLC0415
    from cleopy.initsuperdropsbinary_src import (  # noqa: PLC0415
        attrsgen,
        crdgens,
        probdists,
        rgens,
    )

    if seed is not None:
        np.random.seed(seed)

    python_config = config["python_initconds"]
    super_config = python_config["supers"]
    grid_config = python_config["grid"]

    constants_filename = Path(config["inputfiles"]["constants_filename"])
    grid_filename = Path(config["inputfiles"]["grid_filename"])
    initsupers_filename = Path(config["initsupers"]["initsupers_filename"])

    if initialization_family == "controlled" and audit_filename is None:
        audit_filename = Path(f"{initsupers_filename}.controlled-audit.json")

    outputs = [grid_filename, initsupers_filename]
    if audit_filename is not None:
        outputs.append(audit_filename)
    for output in outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            raise FileExistsError(f"refusing to overwrite existing input: {output}")

    isfigures = [show_figures, save_figures]
    if save_figures:
        figure_directory.mkdir(parents=True, exist_ok=True)

    geninitconds.generate_gridbox_boundaries(
        grid_filename,
        np.asarray(grid_config["zgrid"], dtype=float),
        np.asarray(grid_config["xgrid"], dtype=float),
        np.asarray(grid_config["ygrid"], dtype=float),
        constants_filename,
        isprintinfo=True,
        isfigures=isfigures,
        savefigpath=figure_directory,
    )

    population = None
    if initialization_family == "operational_stochastic":
        initattrsgen = build_operational_attrs_generator(
            super_config,
            attrsgen,
            crdgens,
            probdists,
            rgens,
        )
    else:
        controlled_config = load_config(controlled_config_filename)
        initattrsgen, population = build_controlled_attrs_generator(
            config=config,
            controlled_config=controlled_config,
            crdgens=crdgens,
        )

    geninitconds.generate_initial_superdroplet_conditions(
        initattrsgen,
        initsupers_filename,
        config_filename,
        constants_filename,
        grid_filename,
        int(config["domain"]["maxnsupers"]),
        super_config["numconc"],
        isprintinfo=True,
        isfigures=isfigures,
        savefigpath=figure_directory,
        gbxs2plt=0,
        savelabel="_collisions0d_reference",
    )

    if population is not None:
        constants = cxx2py.read_cxxconsts_into_floats(constants_filename)
        record = controlled_audit(
            population,
            liquid_water_density_kgm3=float(constants["RHO_L"]),
            source_config=config_filename,
            controlled_config=controlled_config_filename,
            grid_file=grid_filename,
            superdroplet_file=initsupers_filename,
            initializer_source=Path(__file__).resolve().with_name("controlled_initialization.py"),
        )
        write_controlled_audit(audit_filename, record)
        print(f"controlled_audit={audit_filename}")

    print(f"initialization_family={initialization_family}")
    print(f"initialization_seed={seed if seed is not None else 'not_applicable'}")
    print(f"grid_file={grid_filename}")
    print(f"superdroplet_file={initsupers_filename}")


def main() -> None:
    args = parse_args()
    generate_inputs(
        args.cleo_source.resolve(),
        args.config.resolve(),
        args.seed,
        args.show_figures,
        args.save_figures,
        args.figure_directory.resolve(),
        args.initialization_family,
        args.controlled_config.resolve() if args.controlled_config else None,
        args.audit_file.resolve() if args.audit_file else None,
    )


if __name__ == "__main__":
    main()
