# ADR 0009: prospective fixed-50 extended Golovin design

- Status: accepted for implementation by the researcher; Levante model
  submission pending explicit resource disclosure
- Date: 2026-07-31
- Scope: controlled 0-D Golovin collision-coalescence calibration
- Compute authorization: none at the time of this ADR

## 1. Decision

Run a new balanced resolution ladder with 50 independent collision streams at
each of nine superdroplet counts:

\[
N_{\rm SD}=4096,\ldots,1048576
\]

in factor-of-two steps.  The experiment contains 450 fresh model members.
It uses the already selected 0.1-s collision timestep, the controlled
initialization method, 300-s state output and the six registered decision
times from 600 through 3600 s.

No earlier model output, collision seed, run label, run directory or
controlled-bundle label is reused.  Each resolution receives one newly
generated, immutable and checksum-verified controlled-initialization bundle;
all 50 members at that resolution read those exact bytes.

The literal ratio of one error reduction to the previous error reduction is
excluded completely.  It is neither a selection rule nor a secondary
statistic.

## 2. Why 50 members is acceptable

Relative to ten members, 50 independent members reduce an ordinary
mean-estimator standard error by the ideal factor

\[
\sqrt{10/50}=0.447 .
\]

Thus the stochastic uncertainty should be about 55% smaller if the finite
variance and independence assumptions are adequate.  Fifty members also give
useful registered prefixes of 10, 20, 30, 40 and 50 for diagnosing whether
the decision is stable as the ensemble grows.

A common count at every resolution has three advantages:

1. resolution comparisons do not inherit different nominal ensemble sizes;
2. convergence-law fitting uses a homogeneous design over a long
   factor-of-two ladder; and
3. the method is easy to audit and explain.

Fifty is not claimed to be a universal or guaranteed-sufficient SDM ensemble
size.  The completed 100-member high-resolution experiment showed that some
late-time uncertainty bounds can remain limiting even at 100 members.  The
new fixed-50 study is therefore a prospectively frozen experiment: if its
confidence-bound criteria remain unresolved, the conclusion is
"not resolved at 50 members," not permission to weaken the criterion or
repeatedly inspect additional blocks with ordinary fixed-sample intervals.

## 3. Practical convergence decision

The primary decision retains ADR 0007:

1. all validity gates must pass;
2. for each primary 500-bin L1, signed \(M_0\) bias and signed \(M_6\) bias,
   the one-sided 95% bootstrap upper bound on the absolute change must not
   exceed one percentage point;
3. this must hold over two successive resolution doublings at every
   registered decision time; and
4. the decision and primary point estimates must be stable between the
   predeclared 40- and 50-member prefixes.

The one-percentage-point minimum worthwhile improvement is 20% of the
standing five-percentage-point analytical-error budget.  It is an absolute,
scientifically interpretable tolerance.  It must not be confused with the
rejected proposal to compare the newest improvement with 1% of the preceding
improvement.

The 250- and 1000-bin calculations remain mandatory sensitivity diagnostics.
They trigger investigation under ADR 0007 but do not each create an automatic
fine-bin veto.

## 4. Supporting convergence-law diagnostic

For L1 and the absolute \(M_0\)/\(M_6\) analytical biases, fit

\[
E(N)=E_\infty+a(N/N_{\min})^{-p}
\]

over the highest four, five and six resolution levels.  Independent
member-level bootstrap resampling propagates ensemble uncertainty into
\(E_\infty\), \(p\), and the predicted gain from one further doubling.

This calculation asks whether:

- the tested range remains consistent with continuing power-law-like error
  reduction;
- a non-zero residual floor is statistically identifiable; and
- the fitted interpretation is stable when the high-resolution window is
  changed.

The fit is explicitly not a selection gate.  A fitted floor can be
ill-conditioned, window-dependent or dominated by stochastic uncertainty.
The practical decision remains the validity-plus-equivalence rule above.

## 5. Why the successive-improvement ratio is excluded

For a power-law error \(E(N)=aN^{-p}\), the ratio of two successive
factor-of-two improvements approaches

\[
\frac{\Delta(2N)}{\Delta(N)}=2^{-p},
\]

not zero.  With Monte Carlo-like \(p=1/2\), it remains approximately 0.707
even when the absolute error is negligible.  In finite ensembles the ratio
is also unstable whenever the preceding observed improvement is small.
Consequently it does not answer the practical-error-budget question and
would add a confusing, non-actionable curve.

## 6. Measured-cost projection before submission

The completed ten-member screen measured 4.94 member CPU-hours for the first
eight levels and 7.10 GB of Zarr output.  Scaling those measured members to 50
projects approximately:

- 24.7 member CPU-hours and 35.5 GB for 4096--524288 SDs;
- approximately 30--36 additional member CPU-hours for 50 members at
  1048576 SDs, based on the two highest measured runtime doublings; and
- approximately 12--15 GB additional raw Zarr for the new highest level.

The current planning range is therefore roughly 55--61 member CPU-hours and
48--51 GB of new raw SCRATCH data.  These are estimates, not a Slurm request
or authorization.  A live capacity check, exact-build gate, fresh bundle
gate, absent-path gate and explicit allocation disclosure are required before
submission.

## 7. Interpretation boundary

This experiment may select a practical Golovin resolution for this box,
initialization, collision timestep, diagnostics, times and error budget.  It
cannot establish a universal SD count for Long-kernel collection, a dynamical
cloud, precipitation, a 1-D/2-D model or a different initialization.
