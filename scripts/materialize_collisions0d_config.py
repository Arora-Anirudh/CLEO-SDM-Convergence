"""Create one absolute-path CLEO configuration for a collision-box run.

The version-controlled YAML file remains the scientific template. This helper
replaces machine/run-specific paths and only the explicitly supplied experiment
overrides. Every materialized file is therefore a complete run record.

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
    parser.add_argument("--max-superdroplets", type=int, default=None)
    parser.add_argument("--collision-timestep-s", type=float, default=None)
    parser.add_argument("--observation-timestep-s", type=float, default=None)
    parser.add_argument("--end-time-s", type=float, default=None)
    parser.add_argument("--grid-file", type=Path, default=None)
    parser.add_argument("--superdroplet-file", type=Path, default=None)
    return parser.parse_args()


def materialize(
    template: Path,
    build_root: Path,
    run_directory: Path,
    output: Path,
    num_threads: int,
    max_superdroplets: int | None = None,
    collision_timestep_s: float | None = None,
    observation_timestep_s: float | None = None,
    end_time_s: float | None = None,
    grid_file: Path | None = None,
    superdroplet_file: Path | None = None,
) -> None:
    if num_threads < 1:
        raise ValueError("num_threads must be at least one")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite configuration: {output}")

    yaml = YAML()
    with template.open("r", encoding="utf-8") as stream:
        config = yaml.load(stream)

    if max_superdroplets is not None and max_superdroplets < 1:
        raise ValueError("max_superdroplets must be at least one")
    for name, value in (
        ("collision_timestep_s", collision_timestep_s),
        ("observation_timestep_s", observation_timestep_s),
        ("end_time_s", end_time_s),
    ):
        if value is not None and value <= 0:
            raise ValueError(f"{name} must be positive")

    if (grid_file is None) != (superdroplet_file is None):
        raise ValueError("--grid-file and --superdroplet-file must be supplied together")

    output_directory = run_directory / "output"
    output_directory.mkdir(parents=True, exist_ok=False)
    if grid_file is None:
        input_directory = run_directory / "inputs"
        input_directory.mkdir(parents=True, exist_ok=False)
        grid_file = input_directory / "grid.dat"
        superdroplet_file = input_directory / "superdroplets.dat"
    else:
        grid_file = grid_file.resolve()
        superdroplet_file = superdroplet_file.resolve()
        if not grid_file.is_file():
            raise FileNotFoundError(f"frozen grid file is missing: {grid_file}")
        if not superdroplet_file.is_file():
            raise FileNotFoundError(f"frozen superdroplet file is missing: {superdroplet_file}")

    config["kokkos_settings"]["num_threads"] = num_threads
    if max_superdroplets is not None:
        config["domain"]["maxnsupers"] = max_superdroplets
    if collision_timestep_s is not None:
        config["timesteps"]["COLLTSTEP"] = collision_timestep_s
    if observation_timestep_s is not None:
        config["timesteps"]["OBSTSTEP"] = observation_timestep_s
    if end_time_s is not None:
        config["timesteps"]["T_END"] = end_time_s
    if config["timesteps"]["T_END"] < config["timesteps"]["OBSTSTEP"]:
        raise ValueError("end time must be at least one observation interval")
    config["inputfiles"]["constants_filename"] = str(
        build_root / "_deps" / "cleo-src" / "libs" / "cleoconstants.hpp"
    )
    config["inputfiles"]["grid_filename"] = str(grid_file)
    config["initsupers"]["initsupers_filename"] = str(superdroplet_file)
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
        args.max_superdroplets,
        args.collision_timestep_s,
        args.observation_timestep_s,
        args.end_time_s,
        args.grid_file,
        args.superdroplet_file,
    )
    print(f"runtime_config={args.output.resolve()}")


if __name__ == "__main__":
    main()
