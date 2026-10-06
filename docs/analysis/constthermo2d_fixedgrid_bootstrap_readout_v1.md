# 2-D fixed-grid condensation--collision: high-resolution bootstrap readout

## Scope and audit boundary

This readout uses the compact aggregate cache created from the fully audited fixed-20 production cohort. Each resolution has 20 independent members, stored at 120-s intervals from 0 to 120 min. The ladder is expressed as SDs per initially populated grid box, `Ncell`; the domain initially contains 120 such populated grid boxes.

The tested resolutions are `Ncell = 2, 4, ..., 4096`. The 4096 cohort is the highest *tested* resolution, and is therefore an **internal operational comparator**. It is not independently established numerical truth. This analysis quantifies high-resolution agreement and finite-ensemble uncertainty; it does not assign a formal convergence number or a post-hoc pass/fail threshold.

## Method

For each diagnostic, the point estimate is the maximum over all post-initial stored times of the difference between two full 20-member ensemble means. For positive scalar diagnostics,

\[
\delta(t) = \frac{200\,|A(t)-B(t)|}{|A(t)|+|B(t)|}\quad [\%].
\]

For the mass DSD, each DSD is normalised to unit liquid-mass integral in log-radius bins, and the reported statistic is 100 times the usual total-variation distance:

\[
\mathrm{TV}(t)=50\sum_b |p_b(t)-q_b(t)|\quad [\%].
\]

Member-bootstrap uncertainty is obtained by independently resampling the 20 members of each side with replacement, recomputing the all-time maximum statistic, and repeating 2,000 times. The figures show the observed full-20 point estimate and the one-sided 95% upper bootstrap bound. This answers: *given these 20-member cohorts, how large might the discrepancy be because of finite ensemble sampling?* It does not remove discretisation bias or make the 4096 cohort exact truth.

## Readout of the finest tested transition

For the adjacent `Ncell=2048` to `4096` transition:

| diagnostic | observed (%) | 95% upper bound (%) |
|---|---:|---:|
| 500-bin mass-DSD total variation | 2.03 | 2.99 |
| \(\lambda_0\) | 0.176 | 0.337 |
| \(\lambda_2\) | 0.429 | 0.746 |
| \(\lambda_3\) | 0.759 | 1.56 |
| \(\lambda_6\) | 2.55 | 5.12 |
| mass-weighted terminal speed | 0.993 | 1.96 |
| mass-weighted \(r_{90}\) | 2.63 | 4.79 |

The number-, area-, and volume-related moments, plus mass-weighted terminal speed, are close across the last doubling. Quantities most sensitive to the detailed large-drop tail--the DSD shape, \(\lambda_6\), and \(r_{90}\)--are not yet negligible at the same level. This hierarchy is physically expected because high powers of radius amplify small differences in the sparse tail.

## DSD bin-resolution sensitivity

The simulation is unchanged when the diagnostic bin count changes; only the resolution at which distributional shape is examined changes. At `2048 -> 4096`, all-time mass-DSD TV is 1.03%, 2.03%, and 2.57% using 250, 500, and 1000 log-radius bins. Finer bins retain more fine-scale structure and expose a residual tail-shape difference that broad binning partly averages away. This cautions against declaring convergence from a single coarse DSD representation.

## Scientific interpretation and next decision

The fixed-20 ladder provides strong evidence of *approach toward* resolution stability. It supports using the 4096 ensemble as the current operational high-resolution trajectory for exploratory figures. It does **not** support a general statement that 2048, or even 4096, is numerically converged for every target diagnostic.

If a formal numerical-resolution selection is needed, the clean next step is an independent higher-resolution cohort (for example `Ncell=8192`) with the same 20-member protocol. The current 4096 cohort can then be evaluated against a comparator outside the current ladder, with stopping margins declared before the comparison. The existing results can support a diagnostic-specific operational choice, but that choice must state target quantities and allowable differences rather than claim universal convergence.

## Generated artifacts

- `results/analysis/constthermo2d_fixedgrid_bootstrap_v2/06_high_resolution_bootstrap_bounds.png`
- `results/analysis/constthermo2d_fixedgrid_bootstrap_v2/07_adjacent_doubling_dsd_bin_sensitivity.png`
- `results/analysis/constthermo2d_fixedgrid_bootstrap_v2/high_resolution_bootstrap_bounds.csv`
- `results/analysis/constthermo2d_fixedgrid_bootstrap_v2/adjacent_doubling_dsd_bin_sensitivity.csv`
