#!/usr/bin/env python3
"""Materialize one immutable constthermo2d configuration at a chosen SD resolution.

The upstream example samples ``nsupers_pergbx`` superdroplets in every initially
populated grid box.  In the prescribed configuration there are 120 such boxes
(six z levels below 500 m times 20 x cells), so ``maxnsupers`` must be exactly
``120 * nsupers_pergbx``.  This script changes only those two linked quantities
and the Kokkos thread count in a copied project-owned configuration.
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
    parser.add_argument("--num-threads", type=int, default=8)
    args = parser.parse_args()

    source = args.source_config.resolve()
    output = args.output_config.resolve()
    ncell = args.nsupers_pergbx
    if not source.is_file():
        raise FileNotFoundError(source)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite materialized config: {output}")
    if ncell <= 0 or args.num_threads <= 0:
        raise ValueError("SDs per populated grid box and thread count must be positive")

    yaml = YAML()
    with source.open("r", encoding="utf-8") as handle:
        config = yaml.load(handle)
    config["python_inputfiles"]["nsupers_pergbx"] = ncell
    config["domain"]["maxnsupers"] = POPULATED_GRIDBOXES * ncell
    config["kokkos_settings"]["num_threads"] = args.num_threads

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        yaml.dump(config, handle)
    print(f"CONSTTHERMO2D_CONFIG_MATERIALIZED ncell={ncell} maxnsupers={POPULATED_GRIDBOXES * ncell}")


if __name__ == "__main__":
    main()
