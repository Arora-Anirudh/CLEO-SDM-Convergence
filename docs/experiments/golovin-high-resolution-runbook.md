# Fresh high-resolution controlled Golovin runbook

## 1. Purpose and scientific boundary

The first controlled Golovin experiment completed 120 members at
\(N_\mathrm{SD}=512\)–16,384 but accepted no resolution under the registered
all-time distribution and adjacent-equivalence rules. This follow-up keeps
the scientific test fixed while extending both resolution and ensemble size:

```text
N_SD = 16,384, 32,768, 65,536, 131,072
members per resolution = 100
total new members = 400
collision timestep = 0.1 s
output interval = 300 s
end time = 3600 s
```

No previous raw member, collision seed, run label, output directory or
controlled-bundle label is used. The previous compact, checksum-published
result remains a planning and provenance record only.

The configuration is
[`config/golovin_controlled_high_resolution_convergence.yaml`](../../config/golovin_controlled_high_resolution_convergence.yaml).
The immutable generated matrix is
[`experiments/golovin_controlled_high_resolution_convergence_v1/`](../../experiments/golovin_controlled_high_resolution_convergence_v1/).

## 2. Why this is one bounded allocation

Submitting 400 independent tiny Slurm jobs would create unnecessary scheduler
overhead. The model runner instead requests four task slots in one allocation
and starts four independent serial workers. Each worker processes a disjoint
strided subset of the matrix:

```text
worker 0: cases 0, 4, 8, ...
worker 1: cases 1, 5, 9, ...
worker 2: cases 2, 6, 10, ...
worker 3: cases 3, 7, 11, ...
```

Every CLEO member still uses exactly one MPI rank and one Kokkos/OpenMP
thread. Scheduler packing changes only throughput; it does not change the
scientific member definition.

## 3. Fresh-data isolation contract

The old raw target is:

```text
/scratch/b/b383673/SDM/CLEO-SDM-Convergence/
  golovin_controlled_resolution_convergence_v1
```

Before deletion it must satisfy all of these checks:

- exact `realpath` equals the path above;
- object is a directory, not a symlink;
- owner is `b383673`;
- exactly 120 top-level member directories exist;
- directory size is reported;
- the separate HOME record and repository result are present.

Only that raw SCRATCH directory was deleted after the registered audit. These
records are retained:

```text
/home/b/b383673/SDM/CLEO-SDM-Convergence-records/
  golovin_controlled_resolution_convergence_v1

results/golovin_controlled_resolution_convergence_v1/
```

The 7.9-GiB SCRATCH deletion is not recoverable through this workflow. The retained
records contain the matrix, summaries, decisions, figures, inventories,
provenance and checksums, but not the full per-superdroplet trajectories.

The new paths are distinct:

```text
run root:
/scratch/b/b383673/SDM/CLEO-SDM-Convergence/
  golovin_controlled_high_resolution_convergence_v1

record root:
/home/b/b383673/SDM/CLEO-SDM-Convergence-records/
  golovin_controlled_high_resolution_convergence_v1
```

## 4. Matrix gates

Before synchronization, verify:

```bash
python scripts/prepare_golovin_matrix.py \
  --config config/golovin_controlled_high_resolution_convergence.yaml \
  --output-directory /a/fresh/test/path
```

The checked-in matrix must contain:

- 400 rows with contiguous indices 0–399;
- exactly 100 rows at every registered resolution;
- 400 distinct 64-bit collision seeds;
- no seed, run-label or bundle-label overlap with the first matrix;
- `submission_authorized=false` remains an immutable metadata safety marker;
  actual submission additionally requires an explicit, dated compute
  disclosure and researcher authorization outside the generated matrix.

The test suite checks these properties directly.

## 5. Exact-commit build

The run scripts refuse a dirty checkout and refuse a build whose manifest
does not contain the exact project commit. After the reviewed commit is
synchronized to Levante, the build request is:

| field | request |
| --- | --- |
| account | temporary `bb1153` |
| partition | `shared` |
| nodes | 1 |
| tasks | 1 |
| CPUs per task | 8 |
| memory | 4 GiB |
| walltime | 10 min |
| accelerator | none |

Submission is not authorized merely because this command is documented:

```bash
sbatch \
  --account=bb1153 \
  scripts/levante/build.sbatch
```

## 6. Fresh controlled bundles

The deterministic scientific initializer is unchanged, but each active
resolution is newly materialized and assigned a new bundle label:

```text
golovin_controlled_highres_N016384_v1
golovin_controlled_highres_N032768_v1
golovin_controlled_highres_N065536_v1
golovin_controlled_highres_N131072_v1
```

