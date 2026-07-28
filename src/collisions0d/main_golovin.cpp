/*
 * Derived from CLEO examples/boxmodelcollisions/src/main_golcolls.cpp at
 * commit 83318c23223546d10759d202d70f4fa2f7fe4688.
 *
 * Copyright (c) 2024 MPI-M, Clara Bayley
 * Modifications copyright (c) 2026 Anirudh Arora
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

#include "main_impl.hpp"
#include "superdrops/collisions/coalescence.hpp"
#include "superdrops/collisions/golovinprob.hpp"

struct CreateGolovinCollisions {
  MicrophysicalProcess auto operator()(const Config &config,
                                       const Timesteps &tsteps) const {
    const PairProbability auto probability = GolovinProb();
    return CollCoal(tsteps.get_collstep(), &step2realtime, probability);
  }
};

int main(int argc, char *argv[]) {
  return run_collisions0d(argc, argv, CreateGolovinCollisions{});
}
