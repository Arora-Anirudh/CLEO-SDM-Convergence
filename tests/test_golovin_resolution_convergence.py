import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_golovin_resolution_convergence.py"
STAGE0_SCRIPT = ROOT / "scripts" / "golovin_stage0.py"


def load_module():
    stage0_spec = importlib.util.spec_from_file_location("golovin_stage0", STAGE0_SCRIPT)
    stage0 = importlib.util.module_from_spec(stage0_spec)
    assert stage0_spec.loader is not None
    sys.modules[stage0_spec.name] = stage0
    stage0_spec.loader.exec_module(stage0)

    spec = importlib.util.spec_from_file_location(
        "analyze_golovin_resolution_convergence",
        SCRIPT,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_inputs(*, fail_smallest: bool = False):
    matrix_rows = []
    rows = []
    archives = {}
    times = (600.0, 1200.0)
    for resolution in (512, 1024, 2048):
        for member in range(4):
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
            for time_s in times:
                bias = 0.20 if fail_smallest and resolution == 512 else 0.0
                rows.append(
                    {
                        "run_label": run_label,
                        "max_superdroplets": str(resolution),
                        "member_index": str(member),
                        "time_s": str(time_s),
                        "golovin_relative_error_radius_moment_0_m3": str(bias),
                        "golovin_relative_error_radius_moment_6_um6_m3": str(bias),
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
                analytical = np.ones((len(times), bin_count))
                distribution_bias = 0.20 if fail_smallest and resolution == 512 else 0.0
                archive[f"edges_um_{bin_count}"] = edges
                archive[f"analytical_gm3_per_ln_radius_{bin_count}"] = analytical
                archive[f"numerical_gm3_per_ln_radius_{bin_count}"] = analytical + distribution_bias
            archives[run_label] = archive

    config = {
        "matrix": {
            "max_superdroplets": [512, 1024, 2048],
            "members_per_cell": 4,
        },
        "diagnostics": {
            "decision_times_s": list(times),
            "confidence_level": 0.95,
            "bootstrap_resamples": 100,
            "bootstrap_seed": 123,
            "bin_robustness_policy": ("require_resolution_decision_at_all_registered_bin_counts"),
            "ensemble_size_sensitivity": {
                "time_s": 1200.0,
                "member_counts": [2, 4],
                "random_subset_draws": 20,
                "random_subset_seed": 456,
                "log_radius_bins": 500,
            },
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


def test_resolution_analysis_selects_smallest_confirmed_level() -> None:
    module = load_module()
    rows, matrix_rows, config, archives = synthetic_inputs()

    analytical, adjacent, decision = module.analyze(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )

    assert analytical
    assert adjacent
    assert decision["status"] == "selected_controlled_resolution"
    assert decision["selected_max_superdroplets"] == 512
    assert decision["resolution_analytical_and_precision_pass"] == {
        "512": True,
        "1024": True,
        "2048": True,
    }
    assert decision["adjacent_pair_equivalence_pass"] == {
        "512-1024": True,
        "1024-2048": True,
    }
    assert all(
        type(value) is bool
        for value in decision["resolution_analytical_and_precision_pass"].values()
    )
    assert all(type(value) is bool for value in decision["adjacent_pair_equivalence_pass"].values())
    assert json.loads(json.dumps(decision)) == decision


def test_portable_artifact_path_survives_analysis_root_move(tmp_path: Path) -> None:
    module = load_module()
    staging_root = tmp_path / ".analysis_v1_job123.tmp"
    combined = staging_root / "ensemble_summary" / "all_member_time_diagnostics.csv"

    published_path = module.portable_artifact_path(
        combined,
        analysis_root=staging_root,
    )

    assert published_path == "ensemble_summary/all_member_time_diagnostics.csv"


def test_resolution_analysis_does_not_accept_failed_smallest_level() -> None:
    module = load_module()
    rows, matrix_rows, config, archives = synthetic_inputs(fail_smallest=True)

    _, _, decision = module.analyze(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )

    assert decision["status"] == "no_resolution_accepted_in_initial_matrix"
    assert decision["selected_max_superdroplets"] is None
    assert decision["resolution_analytical_and_precision_pass"]["512"] is False


def test_resolution_plot_accepts_bootstrap_interval_excluding_estimate(
    tmp_path: Path,
) -> None:
    module = load_module()
    analytical_rows = []
    for metric in (
        "ensemble_mean_l1_bins_500",
        "golovin_relative_error_radius_moment_0_m3",
        "golovin_relative_error_radius_moment_6_um6_m3",
    ):
        for resolution in (512, 1024, 2048):
            analytical_rows.append(
                {
                    "max_superdroplets": resolution,
                    "time_s": 3600.0,
                    "metric": metric,
                    "estimate": 0.10,
                    "95ci_low": 0.12,
                    "95ci_high": 0.20,
                }
            )
    output = tmp_path / "resolution_convergence.png"

    module.plot_result(
        analytical_rows,
        synthetic_inputs()[2],
        output,
    )

    assert output.is_file()
    assert output.stat().st_size > 0


def test_ensemble_size_sensitivity_covers_every_metric_and_resolution() -> None:
    module = load_module()
    rows, matrix_rows, config, archives = synthetic_inputs()

    sensitivity = module.analyze_ensemble_size_sensitivity(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )

    assert len(sensitivity) == 3 * 2 * 3
    assert {int(row["max_superdroplets"]) for row in sensitivity} == {512, 1024, 2048}
    assert {int(row["ensemble_size"]) for row in sensitivity} == {2, 4}
    assert {row["metric"] for row in sensitivity} == {
        "ensemble_mean_l1_bins_500",
        "golovin_relative_error_radius_moment_0_m3",
        "golovin_relative_error_radius_moment_6_um6_m3",
    }
    assert all(
        float(row["subset_95pct_low"]) <= float(row["subset_95pct_high"]) for row in sensitivity
    )
    complete_pool_rows = [row for row in sensitivity if int(row["ensemble_size"]) == 4]
    assert all(int(row["random_subset_draws"]) == 1 for row in complete_pool_rows)
    assert all(
        float(row["subset_median"]) == float(row["full_ensemble_estimate"])
        for row in complete_pool_rows
    )


def test_new_plots_are_written(tmp_path: Path) -> None:
    module = load_module()
    rows, matrix_rows, config, archives = synthetic_inputs()
    analytical, adjacent, _ = module.analyze(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )
    sensitivity = module.analyze_ensemble_size_sensitivity(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
        archives=archives,
    )

    analytical_plot = tmp_path / "analytical.png"
    adjacent_plot = tmp_path / "adjacent.png"
    sensitivity_plot = tmp_path / "sensitivity.png"
    module.plot_result(analytical, config, analytical_plot)
    module.plot_adjacent_equivalence(adjacent, config, adjacent_plot)
    module.plot_ensemble_size_sensitivity(sensitivity, config, sensitivity_plot)

    for filename in (analytical_plot, adjacent_plot, sensitivity_plot):
        assert filename.is_file()
        assert filename.stat().st_size > 0
