import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "controlled_initialization.py"


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def build_population(module, number_of_superdroplets: int = 512):
    return module.build_controlled_population(
        number_of_superdroplets=number_of_superdroplets,
        sample_volume_m3=1.0e12,
        number_concentration_m3=8_388_608.0,
        radius_minimum_m=1.0e-6,
        radius_maximum_m=75.0e-6,
        scale_radius_m=30.531e-6,
        minimum_multiplicity=10,
        maximum_relative_moment0_error=1.0e-10,
        maximum_relative_moment3_error=1.0e-10,
        maximum_relative_moment6_error=0.01,
    )


def test_largest_remainder_is_exact_and_breaks_ties_by_bin_index() -> None:
    module = load_module("controlled_initialization_largest_remainder")
    result = module.largest_remainder_multiplicities(
        np.asarray([0.25, 0.25, 0.25, 0.25]),
        target_total=6,
        minimum_multiplicity=1,
    )

    assert result.tolist() == [2, 2, 1, 1]
    assert sum(int(value) for value in result) == 6


def test_controlled_population_preserves_required_moments_and_bin_support() -> None:
    module = load_module("controlled_initialization_moments")
    population = build_population(module)

    assert sum(int(value) for value in population.multiplicities) == 8_388_608 * 10**12
    assert abs(population.relative_moment_errors[0]) <= 1.0e-10
    assert abs(population.relative_moment_errors[3]) <= 1.0e-10
    assert abs(population.relative_moment_errors[6]) <= 0.01

    representative_volumes = module.sphere_volume(population.radii_m)
    assert np.all(representative_volumes >= population.volume_edges_m3[:-1])
    assert np.all(representative_volumes <= population.volume_edges_m3[1:])
    assert np.min(population.multiplicities) >= 10


def test_controlled_population_and_hash_are_repeatable() -> None:
    module = load_module("controlled_initialization_repeatability")
    first = build_population(module)
    second = build_population(module)

    assert np.array_equal(first.multiplicities, second.multiplicities)
    assert np.array_equal(first.radii_m, second.radii_m)
    assert module.population_sha256(first) == module.population_sha256(second)


@pytest.mark.parametrize(
    "number_of_superdroplets",
    (16_384, 32_768, 65_536, 131_072),
)
def test_controlled_population_supports_registered_high_resolutions(
    number_of_superdroplets: int,
) -> None:
    module = load_module(f"controlled_initialization_highres_{number_of_superdroplets}")
    population = build_population(
        module,
        number_of_superdroplets=number_of_superdroplets,
    )

    assert population.radii_m.size == number_of_superdroplets
    assert sum(int(value) for value in population.multiplicities) == 8_388_608 * 10**12
    assert abs(population.relative_moment_errors[0]) <= 1.0e-10
    assert abs(population.relative_moment_errors[3]) <= 1.0e-10
    assert abs(population.relative_moment_errors[6]) <= 0.01


def test_m6_gate_rejects_an_underresolved_population() -> None:
    module = load_module("controlled_initialization_m6_gate")

    with pytest.raises(ValueError, match="failed M6 tolerance"):
        build_population(module, number_of_superdroplets=16)


def test_minimum_multiplicity_gate_rejects_an_impossible_allocation() -> None:
    module = load_module("controlled_initialization_xi_gate")

    with pytest.raises(ValueError, match="minimum multiplicity"):
        module.largest_remainder_multiplicities(
            np.asarray([0.25, 0.25, 0.25, 0.25]),
            target_total=4,
            minimum_multiplicity=2,
        )


class DeterministicCoordinate:
    def __call__(self, number: int, bounds: np.ndarray) -> np.ndarray:
        return np.linspace(bounds[0], bounds[1], number, endpoint=False)


def test_cleo_adapter_returns_native_dtypes_and_deterministic_coordinates() -> None:
    module = load_module("controlled_initialization_adapter")
    population = build_population(module, number_of_superdroplets=64)
    coordinate = DeterministicCoordinate()
    generator = module.ControlledAttrsGenerator(
        population,
        dry_radius_m=1.0e-16,
        coord3gen=coordinate,
        coord1gen=coordinate,
        coord2gen=coordinate,
    )
    bounds = np.asarray([0.0, 10_000.0, 0.0, 10_000.0, 0.0, 10_000.0])

    multiplicity, radius, solute_mass = generator.generate_attributes(
        nsupers=64,
        rho_sol_kgm3=2016.5,
        gbxindex=0,
        gridboxbounds=bounds,
        number_concentration_m3=8_388_608.0,
    )
    coordinates = generator.generate_coords(64, 3, bounds)

    assert multiplicity.dtype == np.dtype(np.uint)
    assert radius.dtype == np.dtype(np.double)
    assert solute_mass.dtype == np.dtype(np.double)
    assert all(values.dtype == np.dtype(np.double) for values in coordinates)
    assert all(values.shape == (64,) for values in coordinates)
    assert all(np.array_equal(values, coordinates[0]) for values in coordinates[1:])


def test_controlled_audit_hashes_artifacts_and_refuses_overwrite(tmp_path: Path) -> None:
    module = load_module("controlled_initialization_audit")
    population = build_population(module, number_of_superdroplets=64)
    source = tmp_path / "source.yaml"
    source.write_text("scientific: input\n", encoding="utf-8")
    audit_file = tmp_path / "controlled-audit.json"

    record = module.controlled_audit(
        population,
        liquid_water_density_kgm3=998.203,
        source_config=source,
    )
    module.write_controlled_audit(audit_file, record)
    saved = json.loads(audit_file.read_text(encoding="utf-8"))

    assert saved["status"] == "passed"
    assert saved["population"]["represented_real_droplets"] == 8_388_608 * 10**12
    assert saved["constraints"]["moment0_and_moment3_controlled"] is True
    assert saved["constraints"]["moment6_forced"] is False
    assert saved["artifacts"]["source_config"]["sha256"] == module.sha256_file(source)

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        module.write_controlled_audit(audit_file, record)
