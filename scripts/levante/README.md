# Levante workflow

These scripts adapt the verified CLEO Levante toolchain to this repository.
They do not copy CLEO's user-specific example scripts.

The workflow uses Levante's GCC/OpenMPI/NetCDF/Git modules and the system CMake
3.26.5 directly. It deliberately does not call `spack load`: on 2026-07-28 the
system Spack package configuration contained a duplicate YAML key, while the
required software installations remained available through modules and their
verified absolute paths.

## Workflow layers

1. `common.sh` records machine paths, modules and runtime settings.
2. `build.sbatch` creates the locked Python environment, fetches the exact CLEO
   pin and builds both collision-box executables.
3. `run_collisions0d.sbatch` creates one non-overwriting run directory,
   materializes an absolute-path configuration, generates initial conditions,
   and runs either the Golovin or Long executable.
4. `validate_collision_seed_replay.sbatch` proves one-thread exact replay for
   one frozen initialization and two controlled collision streams.
5. `validate_controlled_initialization.sbatch` generates one deterministic
   4096-SD bundle and checks it through CLEO's own native binary reader.
6. `prepare_controlled_bundle.sbatch` creates one persistent, read-only,
   checksummed native bundle for one resolution.
7. `validate_controlled_bundle_replay.sbatch` independently regenerates the
   4096-SD population and requires byte-identical native inputs.
8. `prepare_controlled_bundle_ladder.sbatch` creates the missing immutable
   bundles for 512, 1024, 2048, 8192 and 16384 SDs while verifying and reusing
   the canonical 4096-SD bundle.
9. `run_collisions0d.sbatch` can point a controlled Golovin member directly
   at that bundle and verifies it before and after model execution.
10. `run_golovin_matrix.sbatch` maps one reviewed TSV row to one unique
    member and skips only explicitly resumed, matrix-matching completed cases.
11. `analyze_collisions0d.sbatch` reads one completed run through CLEO's own
   `cleopy`/`plotcleo` tools and writes non-overwriting fixed-bin, moment,
   onset, tail and conservation diagnostics.
12. `run_golovin_timestep_screen.sbatch` and
    `analyze_golovin_timestep_screen.sbatch` execute and decide the controlled
    16,384-SD, 25-member collision-timestep gate.
13. `run_golovin_resolution_convergence.sbatch` executes all 120 rows of the
    reviewed actual resolution matrix sequentially in one restartable job.
14. `analyze_golovin_resolution_convergence.sbatch` creates/validates all 120
    member diagnostics and applies the formal resolution decision.

The permanent source and build trees are in HOME. Run-specific configuration,
input binaries and Zarr output are stored under SCRATCH.

## Build request

The build script requests:

- one node and one task;
- eight CPU cores;
- 4 GiB memory;
- 10 minutes;
- `shared` partition;
- CPU/OpenMP only, with no GPU.

The account is deliberately not committed because `bb1153` is temporary.
Supply the active account at submission:

```bash
mkdir -p /scratch/b/b383673/SDM/logs
sbatch --account=bb1153 scripts/levante/build.sbatch
```

## Single collision-box request

The model script requests:

- one node and one task;
- one CPU core;
- 940 MiB memory;
- 10 minutes;
- `shared` partition;
- one MPI rank and one OpenMP thread;
- no GPU.

For the first Golovin smoke run:

```bash
sbatch \
  --account=bb1153 \
  --export=ALL,KERNEL=golovin,INITIALIZATION_SEED=12345,COLLISION_SEED=67890,RUN_LABEL=first_golovin_seeded,MODEL_THREADS=1 \
  scripts/levante/run_collisions0d.sbatch
```

The job refuses to overwrite an existing `RUN_LABEL`. A Long run uses the same
workflow with `KERNEL=long`, but should only be submitted after the Golovin
validation is understood.

`MODEL_THREADS` is deliberately independent of `SLURM_CPUS_PER_TASK`. Levante
may allocate additional CPUs to satisfy memory policies; the model still uses
only the explicitly requested number of Kokkos/OpenMP threads.

Every new run requires two separate seeds:

- `INITIALIZATION_SEED` controls the Python sampling of the time-zero SD
  population;
- `COLLISION_SEED` controls CLEO's collision shuffle/event RNG pool.

## Collision-seed replay request

The replay gate requests:

- one node and one task;
- one CPU core;
- 940 MiB memory;
- 10 minutes;
- `shared` partition;
- three sequential one-rank, one-thread simulations;
- no GPU.

