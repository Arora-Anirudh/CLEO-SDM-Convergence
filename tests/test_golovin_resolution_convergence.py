import importlib.util
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
        },
        "convergence_criteria": {
            "analytical_agreement": {
                "maximum_l1_upper_95ci": 0.05,
                "moment0_relative_bias_margin": 0.05,
                "moment6_relative_bias_margin": 0.10,
            },
            "adjacent_level_equivalence": {
                "l1_absolute_difference_margin": 0.01,
                "moment0_relative_difference_margin": 0.05,
                "moment6_relative_difference_margin": 0.10,
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
