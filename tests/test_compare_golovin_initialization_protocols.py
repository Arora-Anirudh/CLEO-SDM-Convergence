import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_golovin_initialization_protocols.py"
RESOLUTIONS = (4096, 8192, 16384, 32768, 65536, 131072, 262144, 524288, 1048576)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "compare_golovin_initialization_protocols", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def paired_cases():
    frozen = []
    operational = []
    for resolution in RESOLUTIONS:
        for member in range(50):
            base = {
                "max_superdroplets": str(resolution),
                "member_index": str(member),
                "collision_seed": str(resolution * 1000 + member),
            }
            frozen.append(
                {
                    **base,
                    "initialization_family": "controlled",
                    "initialization_seed": "not_applicable",
                }
            )
            operational.append(
                {
                    **base,
                    "initialization_family": "operational_stochastic",
                    "initialization_seed": str(resolution * 100 + member),
                }
            )
    return frozen, operational


def test_validate_case_pairing_requires_full_collision_matched_matrix() -> None:
    module = load_module()
    frozen, operational = paired_cases()

    keys = module.validate_case_pairing(frozen, operational)

    assert len(keys) == 450
    assert keys[0] == (4096, 0)
    assert keys[-1] == (1048576, 49)


def test_validate_case_pairing_rejects_collision_seed_mismatch() -> None:
    module = load_module()
    frozen, operational = paired_cases()
    operational[-1]["collision_seed"] = "different"

    with pytest.raises(ValueError, match="collision seed"):
        module.validate_case_pairing(frozen, operational)


def test_paired_bootstrap_uses_the_paired_differences() -> None:
    module = load_module()
    estimate, low, high = module.bootstrap_mean_interval(
        np.asarray([0.0, 1.0, 2.0, 3.0]),
        resamples=1000,
        seed=3,
        confidence_level=0.95,
    )

    assert estimate == 1.5
    assert low < estimate < high
