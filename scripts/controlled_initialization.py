"""Deterministic controlled initialization for the Golovin convergence study.

The prescribed exponential-in-volume distribution is conditioned on one fixed
radius support. One superdroplet represents each logarithmic-volume bin.
Integer multiplicities preserve the rounded physical-droplet total, and each
representative volume preserves its bin-integrated liquid volume.

This module contains no CLEO imports. ``prepare_collisions0d_inputs.py`` wraps
the resulting population in CLEO's native initial-condition binary writer.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ControlledPopulation:
    """One deterministic discrete representation of a continuous DSD."""

    volume_edges_m3: np.ndarray
    expected_multiplicities: np.ndarray
    multiplicities: np.ndarray
    radii_m: np.ndarray
    target_bin_liquid_volumes_m3: np.ndarray
    target_real_droplets: int
    configured_number_concentration_m3: float
    represented_number_concentration_m3: float
    sample_volume_m3: float
    scale_radius_m: float
    radius_minimum_m: float
    radius_maximum_m: float
    minimum_multiplicity: int
    target_moments: dict[int, float]
    represented_moments: dict[int, float]
    relative_moment_errors: dict[int, float]


def sphere_volume(radius_m: np.ndarray | float) -> np.ndarray:
    """Return spherical volume in cubic metres."""
    radius_m = np.asarray(radius_m, dtype=float)
    return (4.0 / 3.0) * np.pi * radius_m**3


def radius_from_volume(volume_m3: np.ndarray) -> np.ndarray:
    """Return spherical radius in metres."""
    volume_m3 = np.asarray(volume_m3, dtype=float)
    return np.cbrt(3.0 * volume_m3 / (4.0 * np.pi))


def _validate_inputs(
    *,
    number_of_superdroplets: int,
    sample_volume_m3: float,
    number_concentration_m3: float,
    radius_minimum_m: float,
    radius_maximum_m: float,
    scale_radius_m: float,
    minimum_multiplicity: int,
) -> None:
    if number_of_superdroplets < 1:
        raise ValueError("number_of_superdroplets must be positive")
    for name, value in (
        ("sample_volume_m3", sample_volume_m3),
        ("number_concentration_m3", number_concentration_m3),
        ("radius_minimum_m", radius_minimum_m),
        ("radius_maximum_m", radius_maximum_m),
        ("scale_radius_m", scale_radius_m),
    ):
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    if radius_maximum_m <= radius_minimum_m:
        raise ValueError("radius_maximum_m must exceed radius_minimum_m")
    if minimum_multiplicity < 1:
        raise ValueError("minimum_multiplicity must be positive")


def largest_remainder_multiplicities(
    probabilities: np.ndarray,
    target_total: int,
    minimum_multiplicity: int,
) -> np.ndarray:
    """Allocate an exact integer total with deterministic largest remainders.

    Float probabilities are first mapped to high-resolution integer weights.
    All subsequent quota, floor and remainder operations use Python integers.
    This avoids losing hundreds of physical droplets when a roughly 1e19 total
    is multiplied and summed in float64.
    """
    probabilities = np.asarray(probabilities, dtype=float)
    if probabilities.ndim != 1 or probabilities.size == 0:
        raise ValueError("probabilities must be a non-empty one-dimensional array")
    if np.any(~np.isfinite(probabilities)) or np.any(probabilities < 0):
        raise ValueError("probabilities must be finite and non-negative")
    if target_total < 1:
        raise ValueError("target_total must be positive")
    if target_total > np.iinfo(np.uint64).max:
        raise OverflowError("target physical-droplet total exceeds uint64")

    probability_scale = 10**30
    weights = [round(float(probability) * probability_scale) for probability in probabilities]
    total_weight = sum(weights)
    if total_weight <= 0:
        raise ValueError("probabilities have zero total weight")
    floors = [target_total * weight // total_weight for weight in weights]
    remainders = [target_total * weight % total_weight for weight in weights]
    residual = target_total - sum(floors)
    if residual < 0 or residual > probabilities.size:
        raise RuntimeError("largest-remainder residual is outside its mathematical bounds")

    order = sorted(range(probabilities.size), key=lambda index: (-remainders[index], index))
    multiplicities = np.asarray(floors, dtype=np.uint64)
    if residual:
        multiplicities[np.asarray(order[:residual], dtype=int)] += np.uint64(1)

    if sum(int(value) for value in multiplicities) != target_total:
        raise RuntimeError("integer multiplicity allocation did not preserve the target total")
    if np.any(multiplicities < minimum_multiplicity):
        raise ValueError(
            "controlled initialization would violate the minimum multiplicity; "
            "reduce N_SD, enlarge the collision volume, change the support, or review xi_min"
        )
    return multiplicities


def _conditioned_volume_integrals(
    volume_edges_m3: np.ndarray,
    scale_volume_m3: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return bin integrals of probability, volume and squared volume."""
    # Float64 is an explicit part of the reproducibility contract. NumPy's
    # longdouble differs between platforms and could otherwise change hashes.
    lower = np.asarray(volume_edges_m3[:-1], dtype=np.float64)
    upper = np.asarray(volume_edges_m3[1:], dtype=np.float64)
    scale_volume_m3 = np.float64(scale_volume_m3)
    lower_survival = np.exp(-lower / scale_volume_m3)
    upper_survival = np.exp(-upper / scale_volume_m3)
    normalization = lower_survival[0] - upper_survival[-1]
    if not np.isfinite(normalization) or normalization <= 0:
        raise ValueError("truncated exponential normalization is not positive")

    bin_width = upper - lower
    dimensionless_width = bin_width / scale_volume_m3
    probabilities = lower_survival * -np.expm1(-dimensionless_width) / normalization
    probabilities /= np.sum(probabilities, dtype=np.float64)

    small = dimensionless_width < np.float64(0.05)
    first_unit_interval_moment = np.empty_like(dimensionless_width)
    second_unit_interval_moment = np.empty_like(dimensionless_width)
    x = dimensionless_width[small]
    first_unit_interval_moment[small] = (
        0.5 - x / 12.0 + x**3 / 720.0 - x**5 / 30240.0 + x**7 / 1209600.0
    )
    second_unit_interval_moment[small] = (
        1.0 / 3.0
        - x / 12.0
        + x**2 / 360.0
        + x**3 / 720.0
        - x**4 / 15120.0
        - x**5 / 30240.0
        + x**6 / 604800.0
        + x**7 / 1209600.0
    )
    x = dimensionless_width[~small]
    expm1_x = np.expm1(x)
    first_unit_interval_moment[~small] = 1.0 / x - 1.0 / expm1_x
    second_unit_interval_moment[~small] = (2.0 * expm1_x - 2.0 * x - x**2) / (x**2 * expm1_x)

    conditional_first = lower + bin_width * first_unit_interval_moment
    conditional_second = (
        lower**2
        + 2.0 * lower * bin_width * first_unit_interval_moment
        + bin_width**2 * second_unit_interval_moment
    )
    first_integrals = probabilities * conditional_first
    second_integrals = probabilities * conditional_second
    return probabilities, first_integrals, second_integrals


