import importlib.util
import sys
from pathlib import Path

import numpy as np
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "golovin_fixed50_extended_resolution_convergence.yaml"
UNFROZEN_CONFIG = ROOT / "config" / "golovin_unfrozen_fixed50_extended_resolution_convergence.yaml"
PRECISION_EXTENSION_CONFIG = ROOT / "config" / "golovin_fixed50_highres_precision_extension.yaml"
MATRIX_SCRIPT = ROOT / "scripts" / "prepare_golovin_matrix.py"
LAW_SCRIPT = ROOT / "scripts" / "analyze_golovin_convergence_law.py"


def load_matrix_module():
    spec = importlib.util.spec_from_file_location("prepare_golovin_matrix", MATRIX_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_law_module():
    for name, filename in (
        ("golovin_stage0", ROOT / "scripts" / "golovin_stage0.py"),
        (
            "analyze_golovin_resolution_convergence",
            ROOT / "scripts" / "analyze_golovin_resolution_convergence.py",
        ),
        (
            "analyze_golovin_practical_convergence",
            ROOT / "scripts" / "analyze_golovin_practical_convergence.py",
        ),
        ("analyze_golovin_convergence_law", LAW_SCRIPT),
    ):
        spec = importlib.util.spec_from_file_location(name, filename)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["analyze_golovin_convergence_law"]


def test_fixed50_matrix_is_fresh_balanced_and_extended() -> None:
    config = YAML(typ="safe").load(CONFIG.read_text(encoding="utf-8"))
    module = load_matrix_module()

    module.validate_config(config)
    cases = module.build_cases(config)

    assert config["analysis_protocol"]["formal_convergence_claim_permitted"] is True
    assert config["matrix"]["members_per_cell"] == 50
    assert config["matrix"]["model_threads"] == 1
    assert config["data_isolation"]["previous_raw_members_reused"] == 0
    assert config["data_isolation"]["previous_collision_seeds_reused"] == 0
    assert config["data_isolation"]["previous_controlled_bundle_labels_reused"] == 0
    assert config["practical_convergence"]["explicitly_excluded_diagnostic"] == (
        "successive_improvement_ratio"
    )
    assert len(cases) == 450
    assert {int(case["max_superdroplets"]) for case in cases} == {
        4096,
        8192,
        16384,
        32768,
        65536,
        131072,
        262144,
        524288,
        1048576,
    }
    assert len({str(case["run_label"]) for case in cases}) == 450
    assert len({int(case["collision_seed"]) for case in cases}) == 450


def test_targeted_high_resolution_extension_uses_new_member_indices_and_streams() -> None:
    yaml = YAML(typ="safe")
    base_config = yaml.load(CONFIG.read_text(encoding="utf-8"))
    extension_config = yaml.load(PRECISION_EXTENSION_CONFIG.read_text(encoding="utf-8"))
    module = load_matrix_module()

    base_cases = module.build_cases(base_config)
    extension_cases = module.build_cases(extension_config)

    assert len(extension_cases) == 200
    assert {int(case["max_superdroplets"]) for case in extension_cases} == {
        262_144,
        524_288,
    }
    assert {int(case["member_index"]) for case in extension_cases} == set(range(50, 150))
    assert {str(case["matrix_stage"]) for case in extension_cases} == {
        "golovin_fixed50_extended_resolution_convergence_v1"
    }
    assert {int(case["collision_seed"]) for case in extension_cases}.isdisjoint(
        {int(case["collision_seed"]) for case in base_cases}
    )
    assert {str(case["run_label"]) for case in extension_cases}.isdisjoint(
        {str(case["run_label"]) for case in base_cases}
    )


def test_power_law_fit_recovers_known_zero_floor() -> None:
    module = load_law_module()
    resolutions = np.asarray([4096, 8192, 16384, 32768, 65536, 131072], dtype=float)
    errors = 0.08 * (resolutions / resolutions[0]) ** (-0.5)
    p_values = np.arange(0.05, 2.0001, 0.005)

    fit = module.fit_floor_power_law_grid(resolutions, errors, p_values)

    assert np.isclose(float(fit["floor"]), 0.0, atol=1.0e-12)
    assert np.isclose(float(fit["exponent"]), 0.5, atol=0.005)
    assert np.isclose(float(fit["amplitude"]), 0.08, rtol=1.0e-5)
    assert float(fit["rmse"]) < 1.0e-12


def test_unfrozen_registered_supporting_convergence_law_is_accepted() -> None:
    config = YAML(typ="safe").load(UNFROZEN_CONFIG.read_text(encoding="utf-8"))
    module = load_law_module()

    settings = module.validate_settings(config)

    assert settings["status"] == "supporting_non_selection_diagnostic"
    assert settings["selection_gate"] is False


def test_power_law_fit_recovers_known_positive_floor_for_multiple_draws() -> None:
    module = load_law_module()
    resolutions = np.asarray([4096, 8192, 16384, 32768, 65536, 131072], dtype=float)
    base = 0.012 + 0.08 * (resolutions / resolutions[0]) ** (-0.6)
    errors = np.vstack([base, base * 1.01])
    p_values = np.arange(0.05, 2.0001, 0.005)

    fit = module.fit_floor_power_law_grid(resolutions, errors, p_values)

    assert np.allclose(fit["floor"], [0.012, 0.01212], atol=2.0e-4)
    assert np.allclose(fit["exponent"], [0.6, 0.6], atol=0.005)
    assert np.all(np.asarray(fit["rmse"]) < 1.0e-10)


def test_power_law_fit_reports_unfittable_increasing_draw_without_raising() -> None:
    module = load_law_module()
    resolutions = np.asarray([4096, 8192, 16384, 32768], dtype=float)
    errors = np.asarray([0.02, 0.03, 0.04, 0.05])
    p_values = np.arange(0.05, 2.0001, 0.005)

    fit = module.fit_floor_power_law_grid(resolutions, errors, p_values)

    assert not bool(fit["fit_valid"])
    assert np.isnan(float(fit["floor"]))
    assert np.isnan(float(fit["rmse"]))
