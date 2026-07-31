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

The repository contains completed controlled Golovin resolution experiments,
but it does **not** yet contain a formally accepted resolution or a
transferable recommended number of superdroplets. The first 512–16,384 by 20
matrix and the fresh 16,384–131,072 by 100 matrix both left the strict
all-time distribution-equivalence rule unresolved.

The pre-registered scientific design for the first permanent-repository
convergence study is the
[`Golovin convergence protocol`](docs/experiments/golovin-convergence-protocol.md).
It separates analytical mean bias, stochastic spread, ensemble precision,
initialization sensitivity, timestep adequacy and cost. Its previously
provisional numerical tolerances are now documented project acceptance
criteria; the preparatory implementation and pilot gates have passed.
The literature-grounded high-resolution and ensemble extension is recorded in
[`ADR 0006`](docs/decisions/0006-extend-golovin-before-long.md) and its
[`supporting review`](docs/literature/golovin-convergence-extension-review.md).
The researcher-approved, non-overwriting reanalysis of the completed matrix
uses the practical diminishing-returns rule in
[`ADR 0007`](docs/decisions/0007-proposed-diminishing-returns-convergence.md).
It retains hard analytical/conservation/provenance gates and asks whether two
successive doublings have one-sided 95% upper bounds below the configured
minimum worthwhile improvement. It is prospective for new model data but a
transparent reanalysis of the already inspected matrix; Clara review remains
pending. The first application selected no resolution: the hard validity and
80-to-100-member stability gates pass, but late-time \(M_6\) confidence bounds
remain above the one-percentage-point diminishing-returns margin. The point
changes rule out 16,384 SDs and identify 32,768 SDs as the first plausible,
not-yet-confirmed candidate. The manuscript-ready distinction between a
practical effect-size plateau and an unresolved strict equivalence result is
in [`Golovin convergence evidence`](docs/manuscript/golovin-convergence-evidence.md).
The checksum-published calculation and its two decision figures are in
[`practical_v2`](results/golovin_controlled_high_resolution_convergence_v1/practical_v2/).
The prospective next-stage design is documented in
[`ADR 0008`](docs/decisions/0008-adaptive-golovin-ensemble-extension.md).
It uses the completed 100-member matrix as a variance-and-cost pilot, compares
balanced and cost-aware fixed final allocations, and keeps exploratory interim
monitoring separate from formal stopping. The planning calculation runs no
CLEO model and explicitly authorizes no new simulation compute. The canonical
80%-assurance calculation is
[`adaptive_plan_v5`](results/golovin_controlled_high_resolution_convergence_v1/adaptive_plan_v5/);
its large projected requirement motivates validating the \(1/n\) variance
model from existing member prefixes before any new model submission.
That non-model diagnostic is implemented by
[`analyze_golovin_variance_scaling.py`](scripts/analyze_golovin_variance_scaling.py).
It reports fitted variance slopes, \(n\,\mathrm{Var}(\hat q_n)\) stability and
normal-versus-percentile calibration without imposing an invented universal
pass threshold. The checksum-published
[`variance_scaling_v1`](results/golovin_controlled_high_resolution_convergence_v1/variance_scaling_v1/)
result supports the \(1/n\) approximation for the limiting late-time \(M_6\)
rows but finds that a normal approximation is optimistic for nonlinear L1.
No further Golovin member is authorized merely to force the old strict rule.
No Long convergence experiment begins before its distinct physical setup and
stopping protocol are registered. The completed exploratory fixed-10-member
Golovin screen measured broad resolution and computational scaling through
524,288 SDs; it does not alter the formal 100-member conclusion. See the
[`fixed-10 screen design`](docs/experiments/golovin-fixed10-high-resolution-screen.md)
and [`collisions0d parallel-execution note`](docs/implementation/collisions0d-parallelism.md).

The next prospectively frozen study is a fresh balanced 50-member ladder from
4,096 through 1,048,576 SDs. It retains the one-percentage-point
minimum-worthwhile-improvement rule over two successive doublings, adds
bootstrap-supported floor-plus-power-law fits, and completely excludes ratios
of successive error reductions. The design and execution gates are in
[`ADR 0009`](docs/decisions/0009-fixed50-extended-golovin-design.md) and the
[`fixed-50 runbook`](docs/experiments/golovin-fixed50-extended-runbook.md).
Its committed matrix is preparation only; Levante model submission still
requires an explicit compute and storage disclosure.

The completed high-resolution configuration is
[`golovin_controlled_high_resolution_convergence.yaml`](config/golovin_controlled_high_resolution_convergence.yaml):
16,384, 32,768, 65,536 and 131,072 superdroplets with 100 newly generated
collision-stream members per level. It reused no raw member, collision seed,
run label or controlled-bundle label from the first matrix.

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
