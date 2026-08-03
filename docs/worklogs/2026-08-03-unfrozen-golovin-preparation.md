# 2026-08-03: unfrozen Golovin sensitivity preparation

## Scope

Prepare, test and document the next Golovin experiment without submitting any
Levante compute. The requested question is whether the completed
frozen-initialization result is robust to independently sampled SD initial
populations.

## Artifacts added or changed

- Registered operational configuration and immutable 450-case matrix.
- Separate deterministic 32-bit initialization-seed and 64-bit collision-seed
  namespaces. The collision namespace deliberately reproduces the frozen
  fixed-50 schedule by `(N_SD, member_index)`; the initialization namespace is
  new, operational and unique per member.
- Named input SHA-256 fields in model manifests and a generalized matrix audit
  for controlled or operational initialization.
- Endpoint smoke validator and Slurm smoke wrapper.
- Restartable contiguous matrix-group runner: one eight-core allocation can
  run multiple independent serial members without 450 scheduler submissions.
- Mandatory time-zero ensemble fidelity analysis for operational runs.
- Dynamic operational 5--50 retrospective adequacy reconstruction, conditional
  on the full operational fixed-50 result rather than on frozen 131,072 SDs.
- Paired frozen-versus-operational analysis using common collision-seed labels.
- ADR 0012 and the detailed execution/resource runbook.

## Matrix/provenance checks

- Matrix path:
  `experiments/golovin_unfrozen_fixed50_extended_resolution_convergence_v1/cases.tsv`
- Matrix SHA-256:
  `55290906c22025f8a97f285dc5d4a3f90443ed90559b05a712f2629cf236d554`
- Cases: 450 = 9 resolutions x 50 members.
- Each new initialization seed is unique; all new controlled-bundle labels are
  `not_applicable`; every collision seed matches the completed frozen matrix
  at the same resolution/member key; all new run labels are disjoint.

## Read-only Levante preflight evidence

- Identity: `m301324`; account allocation remains `mh0731`.
- At the check, unrelated Long reference job `26630312_50` was running and was
  not modified.
- HOME use: 5.1 GiB of 60 GiB quota.
- Shared `/scratch` filesystem: 15 TB globally free. This is capacity, not a
  personal quota; live state must be rechecked immediately before submission.
- Completed frozen fixed-50 baseline: 125.39 summed one-core member-hours and
  39.0 GB Zarr across 450 members. This informs, but does not replace, the
  mandatory endpoint smoke measurement for the operational design.

## Verification

- Full repository suite: 118 passed.
- Focused new/changed suite: 20 passed.
- Ruff: all touched scripts/tests pass.
- Bash syntax: all touched Slurm wrappers pass.
- Python compilation: all touched Python scripts pass.

Repository-wide Ruff is not currently clean because the pre-existing
`plot_golovin_explanatory_figures.py` has style findings outside this change;
it was not reformatted or altered here.

## Explicit non-actions

No `sbatch`, build, model run, input generation, raw-output write, Git commit
or remote push occurred in this preparation. Execution requires the
researcher's single explicit approval after reviewing
`docs/experiments/golovin-unfrozen-fixed50-runbook.md`.
