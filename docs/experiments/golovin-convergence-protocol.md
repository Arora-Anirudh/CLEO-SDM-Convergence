# Golovin convergence protocol

- Status: approved scientific direction; numerical tolerances provisional
- Scope: permanent-repository `collisions0d` Golovin calibration
- Model: pinned CLEO commit `83318c23223546d10759d202d70f4fa2f7fe4688`
- Execution mode: one MPI rank and one Kokkos/OpenMP thread per member
- Compute status: no convergence jobs authorized or submitted by this document

## 1. Purpose

This protocol defines the convergence study that must be completed before the
project begins a Long-kernel convergence ensemble.

Golovin is used as a **methodological calibration**, not as the final physical
cloud case. Its analytical mean-field solution makes it possible to test the
complete CLEO experiment and statistical workflow:

1. bias of the ensemble-mean droplet distribution;
2. stochastic spread between independent realizations;
3. convergence with collision timestep and superdroplet count;
4. precision of finite-member ensemble estimates;
5. sensitivity to superdroplet initialization;
6. computational and storage cost.

The resulting Golovin superdroplet threshold must not be transferred directly
to Long, KiD, ICON or LES configurations. Hydrodynamic-kernel lucky-drop
growth, transport, sedimentation, dynamics and precipitation introduce
different convergence requirements.

## 2. Research questions and estimands

The experiment will answer five questions.

### Q1. Analytical mean convergence

At each time, how closely does the ensemble-mean numerical mass-density
distribution reproduce the Golovin analytical solution?

The estimand is the bias of the ensemble mean, not the error of one realization.

### Q2. Finite-superdroplet variability

How does realization-to-realization spread change with the number of
superdroplets, \(N_\mathrm{SD}\)?

The Golovin analytical solution does not prescribe the physically correct
finite-volume variance. The measured spread is therefore reported as CLEO's
finite-\(N_\mathrm{SD}\) Monte Carlo variability, separately from mean bias.

### Q3. Ensemble-member requirement

What is the smallest ensemble size that estimates each required mean with the
pre-registered precision?

The answer may differ between the bulk distribution, low moments, high moments
and onset/tail metrics. The project will not impose one member count on every
diagnostic without evidence.

### Q4. Initialization dependence

How much do the inferred \(N_\mathrm{SD}\) and member requirements depend on
the way the initial superdroplet population represents the prescribed
continuous DSD?

Initialization variability and collision-stream variability are distinct
stochastic sources and retain separate recorded seeds.

### Q5. Cost

How do CPU time, elapsed time and raw/compact storage grow with
\(N_\mathrm{SD}\), timestep and ensemble size?

The final recommendation will report accuracy and uncertainty together with
cost. A numerically adequate setting that cannot be used in later model stages
is not an adequate project recommendation.

## 3. Fixed physical and software configuration

The first protocol iteration uses the version-controlled starting point in
`config/collisions0d_reference.yaml`, inherited from
`PerformanceTestingCLEO/src/collisions0d`.

| Quantity | Starting value |
| --- | ---: |
| Collision volumes | 1 |
| Box volume | \(10^{12}\,\mathrm{m^3}\) |
| Active microphysics | collision-coalescence only |
| Dynamics, movement and boundary conditions | null |
| Collision kernel | Golovin |
| Initial represented number concentration | \(8.388608\,\mathrm{cm^{-3}}\) |
| Initial wet-radius support | \(1\)-\(75\,\mathrm{\mu m}\) |
| Volume-exponential scale | \(30.531\,\mathrm{\mu m}\) |
| Minimum multiplicity | 10 |
| Nominal liquid-water content | approximately \(1\,\mathrm{g\,m^{-3}}\) |
| End time | \(3600\,\mathrm{s}\) |
| Observation interval | \(300\,\mathrm{s}\) |

This is a calibration configuration selected from Clara Bayley's reference
application. It is not yet a claim about a representative cloud droplet number
concentration, collision volume or final Long case.

Each experiment record must include:

- project and CLEO commits;
- materialized YAML and all changed parameters;
- executable, grid and initialization SHA-256 checksums;
- initialization and collision seeds;
- compiler, MPI, modules and Python environment;
- Slurm request, allocation and measured usage;
- raw-output and compact-diagnostic locations and sizes.

## 4. Diagnostic definitions

### 4.1 Distribution metric

The primary distribution metric is a fixed-bin relative L1 difference between
the numerical and analytical mass-density distributions:

\[
E_{L1}(t)=
\frac{
  \sum_b \left|g_{\mathrm{num},b}(t)-g_{\mathrm{ana},b}(t)\right|
  \Delta\ln r
}{
  \sum_b \left|g_{\mathrm{ana},b}(t)\right|\Delta\ln r
}.
\]

