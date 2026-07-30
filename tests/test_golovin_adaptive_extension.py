import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGE0_SCRIPT = ROOT / "scripts" / "golovin_stage0.py"
RESOLUTION_SCRIPT = ROOT / "scripts" / "analyze_golovin_resolution_convergence.py"
PRACTICAL_SCRIPT = ROOT / "scripts" / "analyze_golovin_practical_convergence.py"
PLANNER_SCRIPT = ROOT / "scripts" / "plan_golovin_adaptive_extension.py"


def load_module():
    for name, filename in (
        ("golovin_stage0", STAGE0_SCRIPT),
        ("analyze_golovin_resolution_convergence", RESOLUTION_SCRIPT),
        ("analyze_golovin_practical_convergence", PRACTICAL_SCRIPT),
        ("plan_golovin_adaptive_extension", PLANNER_SCRIPT),
    ):
        spec = importlib.util.spec_from_file_location(name, filename)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["plan_golovin_adaptive_extension"]


def planning_config() -> dict:
    return {
        "matrix": {"members_per_cell": 100},
        "practical_convergence": {
            "primary_log_radius_bins": 500,
            "minimum_worthwhile_improvement_absolute": 0.01,
        },
        "adaptive_extension_planning": {
            "status": "researcher_authorized_exploratory_analysis_only",
            "candidate_max_superdroplets": 1,
            "active_max_superdroplets": [1, 2, 4],
            "current_members_per_resolution": 100,
            "primary_log_radius_bins": 500,
            "confidence_level": 0.95,
            "bootstrap_resamples": 100,
            "bootstrap_seed": 1,
            "minimum_worthwhile_improvement_absolute": 0.01,
            "allocation_grid": {
                "minimum_total_members": 100,
                "maximum_total_members": 1000,
                "increment": 5,
            },
            "balanced_projection_member_counts": [100, 200, 500, 1000],
            "interim_results_are_exploratory_only": True,
            "formal_early_stopping_requires_alpha_spending_or_confidence_sequence": True,
            "fixed_final_allocation_may_use_current_100_members_as_variance_pilot": True,
            "unequal_allocation_requires_protocol_amendment_before_model_submission": True,
        },
    }


def constraint(
    lower: int,
    upper: int,
    *,
    point_change: float = 0.005,
    lower_coefficient: float = 0.001,
    upper_coefficient: float = 0.001,
) -> dict[str, object]:
    return {
        "lower_max_superdroplets": lower,
        "upper_max_superdroplets": upper,
        "time_s": 3600.0,
        "metric": "golovin_relative_error_radius_moment_6_um6_m3",
        "point_change": point_change,
        "minimum_worthwhile_improvement": 0.01,
        "lower_variance_coefficient": lower_coefficient,
        "upper_variance_coefficient": upper_coefficient,
        "normal_quantile": 1.6448536269514722,
    }


def test_projected_bound_decreases_with_independent_member_count() -> None:
    module = load_module()

    at_100 = module.projected_upper_bound(
        point_change=0.005,
        lower_variance_coefficient=0.001,
        upper_variance_coefficient=0.001,
        lower_members=100,
        upper_members=100,
        z_value=1.6448536269514722,
    )
    at_400 = module.projected_upper_bound(
        point_change=0.005,
        lower_variance_coefficient=0.001,
        upper_variance_coefficient=0.001,
        lower_members=400,
        upper_members=400,
        z_value=1.6448536269514722,
    )

    assert at_400 < at_100
    assert at_400 > 0.005


def test_cost_optimizer_finds_a_passing_fixed_allocation() -> None:
    module = load_module()
    config = planning_config()
    constraints = [
        constraint(1, 2, lower_coefficient=0.0004, upper_coefficient=0.002),
        constraint(2, 4, lower_coefficient=0.002, upper_coefficient=0.0004),
    ]
    costs = [
        {
            "max_superdroplets": 1,
            "mean_job_wall_seconds_per_member": 1.0,
            "mean_zarr_bytes_per_member": 10.0,
        },
        {
            "max_superdroplets": 2,
            "mean_job_wall_seconds_per_member": 2.0,
            "mean_zarr_bytes_per_member": 10.0,
        },
        {
            "max_superdroplets": 4,
            "mean_job_wall_seconds_per_member": 8.0,
            "mean_zarr_bytes_per_member": 10.0,
        },
    ]

    frontier, allocation = module.cost_optimal_allocation(
        constraints=constraints,
        cost_rows=costs,
        config=config,
    )

    assert frontier
    assert allocation is not None
    assert module.allocation_passes(constraints, allocation)
    assert set(allocation) == {1, 2, 4}
    assert all(100 <= count <= 1000 for count in allocation.values())


def test_point_change_above_margin_cannot_be_fixed_by_more_members() -> None:
    module = load_module()
    config = planning_config()
    constraints = [
        constraint(1, 2, point_change=0.011),
        constraint(2, 4),
    ]
    costs = [
        {
            "max_superdroplets": resolution,
            "mean_job_wall_seconds_per_member": float(resolution),
            "mean_zarr_bytes_per_member": 10.0,
        }
        for resolution in (1, 2, 4)
    ]

    frontier, allocation = module.cost_optimal_allocation(
        constraints=constraints,
        cost_rows=costs,
        config=config,
    )

    assert frontier == []
    assert allocation is None


def test_unprotected_optional_stopping_is_rejected() -> None:
    module = load_module()
    config = planning_config()
    config["adaptive_extension_planning"][
        "formal_early_stopping_requires_alpha_spending_or_confidence_sequence"
    ] = False

    with pytest.raises(ValueError, match="early-stopping protection"):
        module.validate_planning_settings(config)


def test_no_feasible_design_still_writes_auditable_outputs(tmp_path: Path) -> None:
    module = load_module()
    csv_path = tmp_path / "empty.csv"
    figure_path = tmp_path / "empty.png"

    module.write_optional_csv(csv_path, [], ["allocation", "cost"])
    module.plot_design_costs(
        [
            {
                "design": "balanced_fixed_final",
                "feasible_within_planning_grid": False,
            }
        ],
        figure_path,
    )

    assert csv_path.read_text(encoding="utf-8") == "allocation,cost\n"
    assert figure_path.is_file()
    assert figure_path.stat().st_size > 0