def _radius_moment(
    order: int,
    radii_m: np.ndarray,
    multiplicities: np.ndarray,
    sample_volume_m3: float,
) -> float:
    if order == 0:
        return sum(int(value) for value in multiplicities) / sample_volume_m3
    radii_um = np.asarray(radii_m, dtype=float) * 1.0e6
    return float(
        np.sum(np.asarray(multiplicities, dtype=np.float64) * radii_um**order) / sample_volume_m3
    )


def build_controlled_population(
    *,
    number_of_superdroplets: int,
    sample_volume_m3: float,
    number_concentration_m3: float,
    radius_minimum_m: float,
    radius_maximum_m: float,
    scale_radius_m: float,
    minimum_multiplicity: int,
    maximum_relative_moment0_error: float,
    maximum_relative_moment3_error: float,
    maximum_relative_moment6_error: float,
) -> ControlledPopulation:
    """Construct and audit one deterministic controlled population."""
    _validate_inputs(
        number_of_superdroplets=number_of_superdroplets,
        sample_volume_m3=sample_volume_m3,
        number_concentration_m3=number_concentration_m3,
        radius_minimum_m=radius_minimum_m,
        radius_maximum_m=radius_maximum_m,
        scale_radius_m=scale_radius_m,
        minimum_multiplicity=minimum_multiplicity,
    )
    for name, value in (
        ("maximum_relative_moment0_error", maximum_relative_moment0_error),
        ("maximum_relative_moment3_error", maximum_relative_moment3_error),
        ("maximum_relative_moment6_error", maximum_relative_moment6_error),
    ):
        if not np.isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and non-negative")

    volume_minimum_m3 = float(sphere_volume(radius_minimum_m))
    volume_maximum_m3 = float(sphere_volume(radius_maximum_m))
    scale_volume_m3 = float(sphere_volume(scale_radius_m))
    volume_edges_m3 = np.geomspace(
        volume_minimum_m3,
        volume_maximum_m3,
        number_of_superdroplets + 1,
    )
    probabilities, first_integrals, second_integrals = _conditioned_volume_integrals(
        volume_edges_m3,
        scale_volume_m3,
    )

    target_total = round(number_concentration_m3 * sample_volume_m3)
    expected_multiplicities = probabilities * np.float64(target_total)
    multiplicities = largest_remainder_multiplicities(
        probabilities,
        target_total,
        minimum_multiplicity,
    )

    target_bin_liquid_volumes_m3 = first_integrals * target_total
    representative_volumes_m3 = target_bin_liquid_volumes_m3 / multiplicities.astype(float)
    lower = volume_edges_m3[:-1]
    upper = volume_edges_m3[1:]
    tolerance = 64.0 * np.finfo(float).eps
    inside = (representative_volumes_m3 >= lower * (1.0 - tolerance)) & (
        representative_volumes_m3 <= upper * (1.0 + tolerance)
    )
    if not np.all(inside):
        failing = np.flatnonzero(~inside)
        raise ValueError(
            "integerization moved representative volume outside its source bin; "
            f"first failing bin={int(failing[0])}"
        )

    radii_m = radius_from_volume(representative_volumes_m3)
    represented_number_concentration_m3 = target_total / sample_volume_m3
    volume_to_radius_cubed = 3.0 / (4.0 * np.pi)
    target_moments = {
        0: represented_number_concentration_m3,
        3: float(
            target_total
            * volume_to_radius_cubed
            * np.sum(first_integrals)
            * 1.0e18
            / sample_volume_m3
        ),
        6: float(
            target_total
            * volume_to_radius_cubed**2
            * np.sum(second_integrals)
            * 1.0e36
            / sample_volume_m3
        ),
    }
    represented_moments = {
        order: _radius_moment(order, radii_m, multiplicities, sample_volume_m3)
        for order in (0, 3, 6)
    }
    relative_moment_errors = {
        order: (represented_moments[order] - target_moments[order]) / target_moments[order]
        for order in (0, 3, 6)
    }
    configured_moment0_error = (
        represented_moments[0] - number_concentration_m3
    ) / number_concentration_m3
    if abs(configured_moment0_error) > maximum_relative_moment0_error:
        raise ValueError(
            "controlled initialization failed configured M0 tolerance: "
            f"{configured_moment0_error:.17g}"
        )
    for order, maximum in (
        (3, maximum_relative_moment3_error),
        (6, maximum_relative_moment6_error),
    ):
        if abs(relative_moment_errors[order]) > maximum:
            raise ValueError(
                f"controlled initialization failed M{order} tolerance: "
                f"{relative_moment_errors[order]:.17g}"
            )

    return ControlledPopulation(
        volume_edges_m3=volume_edges_m3,
        expected_multiplicities=expected_multiplicities,
        multiplicities=multiplicities,
        radii_m=radii_m,
        target_bin_liquid_volumes_m3=target_bin_liquid_volumes_m3,
        target_real_droplets=target_total,
        configured_number_concentration_m3=number_concentration_m3,
        represented_number_concentration_m3=represented_number_concentration_m3,
        sample_volume_m3=sample_volume_m3,
        scale_radius_m=scale_radius_m,
        radius_minimum_m=radius_minimum_m,
        radius_maximum_m=radius_maximum_m,
        minimum_multiplicity=minimum_multiplicity,
        target_moments=target_moments,
        represented_moments=represented_moments,
        relative_moment_errors=relative_moment_errors,
    )


