# ADR 0004: controlled Golovin initialization and convergence definitions

- Status: accepted for implementation and pilot validation
- Date: 2026-07-28
- Scope: Golovin calibration in the permanent research repository
- Compute authorization: none; this decision does not authorize a production
  ensemble

## 1. Decision

The Golovin study will use the following pre-registered definitions.

1. The core convergence family uses a deterministic, stratified
   logarithmic-volume initialization. It represents the prescribed continuous
   DSD with exactly controlled radius moments \(M_0\) and \(M_3\). It does not
   force \(M_6\).
2. The primary distribution diagnostic uses 500 fixed logarithmic-radius bins
   from 1 to 5000 μm. All resolutions, members and times use the same edges.
   Mass outside the range is measured and may not be silently discarded.
3. Convergence is established with confidence-interval containment inside
   pre-declared practical-equivalence margins, not with a failure to reject a
   null hypothesis.
4. Millimetre-tail timing is descriptive in the Golovin study, not a required
   convergence gate. Full superdroplet state remains stored every 300 s; the
   formal decision times are 600, 1200, 1800, 2400, 3000 and 3600 s.
5. Levante work may temporarily use account `bb1153`. Every submission must
   still disclose its complete resource request before it is made. The account
   is a scheduling/provenance choice, not part of the scientific result.

The numerical tolerances below are project choices informed by the literature.
They are not claimed to be universal SDM standards.

## 2. Controlled initialization

### 2.1 Target continuous distribution

The initializer represents the same prescribed exponential-in-volume DSD at
every \(N_\mathrm{SD}\). The initial wet-radius support remains 1–75 μm for
this Golovin calibration. Changing the physical DSD is a separate experiment
and must not be mixed with the numerical-resolution ladder.

For this controlled family, the exponential distribution is conditioned on
that finite support and normalized so that its integral equals the configured
initial number concentration. Its corresponding truncated-distribution
liquid mass is then a consequence of the prescribed DSD and is the \(M_3\)
target. This convention must be written into every initialization audit so it
is not confused with an untruncated exponential.

### 2.2 Construction

Let \(v=4\pi r^3/3\), let \(f_v(v)\) be the physical-droplet number-density
distribution per unit volume, and let \(V\) be the collision volume.

1. Divide the fixed support into exactly \(N_\mathrm{SD}\) bins equally spaced
   in \(\ln v\). Equal spacing in \(\ln v\) is also equal spacing in
   \(3\ln r\), so this is a log-radius stratification.
2. For every bin \(i=[v_i^-,v_i^+]\), analytically integrate:

   \[
   X_i=V\int_{v_i^-}^{v_i^+}f_v(v)\,dv
   \]

   for its target number of physical droplets and

   \[
   W_i=V\int_{v_i^-}^{v_i^+}v f_v(v)\,dv
   \]

   for its target liquid volume.
3. Convert the real-valued \(X_i\) to integer multiplicities \(\xi_i\) with a
   deterministic largest-remainder allocation. The allocation must preserve
   the rounded total physical-droplet count exactly and must never reduce a
   retained bin below the configured minimum multiplicity.
4. Assign the representative droplet volume

   \[
   \hat v_i=W_i/\xi_i
   \]

   and derive its radius from \(\hat v_i\).

This makes the sum of multiplicities—the discrete \(M_0\)—exact at the chosen
integer target. It also preserves the analytically integrated liquid
volume—and therefore \(M_3\)—apart from floating-point roundoff.

The implementation must verify that every representative volume lies inside
its source bin. If integerization makes that impossible, it must fail rather
than silently move a droplet across bins.

### 2.3 What is frozen

For one \(N_\mathrm{SD}\), the generated superdroplet binary, its SHA-256
checksum and its moment audit are frozen and reused for every collision-stream
member in the core timestep and resolution studies. “Frozen” therefore means
the identical time-zero discrete population, not merely the same continuous
DSD or the same nominal parameters.