```bash
sbatch \
  --account=bb1153 \
  --export=ALL,KERNEL=golovin,INITIALIZATION_SEED=12345,REPLAY_COLLISION_SEED=67890,DIFFERENT_COLLISION_SEED=98765,VALIDATION_LABEL=golovin_seed_replay_v1 \
  scripts/levante/validate_collision_seed_replay.sbatch
```

The same initialization and collision seed must yield byte-identical Zarr
stores; changing only the collision seed must change the output. See
[`docs/decisions/0002-explicit-collision-seed.md`](../../docs/decisions/0002-explicit-collision-seed.md).

## Controlled-initialization native gate

This input-only validation requests:

- one node and one task;
- one CPU core;
- 940 MiB memory;
- 10 minutes;
- `shared` partition;
- serial Python/CLEO binary writing and reading;
- no collision executable, no model output, no ensemble and no GPU.

It creates one 4096-SD deterministic bundle, then uses CLEO's own
`read_initsuperdrops` module to verify the binary checksum, exact represented
droplet count, one-box membership, coordinate bounds and represented
\(M_0\), \(M_3\) and \(M_6\):

```bash
sbatch \
  --account=bb1153 \
  --export=ALL,VALIDATION_LABEL=controlled_init_n4096_v1 \
  scripts/levante/validate_controlled_initialization.sbatch
```

`VALIDATION_LABEL` is non-overwriting. The raw native inputs and compact JSON
audit/readback records are written under
`$CLEO_SDM_RUN_ROOT/controlled_initialization_validation/`.

## Frozen controlled-bundle request

The bundle-preparation script requests:

- one node and one task;
- one CPU core;
- 940 MiB memory;
- 10 minutes;
- `shared` partition;
- serial input generation and CLEO-native readback;
- no collision executable, model output, ensemble or GPU.

A bundle is stored persistently under
`$CLEO_SDM_BUNDLE_ROOT/<BUNDLE_LABEL>`. The final manifest records the
normalized scientific definition, project/CLEO commits, Python/NumPy
environment, source snapshots and SHA-256/size of every required artifact.
All files have their write bits removed. The path is non-overwriting.

Proposed first validation command—do not submit without the researcher's
explicit compute approval:

```bash
sbatch \
  --account=bb1153 \
  --export=ALL,MAX_SUPERDROPLETS=4096,BUNDLE_LABEL=golovin_controlled_N004096_v1 \
  scripts/levante/prepare_controlled_bundle.sbatch
```

### Same-stack replay and resolution ladder

The replay request is one node, one task, one CPU, 940 MiB and 10 minutes on
`shared`. It runs input generation/readback only:

```bash
sbatch \
  --account=bb1153 \
  --export=ALL,MAX_SUPERDROPLETS=4096,REPLAY_LABEL=golovin_controlled_N004096_replay_v1,CANONICAL_BUNDLE=/home/b/b383673/SDM/CLEO-SDM-Convergence-records/controlled_bundles/golovin_controlled_N004096_v1 \
  scripts/levante/validate_controlled_bundle_replay.sbatch
```

The bundle-ladder request has the same resource shape and creates five missing
native input bundles, not simulations:

```bash
sbatch \
  --account=bb1153 \
  --export=ALL,CANONICAL_N4096_BUNDLE=/home/b/b383673/SDM/CLEO-SDM-Convergence-records/controlled_bundles/golovin_controlled_N004096_v1 \
  scripts/levante/prepare_controlled_bundle_ladder.sbatch
```

Both scripts refuse pre-existing output paths and create no Zarr store.

## Single-member frozen-bundle reuse

After one bundle has passed creation validation, a controlled Golovin member
uses:

```bash
sbatch \
  --account=bb1153 \
  --export=ALL,KERNEL=golovin,INITIALIZATION_FAMILY=controlled,CONTROLLED_BUNDLE=/absolute/frozen/bundle,COLLISION_SEED=67890,RUN_LABEL=controlled_golovin_reuse_v1,MODEL_THREADS=1,MAX_SUPERDROPLETS=4096 \
  scripts/levante/run_collisions0d.sbatch
```

The controlled path:

1. rejects an initialization seed;
2. validates the bundle's resolution, pinned CLEO commit, scientific
   definition, file sizes, checksums and read-only modes;
