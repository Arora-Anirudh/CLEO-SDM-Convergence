import csv
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
STAGE0_SCRIPT = ROOT / "scripts" / "golovin_stage0.py"
SUMMARY_SCRIPT = ROOT / "scripts" / "summarize_golovin_ensemble.py"
DEVELOPMENT_TIME_TABLE = (
    ROOT
    / "results"
    / "golovin_stage0_development_gate_v1"
    / "analysis_stage0_v1"
    / "member_time_diagnostics.csv"
)


def load_module(filename: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_fixed_bin_l1_is_zero_for_identical_distribution() -> None:
    stage0 = load_module(STAGE0_SCRIPT, "golovin_stage0_identical")
    edges = stage0.logarithmic_radius_edges(1.0, 100.0, 10)
    distribution = np.linspace(0.1, 1.0, 10)

    assert stage0.fixed_bin_relative_l1(distribution, distribution, edges) == pytest.approx(0.0)


def test_fixed_bin_l1_detects_known_perturbation() -> None:
    stage0 = load_module(STAGE0_SCRIPT, "golovin_stage0_perturbed")
    edges = stage0.logarithmic_radius_edges(1.0, 100.0, 2)
    analytical = np.asarray([1.0, 1.0])
    numerical = np.asarray([2.0, 1.0])

    assert stage0.fixed_bin_relative_l1(numerical, analytical, edges) == pytest.approx(0.5)


def test_fixed_bin_distribution_accounts_for_in_range_and_overflow_mass() -> None:
    stage0 = load_module(STAGE0_SCRIPT, "golovin_stage0_histogram")
    edges = np.asarray([1.0, 10.0, 100.0])
    radius = np.asarray([0.5, 2.0, 20.0, 200.0])
    multiplicity = np.ones(4)
    mass = np.asarray([1.0, 2.0, 3.0, 4.0])

    result = stage0.fixed_bin_mass_density(
        radius_um=radius,
        multiplicity=multiplicity,
        droplet_mass_g=mass,
        domain_volume_m3=2.0,
        edges_um=edges,
    )

    recovered_in_range_mass_g = (
        np.sum(result.mass_density_gm3_per_ln_radius * np.diff(np.log(edges))) * 2.0
    )
    assert recovered_in_range_mass_g == pytest.approx(5.0)
    assert result.mass_below_range_fraction == pytest.approx(0.1)
    assert result.mass_above_range_fraction == pytest.approx(0.4)


def test_golovin_analytical_radius_moments_have_expected_initial_values() -> None:
    stage0 = load_module(STAGE0_SCRIPT, "golovin_stage0_moments")
    number_concentration = 8.0e6
    scale_radius_m = 30.0e-6
    moments = stage0.golovin_analytical_radius_moments(
        time_s=0.0,
        initial_number_concentration_m3=number_concentration,
        volume_exponential_scale_radius_m=scale_radius_m,
    )

    assert moments[0] == pytest.approx(number_concentration)
    assert moments[3] == pytest.approx(number_concentration * 30.0**3)
    assert moments[6] == pytest.approx(2.0 * number_concentration * 30.0**6)

    later = stage0.golovin_analytical_radius_moments(
        time_s=100.0,
        initial_number_concentration_m3=number_concentration,
        volume_exponential_scale_radius_m=scale_radius_m,
    )
    assert later[0] < moments[0]
    assert later[3] == pytest.approx(moments[3])
    assert later[6] > moments[6]


def test_golovin_fixed_bin_analytical_distribution_is_finite() -> None:
    stage0 = load_module(STAGE0_SCRIPT, "golovin_stage0_distribution")
    edges = stage0.logarithmic_radius_edges(1.0, 5000.0, 500)
    distribution = stage0.golovin_analytical_mass_density(
        edges_um=edges,
        time_s=3600.0,
        initial_number_concentration_m3=8388608.0,
        volume_exponential_scale_radius_m=30.531e-6,
        liquid_water_density_kgm3=998.203,
    )

    assert distribution.shape == (500,)
    assert np.all(np.isfinite(distribution))
    assert np.all(distribution >= 0.0)
    assert np.any(distribution > 0.0)


def test_tail_onset_reports_output_interval_instead_of_false_exact_time() -> None:
    stage0 = load_module(STAGE0_SCRIPT, "golovin_stage0_tail_onset")
    crossing = stage0.first_threshold_crossing(
        np.asarray([0.0, 300.0, 600.0, 900.0]),
        np.asarray([0.0, 0.05, 0.12, 0.20]),
        0.10,
    )

    assert crossing.status == "crossed_between_outputs"
    assert crossing.lower_bound_s == pytest.approx(300.0)
    assert crossing.upper_bound_s == pytest.approx(600.0)
    assert crossing.first_recorded_crossing_s == pytest.approx(600.0)


def test_recorded_stage0_member_has_interval_censored_millimetre_tail_time() -> None:
    stage0 = load_module(STAGE0_SCRIPT, "golovin_stage0_recorded_tail_onset")
    with DEVELOPMENT_TIME_TABLE.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    crossing = stage0.first_threshold_crossing(
        np.asarray([float(row["time_s"]) for row in rows]),
        np.asarray([float(row["mass_fraction_r_ge_large_threshold"]) for row in rows]),
        0.10,
    )

    assert crossing.status == "crossed_between_outputs"
    assert crossing.lower_bound_s == pytest.approx(3000.0)
    assert crossing.upper_bound_s == pytest.approx(3299.999952316284)
    assert crossing.first_recorded_crossing_s == pytest.approx(3299.999952316284)


def test_mass_weighted_quantile_uses_represented_mass() -> None:
    stage0 = load_module(STAGE0_SCRIPT, "golovin_stage0_quantile")
    quantile = stage0.mass_weighted_radius_quantile(
        np.asarray([100.0, 10.0, 1000.0]),
        np.asarray([1.0, 8.0, 1.0]),
        0.90,
    )

    assert quantile == pytest.approx(100.0)


def test_ensemble_summary_statistics_are_reproducible() -> None:
    summary = load_module(SUMMARY_SCRIPT, "golovin_stage0_summary")
    first = summary.summarize_values(
        [1.0, 2.0, 3.0, 4.0],
        confidence_level=0.95,
        bootstrap_resamples=2000,
        bootstrap_seed=123,
    )
    second = summary.summarize_values(
        [1.0, 2.0, 3.0, 4.0],
        confidence_level=0.95,
        bootstrap_resamples=2000,
        bootstrap_seed=123,
    )

    assert first == second
    assert first["n_total"] == 4
    assert first["n_valid"] == 4
    assert first["mean"] == pytest.approx(2.5)
    assert first["sample_standard_deviation"] == pytest.approx(np.std([1, 2, 3, 4], ddof=1))
    assert first["student_ci_low"] < first["mean"] < first["student_ci_high"]


def test_ensemble_summary_requires_exact_matrix_coverage() -> None:
    summary = load_module(SUMMARY_SCRIPT, "golovin_stage0_matrix_coverage")
    common = {
        "run_label": "member_000",
        "matrix_stage": "development",
        "initialization_family": "operational_stochastic",
        "kernel": "golovin",
        "max_superdroplets": "1024",
        "collision_timestep_s": "1.0",
        "observation_timestep_s": "300.0",
        "end_time_s": "3600.0",
        "member_index": "0",
        "initialization_seed": "123",
        "collision_seed": "456",
    }
    time_rows = [{**common, "time_s": "0.0"}]
    member_rows = [common.copy()]
    matrix_rows = [common.copy()]

    summary.validate_matrix_coverage(time_rows, member_rows, matrix_rows)

    with pytest.raises(RuntimeError, match="exactly cover"):
        summary.validate_matrix_coverage(time_rows, [], matrix_rows)