The bundle preparation request is:

| field | request |
| --- | --- |
| account | temporary `bb1153` |
| partition | `shared` |
| nodes | 1 |
| tasks | 1 |
| CPUs per task | 1 |
| memory | 940 MiB |
| walltime | 10 min |
| CLEO model | not run |
| accelerator | none |

After compute approval:

```bash
sbatch \
  --account=bb1153 \
  --export=ALL,REUSE_CANONICAL_N4096=0,BUNDLE_RESOLUTIONS="16384 32768 65536 131072",BUNDLE_LABEL_STEM=golovin_controlled_highres,BUNDLE_LABEL_VERSION=v1,BUNDLE_LADDER_RECORD_LABEL=golovin_controlled_high_resolution_v1_bundle_record \
  scripts/levante/prepare_controlled_bundle_ladder.sbatch
```

The script refuses any pre-existing target, performs CLEO-native readback,
freezes file permissions and records SHA-256 hashes. A newly materialized
deterministic superdroplet binary may be byte-identical to an earlier binary;
freshness here means it is produced and registered independently rather than
borrowed from the old run.

## 7. Model request

The completed first experiment provides a direct measurement at 16,384 SDs:
20 members averaged 14.7 s/member. Its restartable runner spent another
531 s around 120 members, or about 4.4 s/case, on launching, validation,
manifests and filesystem work. Doubling the measured member time at each
doubled resolution gives about 6.13 serial model CPU-hours:

| \(N_\mathrm{SD}\) | members | estimated seconds/member | estimated CPU-hours |
| ---: | ---: | ---: | ---: |
| 16,384 | 100 | 14.7 | 0.41 |
| 32,768 | 100 | 29.4 | 0.82 |
| 65,536 | 100 | 58.8 | 1.63 |
| 131,072 | 100 | 117.6 | 3.27 |
| **total** | **400** | — | **6.13** |

Because the matrix is evenly divisible among four strided workers, each worker
receives 25 members at every resolution. The expected allocation walltime is
therefore about 92 minutes of model work plus about 7–8 minutes of measured
per-case orchestration. The 2 h 15 min limit supplies about 36 minutes of
additional margin without reserving the earlier four-hour ceiling.

The revised allocation is:

| field | request |
| --- | --- |
| account | temporary `bb1153` |
| partition | `shared` |
| nodes | 1 |
| tasks | 4 |
| CPUs per task | 1 |
| simultaneous members | at most 4 |
| memory | 3600 MiB total |
| walltime | 2 h 15 min |
| per member | one MPI rank, one CPU thread |
| GPU | none |
| expected raw output | about 28.0 GB / 26.1 GiB |

The `shared` partition permits at most 940 MiB per allocated logical CPU.
Using 3600 MiB stays within the four requested CPUs and avoids asking Slurm to
add a fifth CPU solely to satisfy memory. Earlier members used at most about
166 MiB each, so this remains a substantial memory margin.

After compute approval, define the exact roots and submit:

```bash
export CLEO_SDM_PROJECT_ROOT=/home/b/b383673/SDM/CLEO-SDM-Convergence
export CLEO_SDM_BUILD_ROOT=/home/b/b383673/SDM/cleo_builds/CLEO-SDM-Convergence/openmp
export CLEO_SDM_RUN_ROOT=/scratch/b/b383673/SDM/CLEO-SDM-Convergence/golovin_controlled_high_resolution_convergence_v1
export CLEO_SDM_BUNDLE_ROOT=/home/b/b383673/SDM/CLEO-SDM-Convergence-records/controlled_bundles
export MATRIX_FILE="${CLEO_SDM_PROJECT_ROOT}/experiments/golovin_controlled_high_resolution_convergence_v1/cases.tsv"
export RESOLUTION_RECORD_ROOT=/home/b/b383673/SDM/CLEO-SDM-Convergence-records/golovin_controlled_high_resolution_convergence_v1

sbatch \
  --account=bb1153 \
  --export=ALL,CLEO_SDM_PROJECT_ROOT="${CLEO_SDM_PROJECT_ROOT}",CLEO_SDM_BUILD_ROOT="${CLEO_SDM_BUILD_ROOT}",CLEO_SDM_RUN_ROOT="${CLEO_SDM_RUN_ROOT}",CLEO_SDM_BUNDLE_ROOT="${CLEO_SDM_BUNDLE_ROOT}",MATRIX_FILE="${MATRIX_FILE}",RESOLUTION_RECORD_ROOT="${RESOLUTION_RECORD_ROOT}",EXPECTED_CASE_COUNT=400,WORKER_COUNT=4,RESUME_COMPLETED=1 \
  scripts/levante/run_golovin_resolution_convergence_parallel.sbatch
```

