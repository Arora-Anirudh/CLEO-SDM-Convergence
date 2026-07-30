import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGE0_SCRIPT = ROOT / "scripts" / "golovin_stage0.py"
RESOLUTION_SCRIPT = ROOT / "scripts" / "analyze_golovin_resolution_convergence.py"
PRACTICAL_SCRIPT = ROOT / "scripts" / "analyze_golovin_practical_convergence.py"
SCALING_SCRIPT = ROOT / "scripts" / "analyze_golovin_variance_scaling.py"


def load_module():
    for name, filename in (
        ("golovin_stage0", STAGE0_SCRIPT),
        ("analyze_golovin_resolution_convergence", RESOLUTION_SCRIPT),
        ("analyze_golovin_practical_convergence", PRACTICAL_SCRIPT),
        ("analyze_golovin_variance_scaling", SCALING_SCRIPT),
    ):
        spec = importlib.util.spec_from_file_location(name, filename)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["analyze_golovin_variance_scaling"]


def scaling_config() -> dict:
    return {
        "matrix": {"members_per_cell": 100},
        "diagnostics": {"primary_log_radius_bins": 500},
        "variance_scaling_validation": {
            "status": "researcher_authorized_existing_data_analysis_only",
            "active_max_superdroplets": [1, 2, 4],
            "available_members_per_resolution": 100,
            "ensemble_prefixes": [40, 60, 80, 100],
            "primary_log_radius_bins": 500,
            "bootstrap_resamples": 100,
            "bootstrap_seed": 1,
            "confidence_level": 0.95,
            "formal_pass_fail_gate": False,
        },
    }


def test_variance_scaling_settings_refuse_a_formal_gate() -> None:
    module = load_module()
    config = scaling_config()
    config["variance_scaling_validation"]["formal_pass_fail_gate"] = True

    with pytest.raises(ValueError, match="diagnostic"):
        module.validate_settings(config)


def test_variance_row_records_n_times_variance() -> None:
    module = load_module()
    draws = np.asarray([1.0, 2.0, 3.0, 4.0])
    row = module.variance_row(
        resolution=1,
        time_s=3600.0,
        metric="ensemble_mean_l1",
        member_count=40,
        point=2.5,
        draws=draws,
    )

    expected_variance = np.var(draws, ddof=1)
    assert row["bootstrap_variance_of_estimate"] == pytest.approx(expected_variance)
    assert row["variance_coefficient_n_times_variance"] == pytest.approx(40 * expected_variance)


def test_summary_recovers_inverse_member_scaling() -> None:
    module = load_module()
    rows = []
    for member_count in (40, 60, 80, 100):
        rows.append(
            {
                "max_superdroplets": 32768,
                "time_s": 3600.0,
                "metric": "golovin_relative_error_radius_moment_6_um6_m3",
                "ensemble_members": member_count,
                "point_estimate": 0.002,
                "bootstrap_variance_of_estimate": 0.004 / member_count,
                "variance_coefficient_n_times_variance": 0.004,
            }
        )

    summary = module.summarize_variance_rows(rows)

    assert len(summary) == 1
    assert summary[0]["fitted_log_variance_slope"] == pytest.approx(-1.0)
    assert summary[0]["fitted_log_variance_r_squared"] == pytest.approx(1.0)
    assert summary[0]["coefficient_max_to_min_ratio"] == pytest.approx(1.0)


def test_normal_calibration_uses_independent_resolution_variances() -> None:
    module = load_module()
    lower_draws = np.asarray([0.10, 0.12, 0.11, 0.09])
    upper_draws = np.asarray([0.08, 0.07, 0.09, 0.08])
    variance_rows = []
    draws = {}
    for metric in module.PRIMARY_METRICS:
        variance_rows.extend(
            [
                {
                    "max_superdroplets": 1,
                    "time_s": 3600.0,
                    "metric": metric,
                    "ensemble_members": 100,
                    "point_estimate": 0.105,
                    "bootstrap_variance_of_estimate": float(np.var(lower_draws, ddof=1)),
                },
                {
                    "max_superdroplets": 2,
                    "time_s": 3600.0,
                    "metric": metric,
                    "ensemble_members": 100,
                    "point_estimate": 0.08,
                    "bootstrap_variance_of_estimate": float(np.var(upper_draws, ddof=1)),
                },
            ]
        )
        draws[(1, 3600.0, metric, 100)] = lower_draws
        draws[(2, 3600.0, metric, 100)] = upper_draws

    rows = module.adjacent_calibration_rows(
        variance_rows=variance_rows,
        bootstrap_draws=draws,
        active_resolutions=[1, 2],
        prefixes=[100],
        decision_times=[3600.0],
        confidence_level=0.95,
    )

    assert len(rows) == 3
    assert rows[0]["absolute_point_change"] == pytest.approx(0.025)
    assert rows[0]["normal_approximation_one_sided_upper_bound"] > 0.025