The formal convergence calculation must use:

- one pre-registered logarithmic-radius range;
- identical bin edges for all members, times and \(N_\mathrm{SD}\);
- the same analytical and numerical bin definitions;
- no \(N_\mathrm{SD}\)-dependent smoothing.

CLEO's official validation plot uses Gaussian smoothing
\(\sigma_{\ln r}=0.62N_\mathrm{SD}^{-1/5}\). That plot remains a required
visual verification, but its resolution-dependent bandwidth makes it
unsuitable as the sole formal convergence statistic.

Before execution, a development test must verify the fixed-bin implementation
on:

1. a synthetic distribution identical to its analytical reference;
2. a deliberately perturbed distribution;
3. the existing audited Golovin run.

### 4.2 Radius moments

For superdroplet multiplicity \(\xi_i\), wet radius \(r_i\), and box volume
\(V\),

\[
M_n(t)=\frac{1}{V}\sum_i \xi_i r_i^n.
\]

The protocol requires:

| Metric | Role |
| --- | --- |
| \(M_0\) | represented real-droplet number concentration |
| \(M_3\) | proportional to liquid-water content; conservation gate |
| \(M_6\) | reflectivity-like, strongly sensitive to the large-drop tail |

Reports must label these explicitly as **radius moments**. Literature that uses
mass moments \(\lambda_k\) must not be compared by index without converting the
definition.

Relative analytical moment error is

\[
E_{M_n}(t)=
\frac{M_{n,\mathrm{num}}(t)-M_{n,\mathrm{ana}}(t)}
     {M_{n,\mathrm{ana}}(t)}.
\]

If the current analytical utility does not expose the required moment, the
protocol must document whether it is calculated analytically, integrated from
the analytical fixed-bin distribution, or omitted.

### 4.3 Conservation gate

Liquid-mass drift is

\[
\delta_L(t)=\frac{L(t)-L(0)}{L(0)}.
\]

This is a software/invariant gate, not a convergence metric. The provisional
gate is

\[
\max_t |\delta_L(t)| \leq 10^{-7},
\]

which is looser than the approximately \(10^{-8}\) drift in the audited
single-member runs but strict enough to detect a meaningful regression. The
threshold must be confirmed before production.

### 4.4 Onset and tail metrics

Required in-box metrics are:

- mass fraction at \(r\geq40\,\mathrm{\mu m}\);
- \(t_{10}\), the first time at which at least 10% of liquid mass is at
  \(r\geq40\,\mathrm{\mu m}\);
- mass fraction above one pre-registered larger-radius threshold;
- mass-weighted 99th-percentile radius.

The observation interval must be sufficiently short to estimate \(t_{10}\) at
the desired precision. If the existing \(300\,\mathrm{s}\) interval is too
coarse, observation frequency must be changed before the production matrix;
linear interpolation cannot recover unresolved onset variability.

These are rain-growth or tail proxies. They are not surface precipitation
because the 0-D model has no sedimentation or fallout.

Maximum radius may be retained as a descriptive diagnostic but must not be a
primary convergence criterion because one exceptionally rare represented
droplet can dominate it.

### 4.5 Ensemble summaries

For every metric, time and experiment cell, retain:

- every member value;
- sample mean;
- sample standard deviation;
- standard error;
- two-sided 95% confidence interval;
- coefficient of variation where the mean is nonzero;
- number of valid members.

Confidence intervals for skewed tail and onset metrics will be checked with a
non-parametric bootstrap as well as the usual Student-\(t\) interval.

## 5. Initialization experiment families

### 5.1 Controlled representation family

Purpose: isolate collision-timestep, collision-stream and
\(N_\mathrm{SD}\)-representation error.

The preferred design is a stratified logarithmic-bin representation of the
prescribed continuous DSD:

- one radius representative per bin;
- multiplicities obtained from analytical DSD integrals;
- fixed target \(M_0\) and liquid mass/\(M_3\), to the documented precision
  permitted by integer multiplicities;
- the exact initialization binary frozen and reused across collision streams.

The implementation must be reviewed before use. It must not silently apply a
global radius rescaling, because that changes the DSD and collision
probabilities. Any integer residual adjustment must identify which bins are
changed and quantify the resulting moment errors.

At different \(N_\mathrm{SD}\), the initial discrete populations are different
representations of the same prescribed continuous distribution. Identical
numeric seeds across resolutions do not create paired stochastic histories.

### 5.2 Operational stochastic family

Purpose: measure the total variability of the current project workflow.

Each member is generated with:

- the present Clara-derived `collisions0d` initializer;
- a unique initialization seed;
- a unique collision seed.

