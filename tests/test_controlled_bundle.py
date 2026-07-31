import importlib.util
import json
import shutil
import stat
import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "controlled_bundle.py"


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def dump_yaml(filename: Path, content: dict) -> None:
    yaml = YAML()
    with filename.open("w", encoding="utf-8") as stream:
        yaml.dump(content, stream)


def prepare_fake_bundle(tmp_path: Path, module, number_of_superdroplets: int = 64) -> Path:
    bundle = tmp_path / "bundle"
    (bundle / "inputs").mkdir(parents=True)
    (bundle / "output").mkdir()
    (bundle / "provenance").mkdir()

    reference = YAML(typ="safe").load(
        (ROOT / "config" / "collisions0d_reference.yaml").read_text(encoding="utf-8")
    )
    controlled = YAML(typ="safe").load(
        (ROOT / "config" / "golovin_stage0_development.yaml").read_text(encoding="utf-8")
    )
    shutil.copy2(
        ROOT / "config" / "collisions0d_reference.yaml",
        bundle / "source_reference_config.yaml",
    )
    shutil.copy2(
        ROOT / "config" / "golovin_stage0_development.yaml",
        bundle / "source_controlled_config.yaml",
    )
    for source in (
        "controlled_initialization.py",
        "prepare_collisions0d_inputs.py",
        "validate_controlled_initialization_binary.py",
    ):
        shutil.copy2(ROOT / "scripts" / source, bundle / "provenance" / source)

    grid = bundle / "inputs" / "grid.dat"
    superdroplets = bundle / "inputs" / "superdroplets.dat"
    grid.write_bytes(b"native-grid")
    superdroplets.write_bytes(b"native-superdroplets")

    runtime = reference
    runtime["domain"]["maxnsupers"] = number_of_superdroplets
    runtime["inputfiles"]["grid_filename"] = str(grid)
    runtime["initsupers"]["initsupers_filename"] = str(superdroplets)
    runtime["outputdata"]["setup_filename"] = str(bundle / "output" / "unused.txt")
    runtime["outputdata"]["zarrbasedir"] = str(bundle / "output" / "unused.zarr")
    dump_yaml(bundle / "config.yaml", runtime)

    audit = {
        "schema": "controlled_initialization_audit_v1",
        "status": "passed",
        "population": {
            "number_of_superdroplets": number_of_superdroplets,
            "represented_real_droplets": 123456,
            "population_sha256": "1" * 64,
        },
        "artifacts": {
            "grid_file": {"sha256": module.sha256_file(grid)},
            "superdroplet_file": {"sha256": module.sha256_file(superdroplets)},
            "initializer_source": {
                "sha256": module.sha256_file(bundle / "provenance" / "controlled_initialization.py")
            },
        },
    }
    (bundle / "controlled_initialization_audit.json").write_text(
        json.dumps(audit),
        encoding="utf-8",
    )
    readback = {
        "schema": "controlled_initialization_native_readback_v1",
        "status": "passed",
        "population": {
            "number_of_superdroplets": number_of_superdroplets,
            "represented_real_droplets": 123456,
            "readback_population_sha256": "2" * 64,
        },
        "artifacts": {
            "grid_binary": {"sha256": module.sha256_file(grid)},
            "superdroplet_binary": {"sha256": module.sha256_file(superdroplets)},
        },
        "checks": {"native_roundtrip": True, "exact_total": True},
    }
    (bundle / "native_readback.json").write_text(
        json.dumps(readback),
        encoding="utf-8",
    )
    assert controlled["controlled_initialization"]
    return bundle


def test_bundle_finalization_and_verification_detect_byte_changes(tmp_path: Path) -> None:
    module = load_module("controlled_bundle_finalization")
    bundle = prepare_fake_bundle(tmp_path, module)
    project_commit = "a" * 40
    cleo_commit = "b" * 40

    manifest = module.finalize_bundle(
        bundle_directory=bundle,
        project_commit=project_commit,
        cleo_commit=cleo_commit,
        number_of_superdroplets=64,
    )

    assert manifest["status"] == "frozen"
    assert manifest["number_of_superdroplets"] == 64
    assert manifest["project_commit"] == project_commit
    assert (bundle / "inputs" / "superdroplets.dat").stat().st_mode & (
        stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
    ) == 0

    reference = module.load_yaml(bundle / "source_reference_config.yaml")
    controlled = module.load_yaml(bundle / "source_controlled_config.yaml")
    module.verify_bundle(
        bundle_directory=bundle,
        expected_number_of_superdroplets=64,
        expected_cleo_commit=cleo_commit,
        reference_config=reference,
        controlled_config=controlled,
    )

    superdroplets = bundle / "inputs" / "superdroplets.dat"
    superdroplets.chmod(superdroplets.stat().st_mode | stat.S_IWUSR)
    superdroplets.write_bytes(b"changed")
    superdroplets.chmod(superdroplets.stat().st_mode & ~stat.S_IWUSR)
    with pytest.raises(ValueError, match="size mismatch"):
        module.verify_bundle(
            bundle_directory=bundle,
            expected_number_of_superdroplets=64,
            expected_cleo_commit=cleo_commit,
            reference_config=reference,
            controlled_config=controlled,
        )


def test_bundle_verification_rejects_wrong_resolution(tmp_path: Path) -> None:
    module = load_module("controlled_bundle_resolution")
    bundle = prepare_fake_bundle(tmp_path, module)
    module.finalize_bundle(
        bundle_directory=bundle,
        project_commit="a" * 40,
        cleo_commit="b" * 40,
        number_of_superdroplets=64,
    )

    with pytest.raises(ValueError, match="N_SD"):
        module.verify_bundle(
            bundle_directory=bundle,
            expected_number_of_superdroplets=128,
            expected_cleo_commit="b" * 40,
            reference_config=module.load_yaml(bundle / "source_reference_config.yaml"),
            controlled_config=module.load_yaml(bundle / "source_controlled_config.yaml"),
        )


def test_scientific_definition_ignores_only_status_metadata() -> None:
    module = load_module("controlled_bundle_definition")
    reference = module.load_yaml(ROOT / "config" / "collisions0d_reference.yaml")
    controlled = module.load_yaml(ROOT / "config" / "golovin_stage0_development.yaml")
    changed_status = {
        **controlled,
        "controlled_initialization": {
            **controlled["controlled_initialization"],
            "status": "a_later_documentation_status",
        },
    }

    assert module.scientific_definition(
        reference,
        controlled,
        4096,
    ) == module.scientific_definition(reference, changed_status, 4096)
