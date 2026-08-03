# ADR 0011: retrospective fixed-50 ensemble-size adequacy analysis

- Status: accepted for analysis by the researcher
- Date: 2026-08-03
- Scope: completed controlled 0-D Golovin fixed-50 archive only
- Compute authorization: analysis-only; no CLEO model and no Slurm job

## Decision

Use the complete archived pool of 50 independent collision histories at each
of the nine factor-of-two resolutions to estimate the smallest tested ensemble
size that would have supplied enough sampling precision for the original
formal resolution decision.

This is a retrospective precision and robustness analysis. It does not change
the prospective fixed-50 experiment and cannot prove a universal minimum
ensemble size.

## Estimand and tested member counts

Test every integer ensemble size from 5 through 50. For each size, project the
sampling intervals that would arise from a fresh ensemble of that size,
conditional on the empirical 50-member pool.

For distribution L1, use 10,000 nonparametric bootstrap ensembles sampled
with replacement independently at every resolution. The bootstrap index
streams are nested across member counts and independent across resolutions.
For signed moment biases, retain the original Student interval; for adjacent
moment differences, retain the original Welch interval, using the full-pool
sample means and variances with the tested member count.

The projected point estimate is the complete 50-member estimate. The interval
changes with ensemble size. This isolates the question "how many histories
were needed to estimate the same underlying ensemble response precisely?"
from the different question "what happened in one particular small subset?"

## Formal rule reproduced

At each tested member count, reapply the original primary 500-bin rule at all
six decision times (600--3600 s):

1. analytical agreement and confidence-interval precision must pass for
   (N), (2N), and (4N);
2. both (N\leftrightarrow2N) and (2N\leftrightarrow4N) confidence intervals
   must lie inside their adjacent-resolution equivalence margins; and
3. the smallest passing base resolution is selected.

The numerical margins remain unchanged: L1 analytical upper bound 0.05, L1
half-width 0.01, signed (M_0) and (M_6) analytical bounds 0.05, their
half-width limits 0.025 and 0.05, and adjacent margins 0.01/0.05/0.05.
Conservation and 1--5000-micrometre coverage remain hard validity gates.

The 250- and 1000-bin grids remain diagnostic-only, as specified in ADR 0009.
The archived analyzer accidentally accumulated their pass/fail values into
the formal resolution boolean despite labelling them diagnostic-only. Before
this analysis, a read-only audit confirmed that correcting the accumulator to
the intended primary 500-bin rule does not change the fixed-50 selection of
131,072 SDs. This implementation inconsistency must be corrected and recorded,
not silently propagated.

## Ensemble-size conclusion

Define the retrospective adequate count as the smallest tested member count
whose projected full formal rule selects the same 131,072-SD base resolution
as the prospective 50-member experiment and for which every larger tested
member count also selects 131,072 SDs.

This sustained-selection requirement prevents a single Monte Carlo boundary
crossing from being called adequate. The result must be phrased as the
"smallest retrospectively supported tested count for this archived Golovin
experiment," not as a mathematically proven or transferable minimum.

If the 10,000-resample result lies within 5% of a normalized pass boundary,
refine the boundary count and its immediate neighbours using three independent
200,000-resample streams. Pool all 600,000 draws for the final percentile
interval and require both the pooled interval and every independent stream to
give the same pass decision. This is a numerical Monte Carlo-stability gate;
it does not change the scientific margin.

## Reproducibility and non-goals

The analysis must verify the 450/450 Stage-0 archives, exact 9-by-50 matrix,
member/resolution/time uniqueness, analytical-array identity, input hashes and
deterministic bootstrap seed before calculating a result. It writes only new
compact CSV/JSON/PNG documentation. It does not modify raw Zarr data, rerun
CLEO, use Long, or revise the original prospective fixed-50 claim.