The runner is restartable only at completed-member boundaries. A completed
member is skipped only when its manifest matches the exact matrix row and
matrix SHA-256. Any partial path causes refusal and manual inspection.

## 8. Model audit

After completion:

```bash
sacct \
  --jobs=<model_job_id> \
  --format=JobID,JobName%22,State,ExitCode,Elapsed,ReqCPUS,AllocCPUS,ReqMem,MaxRSS

test "$(find "${CLEO_SDM_RUN_ROOT}" -mindepth 1 -maxdepth 1 -type d | wc -l)" -eq 400

sha256sum -c \
  "${RESOLUTION_RECORD_ROOT}/analysis_v1/SHA256SUMS"
```

The last checksum command applies after analysis exists. Model completion
alone is established by:

- runner exit status 0;
- all four worker stderr logs empty;
- 400 manifest-complete run directories;
- a checksum-verified `model_inventory.json`;
- total measured Zarr bytes and member walltimes recorded.

## 9. Analysis request

Analysis launches no CLEO model. It computes per-member fixed-bin
distributions, the 100-member ensemble means and bootstraps, analytical
confidence intervals, adjacent-resolution equivalence, conservation/range
gates and the N/2N/4N resolution decision.

The conservative request is:

| field | request |
| --- | --- |
| account | temporary `bb1153` |
| partition | `shared` |
| nodes | 1 |
| tasks | 1 |
| CPUs per task | 1 |
| memory | 940 MiB |
| walltime | 45 min |
| CLEO model | not run |
| GPU | none |

The first full member-diagnostic pass processed 8.4 GB of raw data in about
6 minutes before a later plotting failure. Scaling that I/O volume to 28 GB
suggests roughly 20 minutes. Forty-five minutes leaves more than a factor-two
walltime margin while 940 MiB remains nearly twice the observed analysis
maximum RSS of about 491 MB. Requesting more memory on `shared` would
automatically allocate extra CPUs to this serial job without accelerating it.

After the model succeeds, submit with an `afterok` dependency:

```bash
sbatch \
  --account=bb1153 \
  --dependency=afterok:<model_job_id> \
  --mem=940M \
  --time=00:45:00 \
  --export=ALL,CLEO_SDM_PROJECT_ROOT="${CLEO_SDM_PROJECT_ROOT}",CLEO_SDM_BUILD_ROOT="${CLEO_SDM_BUILD_ROOT}",CLEO_SDM_RUN_ROOT="${CLEO_SDM_RUN_ROOT}",CLEO_SDM_BUNDLE_ROOT="${CLEO_SDM_BUNDLE_ROOT}",MATRIX_FILE="${MATRIX_FILE}",RESOLUTION_CONFIG="${CLEO_SDM_PROJECT_ROOT}/config/golovin_controlled_high_resolution_convergence.yaml",RESOLUTION_RECORD_ROOT="${RESOLUTION_RECORD_ROOT}",EXPECTED_CASE_COUNT=400 \
  scripts/levante/analyze_golovin_resolution_convergence.sbatch
```

## 10. Live SCRATCH capacity audit

Immediately before submission on 2026-07-29, Levante reported:

```text
/scratch filesystem: 15 TiB total, 2.2 TiB used, 13 TiB available
user SCRATCH quota:   2.166 TiB used, no block or inode limit reported
user SDM subtree:     9.2 GiB
project run subtree:  2.4 GiB
new run target:       absent
```

The expected 26.1-GiB raw experiment would raise the SDM subtree to roughly
35.3 GiB before compact analysis products. This is well within the live
filesystem capacity. SCRATCH remains temporary storage; only compact,
checksummed results are retained in HOME and Git.

## 11. Interpretation and stopping

The analysis asks whether either complete confirmation triple passes:

```text
16,384 / 32,768 / 65,536
32,768 / 65,536 / 131,072
```

The smallest candidate is accepted only if analytical agreement, precision,
conservation and range coverage pass at the candidate and the required
adjacent comparisons pass through its next two levels at every registered
time and all three bin counts.

If only confidence-interval width fails, add members toward 200 only at the
limiting resolutions. If point bias or adjacent differences remain outside
the margin, add 262,144 SDs. Long remains blocked until Golovin is formally
accepted or a new prospective decision explicitly changes the protocol.
