# Controlled Golovin calibration: manuscript-ready evidence statement

- Status: evidence synthesis; this is not a Long-kernel result
- Experiment: `golovin_controlled_high_resolution_convergence_v1`
- CLEO commit: `83318c23223546d10759d202d70f4fa2f7fe4688`
- Relevant compact records: `analysis_v4`, `practical_v2`,
  `adaptive_plan_v5`, and `variance_scaling_v1`

## 1. Purpose and scope

The collision-only Golovin box is a methodological calibration of the
project's CLEO workflow. It is deliberately not presented as a cloud case or
as a transferable Long-kernel resolution recommendation. Its particular value
is the available analytical mean-field solution: it permits a check of the
controlled initialization, seeded collision process, output analysis,
uncertainty calculation, and resolution-stopping logic before the project
encounters the more physically realistic but analytically unclosed Long
kernel.

The model contains one 0-D collision volume with null dynamics, movement, and
boundaries. Collision--coalescence is the only active physical process. The
initial volume-exponential droplet population is represented by a
deterministic controlled superdroplet initialization, conditioned to wet
radii 1--75 micrometres. The collision timestep is 0.1 s, the integration is
3600 s, and observations are written every 300 s. At every resolution, the
initialization is frozen and the 100 members differ only in their independently
recorded collision-RNG streams.

## 2. Quantities evaluated

The primary mean-solution quantities were:

1. the fixed-bin relative L1 error of the *ensemble-mean* mass-density
   distribution against the analytical Golovin distribution;
2. radius moment \(M_0\), the represented droplet number concentration;
3. radius moment \(M_6\), a strongly large-drop-tail-weighted,
   reflectivity-like quantity.

The analysis also enforces liquid-mass conservation, diagnostic-range
coverage, complete member provenance, and unique collision streams. L1 uses a
primary 500-bin logarithmic-radius grid, with 250- and 1000-bin grids as
robustness diagnostics. The ensemble mean is formed before L1 is calculated;
this avoids confusing the mean error of individual noisy members with the
error of the estimated mean distribution.

## 3. Completed high-resolution experiment

Four independent 100-member ensembles were completed at 16,384, 32,768,
65,536, and 131,072 superdroplets. The 400-member output contains 28.0 GB of
raw Zarr data on Levante SCRATCH and checksum-published compact analysis in
this repository.

All four resolutions passed the hard validity checks:

- every analytical L1 upper confidence bound remained below 5%;
- every \(M_0\) and \(M_6\) analytical-bias interval remained inside the
  registered 5% margin;
- maximum relative liquid-mass drift was below \(10^{-7}\);
- no material liquid mass lay outside the 1--5000 micrometre diagnostic
  range; and
- all seed, initialization-bundle, configuration, executable, and output
  checks passed.

At 3600 s, the primary 500-bin ensemble-mean L1 errors decreased from
1.937% to 1.425%, 0.983%, and 0.704% as resolution increased. All observed
mean changes in the final two doublings were below one percentage point.

## 4. What can and cannot be claimed

The strict prospectively stated practical-equivalence rule remains
**unresolved**, not passed. It requires the one-sided 95% bootstrap upper
bound on every primary adjacent-resolution change at every registered time to
be at most one percentage point, and it requires two successive doublings.
Late-time \(M_6\) uncertainty prevents this result at 100 members. This is a
precision limitation, not evidence of failed analytical accuracy or failed
mass conservation.

The evidence supports a separate, practically useful statement: 32,768 SDs
is the first **effect-size plateau candidate** for this controlled Golovin
case. It is not called a formally converged resolution because the strict
uncertainty criterion has not been met. Keeping these two statements separate
prevents an observed small point change from being mistaken for statistical
proof of equivalence.

## 5. Why the experiment is not extended merely to force a binary pass

The 40/60/80/100-member prefix analysis tests the planning assumption that the
variance of an ensemble estimate decays as \(1/n\). For the limiting 3600-s
\(M_6\) estimates, fitted log-variance slopes at 32,768, 65,536, and 131,072
SDs were -0.84, -1.10, and -0.93, respectively. The corresponding variance
coefficient ratios across prefixes were 1.20, 1.10, and 1.13. These are
consistent with the \(1/n\) planning approximation.

The check also showed that normal approximations are optimistic for nonlinear
L1 bounds by 0.05--0.31 percentage points; the formal L1 result therefore
retains percentile bootstrap intervals. Under the measured cost and the
validated variance model, the assurance-adjusted fixed extension projected to
certify the strict rule costs about 121 CPU-hours and 176 GB of new raw
output. A small additional wave of 50 members per active resolution would
cost about 10 CPU-hours but would not materially approach the strict bound.

The defensible result is consequently four-layered: analytical validity,
observed resolution effect size, finite-ensemble uncertainty, and the cost of
reducing that uncertainty. The literature basis for this separation is
recorded in [ADR 0007](../decisions/0007-proposed-diminishing-returns-convergence.md)
and [ADR 0008](../decisions/0008-adaptive-golovin-ensemble-extension.md).
In particular, SDM studies distinguish mean convergence from convergence of
stochastic variability; they do not supply a universal superdroplet or
ensemble threshold.

## 6. Limitation requiring explicit wording

The controlled initial distribution is truncated to 1--75 micrometres,
whereas the closed-form Golovin reference is not. The initial mismatch is
small (0.00413% mass-distribution L1 and \(2.97\times10^{-5}\) relative
\(M_3\) mismatch) compared with the late-time errors. It cannot explain the
unresolved strict criterion, but the comparison should be described as
*practically equivalent* rather than mathematically identical. A
support-sensitivity experiment would be appropriate before a final
publication claim.

## 7. Consequence for the Long-kernel stage

The Golovin conclusion validates a reproducible experimental framework. It
does not establish the required Long-kernel resolution. Before Long production
members are run, the project must freeze the Long initial distribution,
reference/comparator, tail or precipitation diagnostic, resolution ladder,
ensemble design, and stopping criterion. The fixed-10-member Golovin screen
described separately is an inexpensive computational-scaling and visual
resolution screen; it cannot replace the formal 100-member uncertainty result.