At different \(N_\mathrm{SD}\), different discrete populations approximate the
same continuous DSD. They are reproducible and controlled comparisons, but
they are not paired droplet histories.

### 2.4 Moment constraints and gates

The controlled initializer must pass:

| Initial quantity | Requirement | Reason |
| --- | ---: | --- |
| relative \(M_0\) error | \(\le 10^{-10}\) | number is explicitly controlled |
| relative \(M_3\) error | \(\le 10^{-10}\) | liquid mass is explicitly controlled |
| relative \(M_6\) error | \(\le 1\%\) | verifies tail quadrature without forcing it |
| every representative | inside its source bin | prevents hidden DSD distortion |
| binary/checksum | identical across collision members | isolates collision randomness |

\(M_6\) is deliberately not matched. Forcing \(M_0\), \(M_3\) and \(M_6\)
simultaneously would change the within-bin representation or add another
optimization constraint. That could hide precisely the large-drop
representation error that \(M_6\) is intended to detect.

This construction replaces a global rescaling of sampled radii. A global
radius rescaling preserves neither the prescribed bin-integrated DSD nor the
collision probabilities within each bin.

### 2.5 Why this design

Unterstrasser et al. (2017, 2020) show that logarithmically stratified
single-SIP initialization represents the rare large-drop tail much more
efficiently than equal-weight sampling and that initialization can control the
subsequent collision solution. Dziekan and Pawlowska (2017), Schwenkel et al.
(2018), and Zmijewski et al. (2024) likewise use or favor one SD per logarithmic
size bin with DSD-derived multiplicity. Morrison et al. (2024) deliberately
scaled multiplicities to remove number-concentration variability and used
fixed size sampling across ensembles.

The papers do not specify this exact integer-allocation algorithm. It is a
project implementation choice that makes the desired constraints auditable.

The present stochastic Clara-derived initializer remains scientifically useful
as a later sensitivity family. It is not mixed into the core ladder because
doing so would combine DSD-sampling variability with collision-stream
variability.

## 3. Fixed distribution grid

### 3.1 Primary definition

The primary numerical and analytical mass distributions use:

- radius range: 1–5000 μm;
- 500 equal bins in \(\ln r\);
- identical edges at every time, member, timestep and \(N_\mathrm{SD}\);
- no resolution-dependent smoothing.

The normalized L1 error is calculated from bin-integrated mass, so the ideal
value is zero and an error of 0.05 means that the summed absolute binwise mass
difference equals 5% of the analytical total mass.

### 3.2 Coverage audit

An analytical Golovin audit of this calibration case found the following
fractions of analytical liquid mass inside 1–5000 μm:

| Time (s) | Fraction inside range |
| ---: | ---: |
| 0 | 0.999999999383 |
| 1200 | 0.999999999898 |
| 2400 | 0.999999999983 |
| 3600 | 0.999999999976 |

The range therefore excludes less than approximately \(6.2\times10^{-10}\) of
the analytical liquid mass at the audited times. The last digits depend on
numerical quadrature, so this is a coverage check, not a new analytical
solution.

Coalescence cannot create radii smaller than the initial minimum, while
5000 μm safely contains the analytical upper tail through 3600 s. The range
must nevertheless be checked against every numerical member because a
stochastic member may contain a rarer large representative than the mean-field
solution.

### 3.3 Range and discretization gates

1. At every stored time and for every member, the fraction of numerical liquid
   mass below 1 μm or above 5000 μm must be no more than \(10^{-6}\).
2. The diagnostic must report under-range and over-range mass separately.
3. The analysis must be repeated with 250 and 1000 bins. Relative to the
   500-bin result, the L1 value may change by at most 0.005 absolute and the
   convergence decision may not change.
4. If either gate fails, no range is enlarged or result clipped after seeing
   only the failing member. A wider common range or finer common grid must be
   registered and the complete comparison reanalyzed.

