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

The repository does **not** yet contain a superdroplet-resolution convergence
result or a recommended number of superdroplets. The controlled timestep gate
is complete and selected 0.1 s; the next model submission is the actual
six-resolution, 120-member Golovin convergence experiment.

The pre-registered scientific design for the first permanent-repository
convergence study is the
[`Golovin convergence protocol`](docs/experiments/golovin-convergence-protocol.md).
It separates analytical mean bias, stochastic spread, ensemble precision,
initialization sensitivity, timestep adequacy and cost. Its previously
provisional numerical tolerances are now documented project acceptance
criteria; the preparatory implementation and pilot gates have passed.

The local Stage-0 measurement, provenance and non-destructive matrix tooling is
explained from first principles in the
[`Golovin Stage-0 implementation guide`](docs/implementation/golovin-stage0-guide.md).
Its development configuration is explicitly not production authorization.
The first single-member Levante gate, including the launcher correction,
compute/storage accounting, scientific diagnostics, replay audit and
limitations, is documented in the
[`Golovin Stage-0 development gate`](docs/runs/golovin-stage0-development-gate.md).
The post-gate decision to separate descriptive 40 μm mass from generic
millimetre-tail timing—and not call either surface precipitation—is recorded
in [`ADR 0003`](docs/decisions/0003-tail-growth-not-rain-onset.md).
The literature-informed definitions for the controlled initializer, fixed-bin
range, practical-equivalence margins, formal decision times and descriptive
tail timing are recorded in
[`ADR 0004`](docs/decisions/0004-golovin-production-definitions.md). These
definitions authorize implementation and pilot validation, not a production
convergence claim.
The controlled Golovin initializer now passes local numerical and unit tests.
Its construction, code path, exact integer allocation, moment gates and
completed native-binary/frozen-artifact validation are explained in the
[`controlled-initialization guide`](docs/implementation/controlled-initialization-guide.md).
The replay, bundle-ladder, diagnostic-robustness, compiled-member and
collision-timestep checks required before the actual resolution ensemble are
complete and explained in the
[`Golovin pre-convergence gates guide`](docs/implementation/golovin-preconvergence-gates.md).
The immutable 120-row matrix, exact compute plan, audit steps and formal
resolution decision are documented in the
[`controlled Golovin resolution runbook`](docs/experiments/golovin-resolution-runbook.md).

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

For a deterministic controlled population, use a fresh materialized runtime
configuration and add:

```bash
uv run python scripts/prepare_collisions0d_inputs.py \
  --cleo-source build/_deps/cleo-src \
  --config /path/to/fresh/runtime-config.yaml \
  --initialization-family controlled \
  --controlled-config config/golovin_stage0_development.yaml \
  --audit-file /path/to/fresh/controlled-initialization-audit.json
```

This path does not accept an initialization seed. Local tests and the
4096-SD CLEO-native write/read gate passed on Levante in job `26534015`; the
compact result is under
[`results/controlled_initialization_native_n4096_v1/`](results/controlled_initialization_native_n4096_v1/).
Persistent frozen-bundle creation and independent verification then passed in
job `26534596`; its compact record is under
[`results/controlled_initialization_bundle_n4096_v1/`](results/controlled_initialization_bundle_n4096_v1/).
Controlled matrix rows require an explicit immutable bundle label. All
pre-convergence gates passed. The reviewed actual matrix is under
[`experiments/golovin_controlled_resolution_convergence_v1/`](experiments/golovin_controlled_resolution_convergence_v1/)
and deliberately retains `submission_authorized=false`: preparing metadata is
not a Slurm submission or a convergence result.

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
accounts, paths and GPU assumptions. The basic single-member workflow is:

1. configure and build the pinned CLEO dependency and both collision-box
   executables;
2. generate one seeded reference initialization;
3. run one single-thread Golovin validation into a fresh SCRATCH directory;
4. inspect the recorded configuration, manifest and Zarr output before any
   Long-kernel or convergence experiment.

The audited first run, including its code path, prescribed conditions and
physical interpretation, is documented in
[`docs/runs/first-golovin-collisions0d.md`](docs/runs/first-golovin-collisions0d.md).
The project diagnostic deliberately reuses CLEO's pinned `cleopy` and
`plotcleo` readers/distribution tools; its additional bulk and conservation
metrics are documented in
[`docs/analysis/collisions0d-diagnostics.md`](docs/analysis/collisions0d-diagnostics.md).
The checksum-verified compact products from the first audited run are under
[`results/first_golovin_serial`](results/first_golovin_serial).
The compact products from the newer fixed-bin Stage-0 development gate are
under
[`results/golovin_stage0_development_gate_v1`](results/golovin_stage0_development_gate_v1).

The first run predated explicit collision-stream control. New runs require both
an initialization seed and collision seed. The design, deliberately minimal
build-local CLEO patch, and one-thread replay gate are documented in
[`ADR 0002`](docs/decisions/0002-explicit-collision-seed.md). The successful
Golovin replay audit is under
[`results/golovin_seed_replay_v1`](results/golovin_seed_replay_v1). A detailed record
of repository creation, the first model/diagnostic run and the seed-control work
is maintained in the
[`2026-07-28 work log`](docs/worklogs/2026-07-28.md).
The controlled-initializer implementation, numerical issues, tests and native
validation are recorded in the
[`2026-07-29 work log`](docs/worklogs/2026-07-29.md).
The checksum-verified compact timestep-screen record, including the 0.1-s
selection and all equivalence tables, is under
[`results/golovin_controlled_timestep_screen_v1/`](results/golovin_controlled_timestep_screen_v1/).

## Attribution

The CMake composition and initial `collisions0d` design follow
[PerformanceTestingCLEO](https://github.com/yoctoyotta1024/PerformanceTestingCLEO)
by Clara Bayley. The application implementation is ported to the CLEO commit
recorded above. Adapted source files retain the upstream BSD-3-Clause copyright
notices.

If using this software, cite this repository through
[`CITATION.cff`](CITATION.cff) and cite the relevant CLEO model-description and
scientific-method papers.
