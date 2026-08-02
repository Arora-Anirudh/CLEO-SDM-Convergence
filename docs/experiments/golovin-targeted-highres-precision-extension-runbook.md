# Golovin targeted high-resolution precision-extension runbook

## Scientific purpose

This is not a new general Golovin scan. It is one frozen follow-up to the fixed-50 result's sole practical-criterion ambiguity: the 3,600-s \(M_6\) upper bound for 262,144 to 524,288 SDs.

| Quantity | Existing members | New members | Final analysis members |
| --- | ---: | ---: | ---: |
| 262,144 SDs | 50 | 100 | 150 |
| 524,288 SDs | 50 | 100 | 150 |
| 1,048,576 SDs | 50 | 0 | 50 |

All members use Golovin collision-coalescence, controlled initialization, 0.1-s collision steps, 600-s output, and end at 3,600 s. No condensation, motion, coupling or fallout is enabled.

## What is new and what is frozen

- New: 200 collision seeds and output directories, member indices 50--149.
- Reused read-only: the two relevant controlled initialization bundles. This is scientifically required to preserve the controlled-initialization estimand; collision randomness, not the starting population, is extended.
- Preserved read-only: all original raw Zarr stores, matrix manifests and `analysis_v2` products.
- Unchanged: the 50-member 1,048,576-SD confirmation level.

## Required gates before the model job

1. Clean, committed and pushed source revision; exact revision built on Levante.
2. Matrix contains exactly 200 rows, only 262,144/524,288 SDs, indices 50--149, and no shared collision seed or run label with the fixed-50 matrix.
3. Both existing controlled bundles pass immutable checksum validation before and after every member.
4. Fresh extension raw and HOME-record paths are absent.
5. Live per-user scratch state is recorded and comfortably exceeds the projected 18.2 GiB new raw output.
6. Researcher has received the exact requested, expected and maximum resource disclosure.

## Model allocation

One `shared` allocation contains 20 concurrently active independent member steps. Each step is one MPI rank and one Kokkos/OpenMP thread; no member is split across MPI ranks. `--hint=nomultithread` prevents the two logical hardware threads of a Levante core from being mistaken for two physical cores.

The allocation requests 8 GiB node memory. A live scheduler check of the first
20-member retry showed individual steps at roughly 200--233 MiB plus about
557 MiB for the batch controller; 4 GiB was therefore insufficient and caused
two OOM kills. The resource-only correction to 8 GiB does not change any model
parameter, member matrix, seed, or scientific criterion.

The runner is restart-safe only for manifest-complete matching members. It does not overwrite incomplete output paths.

## After model completion

1. Run per-member Stage-0 fixed-bin diagnostics and verify each compact archive checksum.
2. Assemble a fresh, read-only combined analysis view. Its `runs/` entries are symlinks to the existing source member directories; no raw data is duplicated.
3. Summarize all 350 high-resolution members and run the analytical, adjacent-equivalence and targeted practical analyses.
4. Keep the original fixed-50 decision and this follow-up decision as separate provenance layers in the result record.

## Decision rule

At every registered 600--3,600-s decision time, both adjacent pairs must have one-sided 95% bootstrap bounds no larger than 0.01 for the 500-bin L1, \(M_0\), and \(M_6\) absolute changes. Analytical agreement, liquid-mass and radius-range gates are required as well. The 250/1000-bin results are reported as sensitivity analyses. The result is a targeted precision conclusion, not a retroactive replacement for the original fixed-50 protocol.
