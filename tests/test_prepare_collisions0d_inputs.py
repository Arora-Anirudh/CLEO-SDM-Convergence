import importlib.util
import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SCRIPT = SCRIPTS / "prepare_collisions0d_inputs.py"


def load_module(name: str):
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_reference_config() -> dict:
    yaml = YAML(typ="safe")
    return yaml.load((ROOT / "config" / "collisions0d_reference.yaml").read_text())


def fake_cleo_source(tmp_path: Path) -> Path:
    source = tmp_path / "cleo"
    package = source / "cleopy"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    return source


def test_controlled_initialization_rejects_a_random_seed(tmp_path: Path) -> None:
    module = load_module("prepare_collisions0d_inputs_seed_rejection")
    controlled_config = ROOT / "config" / "golovin_stage0_development.yaml"

    with pytest.raises(ValueError, match="does not accept --seed"):
        module.validate_inputs(
            fake_cleo_source(tmp_path),
            load_reference_config(),
            12345,
            "controlled",
            controlled_config,
            None,
        )


def test_operational_initialization_rejects_controlled_only_options(tmp_path: Path) -> None:
    module = load_module("prepare_collisions0d_inputs_option_rejection")

    with pytest.raises(ValueError, match="controlled-config"):
        module.validate_inputs(
            fake_cleo_source(tmp_path),
            load_reference_config(),
            12345,
            "operational_stochastic",
            ROOT / "config" / "golovin_stage0_development.yaml",
            None,
        )

    with pytest.raises(ValueError, match="audit-file"):
        module.validate_inputs(
            fake_cleo_source(tmp_path),
            load_reference_config(),
            12345,
            "operational_stochastic",
            None,
            tmp_path / "audit.json",
        )


def test_controlled_initialization_requires_a_two_boundary_one_box(tmp_path: Path) -> None:
    module = load_module("prepare_collisions0d_inputs_grid_rejection")
    config = load_reference_config()
    config["python_initconds"]["grid"]["zgrid"] = [0.0, 5000.0, 10000.0]

    with pytest.raises(ValueError, match="two increasing zgrid bounds"):
        module.validate_inputs(
            fake_cleo_source(tmp_path),
            config,
            None,
            "controlled",
            ROOT / "config" / "golovin_stage0_development.yaml",
            None,
        )