Initial LWC, high moments and tail coverage are recorded. Their variation is
part of the operational uncertainty and must not be mistaken for collision-only
variability.

### 5.3 Crossed source-separation subset

At selected middle and high resolutions, generate multiple frozen
initializations and cross each with the same set of collision-stream indices.
This estimates:

- initialization main effect;
- collision-stream main effect;
- initialization-by-collision interaction/non-additivity.

The first planned crossed subset is \(10\) initializations by \(10\) collision
streams at one middle resolution. A second high-resolution matrix is run only
if the first decomposition materially changes the interpretation of the main
independent-member ensemble.

This factorial subset is variance attribution, not the main
resolution-convergence ensemble.

## 6. Staged experiment matrix

No stage begins until the preceding stage passes its audit and scientific
review.

### Stage 0: implementation and provenance gate

Required before model compute:

1. implement and unit-test fixed-bin Golovin diagnostics;
2. implement \(t_{10}\), analytical moments and ensemble summaries;
3. provide non-destructive member and matrix runners;
4. prove fresh-path refusal, resume behavior and manifest completeness;
5. verify one-thread same-seed replay remains byte-identical;
6. measure one development case's model time, full job time and storage.

### Stage 1: collision-timestep screening

Use \(N_\mathrm{SD}=16\,384\) and initially test:

\[
\Delta t_\mathrm{coll} =
2,\;1,\;0.5,\;0.25,\;0.1\,\mathrm{s}.
\]

Start with five independent collision members per timestep using a controlled
frozen initialization. The screen asks whether the mean differences between
neighboring timestep levels are smaller than the provisional metric margins.

If uncertainty is too large to decide, extend only the ambiguous timestep
levels. Choose the largest timestep that passes the pre-registered equivalence
criterion against the next smaller timestep and is confirmed by the following
level where available.

The literature's \(0.1\,\mathrm{s}\) finding for another model is evidence for
the ladder, not a substitute for this CLEO-specific test.

### Stage 2: controlled \(N_\mathrm{SD}\) ladder

With the accepted collision timestep, test:

\[
N_\mathrm{SD} =
512,\;1024,\;2048,\;4096,\;8192,\;16\,384.
\]

Start with 20 independent collision members per level. Reserve
\(N_\mathrm{SD}=32\,768\) for a case in which the highest planned pair has not
met or confirmed the convergence criteria.

### Stage 3: adaptive member extension

Analyze nested member prefixes:

\[
n=5,\;10,\;20,\;30,\;50,\;100.
\]

Only incomplete prefixes are run. A resolution/metric is extended beyond 20
members when:

- its confidence interval is wider than the registered precision target;
- bootstrap results show unstable mean or interval estimates;
- rare onset/tail events produce too many censored or undefined members;
- an equivalence conclusion changes materially with member prefix.

The protocol does not require 100 members for stable bulk metrics merely
because a tail metric needs 100.

### Stage 4: operational-initialization sensitivity

Repeat a reduced ladder selected from Stage 2 with both initialization and
collision seeds varying. At minimum it includes:

- the smallest provisionally adequate controlled resolution;
- one lower resolution;
- one higher/confirmation resolution.

Expand to the full ladder only if the initialization family changes the inferred
threshold or uncertainty materially.

### Stage 5: crossed source separation

Run the crossed subset from Sect. 5.3 only after the independent-member results
identify the resolutions and times at which source attribution is scientifically
useful.

## 7. Convergence and stopping rules

### 7.1 Provisional scientific margins

These values are proposals for confirmation with the researcher and Clara:

| Metric class | Equivalence/relative-bias margin | Maximum relative 95% CI half-width |
| --- | ---: | ---: |
| fixed-bin L1 and core mean moments | 5% | 5% |
| onset, high moment and tail metrics | 10% | 10% |
| liquid-mass drift | absolute \(10^{-7}\) gate | not applicable |

For an error metric whose ideal value is zero, precision is scaled using an
explicit nonzero scientific reference or reported as an absolute interval.
Relative CI width must not be divided by a mean statistically compatible with
zero.

### 7.2 Analytical agreement

For every required mean diagnostic with an analytical reference, the 95%
confidence interval for its relative bias must lie entirely within the
pre-registered equivalence margin.

### 7.3 Adjacent-resolution agreement

For \(N\) and \(2N\), form the confidence interval for the mean difference,
normalized by the analytical reference or another pre-registered scale. The
entire interval must lie within the metric's equivalence margin.

A non-significant null-hypothesis test, \(p>0.05\), is not evidence of
convergence. The experiment asks whether differences are demonstrably small,
not whether a small ensemble failed to detect them.

### 7.4 Confirmation requirement

