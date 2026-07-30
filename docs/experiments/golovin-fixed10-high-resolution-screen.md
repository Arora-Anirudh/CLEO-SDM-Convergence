# Fixed-10-member Golovin high-resolution screen

- Status: prepared design; no build, bundle, model, or analysis job submitted
- Experiment label: `golovin_fixed10_high_resolution_screen_v1`
- Purpose: inexpensive, independent resolution-screening and scaling evidence
- Not a replacement for: the completed 100-member formal uncertainty study

## 1. Question

With the collision-only controlled Golovin configuration held fixed, how do
the ensemble-mean distribution and tail-sensitive moments behave across a
much broader superdroplet ladder when every resolution has the same small
ensemble size of ten independent collision streams?

This screen serves two limited purposes:

1. provide a visually and computationally broad resolution trend through a
   substantially higher maximum SD count; and
2. measure the practical time, memory, storage, and scheduler behavior before
   Long-kernel production design.

It must not be used to replace the 100-member calculation's strict
uncertainty conclusion. Ten members are deliberately insufficient to certify
a one-percentage-point equivalence bound for late-time tail diagnostics.

## 2. Frozen physical and numerical conditions

All physical and numerical settings are inherited unchanged from the
controlled Golovin high-resolution experiment:

| Quantity | Value |
| --- | ---: |
| kernel | Golovin |
| active process | collision--coalescence only |
| spatial dimensions / collision volumes | 0 / 1 |
| dynamics, movement, boundaries | null |
| initialization | deterministic controlled representation of the same 1--75 micrometre volume-exponential population |
| collision timestep | 0.1 s |
| end time | 3600 s |
| observation interval | 300 s |
| model MPI ranks / Kokkos threads per member | 1 / 1 |
| ensemble members per resolution | 10 |

The only intentional numerical factor is `max_superdroplets`. Each resolution
gets a newly registered controlled bundle and ten fresh collision seeds. No
raw member, collision seed, bundle label, run label, or output directory from
the earlier runs is reused.

## 3. Resolution ladder

The prepared ladder is:

```text
4,096, 8,192, 16,384, 32,768, 65,536, 131,072, 262,144, 524,288 SDs.
```

It provides seven adjacent doublings and reaches four times the largest SD
count in the completed 100-member study. Starting at 4096 makes the lower
resolution trend visible with the same controlled initialization family;
including 524,288 tests a high-but-still practical 0-D case.

The upper level is a **feasibility target**, not an assertion that it is the
largest possible Levante calculation. It is included because a conservative
geometric extrapolation of the measured one-thread 131,072-SD wall time gives
an estimated 26.3 minutes per 524,288-SD member. If the required one-member
preflight exceeds 940 MiB, fails a numerical invariant, or takes materially
longer than this bounded estimate, the screen stops before the production
matrix and the upper resolution is revised transparently.

## 4. Resource estimate and parallel layout

The completed 100-member calculation measured mean per-member wall times of
50.2, 129.6, 204.5, and 393.9 seconds at 16,384 through 131,072 SDs. Extending
the conservative doubling assumption upward gives approximately:

| Resolution range | estimated serial model CPU-hours for 10 members per level |
| --- | ---: |
| 4,096--131,072 | 2.3 |
| 262,144 | 2.2 |
| 524,288 | 4.4 |
| **all eight levels** | **about 8.9** |

This is a planning estimate, not an allocation request. It excludes a
modest amount of manifest, initialization, and filesystem overhead. The
screen will use the existing four-worker runner: four independent serial
members run concurrently in one allocation. Expected elapsed time is roughly
2.5--3.0 hours; a 3.5-hour request is a safety limit, corresponding to at
most 14 allocated CPU-hours, while expected consumed model work is about
9 CPU-hours.

Previous raw Zarr stores used approximately 70 MB per member through 131,072
SDs. The new screen budgets 8 GB on SCRATCH to allow high-resolution output
growth; the live filesystem has about 13 TB free. The persistent HOME record
will contain only manifests, checksums, compact tables, and figures.

## 5. Analysis and interpretation

The normal controlled Golovin analyzer will calculate the same fixed-bin L1,
\(M_0\), \(M_6\), mass-drift, range-coverage, and bootstrap summaries. It
will use member prefixes 5 and 10 to show how the point estimates move when
the ensemble doubles from five to ten.

The screen's outputs will be labeled **exploratory fixed-10 resolution
screen**. They can establish:

- whether error and bulk/tail diagnostics continue to change materially with
  resolution;
- whether a visible plateau appears before 524,288 SDs;
- the cost and storage scaling needed to design the Long experiment; and
- whether any high-resolution implementation or invariant problem appears.

They cannot establish:

- strict one-percentage-point practical equivalence;
- a publication-ready uncertainty bound for late \(M_6\); or
- a transferable Long-kernel SD threshold.

## 6. Execution gates

Before the 80-member model screen:

1. build the exact committed project revision, even if only documentation or
   configuration changed, because the runner verifies its build manifest;
2. materialize and verify eight fresh controlled initialization bundles;
3. run one isolated 524,288-SD, one-rank/one-thread feasibility member;
4. inspect its exit status, maximum RSS, liquid-mass drift, range coverage,
   and output size; and
5. disclose the final Slurm request and storage estimate before submission.

The feasibility member is also a clean place to test whether the estimated
upper-resolution cost is realistic. It uses an independent seed and its own
label; it does not enter the ten-member screen analysis.

Its separate immutable matrix is prepared from
[`golovin_fixed10_high_resolution_feasibility.yaml`](../../config/golovin_fixed10_high_resolution_feasibility.yaml).
It reuses only the freshly verified 524,288-SD initialization bundle from the
screen preparation; it has a distinct collision seed, run label, run root and
persistent record directory.
