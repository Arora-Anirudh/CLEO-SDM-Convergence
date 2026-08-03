# Retrospective ensemble-size adequacy for the fixed-50 Golovin archive

## Result

This analysis re-applies the complete registered primary 500-bin
`N/2N/4N` decision rule while projecting the statistical precision that
would be available with each integer ensemble size from 5 through 50.
It uses all 450 completed Stage-0 member diagnostics from the balanced
Golovin experiment (9 resolutions x 50 independent collision histories).
It does not run any new CLEO simulations.

The smallest **retrospectively supported tested** ensemble size that
selects `N_SD = 131072` and continues to select it at every larger tested
count is **18 members per resolution**.

The selection regimes are:

- 5--9 members: no candidate passes the complete rule;
- 10--17 members: the rule first selects `N_SD = 262144`;
- 18--50 members: the rule first selects `N_SD = 131072`.

The limiting gate at the 17/18 boundary is the 3600-s, 500-bin L1
equivalence interval for the `131072 -> 262144` comparison. The initial
10,000-resample screen placed this boundary close enough to the pass
threshold to require extra numerical checking. Three independent
200,000-resample streams were therefore pooled to 600,000 replicates at
counts 16, 17 and 18. Count 17 was rejected because the pooled normalized
worst bound was 1.00088 (a value no larger than 1 is required), while count
18 passed in the pooled result and in every independent stream, with a
pooled ratio of 0.97244.

## Interpretation boundary

The original experiment prospectively fixed 50 members per resolution;
that fixed-50 design remains the direct evidential basis of the formal
resolution result. The value 18 is a retrospective precision projection
conditional on this exact 50-member empirical parent pool, kernel,
initialization, timestep, output times, diagnostic bins, metrics and
tolerances. It is not a universal minimum, and it is not automatically
transferable to Long or to a different box-model configuration.

## Main products

- `ensemble_size_decision.json`: machine-readable headline result and
  prohibited claims.
- `selection_by_ensemble_size.csv`: selected base resolution at each
  tested member count.
- `projected_analytical_agreement.csv`: projected analytical and precision
  gates.
- `projected_adjacent_equivalence.csv`: projected independent-resolution
  equivalence intervals.
- `limiting_gate_by_ensemble_size.csv`: worst normalized gate by count.
- `boundary_refinement.csv`: independent and pooled 200,000-resample
  checks at counts 16--18.
- `golovin_ensemble_size_formal_adequacy.png`: supervisor-facing summary.
- `stage0_archive_hashes.csv` and `SHA256SUMS`: input and output integrity
  records.

The analysis design was frozen before inspecting these results in
`docs/decisions/0011-retrospective-ensemble-size-adequacy.md` and
`config/golovin_fixed50_ensemble_size_adequacy.yaml`.
