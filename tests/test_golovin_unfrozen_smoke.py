import csv
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_golovin_unfrozen_smoke.py"
WRAPPER = ROOT / "scripts" / "levante" / "run_golovin_unfrozen_smoke.sbatch"
SHARD_WRAPPER = ROOT / "scripts" / "levante" / "run_golovin_unfrozen_resolution_shard.sbatch"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_golovin_unfrozen_smoke", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def create_smoke(tmp_path: Path):
    module = load_module()
    matrix_file = tmp_path / "cases.tsv"
    run_root = tmp_path / "runs"
    cases = []
    for index, resolution in enumerate((4096, 1048576)):
        cases.append(
            {
                "case_index": str(index * 400),
                "run_label": f"unfrozen_N{resolution:06d}_m000",
                "matrix_stage": "unfrozen_v1",
                "initialization_family": "operational_stochastic",
                "kernel": "golovin",
                "max_superdroplets": str(resolution),
                "collision_timestep_s": "0.1",
                "observation_timestep_s": "600.0",
                "end_time_s": "3600.0",
                "model_threads": "1",
                "member_index": "0",
                "initialization_seed": str(100 + index),
                "collision_seed": str(200 + index),
                "controlled_bundle_label": "not_applicable",
            }
        )
    with matrix_file.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(cases[0]), delimiter="\t")
        writer.writeheader()
        writer.writerows(cases)
    matrix_sha256 = module.sha256_file(matrix_file)
    for case in cases:
        run_directory = run_root / case["run_label"]
        inputs = run_directory / "inputs"
        output = run_directory / "output" / "collisions0d_solution.zarr"
        inputs.mkdir(parents=True)
        output.mkdir(parents=True)
        (inputs / "grid.dat").write_bytes(b"grid")
        (inputs / "superdroplets.dat").write_bytes(case["run_label"].encode())
        (output / "0").write_bytes(b"zarr")
        (run_directory / "output" / "collisions0d_setup.txt").write_text("setup\n")
        manifest = {
            "status": "completed",
            "run_label": case["run_label"],
            "matrix_case_index": case["case_index"],
            "initialization_family": case["initialization_family"],
            "initialization_seed": case["initialization_seed"],
            "collision_seed": case["collision_seed"],
            "matrix_sha256": matrix_sha256,
            "max_superdroplets": case["max_superdroplets"],
            "controlled_bundle": "none",
            "input_grid_sha256": module.sha256_file(inputs / "grid.dat"),
            "input_superdroplet_sha256": module.sha256_file(inputs / "superdroplets.dat"),
            "job_wall_seconds": "10",
            "zarr_tree_sha256": "a" * 64,
        }
        (run_directory / "manifest.txt").write_text(
            "".join(f"{key}={value}\n" for key, value in manifest.items()),
            encoding="utf-8",
        )
    return module, matrix_file, run_root, [0, 400]


def test_unfrozen_smoke_validates_distinct_operational_inputs(tmp_path: Path) -> None:
    module, matrix_file, run_root, indices = create_smoke(tmp_path)

    payload = module.validate(
        matrix_file=matrix_file,
        run_root=run_root,
        case_indices=indices,
    )

    assert payload["status"] == "passed"
    assert [member["max_superdroplets"] for member in payload["members"]] == [4096, 1048576]


def test_unfrozen_smoke_rejects_reused_initial_population(tmp_path: Path) -> None:
    module, matrix_file, run_root, indices = create_smoke(tmp_path)
    first = run_root / "unfrozen_N004096_m000" / "inputs" / "superdroplets.dat"
    second = run_root / "unfrozen_N1048576_m000" / "inputs" / "superdroplets.dat"
    second.write_bytes(first.read_bytes())
    second_manifest = run_root / "unfrozen_N1048576_m000" / "manifest.txt"
    second_manifest.write_text(
        second_manifest.read_text(encoding="utf-8").replace(
            "input_superdroplet_sha256="
            + "".join(
                line.split("=", 1)[1]
                for line in second_manifest.read_text(encoding="utf-8").splitlines()
                if line.startswith("input_superdroplet_sha256=")
            ),
            "input_superdroplet_sha256=" + module.sha256_file(second),
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="not distinct"):
        module.validate(matrix_file=matrix_file, run_root=run_root, case_indices=indices)


def test_smoke_wrapper_allows_shared_partition_memory_cpu_adjustment() -> None:
    wrapper = WRAPPER.read_text(encoding="utf-8")

    assert 'if ((SLURM_NTASKS != 1)); then' in wrapper
    assert 'if ((SLURM_CPUS_PER_TASK < 1)); then' in wrapper
    assert "SLURM_CPUS_PER_TASK != 1" not in wrapper
    assert "export OMP_NUM_THREADS=1" in wrapper


def test_shard_wrapper_uses_measured_memory_and_allows_cpu_adjustment() -> None:
    wrapper = SHARD_WRAPPER.read_text(encoding="utf-8")

    assert "#SBATCH --mem=6G" in wrapper
    assert "WORKER_COUNT != 8 || SLURM_NTASKS != 8" in wrapper
    assert "SLURM_CPUS_PER_TASK != 1" not in wrapper
    assert "SLURM_CPUS_PER_TASK < 1" in wrapper