Five hundred radius bins provide about 135 bins per radius decade, equivalent
to about 45 bins per mass decade. This is comparable to the 40 mass bins per
decade used for fine SIP-distribution analysis by Unterstrasser et al. (2017),
while the 250/1000-bin sensitivity prevents that analogy from substituting for
an actual grid check.

## 4. Convergence criteria

### 4.1 Decision times

Time zero is an initialization gate. Formal post-initialization decisions use
600, 1200, 1800, 2400, 3000 and 3600 s. The stored 300 s output remains
available for plots and descriptive evolution.

A required metric must pass at every registered post-initialization decision
time. Passing only at the final time is not convergence over the simulated
evolution.

### 4.2 Analytical agreement

For an ensemble at one numerical setting:

| Diagnostic | Required 95% confidence-interval containment |
| --- | ---: |
| ensemble-mean fixed-bin L1 | upper bound \(\le 0.05\) |
| signed relative \(M_0\) bias | entirely inside \([-0.05,+0.05]\) |
| signed relative \(M_6\) bias | entirely inside \([-0.10,+0.10]\) |
| relative \(M_3\) drift | \(\max_t|\delta_L|\le10^{-7}\) for every member |

\(M_3\) is a conservation gate rather than a tunable accuracy margin because
closed-box coalescence conserves liquid mass.

### 4.3 Adjacent-level practical equivalence

For adjacent timestep levels or \(N_\mathrm{SD}\) levels:

| Difference in ensemble means | Required 95% confidence-interval containment |
| --- | ---: |
| fixed-bin L1 | entirely inside \([-0.01,+0.01]\) absolute |
| signed relative \(M_0\) | entirely inside \([-0.05,+0.05]\) |
| signed relative \(M_6\) | entirely inside \([-0.10,+0.10]\) |

The L1 plateau tolerance is one percentage point, deliberately tighter than
the 5% analytical-error ceiling. A solution is not called converged merely
because it is within 5% if doubling the representation still changes its
distribution error appreciably.

The confidence interval for each adjacent comparison must reflect independent
collision members. Identical initial binaries remove one stochastic source but
do not make collision histories paired.

### 4.4 Ensemble precision

The maximum allowed 95% confidence-interval half-width is:

- 0.01 absolute for mean L1;
- 0.025 of the analytical reference for \(M_0\);
- 0.05 of the analytical reference for \(M_6\).

If the mean passes an accuracy margin but its interval is wider than the
precision target, more members are required before a conclusion.

### 4.5 Confirmation

The minimum adequate level must:

1. pass analytical agreement and precision at every decision time;
2. be practically equivalent to the next finer level;
3. have the conclusion confirmed by one further level or by the documented
   grid/timestep sensitivity;
4. pass all initialization, range, conservation and provenance gates.

If the highest authorized level does not pass, the result is “not converged in
the tested range.”

### 4.6 Why these margins

The literature gives useful scale but no universal acceptance boundary:

- Morrison et al. (2024) described less than 3% change over their largest
  \(N_\mathrm{SD}\) range as nearly converged.
- Dziekan and Pawlowska (2017) found mean 40 μm conversion time within about
  1% of their reference around 1000 SDs, whereas 100 SDs differed by roughly
  10%.
- Zmijewski et al. (2024) found that a low moment could differ by only about
  0.5% while a higher moment differed by about 30% under an inadequate
  timestep.

This project therefore uses a 5% ceiling for the core mean distribution and
low moment, a stricter one-percentage-point plateau requirement for L1, and a
10% allowance for the tail-sensitive \(M_6\). These are intended to reject
10–30% errors clearly while remaining achievable for a practical stochastic
model. They must be reported alongside the results; they must not be presented
as thresholds established by the cited authors.

Using the entire 95% interval is conservative. A non-significant difference
does not establish equivalence: a wide interval can contain both zero and
scientifically unacceptable effects.

## 5. Tail timing decision

