"""Finalize and verify immutable controlled-initialization bundles.

A frozen bundle is the exact CLEO-native grid and superdroplet input reused by
all collision-stream members at one resolution. Scientific equivalence is
checked from a normalized definition; byte identity is checked with SHA-256.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import stat
from pathlib import Path
from typing import Any

import numpy as np
from ruamel.yaml import YAML

SCHEMA = "controlled_initialization_bundle_v1"
ARTIFACT_PATHS = {
    "runtime_config": Path("config.yaml"),
    "source_reference_config": Path("source_reference_config.yaml"),
    "source_controlled_config": Path("source_controlled_config.yaml"),
    "controlled_initialization_source": Path("provenance/controlled_initialization.py"),
    "input_preparer_source": Path("provenance/prepare_collisions0d_inputs.py"),
    "native_validator_source": Path("provenance/validate_controlled_initialization_binary.py"),
    "grid_binary": Path("inputs/grid.dat"),
    "superdroplet_binary": Path("inputs/superdroplets.dat"),
    "creation_audit": Path("controlled_initialization_audit.json"),
    "native_readback": Path("native_readback.json"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    finalize = subparsers.add_parser("finalize", help="create the frozen manifest")
    finalize.add_argument("--bundle-directory", required=True, type=Path)
    finalize.add_argument("--project-commit", required=True)
    finalize.add_argument("--cleo-commit", required=True)
    finalize.add_argument("--expected-superdroplets", required=True, type=int)

    verify = subparsers.add_parser("verify", help="verify an existing frozen bundle")
    verify.add_argument("--bundle-directory", required=True, type=Path)
    verify.add_argument("--expected-superdroplets", required=True, type=int)
    verify.add_argument("--expected-cleo-commit", required=True)
    verify.add_argument("--reference-config", required=True, type=Path)
    verify.add_argument("--controlled-config", required=True, type=Path)
    return parser.parse_args()


def sha256_file(filename: Path) -> str:
    digest = hashlib.sha256()
    with filename.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_yaml(filename: Path) -> dict[str, Any]:
    yaml = YAML(typ="safe")
    with filename.open("r", encoding="utf-8") as stream:
        return yaml.load(stream)


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def scientific_definition(
    reference_config: dict[str, Any],
    controlled_config: dict[str, Any],
    number_of_superdroplets: int,
) -> dict[str, Any]:
    """Return only configuration that determines the native population."""
    if number_of_superdroplets < 1:
        raise ValueError("number_of_superdroplets must be positive")
    controlled_settings = dict(controlled_config["controlled_initialization"])
    controlled_settings.pop("status", None)
    return {
        "kernel_context": "golovin_calibration",
        "python_initconds": reference_config["python_initconds"],
        "domain": {
            "nspacedims": int(reference_config["domain"]["nspacedims"]),
            "ngbxs": int(reference_config["domain"]["ngbxs"]),
            "maxnsupers": int(number_of_superdroplets),
        },
        "controlled_initialization": controlled_settings,
    }


def _require_json(filename: Path, schema: str) -> dict[str, Any]:
    record = json.loads(filename.read_text(encoding="utf-8"))
    if record.get("schema") != schema:
        raise ValueError(f"unexpected schema in {filename}: {record.get('schema')}")
    if record.get("status") != "passed":
        raise ValueError(f"record did not pass: {filename}")
    return record


def _artifact_record(bundle_directory: Path, relative_path: Path) -> dict[str, Any]:
    filename = bundle_directory / relative_path
    if not filename.is_file():
        raise FileNotFoundError(f"bundle artifact is missing: {filename}")
    return {
        "path": relative_path.as_posix(),
        "bytes": filename.stat().st_size,
        "sha256": sha256_file(filename),
    }


def _validate_records(
    bundle_directory: Path,
    number_of_superdroplets: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    runtime_config = load_yaml(bundle_directory / ARTIFACT_PATHS["runtime_config"])
    audit = _require_json(
        bundle_directory / ARTIFACT_PATHS["creation_audit"],
        "controlled_initialization_audit_v1",
    )
    readback = _require_json(
        bundle_directory / ARTIFACT_PATHS["native_readback"],
        "controlled_initialization_native_readback_v1",
    )

    if int(runtime_config["domain"]["maxnsupers"]) != number_of_superdroplets:
        raise ValueError("runtime configuration N_SD differs from the bundle request")
    if int(audit["population"]["number_of_superdroplets"]) != number_of_superdroplets:
        raise ValueError("creation-audit N_SD differs from the bundle request")
    if int(readback["population"]["number_of_superdroplets"]) != number_of_superdroplets:
        raise ValueError("native-readback N_SD differs from the bundle request")

    grid_binary = (bundle_directory / ARTIFACT_PATHS["grid_binary"]).resolve()
    superdroplet_binary = (bundle_directory / ARTIFACT_PATHS["superdroplet_binary"]).resolve()
    if Path(runtime_config["inputfiles"]["grid_filename"]).resolve() != grid_binary:
        raise ValueError("runtime configuration does not point to the frozen grid binary")
    if Path(runtime_config["initsupers"]["initsupers_filename"]).resolve() != superdroplet_binary:
        raise ValueError("runtime configuration does not point to the frozen superdroplet binary")

    grid_sha256 = sha256_file(grid_binary)
    superdroplet_sha256 = sha256_file(superdroplet_binary)
    if audit["artifacts"]["grid_file"]["sha256"] != grid_sha256:
        raise ValueError("creation audit grid checksum mismatch")
    if audit["artifacts"]["superdroplet_file"]["sha256"] != superdroplet_sha256:
        raise ValueError("creation audit superdroplet checksum mismatch")
    if readback["artifacts"]["grid_binary"]["sha256"] != grid_sha256:
        raise ValueError("native readback grid checksum mismatch")
    if readback["artifacts"]["superdroplet_binary"]["sha256"] != superdroplet_sha256:
        raise ValueError("native readback superdroplet checksum mismatch")
    if not readback["checks"] or not all(readback["checks"].values()):
        raise ValueError("native readback contains a failed gate")
    if int(audit["population"]["represented_real_droplets"]) != int(
        readback["population"]["represented_real_droplets"]
    ):
        raise ValueError("audit and native readback physical-droplet totals differ")

    return runtime_config, audit, readback


def finalize_bundle(
    *,
    bundle_directory: Path,
    project_commit: str,
    cleo_commit: str,
    number_of_superdroplets: int,
) -> dict[str, Any]:
    """Validate a prepared directory, write its manifest and remove file write bits."""
    bundle_directory = bundle_directory.resolve()
    manifest_filename = bundle_directory / "bundle_manifest.json"
    if manifest_filename.exists():
        raise FileExistsError(f"refusing to overwrite bundle manifest: {manifest_filename}")
    if number_of_superdroplets < 1:
        raise ValueError("number_of_superdroplets must be positive")
    if not bundle_directory.is_dir():
        raise FileNotFoundError(bundle_directory)
    if len(project_commit) != 40 or any(
        value not in "0123456789abcdef" for value in project_commit
    ):
        raise ValueError("project_commit must be a lowercase 40-character Git SHA")
    if len(cleo_commit) != 40 or any(value not in "0123456789abcdef" for value in cleo_commit):
        raise ValueError("cleo_commit must be a lowercase 40-character Git SHA")

    runtime_config, audit, readback = _validate_records(
        bundle_directory,
        number_of_superdroplets,
    )
    reference_config = load_yaml(bundle_directory / ARTIFACT_PATHS["source_reference_config"])
    controlled_config = load_yaml(bundle_directory / ARTIFACT_PATHS["source_controlled_config"])
    definition = scientific_definition(
        reference_config,
        controlled_config,
        number_of_superdroplets,
    )
    runtime_definition = scientific_definition(
        runtime_config,
        controlled_config,
        number_of_superdroplets,
    )
    if definition != runtime_definition:
        raise ValueError("materialized bundle inputs differ from the source definition")

    initializer_copy = bundle_directory / ARTIFACT_PATHS["controlled_initialization_source"]
    if audit["artifacts"]["initializer_source"]["sha256"] != sha256_file(initializer_copy):
        raise ValueError("initializer source snapshot differs from the creation audit")

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "frozen",
        "kernel_context": "golovin_calibration",
        "initialization_family": "controlled",
        "number_of_superdroplets": number_of_superdroplets,
        "project_commit": project_commit,
        "cleo_commit": cleo_commit,
        "scientific_definition": definition,
        "scientific_definition_sha256": canonical_sha256(definition),
        "environment": {
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "platform": platform.platform(),
            "hostname": platform.node(),
            "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
            "slurm_account": os.environ.get("SLURM_JOB_ACCOUNT"),
            "slurm_partition": os.environ.get("SLURM_JOB_PARTITION"),
        },
        "population": {
            "represented_real_droplets": int(audit["population"]["represented_real_droplets"]),
            "source_population_sha256": audit["population"]["population_sha256"],
            "readback_population_sha256": readback["population"]["readback_population_sha256"],
            "native_superdroplet_sha256": readback["artifacts"]["superdroplet_binary"]["sha256"],
        },
        "artifacts": {
            label: _artifact_record(bundle_directory, relative_path)
            for label, relative_path in ARTIFACT_PATHS.items()
        },
    }
    manifest_filename.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    for filename in bundle_directory.rglob("*"):
        if filename.is_file():
            filename.chmod(filename.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    return verify_bundle(
        bundle_directory=bundle_directory,
        expected_number_of_superdroplets=number_of_superdroplets,
        expected_cleo_commit=cleo_commit,
        reference_config=reference_config,
        controlled_config=controlled_config,
    )


def verify_bundle(
    *,
    bundle_directory: Path,
    expected_number_of_superdroplets: int,
    expected_cleo_commit: str,
    reference_config: dict[str, Any],
    controlled_config: dict[str, Any],
) -> dict[str, Any]:
    """Verify scientific compatibility, artifact identity and file protection."""
    bundle_directory = bundle_directory.resolve()
    manifest_filename = bundle_directory / "bundle_manifest.json"
    if not manifest_filename.is_file():
        raise FileNotFoundError(f"frozen bundle manifest is missing: {manifest_filename}")
    manifest = json.loads(manifest_filename.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA or manifest.get("status") != "frozen":
        raise ValueError("bundle manifest is not a frozen v1 controlled bundle")
    if manifest.get("initialization_family") != "controlled":
        raise ValueError("bundle initialization family is not controlled")
    if int(manifest["number_of_superdroplets"]) != expected_number_of_superdroplets:
        raise ValueError("bundle N_SD does not match the requested member")
    if manifest["cleo_commit"] != expected_cleo_commit:
        raise ValueError("bundle CLEO commit differs from the requested runtime")

    expected_definition = scientific_definition(
        reference_config,
        controlled_config,
        expected_number_of_superdroplets,
    )
    if manifest["scientific_definition"] != expected_definition:
        raise ValueError("bundle scientific definition differs from the requested runtime")
    if manifest["scientific_definition_sha256"] != canonical_sha256(expected_definition):
        raise ValueError("bundle scientific-definition checksum mismatch")

    for label, relative_path in ARTIFACT_PATHS.items():
        expected = manifest["artifacts"].get(label)
        if expected is None or expected["path"] != relative_path.as_posix():
            raise ValueError(f"bundle artifact manifest entry is invalid: {label}")
        filename = bundle_directory / relative_path
        if not filename.is_file():
            raise FileNotFoundError(f"bundle artifact is missing: {filename}")
        if filename.stat().st_size != int(expected["bytes"]):
            raise ValueError(f"bundle artifact size mismatch: {label}")
        if sha256_file(filename) != expected["sha256"]:
            raise ValueError(f"bundle artifact checksum mismatch: {label}")
        if filename.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
            raise PermissionError(f"frozen bundle artifact remains writable: {filename}")
    if manifest_filename.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
        raise PermissionError("frozen bundle manifest remains writable")

    _validate_records(bundle_directory, expected_number_of_superdroplets)
    return manifest


def main() -> None:
    args = parse_args()
    if args.command == "finalize":
        manifest = finalize_bundle(
            bundle_directory=args.bundle_directory,
            project_commit=args.project_commit,
            cleo_commit=args.cleo_commit,
            number_of_superdroplets=args.expected_superdroplets,
        )
        print("CONTROLLED_BUNDLE_FINALIZE_PASS=1")
    else:
        manifest = verify_bundle(
            bundle_directory=args.bundle_directory,
            expected_number_of_superdroplets=args.expected_superdroplets,
            expected_cleo_commit=args.expected_cleo_commit,
            reference_config=load_yaml(args.reference_config.resolve()),
            controlled_config=load_yaml(args.controlled_config.resolve()),
        )
        print("CONTROLLED_BUNDLE_VERIFY_PASS=1")
    print(f"bundle_directory={args.bundle_directory.resolve()}")
    print(f"number_of_superdroplets={manifest['number_of_superdroplets']}")
    print(f"native_superdroplet_sha256={manifest['population']['native_superdroplet_sha256']}")
    print(
        "bundle_manifest_sha256="
        f"{sha256_file(args.bundle_directory.resolve() / 'bundle_manifest.json')}"
    )


if __name__ == "__main__":
    main()
