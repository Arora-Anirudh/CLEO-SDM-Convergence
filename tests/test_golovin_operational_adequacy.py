import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_golovin_ensemble_size_adequacy.py"


def load_module():
    spec = importlib.util.spec_from_file_location("golovin_adequacy", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_operational_adequacy_derives_target_from_full_member_selection() -> None:
    module = load_module()
    resolutions = [4096 * 2**index for index in range(9)]
    times = [600.0]
    stacks = {resolution: np.ones((50, 1, 2)) for resolution in resolutions}
    analytical = {resolution: np.ones((1, 2)) for resolution in resolutions}
    moments = {
        resolution: {
            module.M0: np.zeros((50, 1)),
            module.M6: np.zeros((50, 1)),
        }
        for resolution in resolutions
    }
    config = {
        "analysis": {
            "target_selected_resolution": "derived_from_full_50_selection",
            "confidence_level": 0.95,
            "bootstrap_resamples": 10,
            "bootstrap_seed": 9,
        },
        "convergence_criteria": {
            "analytical_agreement": {
                "maximum_l1_upper_95ci": 0.05,
                "moment0_relative_bias_margin": 0.05,
                "moment6_relative_bias_margin": 0.05,
            },
            "adjacent_level_equivalence": {
                "l1_absolute_difference_margin": 0.01,
                "moment0_relative_difference_margin": 0.05,
                "moment6_relative_difference_margin": 0.05,
            },
            "maximum_95ci_half_width": {
                "l1_absolute": 0.01,
                "moment0_relative": 0.025,
                "moment6_relative": 0.05,
            },
        },
        "interpretation": {"allowed_claim": "test", "prohibited_claims": []},
    }

    _, _, selections, limiting, decision = module.analyze(
        config=config,
        resolutions=resolutions,
        member_counts=[50],
        decision_times=times,
        stacks=stacks,
        analytical=analytical,
        edges=np.asarray([1.0, 2.0, 4.0]),
        moments=moments,
        validity={resolution: True for resolution in resolutions},
    )

    assert decision["target_selected_resolution"] == 4096
    assert decision["target_selection_source"] == "full_50_member_operational_analysis"
    assert decision["smallest_retrospectively_supported_tested_ensemble_size"] == 50
    assert all(row["target_resolution_selected"] for row in selections)
    assert len(limiting) == 3
