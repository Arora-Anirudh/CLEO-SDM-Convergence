# Operational-initialization Golovin fixed-50 runbook

## Status and purpose

Prepared on 2026-08-03; no Slurm submission has been made. This is the direct
sensitivity counterpart of the completed frozen-initialization fixed-50
Golovin ladder. It determines whether the former convergence result survives
when initialization is stochastic across ensemble members.

The registered configuration is
[`golovin_unfrozen_fixed50_extended_resolution_convergence.yaml`](../../config/golovin_unfrozen_fixed50_extended_resolution_convergence.yaml).
The generated matrix has 450 rows and immutable SHA-256
`55290906c22025f8a97f285dc5d4a3f90443ed90559b05a712f2629cf236d554`.

## Execution stages after one approval

| Stage | What happens | Requested compute ceiling | What must pass before next stage |
| --- | --- | --- | --- |
| A | Build exact committed revision | 8 physical cores, 4 GiB, 10 min | build manifest matches Git revision |
| B | Scheduler-layout probe | 8 physical cores, 12 GiB, 10 min | eight one-core steps start concurrently |
| C | Two real endpoint smoke members | 1 physical core, 4 GiB, 3 h | fresh input hashes, Zarr, Stage-0 readability, measured resource audit |
| D1 | Cases 0--249 (4,096--65,536; 250 paths, smoke path reused) | 8 physical cores, 6 GiB, 1 h | every member complete and resumable audit clean |
| D2 | Cases 250--299 (131,072) | 8 physical cores, 6 GiB, 2 h | same |
| D3 | Cases 300--349 (262,144) | 8 physical cores, 6 GiB, 4 h | same |
| D4 | Cases 350--399 (524,288) | 8 physical cores, 6 GiB, 8 h | same |
| D5 | Cases 400--449 (1,048,576; smoke path reused) | 8 physical cores, 6 GiB, 8 h | same |
| E | Stage-0, full convergence decision | 1 physical core, 4 GiB, 90 min | all 450 manifest/Zarr/diagnostic checksums valid |
| F | Operational ensemble-size reconstruction | 1 physical core, 4 GiB, 2 h | operational 50-member resolution result is known |
| G | Frozen-versus-operational paired comparison | 1 physical core, 4 GiB, 90 min | both compact analyses are complete |

Stages D1--D5 are submitted only after stage C has passed and the measured
smoke resource use is consistent with this plan. A failed member leaves a
marked incomplete path and stops its group; completed matching paths can be
reused on a later restart without recomputing them. The dependent analyses run
only after all five production groups succeed.

## Why the model uses allocation-level parallelism

One `collisions0d` box member is one MPI rank and one OpenMP thread. OpenMPI
is the launch/runtime interface; it cannot decompose this one grid box across
many ranks. The efficiency comes from eight independent serial members sharing
one node allocation, each bound to one physical core (`--hint=nomultithread`),
not from multithreading one member. Five grouped allocations therefore replace
450 tiny scheduler jobs.

## Resource estimate before the smoke measurement

The completed frozen matrix provides the appropriate baseline. Its 450 member
manifests sum to 125.39 member wall-hours at one core and 39.0 GB of Zarr.
The operational run adds fresh initialization writes but retains the same
physics, resolution/time grid and output structure.

- Expected model work: about 130--140 physical core-hours, including a
  conservative allowance for input generation.
- Requested model ceilings: 184 physical core-hours across the five grouped
  allocations (8 + 16 + 32 + 64 + 64), plus 3 core-hours for the smoke.
  A ceiling is not expected accounting use: an allocation stops when its work
  finishes.
- Expected raw scratch: about 45 GB (39 GB baseline Zarr plus several GB of
  member-local input binaries and manifests). The preflight requires 60 GB
  headroom beyond existing protected data for a conservative safety margin.
- Current global scratch filesystem state checked on 2026-08-03: 15 TB free
  of 15 TB. This is shared filesystem capacity, not a personal quota; it will
  be rechecked just before submission.

The 8-hour 524k/1M ceilings are intentionally based on the slowest prior
resolution groups and a runtime safety factor. They are not requests for
eight cores for eight hours of active model work if the groups finish earlier.

### Measured smoke revision

The completed 1,048,576-SD endpoint smoke used 0.33 GiB at its actual CLEO
step peak. Eight simultaneous members at that measured peak require about
2.64 GiB before controller and initialization overhead. The production request
is therefore revised from 12 GiB to 6 GiB: it retains substantial headroom,
while avoiding the shared-partition memory request that needlessly enlarged
the Slurm CPU allocation during the scheduler-only probe. The first completed
eight-worker group remains the operational check on this estimate; an OOM
failure stops its group and does not silently continue.

## Output and analysis products

Fresh model members live under:

```text
/scratch/m/m301324/SDM/CLEO-SDM-Convergence/
  golovin_unfrozen_fixed50_extended_resolution_convergence_v1_*/
```

Persistent records live under:

```text
/home/m/m301324/SDM/CLEO-SDM-Convergence-records/
  golovin_unfrozen_fixed50_extended_resolution_convergence_v1/
```

The final analysis creates:

- complete member manifests and Zarr inventories;
- member-level diagnostics and fixed-bin archives;
- time-zero operational-initialization fidelity table/decision;
- formal resolution convergence tables and figures;
- practical and supporting convergence-law diagnostics;
- the separately qualified 5--50 parent-pool ensemble-size reconstruction;
- paired frozen-vs-operational differences, variability ratios and figures.

No frozen raw output, initialization binary, run label or directory is
overwritten or reused. Only the frozen compact analysis is read afterwards for
the paired comparison.
