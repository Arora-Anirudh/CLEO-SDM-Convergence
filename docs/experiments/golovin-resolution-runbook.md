# Controlled Golovin resolution experiment: execution runbook

- Experiment: `golovin_controlled_resolution_convergence_v1`
- Status: fully prepared; model array not submitted
- Account while permanent allocation is pending: `bb1153`
- Scientific role: first actual Golovin superdroplet-resolution convergence
  experiment

## 1. What is fixed before the experiment

All preparatory gates have been completed:

1. explicit collision-stream seeding replays exactly on one thread;
2. the deterministic controlled initial population replays byte for byte;
3. read-only CLEO-native bundles exist at 512, 1024, 2048, 4096, 8192 and
   16,384 superdroplets;
4. a compiled member consumes its frozen bundle without regenerating inputs;
5. fixed-bin diagnostics retain numerical and analytical arrays at 250, 500
   and 1000 bins;
6. the high-resolution timestep screen selected 0.1 s;
7. liquid-mass drift and fixed-bin range coverage passed in the screen.

The timestep result is preserved under
`results/golovin_controlled_timestep_screen_v1/`.

## 2. Actual model matrix

The immutable matrix is
`experiments/golovin_controlled_resolution_convergence_v1/cases.tsv`.

```text
6 resolutions x 20 independent collision streams = 120 members
```

Every member has:

- one rank, one CPU thread and no GPU;
- one read-only controlled initialization bundle;
- collision timestep 0.1 s;
- output every 300 s through 3600 s;
- a unique deterministic 64-bit collision seed;
- no initialization seed, because the population is frozen;
- a unique run label and output directory.

The six populations are deterministic refinements of the same prescribed
continuous DSD. They are not identical individual droplets and the
different-resolution histories are not paired.

## 3. Why the first wave has 20 members

Twenty members is a pre-registered initial ensemble, not an assumption that
20 is always sufficient. It permits an initial estimate of mean, spread and
95% interval width without immediately spending for 50 or 100 members.

After the first wave:

- a cell is extended if its registered interval is too wide;
- only incomplete nested prefixes are added;
- lack of precision is reported as ambiguity, not convergence;
- no level is extended merely because a different metric elsewhere needs
  more members.

## 4. Requested model compute

The planned submission is a bounded Slurm array:

| Item | Request |
| --- | --- |
| account / partition | `bb1153` / `shared` |
| array | `0-119%12` |
| maximum simultaneous tasks | 12 |
| resources per task | 1 node, 1 task, 1 CPU |
| memory per task | 940 MiB |
| walltime per task | 10 minutes |
| mode | serial CLEO; one MPI rank; one Kokkos/OpenMP thread |
| GPU | none |
| new members | 120 |
| retry behavior | skip only manifest-complete members when explicitly resumed |

The hard reservation ceiling is 20 requested CPU-hours
(\(120\times10\) CPU-minutes), but it is not an estimate of consumption.
The 0.1-s timestep-screen members at 16,384 SDs used 74 member-wall-seconds
for five cases (mean 14.8 s, maximum 19 s). Assuming approximately linear
work with the number of sampled superdroplets, the six-level 20-member ladder
has about 583 seconds (0.16 CPU-hour) of model/member-wrapper time before
per-job startup. The earlier single-job measurements show that module,
environment and scheduler overhead can dominate such small models, so the
final report will use `sacct`, not the estimate.

Every completed member produced about 70,001,744 Zarr bytes in the timestep
screen. A conservative raw-output estimate is therefore 8.4 GB for 120
members. SCRATCH contains raw Zarr; HOME contains only compact records.

This disclosure must be repeated immediately before submission. Preparing
the matrix does not itself authorize or launch compute.

## 5. Preflight immediately before submission

Run these read-only checks on the Levante login node:

```bash
export CLEO_SDM_PROJECT_ROOT=/home/b/b383673/SDM/CLEO-SDM-Convergence-golovin-protocol
export CLEO_SDM_BUILD_ROOT=/home/b/b383673/SDM/cleo_builds/CLEO-SDM-Convergence/golovin_controlled_resolution
export CLEO_SDM_RUN_ROOT=/scratch/b/b383673/SDM/CLEO-SDM-Convergence/golovin_controlled_resolution_convergence_v1
export CLEO_SDM_BUNDLE_ROOT=/home/b/b383673/SDM/CLEO-SDM-Convergence-records/controlled_bundles
export MATRIX_FILE=${CLEO_SDM_PROJECT_ROOT}/experiments/golovin_controlled_resolution_convergence_v1/cases.tsv

cd "${CLEO_SDM_PROJECT_ROOT}"
git status --short --branch
git rev-parse HEAD
test "$(wc -l <"${MATRIX_FILE}")" -eq 121
test ! -e "${CLEO_SDM_RUN_ROOT}"
sha256sum "${MATRIX_FILE}"
find "${CLEO_SDM_BUNDLE_ROOT}" -maxdepth 1 -type d \
  -name 'golovin_controlled_N*_v1' -print | sort
grep -F "project_commit=$(git rev-parse HEAD)" \
  "${CLEO_SDM_BUILD_ROOT}/build_manifest.txt"
```

