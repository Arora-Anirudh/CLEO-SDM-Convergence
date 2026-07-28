# CLEO-SDM-Convergence

[![quality](https://github.com/Arora-Anirudh/CLEO-SDM-Convergence/actions/workflows/quality.yml/badge.svg)](https://github.com/Arora-Anirudh/CLEO-SDM-Convergence/actions/workflows/quality.yml)
[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](LICENSE.md)

Reproducible experiments with
[CLEO](https://github.com/yoctoyotta1024/CLEO) for convergence and stochastic
variability in the Superdroplet Method (SDM).

The project begins with collision-coalescence in a zero-dimensional box and is
intended to grow with the scientific programme toward controlled one- and
two-dimensional configurations. It keeps experiment-owned code, configuration,
analysis and provenance independent of the upstream CLEO repository.

## Current scope

The first application is `collisions0d`:

- one collision volume with null dynamics, motion and boundary conditions;
- collision-coalescence as the only active microphysics;
- a Golovin executable for the analytical/numerical validation gate;
- a Long hydrodynamic-kernel executable for the primary experiment;
- scientific Zarr output containing time, radius, multiplicity, solute mass and
  superdroplet ID;
- separate, explicit initialization and collision seeds for controlled
  stochastic provenance;
- a reproducible Python initializer based on Clara Bayley's
  [`PerformanceTestingCLEO/src/collisions0d`](https://github.com/yoctoyotta1024/PerformanceTestingCLEO/tree/main/src/collisions0d).

The repository does **not** yet contain a convergence result or a recommended
number of superdroplets. Initial settings are an attributed reference starting
point and will only be changed through documented experiments.

## CLEO dependency

CLEO is fetched during CMake configuration and is not vendored here.

| Dependency | Pin |
| --- | --- |
| Repository | `https://github.com/yoctoyotta1024/CLEO.git` |
| Commit | `83318c23223546d10759d202d70f4fa2f7fe4688` |
| Verified | 2026-07-28 |

The pin was the head of CLEO `main` when this repository was scaffolded and was
11 commits beyond release v0.65.1. See
[ADR 0001](docs/decisions/0001-external-cleo.md). Upgrades are intentional,
reviewed changes so that old experiments remain reproducible.

## Repository layout

```text
config/                 version-controlled experiment configurations
docs/decisions/         architecture and scientific decision records
scripts/                initialization, execution and analysis tools
src/collisions0d/       project-owned CLEO collision-box applications
src/extern/cleo/        pinned external CLEO dependency
tests/                  inexpensive repository and configuration checks
```

Generated binaries, build trees and Zarr output are excluded from Git. Levante
raw output belongs on scratch storage; compact manifests, checksums, tables and
figures belong in the permanent research record.

## Python environment

CLEO and this repository currently require Python 3.13 or newer.

```bash
uv sync --group dev
```

The initializer imports `cleopy` from the CLEO source fetched into the build
tree. It therefore runs after CMake has downloaded CLEO.

## Configure and build

The exact Levante compiler, MPI, YAC/YAXT and library setup will be documented
in a dedicated runbook before production runs. The CMake structure is:

```bash
cmake -S . -B build \
  -DCMAKE_C_COMPILER=mpicc \
  -DCMAKE_CXX_COMPILER=mpic++ \
  -DKokkos_ENABLE_SERIAL=ON \
  -DKokkos_ENABLE_OPENMP=ON

cmake --build build --target collisions0d_golovin collisions0d_long
```

These commands assume the required CLEO dependencies are already discoverable
by CMake. Do not treat them as a complete Levante module recipe.

## Generate the reference inputs

After CMake configuration:

```bash
uv run python scripts/prepare_collisions0d_inputs.py \
  --cleo-source build/_deps/cleo-src \
  --config config/collisions0d_reference.yaml \
  --seed 12345
```

The reference initializer follows `PerformanceTestingCLEO/collisions0d`:

- radii sampled once per logarithmic-radius bin;
- an exponential distribution in droplet volume;
- a minimum multiplicity;
- negligible dry radius;
- configured total real-droplet concentration.

The exact values are visible in
[`config/collisions0d_reference.yaml`](config/collisions0d_reference.yaml).

## Quality checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Compiled CLEO validation and Levante smoke tests will be added after the
repository is installed on Levante.

## Levante workflow

Project-owned Levante scripts are documented in
[`scripts/levante/README.md`](scripts/levante/README.md). They retain the
verified compiler/MPI/YAC recipe from CLEO while removing user-specific
accounts, paths and GPU assumptions. The first staged workflow is:

1. configure and build the pinned CLEO dependency and both collision-box
   executables;
2. generate one seeded reference initialization;
3. run one single-thread Golovin validation into a fresh SCRATCH directory;
4. validate explicit one-thread collision-stream replay;
5. run one seeded Long functionality and conservation gate;
6. define the controlled ensemble matrix before any convergence experiment.

The audited first run, including its code path, prescribed conditions and
physical interpretation, is documented in
[`docs/runs/first-golovin-collisions0d.md`](docs/runs/first-golovin-collisions0d.md).
The project diagnostic deliberately reuses CLEO's pinned `cleopy` and
`plotcleo` readers/distribution tools; its additional bulk and conservation
metrics are documented in
[`docs/analysis/collisions0d-diagnostics.md`](docs/analysis/collisions0d-diagnostics.md).
The checksum-verified compact products from the first audited run are under
[`results/first_golovin_serial`](results/first_golovin_serial).

The first run predated explicit collision-stream control. New runs require both
an initialization seed and collision seed. The design, deliberately minimal
build-local CLEO patch, and one-thread replay gate are documented in
[`ADR 0002`](docs/decisions/0002-explicit-collision-seed.md). The successful
Golovin replay audit is under
[`results/golovin_seed_replay_v1`](results/golovin_seed_replay_v1). A detailed record
of repository creation, the first model/diagnostic run and the seed-control work
is maintained in the
[`2026-07-28 work log`](docs/worklogs/2026-07-28.md).

The first seeded Long run is documented in
[`docs/runs/first-long-collisions0d.md`](docs/runs/first-long-collisions0d.md),
with checksum-verified compact products under
[`results/first_long_seeded`](results/first_long_seeded). It validates the Long
application and conservation in the tested one-thread mode; it is not a
convergence result or the final scientific configuration.

## Attribution

The CMake composition and initial `collisions0d` design follow
[PerformanceTestingCLEO](https://github.com/yoctoyotta1024/PerformanceTestingCLEO)
by Clara Bayley. The application implementation is ported to the CLEO commit
recorded above. Adapted source files retain the upstream BSD-3-Clause copyright
notices.

If using this software, cite this repository through
[`CITATION.cff`](CITATION.cff) and cite the relevant CLEO model-description and
scientific-method papers.
