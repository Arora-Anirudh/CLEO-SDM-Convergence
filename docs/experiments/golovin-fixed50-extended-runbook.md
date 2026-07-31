# Golovin fixed-50 extended-resolution runbook

## Scientific definition

- Experiment:
  `golovin_fixed50_extended_resolution_convergence_v1`
- Kernel/processes: Golovin collision-coalescence only
- Box: one 0-D collision volume; no condensation, motion, coupling or fallout
- Controlled initialization: one immutable, experiment-specific binary bundle
  per resolution, reused byte-for-byte by the 50 collision members
- Collision timestep: 0.1 s
- End time: 3600 s
- State output: every 600 s, exactly matching the registered analysis cadence
- Decision times: 600, 1200, 1800, 2400, 3000 and 3600 s
- Resolutions: 4096 through 1048576 SDs in factor-of-two steps
- Members: 50 independent collision streams per resolution
- Total model members: 450

The frozen matrix is
`experiments/golovin_fixed50_extended_resolution_convergence_v1/cases.tsv`.
Its manifest records `submission_authorized=false`; preparing or committing
the matrix never submits compute.

## Interpretation

The experiment has three separate result layers:

1. **Validity:** analytical L1 and moment agreement, conservation, radius
   coverage and provenance.
2. **Practical diminishing returns:** one-sided 95% upper bound no larger
   than one percentage point for two successive doublings, with stable
   40-/50-member decisions.
3. **Supporting convergence law:** fits of
   \(E_\infty+a(N/N_{\min})^{-p}\) over the highest four, five and six
   levels.  These fits diagnose continuing power-law behavior versus an
   identifiable floor but do not select a resolution.

No successive-improvement ratio is calculated or plotted.

## Required non-model gates

1. The working tree is clean and the exact Git revision is pushed.
2. All Python tests, Ruff checks, formatting checks and Bash syntax checks
   pass.
3. The exact project revision is rebuilt on `m301324`.
4. Nine fresh controlled bundles are generated and verified under:
   `golovin_fixed50_extended_N<resolution>_v1`.
5. The 450-row matrix checksum matches its committed manifest.
6. The new run and record roots are absent.
7. Live SCRATCH free space exceeds the disclosed requirement with a
   conservative safety factor.
8. No Slurm model submission occurs before the researcher receives the exact
   account, partition, CPU, memory, walltime, concurrency, maximum CPU-hour,
   expected CPU-hour and storage disclosure.

## Reviewed Levante layout

The model is one Slurm allocation, not 450 scheduler jobs.  Sixteen worker
loops run independent one-rank, one-thread CLEO members concurrently.  Each
member is launched with `srun --exclusive --mem=0 --mpi=pmix_v3` and one
physical core.  `collisions0d` itself remains a one-rank executable; OpenMPI
provides the launch/runtime layer and does not split one box member across
MPI ranks.

A Levante node has many more cores than this allocation, but unrequested
cores do not belong to the experiment.  The 16 Slurm tasks are the 16
concurrent model members.  Hardware threads reported by Slurm are not extra
independent physical cores and are deliberately excluded with
`--hint=nomultithread`.

The runner is restartable: a completed member is checksum-audited and
skipped; an incomplete or mismatched path stops for inspection.

## Requested and projected resources

Projection from the completed fixed-10 ladder:

- model work: approximately 55--61 physical core-hours;
- model elapsed time with 16 concurrent workers: approximately 3.5--4.5 h,
  before queueing and with some load/runtime uncertainty;
- new raw SCRATCH: approximately 26--29 GB;
- exact build: eight physical cores, 4 GiB and 10 minutes;
- bundle preparation: input-only, no collision model and no Zarr output;
- model: 16 physical cores, 14.4 GiB and five hours, giving an 80-core-hour
  model ceiling;
- analysis: one physical core, 940 MiB and three hours, reading all 450 Zarr
  stores and producing compact checksum-published results.

The complete requested ceiling is about 84.7 physical core-hours.  Expected
actual work is about 56--63 physical core-hours, mostly in the model stage.
Expected end-to-end elapsed compute time, excluding queueing, is approximately
4.25--6 hours: minutes for build/input preparation, 3.5--4.5 hours for the
model, and 0.75--1.5 hours for analysis.

## Submission record

The production checkout on Levante is detached at project commit `8e39a60`
with CLEO pinned at `83318c23`.  The committed 450-row matrix SHA-256 is:

```text
cc838bc63f2d939f99f21013836d134195de6339658ba9555ca48d17d9a293ed
```

The execution gates and jobs were:

1. Job `26587062`, the first 16-worker layout probe, safely failed after all
   worker steps ran because its final login-node-compatible parser used a
   Python type annotation unsupported by Levante's system Python.  No CLEO
   model ran.
2. Commit `8e39a60` removed that compatibility error.  Replacement probe
   `26587104` completed in 33 seconds; all 16 one-core steps launched within
   0.291 seconds and the probe reported
   `PARALLEL_MEMBER_LAYOUT_PROBE_PASS=1`.
3. Exact build job `26587225` completed in 2 minutes 11 seconds.
4. Input-only bundle job `26587226` generated and froze the first eight
   bundles, then exhausted its 940-MiB allocation while constructing the
   1,048,576-SD bundle.  Its dependent model and analysis jobs, `26587227`
   and `26587228`, were automatically cancelled before allocation.
5. The incomplete bundle and record were preserved under names ending in
   `_failed_job26587226`.  Retry job `26587405` used 4 GiB, generated only
   the missing bundle, and completed in 31 seconds.  All nine immutable
   bundles then passed independent checksum, resolution, configuration,
   project-commit and CLEO-commit verification.
6. Replacement model job `26587532` was submitted with 16 physical workers,
   14.4 GiB and a five-hour ceiling.  Analysis job `26587533` depends on its
   successful completion and requests one physical core, 940 MiB and three
   hours.  Both jobs email the researcher on completion or failure.

This section is an execution record, not a convergence result.  A running
model and a pending dependent analysis do not establish scientific
convergence.

## Post-run products

The dependent analysis allocation performs, in one audited staging tree:

1. per-member Stage-0 fixed-bin diagnostics;
2. complete matrix and checksum audit;
3. ensemble summary;
4. the registered analytical/adjacent-resolution analysis;
5. the practical diminishing-returns analysis; and
6. the supporting convergence-law analysis.

The directory is moved to its final record name only after all calculations
and SHA-256 checks pass.