The submission stops if the exact checked-out commit is not the commit in the
build manifest.

## 6. Actual model submission

Only after the compute disclosure and explicit approval:

```bash
mkdir -p /scratch/b/b383673/SDM/logs

sbatch \
  --account=bb1153 \
  --array=0-119%12 \
  --export=ALL,CLEO_SDM_PROJECT_ROOT="${CLEO_SDM_PROJECT_ROOT}",CLEO_SDM_BUILD_ROOT="${CLEO_SDM_BUILD_ROOT}",CLEO_SDM_RUN_ROOT="${CLEO_SDM_RUN_ROOT}",CLEO_SDM_BUNDLE_ROOT="${CLEO_SDM_BUNDLE_ROOT}",MATRIX_FILE="${MATRIX_FILE}",RESUME_COMPLETED=0 \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/levante/run_golovin_matrix.sbatch"
```

Record the returned array job ID. Do not infer completion from the presence of
some directories. Audit the whole array:

```bash
sacct \
  --jobs=<ARRAY_JOB_ID> \
  --format=JobID,JobName%24,State,ExitCode,Elapsed,ReqCPUS,AllocCPUS,ReqMem,MaxRSS

find "${CLEO_SDM_RUN_ROOT}" -mindepth 2 -maxdepth 2 \
  -name manifest.txt -exec grep -l '^status=completed$' {} + | wc -l
```

Exactly 120 complete manifests are required. A retry uses the identical
matrix with `RESUME_COMPLETED=1`; incomplete pre-existing paths are never
silently overwritten.

## 7. Analysis submission after all 120 members finish

The analysis job runs no CLEO simulation. Its planned request is one node,
one task, one CPU, 2 GiB and 30 minutes on `bb1153/shared`, with no GPU.

```bash
export RESOLUTION_CONFIG=${CLEO_SDM_PROJECT_ROOT}/config/golovin_controlled_resolution_convergence.yaml
export RESOLUTION_RECORD_ROOT=/home/b/b383673/SDM/CLEO-SDM-Convergence-records/golovin_controlled_resolution_convergence_v1

sbatch \
  --account=bb1153 \
  --export=ALL,CLEO_SDM_PROJECT_ROOT="${CLEO_SDM_PROJECT_ROOT}",CLEO_SDM_BUILD_ROOT="${CLEO_SDM_BUILD_ROOT}",CLEO_SDM_RUN_ROOT="${CLEO_SDM_RUN_ROOT}",CLEO_SDM_BUNDLE_ROOT="${CLEO_SDM_BUNDLE_ROOT}",MATRIX_FILE="${MATRIX_FILE}",RESOLUTION_CONFIG="${RESOLUTION_CONFIG}",RESOLUTION_RECORD_ROOT="${RESOLUTION_RECORD_ROOT}",EXPECTED_CASE_COUNT=120 \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/levante/analyze_golovin_resolution_convergence.sbatch"
```

It creates each missing member diagnostic non-destructively, aggregates all
members, applies the formal gates and writes checksummed compact output under
`analysis_v1/`.

## 8. Formal decision

At 600, 1200, 1800, 2400, 3000 and 3600 s the analysis tests:

- ensemble-mean distribution L1 against the Golovin analytical solution;
- signed relative \(M_0\) and \(M_6\) bias;
- registered confidence-interval precision;
- independent adjacent-resolution equivalence;
- per-member liquid-mass drift;
- below/above-range liquid mass;
- the distribution decision independently at 250, 500 and 1000 bins.

For L1, members are averaged bin by bin before the nonlinear absolute-value
operation. Adjacent resolutions use independent bootstrap resampling because
they are independent ensembles.

A candidate \(N\) is selected only when \(N\), \(2N\) and \(4N\) pass their
analytical and precision gates and both adjacent pairs pass equivalence. If no
candidate passes, the correct output is “no resolution accepted in the
initial matrix.” That result triggers targeted member or resolution extension;
it does not license choosing the largest tested value.
