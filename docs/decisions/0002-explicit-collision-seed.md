# ADR 0002: Explicit collision random-number seed

- Status: accepted; one-thread runtime replay validation pending
- Date: 2026-07-28

## Context

The reference initializer already accepts an explicit NumPy seed. Reusing that
seed regenerates the same initial superdroplet binary. CLEO commit
`83318c23223546d10759d202d70f4fa2f7fe4688`, however, constructs the Kokkos
collision random-number pool from `std::random_device`. A completed run therefore
does not record enough information to deliberately reproduce its collision
stream.

This distinction matters because two stochastic sources are present:

1. **initialization sampling** selects the time-zero radii, multiplicities and
   positions;
2. **collision sampling** shuffles superdroplets into candidate pairs and draws
   whether/how many represented collisions occur.

Unknown collision seeds do not make independent ensemble statistics invalid.
They do prevent exact replay, controlled source-separation experiments, and
reliable reruns of an unusual member.

## Decision

Every new project run must provide both:

- `INITIALIZATION_SEED`, a Python/NumPy integer in `[0, 2**32)`;
- `COLLISION_SEED`, a C++ unsigned 64-bit integer in `[0, 2**64 - 1]`.

The repository stores a one-file patch against the exact pinned CLEO commit:

```text
patches/cleo/0001-add-explicit-collision-rng-seed.patch
```

The patch adds a four-argument `DoCollisions` constructor that initializes the
existing Kokkos RNG pool from the supplied seed. It does not change:

- the Golovin or Long kernel;
- collision probabilities;
- the random shuffle;
- the location or number of random draws;
- the Shima-style collision/coalescence enactment;
- CLEO's original random-device constructor.

CMake applies the patch only to its fetched, build-local CLEO source at the
locked commit. Nothing is pushed to or edited in the online upstream CLEO
repository. The project-owned `SeededCollCoal` adapter then selects the new
constructor, and both `collisions0d_golovin` and `collisions0d_long` require the
seed as their second command-line argument.

## Validation gate

The first runtime gate is deliberately one-thread:

```text
same initialization + same collision seed -> byte-identical Zarr output
same initialization + different collision seed -> different Zarr output
```

The dedicated Slurm wrapper runs three sequential simulations and checks that
condition. One-thread replay is the scientific requirement for controlled
ensembles in the initial convergence workflow.

Multi-thread byte replay is not assumed. Parallel execution may acquire Kokkos
RNG-pool states in a schedule-dependent order even with the same pool seed. If
multi-thread production is later needed, reproducibility must be evaluated
separately and described as statistical reproducibility unless exact replay is
demonstrated.

## Consequences

Positive:

- every new member has complete stochastic provenance;
- unusual members can be rerun exactly in the validated execution mode;
- frozen-initialization/crossed-seed experiments become possible;
- Golovin and Long share one collision-seed mechanism.

Costs and risks:

- the build-local CLEO checkout is intentionally dirty by one verified header;
- a CLEO upgrade must re-review or replace the patch;
- the seed controls the random stream, not the physical correctness or
  convergence of a simulation;
- identical numeric seeds across different `N_SD` do not create paired
  collision histories because the sampling paths diverge.
