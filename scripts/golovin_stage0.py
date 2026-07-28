"""Pure numerical utilities for the Golovin Stage-0 convergence diagnostics.

This module deliberately has no dependency on CLEO's output classes.  The
single-run analyzer converts CLEO output to NumPy arrays and calls these
functions.  Keeping the formulas here makes them inexpensive to unit test.

The analytical mass-density expression follows the implementation in the
repository's pinned CLEO ``plotcleo.shima2009fig.golovin_analytical`` utility.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import iv

GOLOVIN_KERNEL_B_M3_S = 1500.0


@dataclass(frozen=True)
class FixedBinDistribution:
    """Mass-density histogram and its registered logarithmic-radius grid."""

    mass_density_gm3_per_ln_radius: np.ndarray
    edges_um: np.ndarray
    centres_um: np.ndarray
    mass_below_range_fraction: float
    mass_above_range_fraction: float


@dataclass(frozen=True)
class ThresholdCrossing:
    """Interval-censored first crossing of a sampled time series."""

    status: str
    lower_bound_s: float
    upper_bound_s: float
    first_recorded_crossing_s: float


def logarithmic_radius_edges(
    minimum_radius_um: float,
    maximum_radius_um: float,
    number_of_bins: int,
) -> np.ndarray:
    """Return one immutable-in-practice log-radius grid for every experiment."""
    if not np.isfinite(minimum_radius_um) or minimum_radius_um <= 0:
        raise ValueError("minimum radius must be finite and positive")
    if not np.isfinite(maximum_radius_um) or maximum_radius_um <= minimum_radius_um:
        raise ValueError("maximum radius must be finite and greater than the minimum")
    if number_of_bins < 1:
        raise ValueError("number_of_bins must be at least one")
    return np.geomspace(minimum_radius_um, maximum_radius_um, number_of_bins + 1)


def water_equivalent_droplet_mass_g(
    radius_um: np.ndarray,
    liquid_water_density_kgm3: float,
) -> np.ndarray:
    """Return mass in grams of water spheres with the supplied wet radii."""
    radius_um = np.asarray(radius_um, dtype=float)
    if np.any(~np.isfinite(radius_um)) or np.any(radius_um <= 0):
        raise ValueError("all radii must be finite and positive")
    if not np.isfinite(liquid_water_density_kgm3) or liquid_water_density_kgm3 <= 0:
        raise ValueError("liquid-water density must be finite and positive")
    radius_m = radius_um * 1.0e-6
    volume_m3 = (4.0 / 3.0) * np.pi * radius_m**3
    return volume_m3 * liquid_water_density_kgm3 * 1000.0


def fixed_bin_mass_density(
    *,
    radius_um: np.ndarray,
    multiplicity: np.ndarray,
    droplet_mass_g: np.ndarray,
    domain_volume_m3: float,
    edges_um: np.ndarray,
) -> FixedBinDistribution:
    """Bin represented liquid mass without smoothing.

    The histogram value in bin ``b`` is

    ``sum(xi_i * mass_i) / (domain_volume * delta_ln_radius)``.

    Values exactly on the final edge are included by ``numpy.histogram``.
    Separate mass fractions below and above the registered range make silent
    truncation visible.
    """
    radius_um = np.asarray(radius_um, dtype=float)
    multiplicity = np.asarray(multiplicity, dtype=float)
    droplet_mass_g = np.asarray(droplet_mass_g, dtype=float)
    edges_um = np.asarray(edges_um, dtype=float)

    if radius_um.shape != multiplicity.shape or radius_um.shape != droplet_mass_g.shape:
        raise ValueError("radius, multiplicity and droplet mass must have identical shapes")
    if radius_um.ndim != 1:
        raise ValueError("superdroplet arrays must be one-dimensional")
    if radius_um.size == 0:
        raise ValueError("at least one superdroplet is required")
    if np.any(~np.isfinite(radius_um)) or np.any(radius_um <= 0):
        raise ValueError("all radii must be finite and positive")
    if np.any(~np.isfinite(multiplicity)) or np.any(multiplicity < 0):
        raise ValueError("all multiplicities must be finite and non-negative")
    if np.any(~np.isfinite(droplet_mass_g)) or np.any(droplet_mass_g < 0):
        raise ValueError("all droplet masses must be finite and non-negative")
    if not np.isfinite(domain_volume_m3) or domain_volume_m3 <= 0:
        raise ValueError("domain volume must be finite and positive")
    if edges_um.ndim != 1 or edges_um.size < 2:
        raise ValueError("edges must be a one-dimensional array with at least two values")
    if np.any(~np.isfinite(edges_um)) or np.any(edges_um <= 0):
        raise ValueError("all bin edges must be finite and positive")
    if np.any(np.diff(edges_um) <= 0):
        raise ValueError("bin edges must increase strictly")

    represented_mass_g = multiplicity * droplet_mass_g
    total_mass_g = float(np.sum(represented_mass_g))
    log_edges = np.log(edges_um)
    mass_per_bin_g, _ = np.histogram(
        np.log(radius_um),
        bins=log_edges,
        weights=represented_mass_g,
    )
    mass_density = mass_per_bin_g / domain_volume_m3 / np.diff(log_edges)

    if total_mass_g > 0:
        below = float(np.sum(represented_mass_g[radius_um < edges_um[0]]) / total_mass_g)
        above = float(np.sum(represented_mass_g[radius_um > edges_um[-1]]) / total_mass_g)
    else:
        below = float("nan")
        above = float("nan")

    return FixedBinDistribution(
        mass_density_gm3_per_ln_radius=np.asarray(mass_density, dtype=float),
        edges_um=edges_um.copy(),
        centres_um=np.sqrt(edges_um[:-1] * edges_um[1:]),
        mass_below_range_fraction=below,
        mass_above_range_fraction=above,
    )


def fixed_bin_relative_l1(
    numerical_gm3_per_ln_radius: np.ndarray,
    analytical_gm3_per_ln_radius: np.ndarray,
    edges_um: np.ndarray,
) -> float:
    """Calculate the relative L1 error using exactly the registered bins."""
    numerical = np.asarray(numerical_gm3_per_ln_radius, dtype=float)
    analytical = np.asarray(analytical_gm3_per_ln_radius, dtype=float)
    edges_um = np.asarray(edges_um, dtype=float)
    if numerical.shape != analytical.shape:
        raise ValueError("numerical and analytical distributions must have identical shapes")
    if numerical.ndim != 1 or edges_um.shape != (numerical.size + 1,):
        raise ValueError("the edge count must be one greater than the distribution length")
    if np.any(~np.isfinite(numerical)) or np.any(~np.isfinite(analytical)):
        raise ValueError("distribution values must be finite")
    if np.any(np.diff(edges_um) <= 0) or np.any(edges_um <= 0):
        raise ValueError("radius edges must be strictly increasing and positive")

    delta_ln_radius = np.diff(np.log(edges_um))
    denominator = float(np.sum(np.abs(analytical) * delta_ln_radius))
    if denominator <= 0:
        return float("nan")
    numerator = float(np.sum(np.abs(numerical - analytical) * delta_ln_radius))
    return numerator / denominator


def golovin_analytical_mass_density(
    *,
    edges_um: np.ndarray,
    time_s: float,
    initial_number_concentration_m3: float,
    volume_exponential_scale_radius_m: float,
    liquid_water_density_kgm3: float,
    kernel_b_m3_s: float = GOLOVIN_KERNEL_B_M3_S,
) -> np.ndarray:
    """Evaluate CLEO's Golovin analytical mass density at fixed-bin centres."""
    edges_um = np.asarray(edges_um, dtype=float)
    if np.any(edges_um <= 0) or np.any(np.diff(edges_um) <= 0):
        raise ValueError("radius edges must be strictly increasing and positive")
    if time_s < 0 or not np.isfinite(time_s):
        raise ValueError("time must be finite and non-negative")
    if initial_number_concentration_m3 <= 0:
        raise ValueError("initial number concentration must be positive")
    if volume_exponential_scale_radius_m <= 0:
        raise ValueError("volume-exponential scale radius must be positive")
    if liquid_water_density_kgm3 <= 0:
        raise ValueError("liquid-water density must be positive")
    if kernel_b_m3_s <= 0:
        raise ValueError("Golovin kernel coefficient must be positive")

    radius_m = np.sqrt(edges_um[:-1] * edges_um[1:]) * 1.0e-6
    scale_volume_m3 = (4.0 / 3.0) * np.pi * volume_exponential_scale_radius_m**3
    dimensionless_volume = (4.0 / 3.0) * np.pi * radius_m**3 / scale_volume_m3

    # The upstream plotting utility replaces t=0 by a tiny positive value to
    # evaluate the limiting expression without dividing by zero.
    evaluation_time_s = max(float(time_s), 1.0e-10)
    tau = 1.0 - np.exp(
        -kernel_b_m3_s * initial_number_concentration_m3 * scale_volume_m3 * evaluation_time_s
    )
    with np.errstate(over="ignore", under="ignore", invalid="ignore", divide="ignore"):
        bessel_exponential = iv(1, 2.0 * dimensionless_volume * np.sqrt(tau)) * np.exp(
            -(1.0 + tau) * dimensionless_volume
        )
        asymptotic = (
            1.0
            / (2.0 * np.sqrt(np.pi * dimensionless_volume))
            * np.exp(dimensionless_volume * (2.0 * np.sqrt(tau) - 1.0 - tau))
        )
        bessel_exponential = np.where(
            np.isfinite(bessel_exponential),
            bessel_exponential,
            asymptotic,
        )
        phi = (1.0 - tau) / (dimensionless_volume * np.sqrt(tau)) * bessel_exponential
        number_density_per_volume = initial_number_concentration_m3 / scale_volume_m3 * phi
        droplet_volume_m3 = (4.0 / 3.0) * np.pi * radius_m**3
        volume_derivative_per_ln_radius = 3.0 * droplet_volume_m3
        mass_density_kgm3 = (
            number_density_per_volume
            * liquid_water_density_kgm3
            * droplet_volume_m3
            * volume_derivative_per_ln_radius
        )

    result = np.nan_to_num(
        mass_density_kgm3 * 1000.0,
        nan=0.0,
        posinf=np.finfo(float).max,
        neginf=0.0,
    )
    return np.asarray(result, dtype=float)


