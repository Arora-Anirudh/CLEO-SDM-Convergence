#!/usr/bin/env python3
"""Validate the low- and high-resolution operational Golovin smoke members.

This is deliberately narrower than the complete-matrix auditor: it proves
that two production-shaped members generated fresh inputs, produced readable
CLEO output and carry the immutable matrix provenance before a larger run is
allowed.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-file", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--case-indices", required=True, nargs="+", type=int)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_manifest(path: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            records[key] = value
    return records


def validate(*, matrix_file: Path, run_root: Path, case_indices: list[int]) -> dict[str, object]:
    if len(case_indices) != 2 or len(set(case_indices)) != 2:
        raise ValueError("the smoke gate must contain exactly two distinct case indices")
    with matrix_file.open(encoding="utf-8", newline="") as stream:
        matrix = {int(row["case_index"]): row for row in csv.DictReader(stream, delimiter="\t")}
    selected = [matrix[index] for index in case_indices]
    if {int(row["max_superdroplets"]) for row in selected} != {4096, 1048576}:
        raise ValueError("smoke cases must be the 4,096 and 1,048,576-SD endpoints")
    matrix_sha256 = sha256_file(matrix_file)
    inputs: set[str] = set()
    members: list[dict[str, object]] = []
    for case in selected:
        if case["initialization_family"] != "operational_stochastic":
            raise ValueError("smoke member is not operational stochastic")
        run_directory = run_root / case["run_label"]
        manifest_path = run_directory / "manifest.txt"
        zarr = run_directory / "output" / "collisions0d_solution.zarr"
        setup = run_directory / "output" / "collisions0d_setup.txt"
        inputs_dir = run_directory / "inputs"
        if not manifest_path.is_file() or not zarr.is_dir() or not setup.is_file():
            raise RuntimeError(f"missing completed smoke output: {run_directory}")
        manifest = read_manifest(manifest_path)
        expected = {
            "status": "completed",
            "run_label": case["run_label"],
            "matrix_case_index": case["case_index"],
            "initialization_family": case["initialization_family"],
            "initialization_seed": case["initialization_seed"],
            "collision_seed": case["collision_seed"],
            "matrix_sha256": matrix_sha256,
            "max_superdroplets": case["max_superdroplets"],
        }
        for key, expected_value in expected.items():
            if manifest.get(key) != expected_value:
                raise RuntimeError(f"{manifest_path}: {key} does not match the matrix")
        if manifest.get("controlled_bundle") != "none":
            raise RuntimeError(f"{manifest_path}: operational smoke unexpectedly used a bundle")
        for filename, manifest_key in (
            ("grid.dat", "input_grid_sha256"),
            ("superdroplets.dat", "input_superdroplet_sha256"),
        ):
            input_file = inputs_dir / filename
            if not input_file.is_file():
                raise RuntimeError(f"missing smoke input: {input_file}")
            digest = sha256_file(input_file)
            if manifest.get(manifest_key) != digest:
                raise RuntimeError(f"{manifest_path}: {manifest_key} does not match input")
            if filename == "superdroplets.dat":
                inputs.add(digest)
        members.append(
            {
                "case_index": int(case["case_index"]),
                "run_label": case["run_label"],
                "max_superdroplets": int(case["max_superdroplets"]),
                "initialization_seed": int(case["initialization_seed"]),
                "collision_seed": int(case["collision_seed"]),
                "job_wall_seconds": int(manifest["job_wall_seconds"]),
                "input_superdroplet_sha256": manifest["input_superdroplet_sha256"],
                "zarr_tree_sha256": manifest["zarr_tree_sha256"],
            }
        )
    if len(inputs) != 2:
        raise RuntimeError("smoke initial-population hashes are not distinct")
    return {
        "status": "passed",
        "schema": "golovin_unfrozen_smoke_gate_v1",
        "matrix_sha256": matrix_sha256,
        "case_indices": sorted(case_indices),
        "members": members,
        "requirements": {
            "fresh_operational_initialization": True,
            "distinct_initial_population_hashes": True,
            "endpoint_resolutions": [4096, 1048576],
        },
    }


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite: {output}")
    payload = validate(
        matrix_file=args.matrix_file.resolve(),
        run_root=args.run_root.resolve(),
        case_indices=args.case_indices,
    )
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("GOLOVIN_UNFROZEN_SMOKE_GATE_PASS=1")
    print(f"output={output}")


if __name__ == "__main__":
    main()
