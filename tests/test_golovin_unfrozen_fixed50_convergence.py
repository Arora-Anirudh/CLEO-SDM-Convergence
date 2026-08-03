import importlib.util
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
FROZEN_CONFIG = ROOT / "config" / "golovin_fixed50_extended_resolution_convergence.yaml"
UNFROZEN_CONFIG = ROOT / "config" / "golovin_unfrozen_fixed50_extended_resolution_convergence.yaml"
MATRIX_SCRIPT = ROOT / "scripts" / "prepare_golovin_matrix.py"


def load_matrix_module():
    spec = importlib.util.spec_from_file_location("prepare_golovin_matrix", MATRIX_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_unfrozen_matrix_is_fresh_balanced_and_collision_paired() -> None:
    yaml = YAML(typ="safe")
    frozen_config = yaml.load(FROZEN_CONFIG.read_text(encoding="utf-8"))
    unfrozen_config = yaml.load(UNFROZEN_CONFIG.read_text(encoding="utf-8"))
    module = load_matrix_module()

    frozen = module.build_cases(frozen_config)
    unfrozen = module.build_cases(unfrozen_config)

    assert len(frozen) == len(unfrozen) == 450
    assert unfrozen_config["experiment"]["initialization_family"] == ("operational_stochastic")
    assert unfrozen_config["matrix"]["members_per_cell"] == 50
    assert unfrozen_config["matrix"]["model_threads"] == 1
    assert unfrozen_config["authorization"]["submission_authorized"] is False
    assert unfrozen_config["initialization_fidelity"]["status"] == ("prospective_required_gate")

    assert len({int(case["initialization_seed"]) for case in unfrozen}) == 450
    assert {case["initialization_seed"] for case in frozen} == {"not_applicable"}
    assert {case["controlled_bundle_label"] for case in unfrozen} == {"not_applicable"}
    assert {case["run_label"] for case in frozen}.isdisjoint(
        {case["run_label"] for case in unfrozen}
    )

    frozen_by_key = {
        (int(case["max_superdroplets"]), int(case["member_index"])): case for case in frozen
    }
    for case in unfrozen:
        key = (int(case["max_superdroplets"]), int(case["member_index"]))
        assert int(case["collision_seed"]) == int(frozen_by_key[key]["collision_seed"])


def test_unfrozen_protocol_preserves_frozen_scientific_controls() -> None:
    yaml = YAML(typ="safe")
    frozen = yaml.load(FROZEN_CONFIG.read_text(encoding="utf-8"))
    unfrozen = yaml.load(UNFROZEN_CONFIG.read_text(encoding="utf-8"))

    assert unfrozen["matrix"]["max_superdroplets"] == frozen["matrix"]["max_superdroplets"]
    for key in (
        "collision_timesteps_s",
        "members_per_cell",
        "observation_timestep_s",
        "end_time_s",
        "model_threads",
    ):
        assert unfrozen["matrix"][key] == frozen["matrix"][key]
    assert (
        unfrozen["diagnostics"]["primary_log_radius_bins"]
        == frozen["diagnostics"]["primary_log_radius_bins"]
    )
    assert (
        unfrozen["diagnostics"]["sensitivity_log_radius_bins"]
        == frozen["diagnostics"]["sensitivity_log_radius_bins"]
    )
    assert unfrozen["diagnostics"]["decision_times_s"] == frozen["diagnostics"]["decision_times_s"]
    assert unfrozen["convergence_criteria"] == frozen["convergence_criteria"]
