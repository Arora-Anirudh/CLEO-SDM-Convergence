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

## Planned Levante layout

The model is one Slurm allocation, not 450 scheduler jobs.  Eight worker
loops run independent one-rank, one-thread CLEO members concurrently.  Each
member is launched with `srun --exclusive --mem=0 --mpi=pmix_v3` and one
physical core.  `collisions0d` itself remains a one-rank executable; OpenMPI
provides the launch/runtime layer and does not split one box member across
MPI ranks.

The runner is restartable: a completed member is checksum-audited and
skipped; an incomplete or mismatched path stops for inspection.

## Projected resources

Projection from the completed fixed-10 ladder:

- model work: approximately 55--61 physical core-hours;
- model elapsed time with eight concurrent workers: approximately 7--8 h,
  before queueing and with some load/runtime uncertainty;
- new raw SCRATCH: approximately 26--29 GB;
- bundle preparation: one CPU, no collision model, no Zarr output;
- analysis: one CPU, reading all 450 Zarr stores and producing compact
  checksum-published results.

These are planning values, not a submission record.

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
