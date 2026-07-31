# ADR 0007: proposed practical diminishing-returns criterion

- Status: approved by the researcher for non-overwriting existing-data
  reanalysis; Clara review remains pending before new model data
- Date: 2026-07-30
- Scope: controlled Golovin calibration only
- Compute authorization: none

## 1. Why the existing rule needs review

The canonical `analysis_v4` rule asks every 95% confidence interval for every
adjacent-resolution fixed-bin L1 difference to lie inside a one-percentage-
point equivalence interval at all six times and at 250, 500 and 1000 bins.
This is a defensible high-stringency equivalence test, but it is a project
choice rather than a published SDM standard.

The current experiment already has strong evidence of numerical validity:

- all 16,384--131,072-SD levels pass the registered analytical and precision
  gates;
- liquid mass and analysis-range coverage pass;
- at 3600 s, primary 500-bin L1 errors decrease monotonically through
  1.937%, 1.425%, 0.983% and 0.704%;
- all absolute \(M_0\) and \(M_6\) ensemble-mean biases are below 1% at
  3600 s;
- the strict non-acceptance is caused by confidence bounds for adjacent
  histogram L1 differences, especially on the 1000-bin sensitivity grid.

Requiring more members until every fine-bin interval is contained would test
an increasingly precise histogram-equivalence question. It would not
necessarily answer the project's practical question: what is the smallest
resolution beyond which another doubling gives no scientifically material
improvement in the already accurate mean solution?

## 2. Literature basis

The proposal below is a synthesis, not a threshold copied from one paper.