3. materializes a member configuration pointing directly to the frozen files;
4. does not create a member-local input directory or call the initializer;
5. verifies the bundle again after CLEO exits;
6. records the bundle path and manifest/grid/superdroplet hashes.

The existing `operational_stochastic` path remains seeded and continues to
generate member-local inputs.

## Scientific and machine configuration

The scientific template is
`config/collisions0d_reference.yaml`. It contains the droplet distribution,
grid-box dimensions, number of superdroplets, collision timestep, observation
interval and end time.

`scripts/materialize_collisions0d_config.py` changes:

- absolute paths to constants, grid, initial superdroplets and output;
- the Kokkos thread count requested by Slurm;
- only explicitly supplied experiment overrides for maximum superdroplets,
  collision timestep, observation interval and end time.

The materialized YAML is the complete per-member record. Unspecified
scientific values remain exactly those in the version-controlled template.

## Single-run diagnostic request

The diagnostic script requests:

- one node and one task;
- one CPU core;
- 940 MiB memory;
- 10 minutes;
- `shared` partition;
- serial CPU analysis with no GPU.

For the audited first Golovin run:

```bash
sbatch \
  --account=bb1153 \
  --export=ALL,KERNEL=golovin,RUN_LABEL=first_golovin_serial \
  scripts/levante/analyze_collisions0d.sbatch
```

The implementation and formulas are documented in
[`docs/analysis/collisions0d-diagnostics.md`](../../docs/analysis/collisions0d-diagnostics.md).

## Stage-0 matrix status

`config/golovin_stage0_development.yaml` and
`scripts/prepare_golovin_matrix.py` create a four-row metadata-only development
matrix. The generator runs no model and writes
`submission_authorized=false`. Do not submit it until the researcher has
received a compute disclosure and explicitly approved the development smoke
run.

The complete design, output schema, seed mapping, refusal/resume semantics and
remaining scientific decisions are documented in the
[`Golovin Stage-0 implementation guide`](../../docs/implementation/golovin-stage0-guide.md).

## Controlled timestep-screen status

The registered pre-convergence screen uses one immutable 16,384-SD
initialization, five collision timesteps and five collision-stream labels:

```text
5 timesteps x 5 streams = 25 sequential members
```

The same five seed labels are reused across timesteps for reproducible
common-stream comparisons; changing timestep still changes collision-update
histories. The exact decision rules and output tables are documented in the
[`pre-convergence gates guide`](../../docs/implementation/golovin-preconvergence-gates.md).

The runner requests one node, one task, one CPU, 940 MiB and two hours on
`shared`; the longer walltime is a conservative bound for the 16,384-SD
0.1-s members. The analysis requests the same CPU/memory shape for 30 minutes.
The screen completed and selected 0.1 s. Its compact result is under
`results/golovin_controlled_timestep_screen_v1/`.

## First controlled resolution experiment

The completed first model experiment was:

```text
6 resolutions x 20 independent collision streams = 120 members
```

It uses the six frozen controlled bundles and the selected 0.1-s collision
timestep. The planned model submission is one restartable job that loops over
all 120 matrix rows sequentially. It requests one node, one task, one CPU,
940 MiB and one hour on `shared`; every CLEO member uses one rank/thread and no
GPU. Separate seeds, configurations, outputs and manifests preserve scientific
member identity independently of the scheduler layout. The analysis request is
one CPU, 2 GiB and 30 minutes and launches no CLEO model.

Its exact preflight, submission, resume, accounting and analysis commands are
in the
[`controlled Golovin resolution runbook`](../../docs/experiments/golovin-resolution-runbook.md).
It selected no resolution under the registered rule.

## Fresh high-resolution controlled experiment

The registered follow-up is 16,384, 32,768, 65,536 and 131,072 SDs with 100
fresh collision streams per level. It uses a new seed namespace, run labels,
run root and bundle labels; no previous raw member enters the analysis.

To avoid 400 scheduler jobs,
`run_golovin_resolution_convergence_parallel.sbatch` requests four task slots
in one restartable allocation and runs at most four independent one-rank,
one-thread CLEO members concurrently. Its measured-runtime-based request is
four CPUs, 3600 MiB total memory and 2 hours 15 minutes. The serial analysis
requests one CPU, 940 MiB and 45 minutes. Exact storage evidence, runtime
extrapolation, data-deletion boundaries, preparation, submission, audit and
interpretation are in the
[`fresh high-resolution runbook`](../../docs/experiments/golovin-high-resolution-runbook.md).
That runbook is documentation, not compute authorization.