A candidate minimum \(N_\mathrm{SD}=N\) is accepted for one metric only when:

1. the analytical-bias condition passes at \(N\);
2. \(N\) and \(2N\) are equivalent;
3. the conclusion is confirmed by the next available level or a documented
   sensitivity check;
4. the ensemble-precision condition passes;
5. all software/invariant gates pass.

The project-level recommendation is based on the strictest **required** metric,
not on the easiest bulk metric. Results will also retain a metric-by-metric
table so that a less expensive configuration can be chosen if a later model
stage does not require all tail diagnostics.

### 7.5 Stop or expand

Stop a ladder when all required metrics satisfy the confirmation rule and the
cost record is complete.

Expand resolution when the highest planned pair has not established
equivalence or analytical agreement.

Expand ensemble size when statistical precision is inadequate but the mean
trend suggests a plateau.

Revisit timestep or initialization when bias persists without systematic
improvement as \(N_\mathrm{SD}\) increases.

Report “not converged in the tested range” when the authorized maximum is
reached. Do not replace that conclusion with the highest tested value.

## 8. Compute and storage authorization gate

Before each Slurm submission, report:

- account and partition;
- nodes, tasks and CPUs per task;
- memory and walltime;
- serial/OpenMP/MPI/GPU mode;
- number of new members and resume behavior;
- measured basis for the request;
- estimated model CPU time, scheduler elapsed time and raw/compact storage.

The audited 4,096-SD Golovin smoke run reported approximately \(0.80\,\mathrm{s}\)
of CLEO model time, while its complete Slurm job took \(27\,\mathrm{s}\).
This demonstrates that job startup, input generation and I/O can dominate tiny
box runs. It is not sufficient to multiply model time alone.

Use one or both of:

- bounded Slurm arrays, with each task owning disjoint output paths;
- several sequential tiny members per allocation, with one rank/thread per
  member.

The final choice must be justified from a small matrix dry run. Raw Zarr belongs
on SCRATCH; compact manifests, tables, figures and checksums belong in the
permanent record. Raw deletion or archival is a later explicit decision, not an
implicit consequence of analysis.

## 9. Required products

Each completed stage produces:

1. validated per-member diagnostic table;
2. ensemble summary table with member count and uncertainty;
3. analytical-bias and adjacent-resolution equivalence table;
4. convergence figures showing members, means and 95% intervals;
5. timestep or \(N_\mathrm{SD}\) decision record;
6. runtime/storage inventory;
7. complete seed/configuration/commit/checksum manifest;
8. interpretation stating what did and did not converge.

The final Golovin report must state separate recommendations for:

- core distribution/moment means;
- high moments and onset/tail metrics;
- ensemble size for each class;
- controlled versus operational initialization;
- transfer limitations for Long and later model hierarchy stages.

## 10. Open decisions before Stage 0 is complete

The following remain explicitly provisional:

1. Clara's acceptance of 5% core and 10% onset/tail margins;
2. the exact large-radius tail threshold;
3. the observation interval needed for \(t_{10}\);
4. the controlled initialization construction and exact moment constraints;
5. whether the present 10-km-box physical parameters remain only a calibration
   case or should be replaced before the operational-initialization study;
6. the Levante project account and persistent storage boundary.

No production convergence ensemble should be submitted until these decisions,
the Stage 0 implementation, and the compute disclosure have been recorded.

## 11. Literature basis

- Shima et al. (2009), *QJRMS*, DOI
  [10.1002/qj.441](https://doi.org/10.1002/qj.441).
- Unterstrasser et al. (2017), *GMD*, DOI
  [10.5194/gmd-10-1521-2017](https://doi.org/10.5194/gmd-10-1521-2017).
- Dziekan and Pawlowska (2017), *ACP*, DOI
  [10.5194/acp-17-13509-2017](https://doi.org/10.5194/acp-17-13509-2017).
- Unterstrasser et al. (2020), *GMD*, DOI
  [10.5194/gmd-13-5119-2020](https://doi.org/10.5194/gmd-13-5119-2020).
- Morrison et al. (2024), *JAS*, DOI
  [10.1175/JAS-D-23-0132.1](https://doi.org/10.1175/JAS-D-23-0132.1).
- Zmijewski et al. (2024), *GMD*, DOI
  [10.5194/gmd-17-759-2024](https://doi.org/10.5194/gmd-17-759-2024).
- Yin et al. (2024), *GMD*, DOI
  [10.5194/gmd-17-5167-2024](https://doi.org/10.5194/gmd-17-5167-2024).
- Bayley et al. (2026), *GMD*, DOI
  [10.5194/gmd-19-6121-2026](https://doi.org/10.5194/gmd-19-6121-2026).

