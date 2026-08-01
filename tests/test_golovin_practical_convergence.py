import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
STAGE0_SCRIPT = ROOT / "scripts" / "golovin_stage0.py"
RESOLUTION_SCRIPT = ROOT / "scripts" / "analyze_golovin_resolution_convergence.py"
PRACTICAL_SCRIPT = ROOT / "scripts" / "analyze_golovin_practical_convergence.py"


def load_module():
    for name, filename in (
        ("golovin_stage0", STAGE0_SCRIPT),
        ("analyze_golovin_resolution_convergence", RESOLUTION_SCRIPT),
        ("analyze_golovin_practical_convergence", PRACTICAL_SCRIPT),
    ):
        spec = importlib.util.spec_from_file_location(name, filename)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["analyze_golovin_practical_convergence"]


def synthetic_inputs(*, smallest_offset: float = 0.0):
    matrix_rows = []
    rows = []
    archives = {}
    times = (600.0, 1200.0)
    resolutions = (512, 1024, 2048)
    members_per_resolution = 4
    for resolution in resolutions:
        for member in range(members_per_resolution):
            run_label = f"nsd{resolution}_m{member}"
            matrix_rows.append(
                {
                    "run_label": run_label,
                    "initialization_family": "controlled",
                    "collision_timestep_s": "0.1",
                    "max_superdroplets": str(resolution),
                    "member_index": str(member),
                }
            )
            offset = smallest_offset if resolution == resolutions[0] else 0.0
            for time_s in times:
                rows.append(
                    {
                        "run_label": run_label,
                        "max_superdroplets": str(resolution),
                        "member_index": str(member),
                        "time_s": str(time_s),
                        "golovin_relative_error_radius_moment_0_m3": str(offset),
                        "golovin_relative_error_radius_moment_6_um6_m3": str(offset),
                        "relative_liquid_mass_drift": "1e-9",
                        "fixed_bin_mass_below_range_fraction": "0.0",
                        "fixed_bin_mass_above_range_fraction": "0.0",
                    }
                )
            archive = {
                "diagnostic_schema_version": np.asarray([3]),
                "time_s": np.asarray(times),
                "bin_counts": np.asarray([250, 500, 1000]),
            }
            for bin_count in (250, 500, 1000):
                edges = np.geomspace(1.0, 5000.0, bin_count + 1)
                analytical = np.linspace(1.0, 2.0, bin_count)[None, :]
                analytical = np.repeat(analytical, len(times), axis=0)
                numerical = analytical.copy()
                numerical[:, : bin_count // 2] *= 1.0 + offset
                numerical[:, bin_count // 2 :] *= 1.0 - offset
                archive[f"edges_um_{bin_count}"] = edges
                archive[f"analytical_gm3_per_ln_radius_{bin_count}"] = analytical
                archive[f"numerical_gm3_per_ln_radius_{bin_count}"] = numerical
            archives[run_label] = archive

    config = {
        "matrix": {
            "max_superdroplets": list(resolutions),
            "members_per_cell": members_per_resolution,
        },
        "diagnostics": {
            "decision_times_s": list(times),
            "confidence_level": 0.95,
            "bootstrap_resamples": 100,
            "bootstrap_seed": 123,
            "bin_robustness_policy": ("require_resolution_decision_at_all_registered_bin_counts"),
        },
        "practical_convergence": {
            "status": "researcher_approved_existing_data_reanalysis_pending_clara_review",
            "protocol_version": 1,
            "primary_log_radius_bins": 500,
            "sensitivity_log_radius_bins": [250, 1000],
            "confidence_level": 0.95,
            "bootstrap_resamples": 100,
            "bootstrap_seed": 456,
            "ensemble_prefixes": [2, 4],
            "final_prefixes_for_stability": [2, 4],
            "minimum_worthwhile_improvement_absolute": 0.01,
            "maximum_point_change_between_final_prefixes": 0.01,
            "require_two_successive_doublings": True,
            "sensitivity_bins_are_diagnostic_only": True,
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
            "maximum_relative_liquid_mass_drift": 1.0e-7,
            "maximum_out_of_range_mass_fraction": 1.0e-6,
            "require_pass_at_every_decision_time": True,
            "require_next_level_confirmation": True,
        },
        "timestep_selection_provenance": {
            "selected_collision_timestep_s": 0.1,
        },
        "authorization": {
            "submission_authorized": False,
        },
    }
    return rows, matrix_rows, config, archives


def test_exact_plateau_selects_smallest_confirmed_resolution() -> None:
    module = load_module()
    rows, matrix_rows, config, archives = synthetic_inputs()

    estimates, changes, stability, sensitivity, decision = module.analyze_practical_convergence(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )

    assert estimates
    assert changes
    assert stability
    assert sensitivity
    assert decision["status"] == "selected_practical_resolution"
    assert decision["selected_max_superdroplets"] == 512
    assert decision["ensemble_stability"]["ensemble_sufficiency_pass"] is True
    assert all(bool(row["diminishing_returns_pass"]) for row in changes)


def test_material_but_analytically_valid_change_blocks_selection() -> None:
    module = load_module()
    rows, matrix_rows, config, archives = synthetic_inputs(smallest_offset=0.02)

    estimates, changes, _, _, decision = module.analyze_practical_convergence(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )

    full_primary = [
        row
        for row in estimates
        if int(row["ensemble_size"]) == 4 and int(row["log_radius_bins"]) == 500
    ]
    assert all(bool(row["analytical_validity_pass"]) for row in full_primary)
    limiting = [
        row
        for row in changes
        if int(row["ensemble_size"]) == 4
        and int(row["log_radius_bins"]) == 500
        and int(row["lower_max_superdroplets"]) == 512
    ]
    assert any(not bool(row["diminishing_returns_pass"]) for row in limiting)
    assert decision["status"] == "no_practical_resolution_selected"
    assert decision["selected_max_superdroplets"] is None


def test_diminishing_returns_uses_absolute_one_sided_upper_bound() -> None:
    module = load_module()
    rows, matrix_rows, config, archives = synthetic_inputs(smallest_offset=0.02)

    _, changes, _ = module.evaluate_prefix(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
        member_count=4,
        bin_count=500,
    )

    assert all(float(row["absolute_change"]) >= 0.0 for row in changes)
    assert all(
        float(row["one_sided_95_upper_bound"]) >= float(row["absolute_change"]) for row in changes
    )


def test_targeted_member_counts_are_recorded_per_resolution() -> None:
    module = load_module()
    rows, matrix_rows, config, archives = synthetic_inputs()
    config["practical_convergence"].pop("ensemble_prefixes")
    config["practical_convergence"].pop("final_prefixes_for_stability")
    config["practical_convergence"]["targeted_member_counts_by_resolution"] = {
        512: 4,
        1024: 3,
        2048: 2,
    }

    _, changes, decision = module.evaluate_prefix(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
        member_count=4,
        bin_count=500,
        member_counts_by_resolution={512: 4, 1024: 3, 2048: 2},
    )

    assert decision["members_by_resolution"] == {"512": 4, "1024": 3, "2048": 2}
    lower_counts = {
        int(row["lower_n_members"]) for row in changes if int(row["lower_max_superdroplets"]) == 512
    }
    upper_counts = {
        int(row["upper_n_members"])
        for row in changes
        if int(row["upper_max_superdroplets"]) == 1024
    }
    assert lower_counts == {4}
    assert upper_counts == {3}


def test_practical_plots_are_written(tmp_path: Path) -> None:
    module = load_module()
    rows, matrix_rows, config, archives = synthetic_inputs()
    _, changes, _, _, _ = module.analyze_practical_convergence(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )
    diminishing = tmp_path / "diminishing.png"
    prefixes = tmp_path / "prefixes.png"

    module.plot_diminishing_returns(changes, config, diminishing)
    module.plot_prefix_stability(changes, config, prefixes)

    for filename in (diminishing, prefixes):
        assert filename.is_file()
        assert filename.stat().st_size > 0
