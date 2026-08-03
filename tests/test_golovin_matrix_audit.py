import csv
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_golovin_matrix.py"


def load_module():
    spec = importlib.util.spec_from_file_location("audit_golovin_matrix", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def create_case(tmp_path: Path):
    module = load_module()
    matrix_file = tmp_path / "cases.tsv"
    run_root = tmp_path / "runs"
    case = {
        "case_index": "0",
        "run_label": "case_000",
        "matrix_stage": "resolution_v1",
        "initialization_family": "controlled",
        "kernel": "golovin",
        "max_superdroplets": "512",
        "collision_timestep_s": "0.1",
        "observation_timestep_s": "300.0",
        "end_time_s": "3600.0",
        "model_threads": "1",
        "member_index": "0",
        "initialization_seed": "not_applicable",
        "collision_seed": "123",
        "controlled_bundle_label": "golovin_controlled_N000512_v1",
    }
    with matrix_file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(case),
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(case)

    matrix_sha256 = module.sha256_file(matrix_file)
    run_directory = run_root / case["run_label"]
    zarr_directory = run_directory / "output" / "collisions0d_solution.zarr"
    zarr_directory.mkdir(parents=True)
    (zarr_directory / "0").write_bytes(b"zarr")
    manifest = {
        "status": "completed",
        **{
            key: case[key]
            for key in (
                "run_label",
                "matrix_stage",
                "member_index",
                "initialization_family",
                "kernel",
                "initialization_seed",
                "collision_seed",
                "max_superdroplets",
                "collision_timestep_s",
                "observation_timestep_s",
                "end_time_s",
            )
        },
        "matrix_case_index": case["case_index"],
        "matrix_sha256": matrix_sha256,
        "controlled_bundle": ("/bundles/" + case["controlled_bundle_label"]),
        "project_commit": "a" * 40,
        "job_wall_seconds": "7",
        "slurm_job_id": "12345_0",
        "zarr_tree_sha256": "b" * 64,
        "bundle_superdroplet_sha256": "c" * 64,
        "input_grid_sha256": "d" * 64,
        "input_superdroplet_sha256": "c" * 64,
    }
    (run_directory / "manifest.txt").write_text(
        "".join(f"{key}={value}\n" for key, value in manifest.items()),
        encoding="utf-8",
    )
    return module, matrix_file, run_root


def test_matrix_audit_verifies_manifest_and_inventory(tmp_path: Path) -> None:
    module, matrix_file, run_root = create_case(tmp_path)

    inventory = module.audit(matrix_file=matrix_file, run_root=run_root)

    assert inventory["status"] == "completed"
    assert inventory["case_count"] == 1
    assert inventory["project_commit"] == "a" * 40
    assert inventory["total_zarr_bytes"] == 4
    assert inventory["members"][0]["zarr_tree_sha256"] == "b" * 64


def test_matrix_audit_rejects_manifest_seed_mismatch(tmp_path: Path) -> None:
    module, matrix_file, run_root = create_case(tmp_path)
    manifest = run_root / "case_000" / "manifest.txt"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace(
            "collision_seed=123",
            "collision_seed=999",
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="collision_seed"):
        module.audit(matrix_file=matrix_file, run_root=run_root)


def test_matrix_audit_accepts_archived_controlled_manifest_without_named_input_hashes(
    tmp_path: Path,
) -> None:
    module, matrix_file, run_root = create_case(tmp_path)
    manifest = run_root / "case_000" / "manifest.txt"
    records = module.read_manifest(manifest)
    records.pop("input_grid_sha256")
    records.pop("input_superdroplet_sha256")
    records["bundle_grid_sha256"] = "d" * 64
    manifest.write_text(
        "".join(f"{key}={value}\n" for key, value in records.items()),
        encoding="utf-8",
    )

    inventory = module.audit(matrix_file=matrix_file, run_root=run_root)

    assert inventory["members"][0]["input_superdroplet_sha256"] == "c" * 64


def test_matrix_audit_accepts_operational_initialization(tmp_path: Path) -> None:
    module, matrix_file, run_root = create_case(tmp_path)
    with matrix_file.open(encoding="utf-8", newline="") as stream:
        case = next(csv.DictReader(stream, delimiter="\t"))
    case["initialization_family"] = "operational_stochastic"
    case["initialization_seed"] = "456"
    case["controlled_bundle_label"] = "not_applicable"
    with matrix_file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(case), delimiter="\t")
        writer.writeheader()
        writer.writerow(case)

    manifest_path = run_root / case["run_label"] / "manifest.txt"
    records = module.read_manifest(manifest_path)
    records.update(
        {
            "initialization_family": "operational_stochastic",
            "initialization_seed": "456",
            "controlled_bundle": "none",
            "bundle_superdroplet_sha256": "none",
            "input_superdroplet_sha256": "e" * 64,
            "matrix_sha256": module.sha256_file(matrix_file),
        }
    )
    manifest_path.write_text(
        "".join(f"{key}={value}\n" for key, value in records.items()),
        encoding="utf-8",
    )

    inventory = module.audit(matrix_file=matrix_file, run_root=run_root)

    member = inventory["members"][0]
    assert member["initialization_family"] == "operational_stochastic"
    assert member["initialization_seed"] == 456
    assert member["input_superdroplet_sha256"] == "e" * 64