The Golovin production decision does not require
\(t_{1000\,\mu\mathrm{m},0.10}\).

Reasons:

1. Golovin already provides the stronger reference: the complete analytical
   mean distribution at every registered time.
2. \(M_6\), mass fraction above 1000 μm and the 99th-percentile mass radius
   diagnose large-drop growth without turning a 300 s sampling interval into
   an apparently exact crossing time.
3. In a closed 0-D box, the threshold is not surface precipitation or rain
   onset because drops neither sediment nor leave the domain.
4. A threshold-crossing time adds sensitivity to an arbitrary radius,
   arbitrary mass fraction and observation cadence.

The interval-censored value may still be reported descriptively. The project
will not increase full-state Zarr output frequency solely for it.

For the later Long study, where there is no analytical distribution solution,
a physically motivated tail-formation time may become a required diagnostic.
If so, its threshold must be chosen from the Long initial support and research
question, and a lightweight scalar observer should sample it at no more than
30 s intervals. Full superdroplet output need not be written that frequently.

## 6. Alternatives rejected

### Random initialization in the core ladder

Rejected because it combines initialization and collision-stream variability.
It remains a required sensitivity study after the controlled ladder.

### Equal multiplicity

Rejected for the controlled family because published SDM studies show
inefficient or biased representation of the rare large-drop tail.

### Matching \(M_6\) exactly

Rejected because it would suppress an intended tail-resolution diagnostic and
could distort the prescribed DSD.

### Resolution-dependent smoothing

Rejected for the formal statistic because changing the bandwidth with
\(N_\mathrm{SD}\) changes the diagnostic while testing the model.

### A \(p>0.05\) “no difference” rule

Rejected because low power and wide uncertainty can produce non-significance
even when scientifically important differences remain possible.

### Making millimetre-tail time a primary Golovin metric

Rejected because it is weaker than direct comparison with the analytical
distribution and is strongly cadence-dependent.

## 7. Consequences and next gate

Implementation update, 2026-07-29:

- the project-owned scientific constructor and CLEO attribute-generator
  adapter are implemented;
- local numerical tests pass through \(N_\mathrm{SD}=32768\);
- ten unit tests cover exact allocation, moment and bin gates, determinism,
  CLEO-compatible arrays, auditing, family-option refusal and deliberate
  failure;
- the native CLEO binary/readback, frozen-bundle reuse and compiled-model
  pilot remain pending;
- production compute remains unauthorized.

Before any production compute:

1. validate one native controlled binary and readback on Levante;
2. implement and verify one frozen binary bundle per resolution;
3. add numerical under/overflow and 250/500/1000-bin sensitivity summaries;
4. test the compiled model on a tiny single-member Levante pilot;
5. report the complete proposed `bb1153` Slurm request before submission.

Passing these gates validates the experiment machinery. It does not itself
establish Golovin convergence.

## 8. Evidence

- Shima et al. (2009), DOI
  [10.1002/qj.441](https://doi.org/10.1002/qj.441).
- Unterstrasser et al. (2017), DOI
  [10.5194/gmd-10-1521-2017](https://doi.org/10.5194/gmd-10-1521-2017).
- Dziekan and Pawlowska (2017), DOI
  [10.5194/acp-17-13509-2017](https://doi.org/10.5194/acp-17-13509-2017).
- Schwenkel et al. (2018), DOI
  [10.5194/gmd-11-3929-2018](https://doi.org/10.5194/gmd-11-3929-2018).
- Unterstrasser et al. (2020), DOI
  [10.5194/gmd-13-5119-2020](https://doi.org/10.5194/gmd-13-5119-2020).
- Morrison et al. (2024), DOI
  [10.1175/JAS-D-23-0132.1](https://doi.org/10.1175/JAS-D-23-0132.1).
- Zmijewski et al. (2024), DOI
  [10.5194/gmd-17-759-2024](https://doi.org/10.5194/gmd-17-759-2024).
