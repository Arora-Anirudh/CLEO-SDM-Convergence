/*
 * Project-owned adapter around CLEO collision-coalescence.
 *
 * Copyright (c) 2026 Anirudh Arora
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

#ifndef CLEO_SDM_CONVERGENCE_COLLISIONS0D_SEEDED_COLLISIONS_HPP_
#define CLEO_SDM_CONVERGENCE_COLLISIONS0D_SEEDED_COLLISIONS_HPP_

#include <cstdint>
#include <functional>

#include "superdrops/collisions/coalescence.hpp"
#include "superdrops/microphysicalprocess.hpp"

/**
 * Construct CLEO collision-coalescence with an explicit Kokkos RNG-pool seed.
 *
 * This adapter deliberately reuses CLEO's probability, coalescence and
 * timestep implementations. The build-local patch only adds the four-argument
 * DoCollisions constructor used here; no collision equations or draw locations
 * are changed.
 */
template <PairProbability Probability>
inline MicrophysicalProcess auto SeededCollCoal(
    const unsigned int interval,
    const std::function<double(unsigned int)> int2realtime,
    const Probability collision_probability, const std::uint64_t seed) {
  const auto delta_t = int2realtime(interval);
  const DoCoalescence coalescence{};
  const MicrophysicsFunc auto collisions =
      DoCollisions<Probability, DoCoalescence>(
          delta_t, collision_probability, coalescence, seed);

  return ConstTstepMicrophysics(interval, collisions);
}

#endif  // CLEO_SDM_CONVERGENCE_COLLISIONS0D_SEEDED_COLLISIONS_HPP_