def radius_moment(
    *,
    order: int,
    radius_um: np.ndarray,
    multiplicity: np.ndarray,
    domain_volume_m3: float,
) -> float:
    """Calculate ``M_n = sum(xi * r_um**n) / V``."""
    if order < 0:
        raise ValueError("radius-moment order must be non-negative")
    radius_um = np.asarray(radius_um, dtype=float)
    multiplicity = np.asarray(multiplicity, dtype=float)
    if radius_um.shape != multiplicity.shape:
        raise ValueError("radius and multiplicity must have identical shapes")
    if np.any(~np.isfinite(radius_um)) or np.any(radius_um <= 0):
        raise ValueError("all radii must be finite and positive")
    if np.any(~np.isfinite(multiplicity)) or np.any(multiplicity < 0):
        raise ValueError("all multiplicities must be finite and non-negative")
    if domain_volume_m3 <= 0:
        raise ValueError("domain volume must be positive")
    return float(np.sum(multiplicity * radius_um**order) / domain_volume_m3)


def golovin_analytical_radius_moments(
    *,
    time_s: float,
    initial_number_concentration_m3: float,
    volume_exponential_scale_radius_m: float,
    kernel_b_m3_s: float = GOLOVIN_KERNEL_B_M3_S,
) -> dict[int, float]:
    """Return exact untruncated Golovin radius moments M0, M3 and M6.

    Radii are reported in micrometres, so the units are ``m^-3``,
    ``um^3 m^-3`` and ``um^6 m^-3``.  For the exponential-in-volume
    initial distribution:

    * ``M0 = N0 exp(-a t)``
    * ``M3 = N0 r_a^3``
    * ``M6 = 2 N0 r_a^6 exp(2 a t)``

    where ``a = b N0 (4 pi r_a^3 / 3)``.
    """
    if time_s < 0 or not np.isfinite(time_s):
        raise ValueError("time must be finite and non-negative")
    if initial_number_concentration_m3 <= 0:
        raise ValueError("initial number concentration must be positive")
    if volume_exponential_scale_radius_m <= 0:
        raise ValueError("volume-exponential scale radius must be positive")
    if kernel_b_m3_s <= 0:
        raise ValueError("Golovin kernel coefficient must be positive")

    scale_volume_m3 = (4.0 / 3.0) * np.pi * volume_exponential_scale_radius_m**3
    rate_s_inv = kernel_b_m3_s * initial_number_concentration_m3 * scale_volume_m3
    scale_radius_um = volume_exponential_scale_radius_m * 1.0e6
    return {
        0: float(initial_number_concentration_m3 * np.exp(-rate_s_inv * time_s)),
        3: float(initial_number_concentration_m3 * scale_radius_um**3),
        6: float(
            2.0
            * initial_number_concentration_m3
            * scale_radius_um**6
            * np.exp(2.0 * rate_s_inv * time_s)
        ),
    }


