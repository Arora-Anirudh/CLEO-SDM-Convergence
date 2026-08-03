# ADR 0012: operational-initialization Golovin sensitivity experiment

- Status: prepared; no Levante job submitted
- Date: 2026-08-03
- Scope: 0-D Golovin collision-coalescence only
- Decision owner: researcher-authorized exploratory follow-up

## Question

The completed fixed-50 Golovin experiment selected 131,072 SDs under its
registered N/2N/4N formal rule while holding the initial superdroplet binary
fixed at each resolution. That was intentional: it isolates stochastic
collision-coalescence variability. It does not answer whether the same result
is robust when each member begins with its own stochastic representation of
the same physical droplet population.

This experiment asks precisely that sensitivity question. It is not a Long
experiment and does not change the project-specific future box configuration.

## Design frozen before output inspection

- Nine resolutions: 4,096, 8,192, ..., 1,048,576 SDs.
- 50 members at each resolution: 450 fresh model members.
- One 0-D, 10-km-cube `collisions0d` box; Golovin collision-coalescence only.
- Baseline physical initializer remains Clara's `collisions0d` reference:
  1--75 micrometre logarithmic-radius sampling, exponential-in-volume
  population, 8.388608 cm-3 droplet concentration, minimum multiplicity 10.
- Collision timestep 0.1 s; observations every 600 s; end time 3600 s.
- One MPI rank and one OpenMP/Kokkos thread per member on a physical core.

The new matrix is
[`cases.tsv`](../../experiments/golovin_unfrozen_fixed50_extended_resolution_convergence_v1/cases.tsv),
SHA-256 `55290906c22025f8a97f285dc5d4a3f90443ed90559b05a712f2629cf236d554`.
Its manifest explicitly says `submission_authorized: false`.

## What is changed and what is held fixed

| Aspect | Frozen experiment | This operational experiment |
| --- | --- | --- |
| Initial superdroplet population | One immutable binary per resolution, reused for all 50 members | One fresh seeded binary for every member (450 total) |
| Collision seed | Independent per member | Exactly matched by resolution/member to frozen experiment |
| Physics, timestep, output cadence, resolution ladder, diagnostics, decision rule | Registered fixed-50 values | Identical |
| Raw Zarr and run directories | Read-only completed reference | Fresh, non-overlapping paths |

The paired collision-seed schedule reduces avoidable Monte Carlo noise in the
comparison. It does **not** make the collision events identical: changing the
initial population changes the particle state and therefore subsequent
collision probabilities.

## Statistical interpretation

This operational matrix estimates the combined variability from:

1. stochastic initial SD representation;
2. collision RNG; and
3. their interaction during coalescence.

It does not attribute those components separately. A later crossed design
(several collision streams for each frozen initial population) would be needed
for a variance decomposition, and is deliberately not part of this first
experiment.

Time-zero is a hard validity gate only at the **ensemble** level. At each
resolution, we will calculate the ensemble-mean DSD L1 mismatch and signed
ensemble-mean M0, M3 and M6 biases at 0 s. Their 95% bounds must lie within
the registered 5% margins. Individual member time-zero differences are
expected and are descriptive, not failures by themselves. Each operational
input binary's SHA-256 is recorded and must be unique across the matrix.

The downstream formal convergence decision is unchanged: at every
600--3600-s time, analytical agreement, precision, conservation/range, and
two adjacent equivalence gates must pass for N, 2N and 4N. The first eligible
N is selected. If full-50 operational analysis selects a resolution, a
separate analysis-only adequacy reconstruction tests every projected member
count 5--50 against that new full-50 selection; it does not reuse the frozen
experiment's 18-member result.

## Safety and resource gates

No full matrix can run until all of these are true:

1. exact Git revision is committed/pushed and rebuilt on Levante;
2. local unit, formatting and shell-syntax checks pass;
3. live scratch and account state are checked again immediately before
   submission;
4. two genuine endpoint members (4,096 and 1,048,576 SDs) pass the smoke
   gate, including fresh input hashes, output/Zarr presence and Stage-0
   readability; and
5. measured smoke runtime/memory are reviewed before production groups are
   launched.

The production matrix is grouped into five restartable allocations, not 450
Slurm jobs: cases 0--249, 250--299, 300--349, 350--399 and 400--449. Each
group runs eight exclusive serial members on eight physical cores. Successful
smoke members are retained and skipped by the relevant production group.

## Non-claims

The result will not be described as a universal SD or ensemble requirement,
proof of Long convergence, a cloud-scale recommendation, or a separation of
initialization from collision variability.
