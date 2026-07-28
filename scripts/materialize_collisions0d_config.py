"""Create one absolute-path CLEO configuration for a collision-box run.

The version-controlled YAML file remains the scientific template. This helper
replaces only machine/run-specific paths and the requested Kokkos thread count.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ruamel.yaml import YAML


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--build-root", required=True, type=Path)
    parser.add_argument("--run-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--num-threads", required=True, type=int)
    return parser.parse_args()


def materialize(
    template: Path,
    build_root: Path,
    run_directory: Path,
    output: Path,
    num_threads: int,
) -> None:
    if num_threads < 1:
        raise ValueError("num_threads must be at least one")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite configuration: {output}")

    yaml = YAML()
    with template.open("r", encoding="utf-8") as stream:
        config = yaml.load(stream)

    input_directory = run_directory / "inputs"
    output_directory = run_directory / "output"
    input_directory.mkdir(parents=True, exist_ok=False)
    output_directory.mkdir(parents=True, exist_ok=False)

    config["kokkos_settings"]["num_threads"] = num_threads
    config["inputfiles"]["constants_filename"] = str(
        build_root / "_deps" / "cleo-src" / "libs" / "cleoconstants.hpp"
    )
    config["inputfiles"]["grid_filename"] = str(input_directory / "grid.dat")
    config["initsupers"]["initsupers_filename"] = str(input_directory / "superdroplets.dat")
    config["outputdata"]["setup_filename"] = str(output_directory / "collisions0d_setup.txt")
    config["outputdata"]["zarrbasedir"] = str(output_directory / "collisions0d_solution.zarr")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        yaml.dump(config, stream)


def main() -> None:
    args = parse_args()
    materialize(
        args.template.resolve(),
        args.build_root.resolve(),
        args.run_directory.resolve(),
        args.output.resolve(),
        args.num_threads,
    )
    print(f"runtime_config={args.output.resolve()}")


if __name__ == "__main__":
    main()
