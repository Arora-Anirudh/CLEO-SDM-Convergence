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
from ruamel.yaml import YAML


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
        help="optional NumPy initialization seed in [0, 2**32)",
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


def validate_inputs(cleo_source: Path, config: dict, seed: int | None) -> None:
    if not (cleo_source / "cleopy" / "__init__.py").is_file():
        raise FileNotFoundError(f"CLEO cleopy package not found under {cleo_source}")

    if seed is not None and not 0 <= seed < 2**32:
        raise ValueError("seed must be in [0, 2**32)")

    domain = config["domain"]
    if domain["ngbxs"] != 1:
        raise ValueError("the reference collisions0d setup requires exactly one grid box")
    if domain["nspacedims"] != 3:
        raise ValueError(
            "the reference PerformanceTestingCLEO initializer generates three coordinates"
        )
    if domain["maxnsupers"] <= 0:
        raise ValueError("maxnsupers must be positive")


def generate_inputs(
    cleo_source: Path,
    config_filename: Path,
    seed: int | None,
    show_figures: bool,
    save_figures: bool,
    figure_directory: Path,
) -> None:
    config = load_config(config_filename)
    validate_inputs(cleo_source, config, seed)

    sys.path.insert(0, str(cleo_source))
    from cleopy import geninitconds  # noqa: PLC0415
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

    for output in (grid_filename, initsupers_filename):
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

    rspan = super_config["rspan"]
    radiigen = rgens.SampleLog10RadiiGen(rspan)
    dryradiigen = rgens.MonoAttrGen(super_config["dryradius"])
    xiprobdist = probdists.VolExponential(super_config["volexpr0"], rspan)
    xiprobdist = probdists.MinXiDistrib(xiprobdist, super_config["xi_min"])

    coordinates = [crdgens.SampleCoordGen(True) for _ in range(3)]
    initattrsgen = attrsgen.AttrsGenerator(
        radiigen,
        dryradiigen,
        xiprobdist,
        coordinates[0],
        coordinates[1],
        coordinates[2],
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

    print(f"initialization_seed={seed}")
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
    )


if __name__ == "__main__":
    main()
