import importlib.util
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_golovin_followup.py"


def load_module():
    spec = importlib.util.spec_from_file_location("analyze_golovin_followup", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def adjacent_row(
    *,
    estimate: float = 0.008,
    low: float = 0.006,
    high: float = 0.013,
    passed: bool = False,
) -> dict[str, str]:
    return {
        "lower_max_superdroplets": "32768",
        "upper_max_superdroplets": "65536",
        "time_s": "3600.0",
        "metric": "ensemble_mean_l1_bins_1000",
        "lower_n_members": "100",
        "upper_n_members": "100",
        "estimated_difference_lower_minus_upper": str(estimate),
        "95ci_low": str(low),
        "95ci_high": str(high),
        "equivalence_margin": "0.01",
        "equivalence_pass": str(passed),
    }


def test_projected_interval_contracts_as_inverse_square_root() -> None:
    module = load_module()
    row = adjacent_row()

    estimate, low, high = module.projected_interval(row, 400)

    assert estimate == 0.008
    assert low == 0.007
    assert math.isclose(high, 0.0105)


def test_required_members_are_balanced_and_margin_aware() -> None:
    module = load_module()

    required = module.required_balanced_members(adjacent_row())

    assert required == 625
    assert (
        module.required_balanced_members(
            adjacent_row(estimate=0.011, low=0.009, high=0.013),
        )
        is None
    )


def test_projection_and_pair_summary_preserve_planning_warning() -> None:
    module = load_module()
    rows = [
        adjacent_row(),
        {
            **adjacent_row(estimate=0.004, low=0.001, high=0.008, passed=True),
            "time_s": "3000.0",
            "metric": "ensemble_mean_l1_bins_500",
        },
    ]

    projection, requirements = module.build_sample_size_projection(
        rows,
        [100, 400, 800],
    )
    summary = module.summarize_pair_requirements(requirements)

    assert len(projection) == 6
    assert len(requirements) == 2
    assert summary[0]["projected_members_each_resolution_for_all_rows"] == 625
    assert {row["projection_method"] for row in projection} == {
        "observed_95ci_scaled_by_sqrt_100_over_n"
    }


def test_projection_rejects_unbalanced_observed_ensembles() -> None:
    module = load_module()
    row = adjacent_row()
    row["upper_n_members"] = "80"

    try:
        module.projected_interval(row, 100)
    except ValueError as error:
        assert "balanced" in str(error)
    else:
        raise AssertionError("unbalanced ensembles should be rejected")