1. Shima et al. (2009, <https://doi.org/10.1002/qj.441>) assessed the Golovin
   mean mass distribution with an \(N_\mathrm{SD}\)-dependent Gaussian kernel
   density estimate. \(2^{13}\) SDs agreed "fairly well" and \(2^{17}\)
   improved the result. The paper did not require unsmoothed fixed-bin
   confidence-interval equivalence.
2. Unterstrasser et al. (2017,
   <https://doi.org/10.5194/gmd-10-1521-2017>) showed that initialization can
   change the number of particles needed more strongly than particle count
   alone. It used ensembles and comparisons of distributions and moments, but
   no universal all-bin numerical margin.
3. Schwenkel et al. (2018,
   <https://doi.org/10.5194/gmd-11-3929-2018>) described a solution as well
   reproduced when increasing the number of superdroplets yielded only minor
   improvements. This is a direct precedent for a practical plateau argument,
   although its kernel, initialization and very large effective ensemble are
   different.
4. Morrison et al. (2024,
   <https://doi.org/10.1175/JAS-D-23-0132.1>) called a 0.7% change in total
   rain mass and a 1.0% change in rain flux after the final LES doubling
   "some evidence for convergence", contrasting them with approximately
   28% and 27% changes after the preceding doubling. In its separate box
   study, mean rain-initiation time changed by less than 3% over
   \(N_\mathrm{SD}=2048\)--8192. The authors still asked for additional runs
   before a definitive LES claim.
5. Zmijewski et al. (2024,
   <https://doi.org/10.5194/gmd-17-759-2024>) explicitly separated convergence
   of the mean from convergence of variance. In its box, the mean DSD
   converged near \(10^3\) SDs, while the DSD standard deviation continued
   decreasing approximately as \(N_\mathrm{SD}^{-1/2}\) through \(10^5\).
   Therefore a literal plateau of stochastic spread is not expected: a
   practical stopping rule must be tied to an accuracy budget and a target
   estimand.
6. Current CLEO papers describe and validate the Shima linear-sampling
   collision algorithm, but do not prescribe a universal convergence margin
   (Bayley et al., 2026,
   <https://doi.org/10.5194/gmd-19-6121-2026>).

The common pattern is to establish correctness against a reference, inspect
the quantities relevant to the application, and judge whether the last
resolution increase changes those quantities materially. Mean and variance
must not be forced to share one stopping rule.

## 3. Proposed prospectively frozen rule

This amendment can only be prospective relative to future model data; the
existing Golovin matrix has already been inspected. To avoid a post-hoc
threshold, the rule must be reviewed and frozen before any extra Golovin
members or resolutions are run.

### 3.1 Hard validity gate

For a candidate \(N\), all of \(N\), \(2N\) and \(4N\) must pass at every
registered decision time:

- primary 500-bin ensemble-mean L1 upper 95% confidence bound \(\le 5\%\);
- \(M_0\) and \(M_6\) analytical-bias 95% confidence intervals contained in
  \([-5\%,+5\%]\);
- maximum relative liquid-mass drift \(\le 10^{-7}\);
- out-of-range liquid-mass fraction \(\le 10^{-6}\);
- frozen-input, unique-collision-stream and complete-matrix provenance gates.

This prevents a flat but wrong numerical sequence from being labeled
converged.

### 3.2 Minimum worthwhile improvement

Define the absolute adjacent-resolution change, in percentage points, for
each primary diagnostic \(q\):

\[
D_q(N,t)=100\,\left|\hat q(N,t)-\hat q(2N,t)\right|.
\]

Here \(q\) is primary 500-bin L1, signed relative \(M_0\) bias, or signed
relative \(M_6\) bias. A one-percentage-point change is the **minimum
worthwhile improvement**:

\[
\delta_\mathrm{MWI}=1.0\ \text{percentage point}.
\]

This is 20% of the five-percentage-point analytical-error budget. Doubling
the number of SDs approximately doubles particle work and storage. If two
successive doublings each change every primary result by less than one fifth
of the already accepted error budget, the remaining gain is judged too small
for the calibration cost.

The candidate \(N\) passes diminishing returns only if, for both
\(N\rightarrow2N\) and \(2N\rightarrow4N\), the one-sided 95% bootstrap upper
confidence bound on \(D_q\) is no larger than 1.0 percentage point at every
decision time.

Using an upper confidence bound rather than only a point estimate guards
against declaring a plateau from an underpowered ensemble. Requiring two
successive doublings guards against choosing an accidental crossing or a
single non-monotonic step.

### 3.3 Ensemble sufficiency

Ensemble size is a precision parameter, not another physical resolution.
For each \(N\), calculate the complete decision at predeclared member prefixes
and repeated without-replacement subsets. The ensemble is adequate only when:

1. the analytical-validity decision is unchanged over the final two assessed
   member counts;
2. the diminishing-returns decision is unchanged over the final two assessed
   member counts; and
3. adding another member block changes no primary point estimate by more than
   1.0 percentage point.

If this fails, add independent collision members at the limiting resolutions;
do not automatically add a higher resolution.

### 3.4 Bin sensitivity

The 500-bin grid remains the prospectively registered primary estimand.
The 250- and 1000-bin results remain mandatory robustness diagnostics, but
they do not separately veto a practical decision solely because finer
histograms expose more finite-ensemble roughness. They trigger investigation
if they:

- reverse the resolution ordering;
- reveal an analytical error above 5%;
- reveal failed range coverage; or
- move the practical candidate by more than one factor-of-two resolution
  step.

This changes the role of alternative bin counts and therefore requires an
explicit protocol amendment if accepted.

## 4. What the current result says under this proposal

The rule has now been applied to the completed 100-member matrix. It selects
**no practical resolution yet**, but it substantially narrows the unresolved
question:

- every resolution passes the hard analytical, conservation, range and
  provenance gates;
- the complete decision and every primary point estimate are stable between
  80 and 100 members;
- all 250/500/1000-bin sensitivity checks pass without an ordering reversal
  or candidate disagreement;
- \(M_0\) passes the one-percentage-point diminishing-returns rule for every
  pair and time;
- primary 500-bin L1 passes for the two upper pairs, while
  16,384--32,768 fails at 3000 and 3600 s;
- \(M_6\) is limiting: 32,768--65,536 and 65,536--131,072 have 3600-s point
  changes of only 0.472 and 0.444 percentage points, but one-sided 95% upper
  bounds of 1.752 and 1.293 percentage points.

The 16,384--32,768 \(M_6\) point change at 3600 s is 1.672 percentage points.
Because the observed change itself exceeds the one-point margin, additional
members cannot make 16,384 SDs pass without a material shift in the ensemble
means. Therefore 16,384 is rejected as a candidate and 32,768 is the first
scientifically plausible, but not-yet-confirmed, practical resolution.

The remaining upper-pair failures are uncertainty failures rather than point-
estimate failures. Under a fixed-variance \(n^{-1/2}\) planning approximation,
the 3600-s \(M_6\) rows imply roughly 590 members per resolution for the
32,768--65,536 comparison and roughly 230 for the 65,536--131,072 comparison.
These are planning estimates, not new convergence evidence or an authorized
compute request; the actual extension must be staged and re-audited.

Canonical compact record:
`results/golovin_controlled_high_resolution_convergence_v1/practical_v2/`.
Its numerical CSV products reproduce the first calculation byte for byte.
The decision JSON differs only in the provenance path used to address the same
checksum-identical matrix. `practical_v2` replaces clipped figure layout; it
does not alter the method or decision.

## 5. Is the current Golovin experiment credible?

Yes, as a controlled numerical calibration, with two qualifications.

The high SD counts are not evidence of a broken CLEO run. Shima et al. used a
resolution-dependent smooth density estimator and qualitative curve
agreement. The present experiment asks a stricter question using common,
unsmoothed fixed bins, six decision times, independent ensembles and
confidence bounds. A 0.7%--1.9% primary L1 error is already strong analytical
agreement even though every adjacent fine-bin confidence interval is not
equivalent.

Golovin is idealized because its kernel has an analytical mean-field
solution, not because Monte Carlo sampling becomes deterministic. The rare
large-drop tail and the AON collision history remain stochastic. Published
work shows that mean DSDs can converge while DSD variance continues to fall
as \(N_\mathrm{SD}^{-1/2}\); demanding a literal variance plateau would
require indefinitely increasing resolution.

The qualification is that the controlled initializer is a 1--75 μm
**conditioned** exponential, while the implemented closed-form Golovin
reference is explicitly **untruncated**. A direct initial-distribution audit
finds:

- excluded number fraction: \(3.51\times10^{-5}\) below 1 μm and
  \(3.65\times10^{-7}\) above 75 μm;
- conditioned-versus-untruncated initial \(M_3\) difference:
  \(2.97\times10^{-5}\) relative;
- initial mass-distribution L1 mismatch: \(4.13\times10^{-5}\), or
  0.00413%.

This is two to three orders of magnitude smaller than the current numerical
L1 errors and cannot explain the present strict non-acceptance. Nevertheless,
the final methods must call the analytical comparison "practically
equivalent" rather than mathematically exact, or perform a dedicated support
sensitivity before publication.

## 6. Recommended next action

1. Review the rule and the existing-data result with Clara before new model
   data are generated.
2. If accepted, add independent collision-stream members only at 32,768,
   65,536 and 131,072 SDs in measured, restartable blocks. Recalculate the
   decision after each block rather than committing immediately to the
   asymptotic planning counts.
3. Do not rerun 16,384 SDs: its limiting 3600-s point change already exceeds
   the practical margin.
4. Add 262,144 SDs only if the better-powered 65,536--131,072 comparison still
   indicates a material improvement, or if 65,536 is to be tested as the
   candidate in a new 65,536/131,072/262,144 ladder.
5. Report the result as a **Golovin practical calibration for this box,
   initialization, timestep, diagnostics and cost model**, not as a universal
   SD-per-grid-box requirement and not as a Long/cloud-model threshold.
