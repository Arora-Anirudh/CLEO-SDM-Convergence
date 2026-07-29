import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_golovin_timestep_screen.py"


def load_module():
    spec = importlib.util.spec_from_file_location("analyze_golovin_timestep_screen", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_inputs(moment6_difference: float = 0.02):
    matrix_rows = []
    rows = []
    for timestep in (1.0, 0.1):
        for member in range(5):
            run_label = f"dt{timestep}_m{member}"
            matrix_rows.append(
                {
                    "run_label": run_label,
                    "initialization_family": "controlled",
                    "controlled_bundle_label": "bundle",
                    "collision_timestep_s": str(timestep),
                    "member_index": str(member),
                    "collision_seed": str(100 + member),
                }
            )
            for time_s in (600.0, 1200.0):
                offset = 0.0 if timestep == 0.1 else 1.0
                primary_l1 = 0.20 + 0.01 * member
                rows.append(
                    {
                        "run_label": run_label,
                        "collision_timestep_s": str(timestep),
                        "member_index": str(member),
                        "collision_seed": str(100 + member),
                        "time_s": str(time_s),
                        "golovin_fixed_bin_l1_relative": str(primary_l1 + 0.002 * offset),
                        "golovin_relative_error_radius_moment_0_m3": str(-0.03 + 0.003 * offset),
                        "golovin_relative_error_radius_moment_6_um6_m3": str(
                            0.04 + moment6_difference * offset
                        ),
                        "relative_liquid_mass_drift": "1e-9",
                        "fixed_bin_mass_below_range_fraction": "0.0",
                        "fixed_bin_mass_above_range_fraction": "0.0",
                        "golovin_fixed_bin_l1_relative_bins_250": str(
                            primary_l1 + 0.001 + 0.002 * offset
                        ),
                        "golovin_fixed_bin_l1_relative_bins_500": str(primary_l1 + 0.002 * offset),
                        "golovin_fixed_bin_l1_relative_bins_1000": str(
                            primary_l1 - 0.001 + 0.002 * offset
                        ),
                    }
                )
    config = {
        "screening": {
            "reference_collision_timestep_s": 0.1,
            "decision_times_s": [600.0, 1200.0],
            "maximum_l1_mean_absolute_difference": 0.01,
            "maximum_moment0_mean_relative_difference": 0.05,
            "maximum_moment6_mean_relative_difference": 0.10,
            "maximum_relative_liquid_mass_drift": 1.0e-7,
            "maximum_bin_robustness_mean_absolute_difference": 0.005,
            "maximum_out_of_range_mass_fraction": 1.0e-6,
            "selection_rule": "largest_timestep_passing_all_registered_gates",
        }
    }
    return rows, matrix_rows, config


def test_screen_selects_largest_timestep_inside_all_equivalence_margins() -> None:
    module = load_module()
    rows, matrix_rows, config = synthetic_inputs()

    comparisons, robustness, selection = module.analyze(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
    )

    assert len(comparisons) == 2 * 2 * 3
    assert len(robustness) == 2 * 2
    assert selection["selected_collision_timestep_s"] == 1.0
    assert selection["timestep_pass"] == {"0.1": True, "1.0": True}


def test_screen_falls_back_to_reference_when_coarser_m6_difference_fails() -> None:
    module = load_module()
    rows, matrix_rows, config = synthetic_inputs(moment6_difference=0.2)

    _, _, selection = module.analyze(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
    )

    assert selection["selected_collision_timestep_s"] == 0.1
    assert selection["timestep_pass"] == {"0.1": True, "1.0": False}


def test_screen_rejects_coarser_timestep_when_bin_robustness_fails() -> None:
    module = load_module()
    rows, matrix_rows, config = synthetic_inputs()
    for row in rows:
        if row["collision_timestep_s"] == "1.0":
            row["golovin_fixed_bin_l1_relative_bins_250"] = str(
                float(row["golovin_fixed_bin_l1_relative_bins_500"]) + 0.02
            )

    _, _, selection = module.analyze(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
    )

    assert selection["selected_collision_timestep_s"] == 0.1
    assert selection["timestep_pass"] == {"0.1": True, "1.0": False}


def test_screen_rejects_coarser_timestep_when_mass_leaves_registered_bins() -> None:
    module = load_module()
    rows, matrix_rows, config = synthetic_inputs()
    for row in rows:
        if row["collision_timestep_s"] == "1.0":
            row["fixed_bin_mass_above_range_fraction"] = "2e-6"

    _, _, selection = module.analyze(
        rows=rows,
        matrix_rows=matrix_rows,
        config=config,
    )

    assert selection["selected_collision_timestep_s"] == 0.1
    assert selection["timestep_pass"] == {"0.1": True, "1.0": False}
