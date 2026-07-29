import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_collisions0d.py"


def load_analyzer():
    spec = importlib.util.spec_from_file_location("analyze_collisions0d", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_analyzer_loads_from_an_isolated_python_process(tmp_path: Path) -> None:
    command = (
        "import importlib.util\n"
        f"script = {str(SCRIPT)!r}\n"
        "spec = importlib.util.spec_from_file_location('analyze_collisions0d', script)\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
    )

    subprocess.run(
        [sys.executable, "-I", "-c", command],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )


def test_bulk_row_uses_multiplicity_and_conserves_mass() -> None:
    analyzer = load_analyzer()
    radius = np.asarray([10.0, 50.0, 1500.0])
    multiplicity = np.asarray([3.0, 2.0, 1.0])
    water_mass = np.asarray([1.0, 2.0, 5.0])

    row = analyzer.calculate_bulk_row(
        time_s=60.0,
        radius_um=radius,
        multiplicity=multiplicity,
        water_mass_g=water_mass,
        domain_volume_m3=2.0,
        initial_liquid_water_gm3=6.0,
    )

    assert row["n_superdroplet_records"] == 3
    assert row["number_concentration_cm3"] == pytest.approx(3.0e-6)
    assert row["liquid_water_gm3"] == pytest.approx(6.0)
    assert row["relative_liquid_mass_drift"] == pytest.approx(0.0)
    assert row["max_radius_um"] == pytest.approx(1500.0)
    assert row["mass_fraction_r_ge_cloud_threshold"] == pytest.approx(9.0 / 12.0)
    assert row["mass_fraction_r_ge_large_threshold"] == pytest.approx(5.0 / 12.0)
    assert row["mass_fraction_r_ge_onset_threshold"] == pytest.approx(5.0 / 12.0)


def test_relative_l1_error_is_zero_for_identical_distributions() -> None:
    analyzer = load_analyzer()
    radius = np.geomspace(1.0, 100.0, 20)
    distribution = np.exp(-((np.log(radius) - 2.0) ** 2))

    assert analyzer.relative_l1_error(distribution, distribution, radius) == pytest.approx(0.0)


def test_nominal_times_accept_cleo_float_scaling() -> None:
    analyzer = load_analyzer()
    stored = np.asarray([0.0, 1200.0000476837158, 2400.0000953674316, 3599.9999046325684])

    analyzer.require_exact_times(stored, [0.0, 1200.0, 2400.0, 3600.0])


def test_fixed_bin_robustness_reports_every_registered_grid() -> None:
    analyzer = load_analyzer()
    radius_um = np.asarray([5.0, 20.0, 80.0])
    multiplicity = np.asarray([4.0, 2.0, 1.0])
    wet_mass_g = analyzer.water_equivalent_droplet_mass_g(radius_um, 998.203)
    edges_by_count = {
        count: analyzer.logarithmic_radius_edges(1.0, 5000.0, count) for count in (250, 500, 1000)
    }

    result = analyzer.calculate_fixed_bin_robustness(
        radius_um=radius_um,
        multiplicity=multiplicity,
        wet_mass_g=wet_mass_g,
        domain_volume_m3=1.0e6,
        edges_by_count=edges_by_count,
        time_s=0.0,
        number_concentration_m3=8.388608e6,
        volume_exponential_scale_m=30.531e-6,
        liquid_water_density_kgm3=998.203,
    )

    for count in edges_by_count:
        assert np.isfinite(result[f"golovin_fixed_bin_l1_relative_bins_{count}"])
        assert result[f"fixed_bin_mass_below_range_fraction_bins_{count}"] == pytest.approx(0.0)
        assert result[f"fixed_bin_mass_above_range_fraction_bins_{count}"] == pytest.approx(0.0)
