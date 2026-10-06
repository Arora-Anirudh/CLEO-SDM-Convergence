#!/usr/bin/env python3
"""Materialize an immutable 2-D constthermo2d resolution/support configuration.

The v2 high-resolution extension changes only the linked superdroplet count,
Kokkos thread count, and explicitly requested initial-radius sampling support.
All physical distribution parameters remain copied from the provenance-frozen
baseline configuration.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ruamel.yaml import YAML


POPULATED_GRIDBOXES = 120


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-config", required=True, type=Path)
    parser.add_argument("--output-config", required=True, type=Path)
    parser.add_argument("--nsupers-pergbx", required=True, type=int)
    parser.add_argument("--num-threads", required=True, type=int)
    parser.add_argument("--rspan-min-m", required=True, type=float)
    parser.add_argument("--rspan-max-m", required=True, type=float)
    args = parser.parse_args()
    source, output = args.source_config.resolve(), args.output_config.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite materialized config: {output}")
    if args.nsupers_pergbx <= 0 or args.num_threads <= 0:
        raise ValueError("SDs per populated grid box and thread count must be positive")
    if not (0.0 < args.rspan_min_m < args.rspan_max_m):
        raise ValueError("require 0 < rspan minimum < rspan maximum")

    yaml = YAML()
    with source.open("r", encoding="utf-8") as handle:
        config = yaml.load(handle)
    config["python_inputfiles"]["nsupers_pergbx"] = args.nsupers_pergbx
    config["python_inputfiles"]["rspan"] = [args.rspan_min_m, args.rspan_max_m]
    config["domain"]["maxnsupers"] = POPULATED_GRIDBOXES * args.nsupers_pergbx
    config["kokkos_settings"]["num_threads"] = args.num_threads

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        yaml.dump(config, handle)
    print("CONSTTHERMO2D_CONFIG_MATERIALIZED_V2 "
          f"ncell={args.nsupers_pergbx} maxnsupers={POPULATED_GRIDBOXES * args.nsupers_pergbx} "
          f"rspan_m=[{args.rspan_min_m:g},{args.rspan_max_m:g}]")


if __name__ == "__main__":
    main()