def relative_error(numerical: float, analytical: float) -> float:
    """Return signed relative error, or NaN for a zero analytical value."""
    if not np.isfinite(numerical) or not np.isfinite(analytical):
        return float("nan")
    if analytical == 0:
        return float("nan")
    return numerical / analytical - 1.0


def mass_fraction_at_or_above(
    radius_um: np.ndarray,
    represented_mass_g: np.ndarray,
    threshold_um: float,
) -> float:
    """Return represented liquid-mass fraction at or above a wet-radius threshold."""
    radius_um = np.asarray(radius_um, dtype=float)
    represented_mass_g = np.asarray(represented_mass_g, dtype=float)
    if radius_um.shape != represented_mass_g.shape:
        raise ValueError("radius and represented mass must have identical shapes")
    if threshold_um <= 0:
        raise ValueError("threshold radius must be positive")
    total_mass = float(np.sum(represented_mass_g))
    if total_mass <= 0:
        return float("nan")
    return float(np.sum(represented_mass_g[radius_um >= threshold_um]) / total_mass)


def mass_weighted_radius_quantile(
    radius_um: np.ndarray,
    represented_mass_g: np.ndarray,
    quantile: float,
) -> float:
    """Return the smallest radius whose cumulative represented mass reaches q."""
    radius_um = np.asarray(radius_um, dtype=float)
    represented_mass_g = np.asarray(represented_mass_g, dtype=float)
    if radius_um.shape != represented_mass_g.shape:
        raise ValueError("radius and represented mass must have identical shapes")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be in [0, 1]")
    if np.any(represented_mass_g < 0):
        raise ValueError("represented masses must be non-negative")
    total_mass = float(np.sum(represented_mass_g))
    if total_mass <= 0:
        return float("nan")

    order = np.argsort(radius_um, kind="stable")
    sorted_radius = radius_um[order]
    cumulative_mass = np.cumsum(represented_mass_g[order])
    target = quantile * total_mass
    index = int(np.searchsorted(cumulative_mass, target, side="left"))
    return float(sorted_radius[min(index, sorted_radius.size - 1)])


