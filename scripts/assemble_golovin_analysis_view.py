"""Create a read-only, symlinked Golovin analysis view from completed matrices.

The view never copies, moves, modifies, or re-manifests model output.  It
contains a combined analysis-only ``cases.tsv``, a source-provenance table,
and one absolute symlink per completed member directory.  It must not be used
with a model runner because its cases table intentionally combines outputs
whose original per-run manifests refer to two different immutable matrices.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

from prepare_golovin_matrix import FIELDNAMES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-matrix", required=True, type=Path)
    parser.add_argument("--base-run-root", required=True, type=Path)
    parser.add_argument("--base-inventory", required=True, type=Path)
    parser.add_argument("--extension-matrix", required=True, type=Path)
    parser.add_argument("--extension-run-root", required=True, type=Path)
    parser.add_argument("--extension-inventory", required=True, type=Path)
    parser.add_argument(
        "--include-resolutions",
        nargs="+",
        type=int,
        help="Optional exact set of superdroplet resolutions to include in the view",
    )
    parser.add_argument("--output-directory", required=True, type=Path)
    return parser.parse_args()


def sha256_file(filename: Path) -> str:
    digest = hashlib.sha256()
    with filename.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_matrix(filename: Path) -> list[dict[str, str]]:
    with filename.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if tuple(reader.fieldnames or ()) != FIELDNAMES:
            raise RuntimeError(f"unexpected matrix schema: {filename}")
        rows = list(reader)
    if not rows:
        raise RuntimeError(f"matrix is empty: {filename}")
    return rows


def completed_run_directory(run_root: Path, row: dict[str, str]) -> Path:
    run_directory = (run_root / row["run_label"]).resolve()
    manifest = run_directory / "manifest.txt"
    stage0 = run_directory / "analysis_stage0_v2" / "diagnostic_metadata.json"
    if not manifest.is_file() or not stage0.is_file():
        raise RuntimeError(f"run is incomplete or missing Stage-0 diagnostics: {run_directory}")
    if "status=completed" not in manifest.read_text(encoding="utf-8").splitlines():
        raise RuntimeError(f"model manifest is not complete: {manifest}")
    metadata = json.loads(stage0.read_text(encoding="utf-8"))
    if metadata.get("status") != "completed":
        raise RuntimeError(f"Stage-0 diagnostic is not complete: {stage0}")
    return run_directory


def load_inventory(filename: Path, matrix_file: Path) -> dict[str, object]:
    payload = json.loads(filename.read_text(encoding="utf-8"))
    if payload.get("status") != "completed":
        raise RuntimeError(f"inventory is not complete: {filename}")
    if payload.get("matrix_sha256") != sha256_file(matrix_file):
        raise RuntimeError(f"inventory matrix checksum does not match: {filename}")
    return payload


def assemble(
    *,
    base_matrix: Path,
    base_run_root: Path,
    base_inventory: Path,
    extension_matrix: Path,
    extension_run_root: Path,
    extension_inventory: Path,
    output_directory: Path,
    include_resolutions: set[int] | None = None,
) -> dict[str, object]:
    if output_directory.exists():
        raise FileExistsError(f"refusing to overwrite analysis view: {output_directory}")
    base_rows = read_matrix(base_matrix)
    extension_rows = read_matrix(extension_matrix)
    base_inventory_payload = load_inventory(base_inventory, base_matrix)
    extension_inventory_payload = load_inventory(extension_inventory, extension_matrix)

    base_labels = {row["run_label"] for row in base_rows}
    extension_labels = {row["run_label"] for row in extension_rows}
    if base_labels & extension_labels:
        raise RuntimeError("base and extension matrices reuse run labels")
    base_seeds = {row["collision_seed"] for row in base_rows}
    extension_seeds = {row["collision_seed"] for row in extension_rows}
    if base_seeds & extension_seeds:
        raise RuntimeError("base and extension matrices reuse collision seeds")
    if {row["matrix_stage"] for row in base_rows} != {
        row["matrix_stage"] for row in extension_rows
    }:
        raise RuntimeError("base and extension have different analysis matrix stages")

    combined_source_rows = [
        ("base", row, completed_run_directory(base_run_root, row)) for row in base_rows
    ] + [
        ("extension", row, completed_run_directory(extension_run_root, row))
        for row in extension_rows
    ]
    if include_resolutions is not None:
        if not include_resolutions or any(resolution < 1 for resolution in include_resolutions):
            raise ValueError("include_resolutions must contain positive resolution values")
        combined_source_rows = [
            item
            for item in combined_source_rows
            if int(item[1]["max_superdroplets"]) in include_resolutions
        ]
        actual_resolutions = {int(item[1]["max_superdroplets"]) for item in combined_source_rows}
        if actual_resolutions != include_resolutions:
            raise RuntimeError("requested analysis-view resolutions are not all present")
    combined_source_rows.sort(
        key=lambda item: (
            int(item[1]["max_superdroplets"]),
            int(item[1]["member_index"]),
        )
    )
    member_identity = {
        (int(row["max_superdroplets"]), int(row["member_index"]))
        for _, row, _ in combined_source_rows
    }
    if len(member_identity) != len(combined_source_rows):
        raise RuntimeError("combined analysis view has duplicate resolution/member identities")

    output_directory.mkdir(parents=True)
    runs_directory = output_directory / "runs"
    runs_directory.mkdir()
    cases: list[dict[str, str]] = []
    provenance: list[dict[str, object]] = []
    for analysis_index, (source, row, run_directory) in enumerate(combined_source_rows):
        analysis_row = dict(row)
        analysis_row["case_index"] = str(analysis_index)
        cases.append(analysis_row)
        link = runs_directory / row["run_label"]
        os.symlink(run_directory, link)
        provenance.append(
            {
                "analysis_case_index": analysis_index,
                "source_matrix": source,
                "source_case_index": row["case_index"],
                "run_label": row["run_label"],
                "max_superdroplets": row["max_superdroplets"],
                "member_index": row["member_index"],
                "collision_seed": row["collision_seed"],
                "absolute_run_directory": str(run_directory),
            }
        )

    cases_file = output_directory / "cases.tsv"
    with cases_file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(cases)
    with (output_directory / "source_provenance.csv").open(
        "w", encoding="utf-8", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(provenance[0]))
        writer.writeheader()
        writer.writerows(provenance)

    manifest = {
        "schema": "golovin_read_only_combined_analysis_view_v1",
        "status": "completed",
        "analysis_only": True,
        "model_runner_permitted": False,
        "case_count": len(cases),
        "members_per_resolution": {
            str(resolution): sum(int(row["max_superdroplets"]) == resolution for row in cases)
            for resolution in sorted({int(row["max_superdroplets"]) for row in cases})
        },
        "included_resolutions": (
            sorted(include_resolutions) if include_resolutions is not None else None
        ),
        "base_matrix": str(base_matrix),
        "base_matrix_sha256": sha256_file(base_matrix),
        "base_inventory": str(base_inventory),
        "base_inventory_sha256": sha256_file(base_inventory),
        "base_inventory_case_count": base_inventory_payload["case_count"],
        "extension_matrix": str(extension_matrix),
        "extension_matrix_sha256": sha256_file(extension_matrix),
        "extension_inventory": str(extension_inventory),
        "extension_inventory_sha256": sha256_file(extension_inventory),
        "extension_inventory_case_count": extension_inventory_payload["case_count"],
        "combined_cases_sha256": sha256_file(cases_file),
        "run_links_directory": str(runs_directory),
        "notes": [
            "All model outputs remain in their original source run directories.",
            "Each runs/<label> entry is an absolute symlink to one completed source run.",
            "The combined cases table is an analysis view and does not match "
            "per-run model manifests.",
        ],
    }
    (output_directory / "analysis_view_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    args = parse_args()
    output = args.output_directory.resolve()
    manifest = assemble(
        base_matrix=args.base_matrix.resolve(),
        base_run_root=args.base_run_root.resolve(),
        base_inventory=args.base_inventory.resolve(),
        extension_matrix=args.extension_matrix.resolve(),
        extension_run_root=args.extension_run_root.resolve(),
        extension_inventory=args.extension_inventory.resolve(),
        output_directory=output,
        include_resolutions=(
            set(args.include_resolutions) if args.include_resolutions is not None else None
        ),
    )
    checksums = output / "SHA256SUMS"
    checksums.write_text(
        "\n".join(
            f"{sha256_file(filename)}  {filename.name}"
            for filename in (
                output / "cases.tsv",
                output / "source_provenance.csv",
                output / "analysis_view_manifest.json",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    print("GOLOVIN_COMBINED_ANALYSIS_VIEW_PASS=1")
    print(f"case_count={manifest['case_count']}")
    print(f"members_per_resolution={manifest['members_per_resolution']}")
    print(f"output_directory={output}")


if __name__ == "__main__":
    main()
