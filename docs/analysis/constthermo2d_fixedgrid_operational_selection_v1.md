# 2-D constthermo2d: retrospective operational resolution selection

## Scope and decision boundary

This record extends the fully audited fixed-20 normal-sampling resolution
ladder from 2 through 8,192 SDs per initially populated grid box
(Ncell). Each level has 20 independent members and 61 stored outputs from
0 to 120 minutes. There are 120 initially populated grid boxes, so the
selected Ncell corresponds to 120 Ncell initial domain SDs.

The rule below was applied **retrospectively** to the completed data. It is a
transparent operational selection, not a preregistered hypothesis test, not a
universal SDM resolution requirement, and not a proof against an independent
numerical reference.

## Comparator and support-comparability audit

Ncell=8192 is the highest completed level and is the internal high-resolution
comparator. It could not be initialized with the prior 3 nm--3 micrometre
sampling support because three sampled SDs received zero multiplicity. Its
audited support was therefore changed to 4 nm--2 micrometres.

The analytic support audit estimates that this correction excludes 0.000052%
of initial number and 0.00205% of initial mass. At the initial stored output,
the observed 4,096-versus-8,192 ensemble-mean differences are:

| quantity | difference |
|---|---:|
| 250-bin mass-DSD TV | 0.0159% |
| 500-bin mass-DSD TV | 0.0350% |
| 1,000-bin mass-DSD TV | 0.0747% |
| total droplet mass | 0.0020% |
| lambda2 | 0.00021% |
| lambda3 | 0.0020% |
| lambda6 | 0.337% |

Thus the support difference is explicitly visible and small in bulk mass/DSD
terms, but the two protocols are not described as literally identical. The
8,192-SD cohort remains a **support-corrected internal comparator**, rather
than numerical truth.

## Retrospectively applied rule

At every comparison, the statistic is the maximum over post-initial stored
times. For positive scalar quantities, the difference is the symmetric
percentage difference

\[
\delta(t)=\frac{200\,|A(t)-B(t)|}{|A(t)|+|B(t)|}.
\]

For the primary 500-bin mass DSD, total variation is evaluated after
normalising each distribution to unit liquid-mass integral in log-radius bins:

\[
\mathrm{TV}(t)=50\sum_b |p_b(t)-q_b(t)|.
\]

For every pair, the 20 members on both sides are independently resampled with
replacement 2,000 times. The criterion uses the one-sided 95% bootstrap
upper bound of the all-time maximum statistic.

The applied margins are:

- **5% core margin:** 500-bin mass-DSD TV, lambda0, lambda2, lambda3, and
  mass-weighted terminal speed.
- **10% tail margin:** lambda6 and mass-weighted r90.
- A candidate must satisfy every metric against 8,192 and in both of its
  consecutive adjacent doublings, N to 2N and 2N to 4N.
- The 250- and 1,000-bin DSD calculations remain diagnostic-resolution
  sensitivity checks; 500 bins is the primary decision representation.

The 5%/10% divisions are project-level operational margins: core statistics
measure the distribution/bulk trajectory, while lambda6 and r90 are
intrinsically more sensitive to sparse large-drop sampling. They should not
be presented as a universal physical tolerance.

## Gate results

Each entry below is the largest upper-bound/tolerance ratio across all required
metrics. Values at or below 1 pass. The limiting metric is given in
parentheses.

| Ncell | candidate vs 8,192 | N to 2N | 2N to 4N | outcome |
|---:|---:|---:|---:|---|
| 2 | 36.52 (lambda3) | 34.15 (lambda3) | 11.60 (lambda3) | fail |
| 4 | 15.27 (lambda6) | 11.60 (lambda3) | 8.37 (DSD TV) | fail |
| 8 | 8.25 (lambda6) | 8.37 (DSD TV) | 5.94 (DSD TV) | fail |
| 16 | 6.16 (lambda6) | 5.94 (DSD TV) | 4.13 (DSD TV) | fail |
| 32 | 3.46 (DSD TV) | 4.13 (DSD TV) | 3.27 (lambda6) | fail |
| 64 | 3.75 (lambda6) | 3.27 (lambda6) | 2.04 (DSD TV) | fail |
| 128 | 1.84 (lambda6) | 2.04 (DSD TV) | 1.46 (DSD TV) | fail |
| 256 | 1.23 (DSD TV) | 1.46 (DSD TV) | 1.02 (DSD TV) | fail |
| 512 | 0.95 (lambda6) | **1.02 (DSD TV)** | 0.75 (DSD TV) | fail |
| **1,024** | **0.60 (DSD TV)** | **0.75 (DSD TV)** | **0.59 (DSD TV)** | **pass** |
| 2,048 | 0.53 (DSD TV) | 0.59 (DSD TV) | 0.36 (DSD TV) | pass |

The selected level is therefore:

\[
\boxed{N_{\rm cell}=1{,}024}
\]

or **122,880 initial SDs over the whole 2-D domain**. The nearest lower
candidate, 512 SDs per populated cell, is close but fails the first adjacent
doubling: its 500-bin mass-DSD upper bound is 5.11% against the 5% core
margin.

## Physical-diagnostic corroboration

The original gate did not yet include the Bjorn-motivated terminal-speed
mass-transport proxy. The complete physical suite now evaluates geometric
surface area, liquid-equivalent water, Rayleigh reflectivity proxy,
mass-weighted terminal speed, and terminal-speed mass flux. For 1,024 versus
8,192, the largest one-sided 95% bootstrap-bound/tolerance ratio is 0.707,
from terminal-speed mass flux (3.53% against the 5% core margin). Thus these
additional physical diagnostics corroborate, rather than overturn, the
1,024-SD operational selection.

For the adjacent 512-to-1,024 transition, terminal-speed mass flux has a
6.46% upper bound against the same 5% margin. It independently supports the
decision to reject 512 as the selected operational resolution.

The visually checked physical readout and figures are in
results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/.

![Gate matrix](../../results/analysis/constthermo2d_fixedgrid_operational_selection_v5/01_operational_convergence_gate_matrix.png)

## Interpretation and limits

For this exact normal-sampling constthermo2d configuration, Ncell=1024 is
the smallest tested operational resolution that meets the stated ensemble,
metric, and double-doubling checks. This selection is appropriate for
subsequent experiments that target the same 120-minute 2-D trajectory and the
same diagnostic set.

It does **not** establish:

- convergence against a separate numerical solver or an infinitely resolved
  SDM calculation;
- a guarantee for a newly drawn 1,024-SD single realization;
- a universal resolution for different thermodynamics, kernels, domains,
  initialization strategies, or alpha sampling;
- a surface-rainfall conclusion. This configuration has null boundaries, so
  terminal-speed/transport diagnostics are not surface precipitation.

## Reproducible products

- Generator:
  scripts/select_constthermo2d_fixedgrid_convergence_v1.py
- Decision table:
  results/analysis/constthermo2d_fixedgrid_operational_selection_v5/selection_decisions.csv
- Metric-level bootstrap audit:
  results/analysis/constthermo2d_fixedgrid_operational_selection_v5/selection_pair_diagnostics.csv
- Machine-readable metadata:
  results/analysis/constthermo2d_fixedgrid_operational_selection_v5/metadata.json
