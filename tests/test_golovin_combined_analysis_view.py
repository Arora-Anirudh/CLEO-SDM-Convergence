import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
MATRIX_SCRIPT = ROOT / "scripts" / "prepare_golovin_matrix.py"
VIEW_SCRIPT = ROOT / "scripts" / "assemble_golovin_analysis_view.py"


def load_modules():
    for name, filename in (
        ("prepare_golovin_matrix", MATRIX_SCRIPT),
        ("assemble_golovin_analysis_view", VIEW_SCRIPT),
    ):
        spec = importlib.util.spec_from_file_location(name, filename)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["prepare_golovin_matrix"], sys.modules["assemble_golovin_analysis_view"]


def write_matrix(tmp_path: Path, config: dict, name: str):
    matrix, _ = load_modules()
    directory = tmp_path / name
    matrix.write_matrix(
        ROOT / "config" / "golovin_stage0_development.yaml",
        directory,
        matrix.build_cases(config),
    )
    return directory / "cases.tsv"


def prepare_completed_runs(run_root: Path, matrix_file: Path) -> Path:
    with matrix_file.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))
    for row in rows:
        run_directory = run_root / row["run_label"]
        stage0 = run_directory / "analysis_stage0_v2"
        stage0.mkdir(parents=True)
        (run_directory / "manifest.txt").write_text("status=completed\n", encoding="utf-8")
        (stage0 / "diagnostic_metadata.json").write_text(
            json.dumps({"status": "completed"}), encoding="utf-8"
        )
    inventory = run_root / "inventory.json"
    inventory.write_text(
        json.dumps(
            {
                "status": "completed",
                "matrix_sha256": hashlib.sha256(matrix_file.read_bytes()).hexdigest(),
                "case_count": len(rows),
            }
        ),
        encoding="utf-8",
    )
    return inventory


def test_combined_analysis_view_is_symlinked_and_non_overwriting(tmp_path: Path) -> None:
    _, view = load_modules()
    yaml = YAML(typ="safe")
    base = yaml.load((ROOT / "config" / "golovin_stage0_development.yaml").read_text())
    extension = yaml.load((ROOT / "config" / "golovin_stage0_development.yaml").read_text())
    extension["experiment"]["name"] = "golovin_extension_test"
    extension["experiment"]["matrix_stage"] = base["experiment"]["name"]
    extension["experiment"]["seed_namespace"] = "golovin-extension-test"
    extension["matrix"]["member_index_start"] = 4

    base_matrix = write_matrix(tmp_path, base, "base_matrix")
    extension_matrix = write_matrix(tmp_path, extension, "extension_matrix")
    base_runs = tmp_path / "base_runs"
    extension_runs = tmp_path / "extension_runs"
    base_inventory = prepare_completed_runs(base_runs, base_matrix)
    extension_inventory = prepare_completed_runs(extension_runs, extension_matrix)
    view_root = tmp_path / "view"

    manifest = view.assemble(
        base_matrix=base_matrix,
        base_run_root=base_runs,
        base_inventory=base_inventory,
        extension_matrix=extension_matrix,
        extension_run_root=extension_runs,
        extension_inventory=extension_inventory,
        output_directory=view_root,
    )

    assert manifest["case_count"] == 8
    links = sorted((view_root / "runs").iterdir())
    assert len(links) == 8
    assert all(link.is_symlink() for link in links)
    assert (view_root / "cases.tsv").is_file()
    assert (view_root / "source_provenance.csv").is_file()