def population_sha256(population: ControlledPopulation) -> str:
    """Hash the scientific population arrays independent of CLEO metadata."""
    digest = hashlib.sha256()
    digest.update(np.asarray(population.multiplicities, dtype="<u8").tobytes())
    digest.update(np.asarray(population.radii_m, dtype="<f8").tobytes())
    return digest.hexdigest()


def sha256_file(filename: Path) -> str:
    """Return one file's SHA-256 checksum."""
    digest = hashlib.sha256()
    with filename.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def controlled_audit(
    population: ControlledPopulation,
    *,
    liquid_water_density_kgm3: float,
    source_config: Path | None = None,
    controlled_config: Path | None = None,
    grid_file: Path | None = None,
    superdroplet_file: Path | None = None,
    initializer_source: Path | None = None,
) -> dict[str, Any]:
    """Return the serializable audit record for one population."""
    if not np.isfinite(liquid_water_density_kgm3) or liquid_water_density_kgm3 <= 0:
        raise ValueError("liquid_water_density_kgm3 must be finite and positive")

    liquid_water_content_gm3 = (
        np.sum(population.target_bin_liquid_volumes_m3)
        * liquid_water_density_kgm3
        * 1000.0
        / population.sample_volume_m3
    )
    record: dict[str, Any] = {
        "schema": "controlled_initialization_audit_v1",
        "status": "passed",
        "method": "deterministic_log_volume_bin_quadrature",
        "distribution": {
            "family": "volume_exponential_conditioned_on_finite_support",
            "radius_support_um": [
                population.radius_minimum_m * 1.0e6,
                population.radius_maximum_m * 1.0e6,
            ],
            "scale_radius_um": population.scale_radius_m * 1.0e6,
            "number_concentration_m3": population.configured_number_concentration_m3,
            "sample_volume_m3": population.sample_volume_m3,
        },
        "population": {
            "number_of_superdroplets": int(population.radii_m.size),
            "target_real_droplets": population.target_real_droplets,
            "represented_real_droplets": sum(int(value) for value in population.multiplicities),
            "minimum_multiplicity": int(np.min(population.multiplicities)),
            "maximum_multiplicity": int(np.max(population.multiplicities)),
            "minimum_radius_um": float(np.min(population.radii_m) * 1.0e6),
            "maximum_radius_um": float(np.max(population.radii_m) * 1.0e6),
            "population_sha256": population_sha256(population),
        },
        "moments": {f"M{order}_target": population.target_moments[order] for order in (0, 3, 6)}
        | {f"M{order}_represented": population.represented_moments[order] for order in (0, 3, 6)}
        | {
            f"M{order}_relative_error": population.relative_moment_errors[order]
            for order in (0, 3, 6)
        },
        "liquid_water_content_gm3": float(liquid_water_content_gm3),
        "constraints": {
            "moment0_and_moment3_controlled": True,
            "moment6_forced": False,
            "representatives_inside_source_bins": True,
        },
        "artifacts": {},
    }
    for label, filename in (
        ("source_config", source_config),
        ("controlled_config", controlled_config),
        ("grid_file", grid_file),
        ("superdroplet_file", superdroplet_file),
        ("initializer_source", initializer_source),
    ):
        if filename is not None:
            filename = filename.resolve()
            record["artifacts"][label] = {
                "path": str(filename),
                "sha256": sha256_file(filename),
            }
    return record