def first_threshold_crossing(
    times_s: np.ndarray,
    values: np.ndarray,
    threshold: float,
) -> ThresholdCrossing:
    """Locate the first sampled threshold crossing without inventing sub-output timing."""
    times_s = np.asarray(times_s, dtype=float)
    values = np.asarray(values, dtype=float)
    if times_s.shape != values.shape or times_s.ndim != 1 or times_s.size == 0:
        raise ValueError("times and values must be non-empty one-dimensional arrays")
    if np.any(~np.isfinite(times_s)) or np.any(np.diff(times_s) <= 0):
        raise ValueError("times must be finite and strictly increasing")
    if not np.isfinite(threshold):
        raise ValueError("threshold must be finite")

    valid_crossings = np.flatnonzero(np.isfinite(values) & (values >= threshold))
    if valid_crossings.size == 0:
        return ThresholdCrossing(
            status="not_crossed",
            lower_bound_s=float(times_s[-1]),
            upper_bound_s=float("nan"),
            first_recorded_crossing_s=float("nan"),
        )

    index = int(valid_crossings[0])
    if index == 0:
        return ThresholdCrossing(
            status="already_crossed_at_first_output",
            lower_bound_s=float("nan"),
            upper_bound_s=float(times_s[0]),
            first_recorded_crossing_s=float(times_s[0]),
        )
    return ThresholdCrossing(
        status="crossed_between_outputs",
        lower_bound_s=float(times_s[index - 1]),
        upper_bound_s=float(times_s[index]),
        first_recorded_crossing_s=float(times_s[index]),
    )
