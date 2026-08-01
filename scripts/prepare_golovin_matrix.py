"""Create an immutable, deterministic Golovin development-case matrix.

This prepares metadata only.  It does not submit a Slurm job or run CLEO.
Every output directory must be fresh so an existing experiment cannot be
silently changed.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

FIELDNAMES = (
    "case_index",
    "run_label",
    "matrix_stage",
    "initialization_family",
    "kernel",
    "max_superdroplets",
    "collision_timestep_s",
    "observation_timestep_s",
    "end_time_s",
    "model_threads",
    "member_index",
    "initialization_seed",
    "collision_seed",
    "controlled_bundle_label",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
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


def deterministic_seed(
    *,
    namespace: str,
    role: str,
    max_superdroplets: int,
    collision_timestep_s: float,
    member_index: int,
    bits: int,
) -> int:
    """Map a fully described case to a stable unsigned seed."""
    if bits not in (32, 64):
        raise ValueError("only 32-bit and 64-bit seeds are supported")
    payload = (
        f"{namespace}|{role}|N={max_superdroplets}|"
        f"dt={collision_timestep_s:.17g}|member={member_index}"
    ).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[: bits // 8], "big")


def validate_config(config: dict[str, Any]) -> None:
    experiment = config["experiment"]
    matrix = config["matrix"]
    if experiment["status"] not in {
        "development_only",
        "preproduction_gate",
        "production_ready_not_submitted",
    }:
        raise ValueError(
            "matrix preparation accepts development, gate or reviewed-not-submitted status"
        )
    if experiment["kernel"] != "golovin":
        raise ValueError("the Golovin matrix tool requires kernel=golovin")
    initialization_family = str(experiment["initialization_family"])
    if initialization_family not in {"operational_stochastic", "controlled"}:
        raise ValueError("unsupported initialization_family")
    if not experiment["name"] or not experiment["seed_namespace"]:
        raise ValueError("experiment name and seed namespace must be non-empty")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", str(experiment["name"])) is None:
        raise ValueError("experiment name contains unsupported run-label characters")

    resolutions = [int(value) for value in matrix["max_superdroplets"]]
    timesteps = [float(value) for value in matrix["collision_timesteps_s"]]
    if not resolutions or any(value < 1 for value in resolutions):
        raise ValueError("all max_superdroplets values must be positive")
    if len(resolutions) != len(set(resolutions)):
        raise ValueError("max_superdroplets values must be unique")
    if not timesteps or any(value <= 0 for value in timesteps):
        raise ValueError("all collision timesteps must be positive")
    if len(timesteps) != len(set(timesteps)):
        raise ValueError("collision timesteps must be unique")
    if int(matrix["members_per_cell"]) < 1:
        raise ValueError("members_per_cell must be positive")
    member_index_start = int(matrix.get("member_index_start", 0))
    if member_index_start < 0:
        raise ValueError("member_index_start must be non-negative")
    if float(matrix["observation_timestep_s"]) <= 0:
        raise ValueError("observation timestep must be positive")
    if float(matrix["end_time_s"]) < float(matrix["observation_timestep_s"]):
        raise ValueError("end time must be at least one observation interval")
    if int(matrix["model_threads"]) < 1:
        raise ValueError("model_threads must be positive")
    seed_design = str(matrix.get("collision_seed_design", "unique_per_case"))
    if seed_design not in {"unique_per_case", "reused_across_timesteps"}:
        raise ValueError("unsupported collision_seed_design")
    if initialization_family == "controlled":
        raw_bundle_labels = matrix.get("controlled_bundle_labels")
        if not isinstance(raw_bundle_labels, dict):
            raise ValueError("controlled initialization requires controlled_bundle_labels")
        bundle_labels = {int(key): str(value) for key, value in raw_bundle_labels.items()}
        if set(bundle_labels) != set(resolutions):
            raise ValueError(
                "controlled_bundle_labels must contain exactly one label per resolution"
            )
        for label in bundle_labels.values():
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", label) is None:
                raise ValueError("controlled bundle label contains unsupported characters")


def build_cases(config: dict[str, Any]) -> list[dict[str, int | float | str]]:
    validate_config(config)
    experiment = config["experiment"]
    matrix = config["matrix"]
    namespace = str(experiment["seed_namespace"])
    initialization_family = str(experiment["initialization_family"])
    seed_design = str(matrix.get("collision_seed_design", "unique_per_case"))
    bundle_labels = {
        int(key): str(value) for key, value in matrix.get("controlled_bundle_labels", {}).items()
    }
    cases: list[dict[str, int | float | str]] = []

    member_index_start = int(matrix.get("member_index_start", 0))
    matrix_stage = str(experiment.get("matrix_stage", experiment["name"]))
    if not matrix_stage:
        raise ValueError("matrix_stage must be non-empty")

    for max_superdroplets in sorted(int(value) for value in matrix["max_superdroplets"]):
        for collision_timestep_s in sorted(
            (float(value) for value in matrix["collision_timesteps_s"]),
            reverse=True,
        ):
            for member_index in range(
                member_index_start,
                member_index_start + int(matrix["members_per_cell"]),
            ):
                case_index = len(cases)
                timestep_token = f"{collision_timestep_s:.6g}".replace(".", "p")
                run_label = (
                    f"{experiment['name']}_N{max_superdroplets:06d}_"
                    f"dt{timestep_token}_m{member_index:03d}"
                )
                cases.append(
                    {
                        "case_index": case_index,
                        "run_label": run_label,
                        "matrix_stage": matrix_stage,
                        "initialization_family": experiment["initialization_family"],
                        "kernel": experiment["kernel"],
                        "max_superdroplets": max_superdroplets,
                        "collision_timestep_s": collision_timestep_s,
                        "observation_timestep_s": float(matrix["observation_timestep_s"]),
                        "end_time_s": float(matrix["end_time_s"]),
                        "model_threads": int(matrix["model_threads"]),
                        "member_index": member_index,
                        "initialization_seed": (
                            deterministic_seed(
                                namespace=namespace,
                                role="initialization",
                                max_superdroplets=max_superdroplets,
                                collision_timestep_s=collision_timestep_s,
                                member_index=member_index,
                                bits=32,
                            )
                            if initialization_family == "operational_stochastic"
                            else "not_applicable"
                        ),
                        "collision_seed": deterministic_seed(
                            namespace=namespace,
                            role="collision",
                            max_superdroplets=max_superdroplets,
                            collision_timestep_s=(
                                0.0
                                if seed_design == "reused_across_timesteps"
                                else collision_timestep_s
                            ),
                            member_index=member_index,
                            bits=64,
                        ),
                        "controlled_bundle_label": (
                            bundle_labels[max_superdroplets]
                            if initialization_family == "controlled"
                            else "not_applicable"
                        ),
                    }
                )
    if len({str(case["run_label"]) for case in cases}) != len(cases):
        raise RuntimeError("generated run labels are not unique")
    if initialization_family == "operational_stochastic" and len(
        {int(case["initialization_seed"]) for case in cases}
    ) != len(cases):
        raise RuntimeError("generated initialization seeds are not unique")
    collision_seed_count = len({int(case["collision_seed"]) for case in cases})
    expected_collision_seed_count = (
        len(cases)
        if seed_design == "unique_per_case"
        else len({(int(case["max_superdroplets"]), int(case["member_index"])) for case in cases})
    )
    if collision_seed_count != expected_collision_seed_count:
        raise RuntimeError("generated collision seeds are not unique")
    return cases


def write_matrix(
    config_filename: Path,
    output_directory: Path,
    cases: list[dict[str, int | float | str]],
) -> None:
    if output_directory.exists():
        raise FileExistsError(
            f"refusing to overwrite existing matrix directory: {output_directory}"
        )
    output_directory.mkdir(parents=True)
    matrix_filename = output_directory / "cases.tsv"
    with matrix_filename.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=FIELDNAMES,
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(cases)

    config_copy = output_directory / "source_config.yaml"
    config_copy.write_bytes(config_filename.read_bytes())
    metadata = {
        "status": "prepared_not_run",
        "case_count": len(cases),
        "matrix_file": matrix_filename.name,
        "matrix_sha256": sha256_file(matrix_filename),
        "source_config": config_copy.name,
        "source_config_sha256": sha256_file(config_copy),
        "case_index_minimum": 0,
        "case_index_maximum": len(cases) - 1,
        "member_index_minimum": min(int(case["member_index"]) for case in cases),
        "member_index_maximum": max(int(case["member_index"]) for case in cases),
        "submission_authorized": False,
        "notes": [
            "Preparing this matrix does not submit compute.",
            "This manifest does not authorize production convergence compute.",
            "Each case index owns one unique run label and output path.",
        ],
    }
    (output_directory / "matrix_manifest.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    config_filename = args.config.resolve()
    output_directory = args.output_directory.resolve()
    config = load_yaml(config_filename)
    cases = build_cases(config)
    write_matrix(config_filename, output_directory, cases)
    print("MATRIX_PREPARATION_PASS=1")
    print(f"case_count={len(cases)}")
    print(f"matrix_file={output_directory / 'cases.tsv'}")
    print("submission_authorized=false")


if __name__ == "__main__":
    main()