def write_controlled_audit(filename: Path, record: dict[str, Any]) -> None:
    """Write one new audit record without replacing an existing record."""
    if filename.exists():
        raise FileExistsError(f"refusing to overwrite controlled audit: {filename}")
    filename.parent.mkdir(parents=True, exist_ok=True)
    filename.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class ControlledAttrsGenerator:
    """Adapter exposing a controlled population to CLEO's binary writer."""

    def __init__(
        self,
        population: ControlledPopulation,
        *,
        dry_radius_m: float,
        coord3gen: Any,
        coord1gen: Any,
        coord2gen: Any,
    ) -> None:
        if not np.isfinite(dry_radius_m) or dry_radius_m <= 0:
            raise ValueError("dry_radius_m must be finite and positive")
        self.population = population
        self.dry_radius_m = dry_radius_m
        self.coord3gen = coord3gen
        self.coord1gen = coord1gen
        self.coord2gen = coord2gen

    def generate_attributes(
        self,
        nsupers: int,
        rho_sol_kgm3: float,
        gbxindex: int,
        gridboxbounds: np.ndarray,
        number_concentration_m3: float,
        numconc_tolerance: float = 0.0,
        isprint: bool = False,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return native CLEO dimensional multiplicity, radius and solute mass."""
        del numconc_tolerance
        if nsupers != self.population.radii_m.size:
            raise ValueError("CLEO requested a different N_SD than the controlled population")
        if gbxindex != 0:
            raise ValueError("controlled collisions0d initialization supports one gridbox")
        if not np.isclose(
            number_concentration_m3,
            self.population.configured_number_concentration_m3,
            rtol=1.0e-14,
            atol=0.0,
        ):
            raise ValueError("runtime number concentration differs from the controlled target")
        bounds = np.asarray(gridboxbounds, dtype=float)
        sample_volume_m3 = float(np.prod(bounds[1::2] - bounds[0::2]))
        if not np.isclose(
            sample_volume_m3,
            self.population.sample_volume_m3,
            rtol=1.0e-14,
            atol=0.0,
        ):
            raise ValueError("runtime gridbox volume differs from the controlled target")
        if not np.isfinite(rho_sol_kgm3) or rho_sol_kgm3 <= 0:
            raise ValueError("solute density must be finite and positive")

        dry_radii_m = np.minimum(self.dry_radius_m, self.population.radii_m)
        solute_masses_kg = (4.0 / 3.0) * np.pi * dry_radii_m**3 * rho_sol_kgm3
        if isprint:
            print(
                "controlled initialization: "
                f"N_SD={nsupers}, "
                f"N_real={sum(int(value) for value in self.population.multiplicities)}"
            )
        return (
            np.asarray(self.population.multiplicities, dtype=np.uint),
            np.asarray(self.population.radii_m, dtype=np.double),
            np.asarray(solute_masses_kg, dtype=np.double),
        )

    def generate_coords(
        self,
        nsupers: int,
        nspacedims: int,
        gridboxbounds: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Generate deterministic coordinates through CLEO's coordinate generators."""
        generators = (self.coord3gen, self.coord1gen, self.coord2gen)
        if nspacedims != sum(generator is not None for generator in generators):
            raise ValueError("coordinate generators do not match nspacedims")
        bounds = np.asarray(gridboxbounds, dtype=float)
        coordinates = []
        for dimension, generator in enumerate(generators):
            if generator is None:
                coordinates.append(np.array([], dtype=np.double))
            else:
                coordinate_range = bounds[2 * dimension : 2 * dimension + 2]
                coordinates.append(
                    np.asarray(generator(nsupers, coordinate_range), dtype=np.double)
                )
        return coordinates[0], coordinates[1], coordinates[2]
