"""Audit complete Golovin matrix outputs and write a compact inventory.

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
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def sha256_file(filename: Path) -> str:
    digest = hashlib.sha256()
    with filename.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(filename: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    for line in filename.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            records[key] = value
    return records


def audit(
    *,
    matrix_file: Path,
    run_root: Path,
) -> dict[str, object]:
    matrix_sha256 = sha256_file(matrix_file)
    with matrix_file.open(encoding="utf-8", newline="") as stream:
        cases = list(csv.DictReader(stream, delimiter="\t"))
    if not cases:
        raise RuntimeError("matrix is empty")

    inventory: list[dict[str, object]] = []
    total_zarr_bytes = 0
    project_commits: set[str] = set()
    for case in cases:
        run_directory = run_root / case["run_label"]
        manifest_file = run_directory / "manifest.txt"
        zarr_directory = run_directory / "output" / "collisions0d_solution.zarr"
        if not manifest_file.is_file() or not zarr_directory.is_dir():
            raise RuntimeError(f"incomplete matrix member: {run_directory}")
        manifest = read_manifest(manifest_file)
        expected = {
            "status": "completed",
            "run_label": case["run_label"],
            "matrix_stage": case["matrix_stage"],
            "matrix_case_index": case["case_index"],
            "member_index": case["member_index"],
            "initialization_family": case["initialization_family"],
            "kernel": case["kernel"],
            "initialization_seed": case["initialization_seed"],
            "collision_seed": case["collision_seed"],
            "matrix_sha256": matrix_sha256,
            "max_superdroplets": case["max_superdroplets"],
            "collision_timestep_s": case["collision_timestep_s"],
            "observation_timestep_s": case["observation_timestep_s"],
            "end_time_s": case["end_time_s"],
        }
        for key, expected_value in expected.items():
            if manifest.get(key) != expected_value:
                raise RuntimeError(
                    f"{manifest_file}: {key}={manifest.get(key)!r}, expected {expected_value!r}"
                )
        if not manifest["controlled_bundle"].endswith(f"/{case['controlled_bundle_label']}"):
            raise RuntimeError(f"{manifest_file}: controlled bundle label mismatch")

        project_commits.add(manifest["project_commit"])
        zarr_bytes = sum(
            path.stat().st_size for path in zarr_directory.rglob("*") if path.is_file()
        )
        total_zarr_bytes += zarr_bytes
        inventory.append(
            {
                "case_index": int(case["case_index"]),
                "run_label": case["run_label"],
                "max_superdroplets": int(case["max_superdroplets"]),
                "member_index": int(case["member_index"]),
                "collision_seed": int(case["collision_seed"]),
                "job_wall_seconds": int(manifest["job_wall_seconds"]),
                "slurm_job_id": manifest["slurm_job_id"],
                "zarr_bytes": zarr_bytes,
                "zarr_tree_sha256": manifest["zarr_tree_sha256"],
                "bundle_superdroplet_sha256": manifest["bundle_superdroplet_sha256"],
            }
        )

    if len(project_commits) != 1:
        raise RuntimeError("members were produced by more than one project commit")
    return {
        "status": "completed",
        "schema": "golovin_controlled_resolution_inventory_v1",
        "case_count": len(inventory),
        "matrix_file": str(matrix_file.resolve()),
        "matrix_sha256": matrix_sha256,
        "project_commit": next(iter(project_commits)),
        "total_zarr_bytes": total_zarr_bytes,
        "members": inventory,
    }


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite: {output}")
    payload = audit(
        matrix_file=args.matrix_file.resolve(),
        run_root=args.run_root.resolve(),
    )
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("GOLOVIN_MATRIX_AUDIT_PASS=1")
    print(f"case_count={payload['case_count']}")
    print(f"total_zarr_bytes={payload['total_zarr_bytes']}")
    print(f"output={output}")


if __name__ == "__main__":
    main()
