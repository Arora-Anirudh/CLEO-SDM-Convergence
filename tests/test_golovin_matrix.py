import importlib.util
import os
import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
MATRIX_SCRIPT = ROOT / "scripts" / "prepare_golovin_matrix.py"
MATERIALIZER_SCRIPT = ROOT / "scripts" / "materialize_collisions0d_config.py"
DEVELOPMENT_CONFIG = ROOT / "config" / "golovin_stage0_development.yaml"


def load_module(filename: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_yaml(filename: Path) -> dict:
    yaml = YAML(typ="safe")
    with filename.open("r", encoding="utf-8") as stream:
        return yaml.load(stream)


def test_development_matrix_is_deterministic_and_unique() -> None:
    matrix = load_module(MATRIX_SCRIPT, "prepare_golovin_matrix_deterministic")
    config = load_yaml(DEVELOPMENT_CONFIG)

    first = matrix.build_cases(config)
    second = matrix.build_cases(config)

    assert first == second
    assert len(first) == 4
    assert [case["case_index"] for case in first] == list(range(4))
    assert len({case["run_label"] for case in first}) == 4
    assert len({case["initialization_seed"] for case in first}) == 4
    assert len({case["collision_seed"] for case in first}) == 4


def test_matrix_writer_refuses_existing_directory(tmp_path: Path) -> None:
    matrix = load_module(MATRIX_SCRIPT, "prepare_golovin_matrix_refusal")
    config = load_yaml(DEVELOPMENT_CONFIG)
    cases = matrix.build_cases(config)
    output = tmp_path / "matrix"

    matrix.write_matrix(DEVELOPMENT_CONFIG, output, cases)
    with pytest.raises(FileExistsError):
        matrix.write_matrix(DEVELOPMENT_CONFIG, output, cases)


def test_materializer_applies_only_explicit_scientific_overrides(tmp_path: Path) -> None:
    materializer = load_module(MATERIALIZER_SCRIPT, "collisions0d_materializer")
    output = tmp_path / "run" / "config.yaml"
    materializer.materialize(
        ROOT / "config" / "collisions0d_reference.yaml",
        tmp_path / "build",
        tmp_path / "run",
        output,
        1,
        max_superdroplets=8192,
        collision_timestep_s=0.5,
        observation_timestep_s=100.0,
        end_time_s=1000.0,
    )
    config = load_yaml(output)

    assert config["domain"]["maxnsupers"] == 8192
    assert config["timesteps"]["COLLTSTEP"] == pytest.approx(0.5)
    assert config["timesteps"]["OBSTSTEP"] == pytest.approx(100.0)
    assert config["timesteps"]["T_END"] == pytest.approx(1000.0)
    assert (
        config["python_initconds"]
        == load_yaml(ROOT / "config" / "collisions0d_reference.yaml")["python_initconds"]
    )


def test_materializer_refuses_existing_output(tmp_path: Path) -> None:
    materializer = load_module(MATERIALIZER_SCRIPT, "collisions0d_materializer_refusal")
    output = tmp_path / "config.yaml"
    output.write_text("existing\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        materializer.materialize(
            ROOT / "config" / "collisions0d_reference.yaml",
            tmp_path / "build",
            tmp_path / "run",
            output,
            1,
        )


def test_materializer_reuses_frozen_inputs_without_copying(tmp_path: Path) -> None:
    materializer = load_module(MATERIALIZER_SCRIPT, "collisions0d_frozen_materializer")
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    grid = frozen / "grid.dat"
    superdroplets = frozen / "superdroplets.dat"
    grid.write_bytes(b"grid")
    superdroplets.write_bytes(b"superdroplets")
    run_directory = tmp_path / "run"
    output = run_directory / "config.yaml"

    materializer.materialize(
        ROOT / "config" / "collisions0d_reference.yaml",
        tmp_path / "build",
        run_directory,
        output,
        1,
        max_superdroplets=4096,
        grid_file=grid,
        superdroplet_file=superdroplets,
    )
    config = load_yaml(output)

    assert config["inputfiles"]["grid_filename"] == str(grid.resolve())
    assert config["initsupers"]["initsupers_filename"] == str(superdroplets.resolve())
    assert not (run_directory / "inputs").exists()


def test_materializer_requires_both_frozen_input_paths(tmp_path: Path) -> None:
    materializer = load_module(
        MATERIALIZER_SCRIPT,
        "collisions0d_incomplete_frozen_materializer",
    )
    grid = tmp_path / "grid.dat"
    grid.write_bytes(b"grid")

    with pytest.raises(ValueError, match="must be supplied together"):
        materializer.materialize(
            ROOT / "config" / "collisions0d_reference.yaml",
            tmp_path / "build",
            tmp_path / "run",
            tmp_path / "run" / "config.yaml",
            1,
            grid_file=grid,
        )


def test_matrix_wrapper_skips_only_explicitly_resumed_completed_case(
    tmp_path: Path,
) -> None:
    matrix = load_module(MATRIX_SCRIPT, "prepare_golovin_matrix_resume")
    cases = matrix.build_cases(load_yaml(DEVELOPMENT_CONFIG))
    matrix_directory = tmp_path / "matrix"
    matrix.write_matrix(DEVELOPMENT_CONFIG, matrix_directory, cases)

    run_root = tmp_path / "runs"
    completed = run_root / str(cases[0]["run_label"])
    completed.mkdir(parents=True)
    (completed / "manifest.txt").write_text("status=completed\n", encoding="utf-8")

    environment = {
        **os.environ,
        "MATRIX_FILE": str(matrix_directory / "cases.tsv"),
        "SLURM_ARRAY_TASK_ID": "0",
        "RESUME_COMPLETED": "1",
        "CLEO_SDM_RUN_ROOT": str(run_root),
    }
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "levante" / "run_golovin_matrix.sbatch")],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "CASE_ALREADY_COMPLETED=1" in result.stdout

    environment["RESUME_COMPLETED"] = "0"
    refusal = subprocess.run(
        ["bash", str(ROOT / "scripts" / "levante" / "run_golovin_matrix.sbatch")],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert refusal.returncode == 1
    assert "case path exists" in refusal.stderr


def test_matrix_wrapper_refuses_incomplete_case_even_in_resume_mode(
    tmp_path: Path,
) -> None:
    matrix = load_module(MATRIX_SCRIPT, "prepare_golovin_matrix_incomplete")
    cases = matrix.build_cases(load_yaml(DEVELOPMENT_CONFIG))
    matrix_directory = tmp_path / "matrix"
    matrix.write_matrix(DEVELOPMENT_CONFIG, matrix_directory, cases)

    run_root = tmp_path / "runs"
    incomplete = run_root / str(cases[1]["run_label"])
    incomplete.mkdir(parents=True)
    (incomplete / "manifest.inprogress.txt").write_text(
        "status=running\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "levante" / "run_golovin_matrix.sbatch")],
        env={
            **os.environ,
            "MATRIX_FILE": str(matrix_directory / "cases.tsv"),
            "SLURM_ARRAY_TASK_ID": "1",
            "RESUME_COMPLETED": "1",
            "CLEO_SDM_RUN_ROOT": str(run_root),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "not eligible for completed-case skip" in result.stderr
