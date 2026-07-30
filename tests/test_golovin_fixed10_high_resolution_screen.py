import importlib.util
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "golovin_fixed10_high_resolution_screen.yaml"
CONFIG_V2 = ROOT / "config" / "golovin_fixed10_high_resolution_screen_v2.yaml"
MATRIX_SCRIPT = ROOT / "scripts" / "prepare_golovin_matrix.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_golovin_matrix", MATRIX_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fixed10_screen_is_isolated_exploratory_ladder() -> None:
    config = YAML(typ="safe").load(CONFIG.read_text(encoding="utf-8"))
    module = load_module()

    module.validate_config(config)
    cases = module.build_cases(config)

    assert config["analysis_protocol"]["formal_convergence_claim_permitted"] is False
    assert config["matrix"]["members_per_cell"] == 10
    assert config["matrix"]["model_threads"] == 1
    assert config["data_isolation"]["previous_raw_members_reused"] == 0
    assert config["data_isolation"]["previous_collision_seeds_reused"] == 0
    assert len(cases) == 80
    assert {int(case["max_superdroplets"]) for case in cases} == {
        4096,
        8192,
        16384,
        32768,
        65536,
        131072,
        262144,
        524288,
    }
    assert len({str(case["run_label"]) for case in cases}) == len(cases)
    assert len({int(case["collision_seed"]) for case in cases}) == len(cases)


def test_fixed10_screen_v2_has_fresh_collision_namespace_and_fixed_bundles() -> None:
    config = YAML(typ="safe").load(CONFIG_V2.read_text(encoding="utf-8"))
    module = load_module()

    module.validate_config(config)
    cases = module.build_cases(config)

    assert config["experiment"]["name"].endswith("_v2")
    assert config["analysis_protocol"]["formal_convergence_claim_permitted"] is False
    assert config["data_isolation"]["previous_raw_members_reused"] == 0
    assert config["data_isolation"]["previous_collision_seeds_reused"] == 0
    assert config["data_isolation"]["reused_controlled_bundle_labels"] == 8
    assert len(cases) == 80
    assert len({str(case["run_label"]) for case in cases}) == len(cases)
    assert len({int(case["collision_seed"]) for case in cases}) == len(cases)
