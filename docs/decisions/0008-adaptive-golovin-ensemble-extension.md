# ADR 0008: pilot-informed Golovin ensemble extension

- Status: researcher authorized exploratory planning; model allocation not yet
  frozen or submitted
- Date: 2026-07-30
- Scope: controlled Golovin calibration only
- Compute authorization: analysis-only planning job; no CLEO model member

## 1. Decision

Use the completed 100-member ensembles at 32,768, 65,536 and 131,072 SDs as a
variance-and-cost pilot. Estimate how the one-sided uncertainty bound on each
registered adjacent-resolution change would contract under larger independent
ensembles, compare a balanced fixed final design with a cost-aware unequal
fixed final design, and publish the projection without calling it convergence
evidence.

The planner must not repeatedly apply ordinary 95% intervals after every new
member block and stop at the first passing result. Before additional model
members are examined for formal acceptance, choose one of:

1. freeze one final allocation and make the formal practical-convergence
   decision only at that allocation; or
2. prospectively implement a time-uniform confidence sequence or an explicit
   alpha-spending design for the planned interim looks.

The present implementation recommends the first option because it is simpler
to explain and audit in a methods section. A smaller first update to 150
members per active resolution may be used only to validate the variance model;
it is not an unadjusted formal early-stopping look.

The fixed-design projection targets **80% design assurance**: under the pilot
point estimates, variance coefficients, independence and normal approximation,
the planned final experiment should have 80% probability of placing the
one-sided 95% bound inside the one-percentage-point margin. Eighty percent is a
project planning choice, not an SDM standard. It is the lower commonly
illustrated assurance level in precision-based sample-size literature and is
reported explicitly so that a later paper can assess the trade-off.

## 2. Why an adaptive allocation is scientifically preferable

The unresolved practical decision is not symmetric:

- 16,384 SDs is already ruled out because its late \(M_6\) point change exceeds
  the one-percentage-point minimum worthwhile improvement;
- 32,768 SDs is the first plausible candidate;
- the remaining uncertainty comes from the two adjacent comparisons
  32,768--65,536 and 65,536--131,072;
- member cost increases strongly with SD resolution; and
- different metrics, times and adjacent pairs have different stochastic
  variances.

Adding the same arbitrary number of members everywhere is reproducible but may
spend expensive 131,072-SD simulations where a cheaper lower-resolution member
would reduce the limiting uncertainty more. Conversely, adding a higher SD
resolution would answer a different question and is not justified while the
observed upper-pair changes are already below the scientific margin.

## 3. Literature grounding

This design combines principles from SDM and statistical simulation
literature. No cited paper prescribes the exact member counts or the project's
one-percentage-point margin.

### 3.1 SDM evidence

Unterstrasser et al. (2017,
<https://doi.org/10.5194/gmd-10-1521-2017>) show that AON collision outcomes
can retain substantial ensemble fluctuation even after tens of realizations
and use hundreds of realizations to smooth Long-kernel distributions.
Unterstrasser et al. (2020,
<https://doi.org/10.5194/gmd-13-5119-2020>) use ensemble sizes that depend on
the diagnostic and configuration, including very large effective samples
when robust grid-box averages are required.

Morrison et al. (2024,
<https://doi.org/10.1175/JAS-D-23-0132.1>) use independent stochastic seeds,
separate stochastic variability from resolution behavior, and judge the
material size of changes after resolution increases. Zmijewski et al. (2024,
<https://doi.org/10.5194/gmd-17-759-2024>) explicitly separate convergence of
the ensemble mean from convergence of variance and show approximately
\(N_\mathrm{SD}^{-1/2}\) behavior for DSD variability. These studies support
estimand-specific ensemble planning; they do not support one universal
ensemble count.

### 3.2 Statistical-simulation evidence

Adam (1983, <https://doi.org/10.1287/mnsc.29.7.856>) frames simulation run
length as the sample size required to achieve a preassigned confidence
interval. That is the role of the current 100-member pilot: estimate variance,
then size the next fixed calculation against a predeclared precision target.
O'Neill (2022, <https://doi.org/10.1371/journal.pone.0262804>) shows why
treating a pilot variance estimate as known can understate the required sample
size. Dong et al. (2023, <https://pubmed.ncbi.nlm.nih.gov/36727203/>) define
assurance as the probability of achieving the prespecified confidence-interval
precision and demonstrate precision-plus-assurance planning. Their application
is different, but the distinction between expected precision and probability
of attaining it applies directly here.

Cost-constrained allocation methods assign more samples where variance
reduction per cost is greatest. Wright (2019,
<https://www.census.gov/library/working-papers/2019/adrm/RRS2019-03.html>)
derives this principle for stratified sampling. The present optimizer is an
application-specific discrete search rather than a claim of exact Neyman
allocation: each resolution contributes to two shared adjacent-comparison
constraints, so the coupling must be solved explicitly.

Howard et al. (2021, <https://doi.org/10.1214/20-AOS1991>) distinguish
time-uniform confidence sequences from fixed-sample confidence intervals.
Their coverage is valid across arbitrary stopping times; ordinary pointwise
95% intervals do not automatically acquire that property. This is why
exploratory block-by-block monitoring and formal acceptance are kept
separate.

## 4. Projection model

For each resolution \(N\), time \(t\), and primary metric \(q\), bootstrap the
current 100-member estimator and calculate

\[
a_{N,t,q}=100\,\widehat{\operatorname{Var}}\!\left(\hat q_{100}\right).
\]

The planning approximation is

\[
\operatorname{Var}\!\left(\hat q_n\right)\approx\frac{a_{N,t,q}}{n}.
\]

For independent ensembles at adjacent resolutions \(N_1,N_2\), project the
one-sided 95% bound

\[
U(n_1,n_2)
=
\left|\hat q_{N_1}-\hat q_{N_2}\right|
+z_{0.95}
\sqrt{\frac{a_{N_1}}{n_1}+\frac{a_{N_2}}{n_2}}.
\]

The point estimates are held fixed. Therefore the calculation answers:
“If the observed difference is representative and variance continues to
scale as \(1/n\), how many independent members would be needed to place the
upper uncertainty bound below 0.01?” It does not predict how the ensemble
means themselves will move.

The script records the difference between this normal approximation and the
current percentile-bootstrap bound. A poor current fit is a reason to distrust
the projection and validate it with another variance-only member block.

Sizing only until the **expected** bound touches the margin would give roughly
50% probability that a fresh realized bound passes. To target assurance
\(\gamma=0.80\), the fixed design instead requires

\[
\left|\hat q_{N_1}-\hat q_{N_2}\right|
+\left(z_{0.95}+z_{0.80}\right)
\sqrt{\frac{a_{N_1}}{n_1}+\frac{a_{N_2}}{n_2}}
\leq 0.01.
\]

This approximation accounts for the future point estimate moving as well as
the reported confidence allowance. It still conditions on the pilot estimates
and does not account fully for uncertainty in the bootstrap variance
coefficient; that limitation remains explicit.

## 5. Compared designs

1. **Balanced fixed final:** the same total member count at all three active
   resolutions. This is simple, auditable and directly compatible with the
   current common-prefix analyzer.
2. **Cost-optimized fixed final:** search integer allocations from 100 to 1000
   members in steps of five, use measured mean model wall time per resolution,
   and minimize projected added CPU time while every metric/time constraint
   passes.

The unequal design is not executable under the current formal protocol. If it
is chosen, freeze its exact counts and amend the analyzer before model
submission.

## 6. Outputs and interpretation limits

The non-overwriting planner publishes:

- bootstrap variance coefficients;
- measured per-member cost and storage;
- every metric/time projection constraint and its current
  normal-versus-bootstrap discrepancy;
- balanced precision curves;
- the cost-optimization frontier;
- exact fixed-design allocations and their limiting constraints; and
- a JSON decision that explicitly sets `new_model_compute_authorized=false`.

These are planning artifacts. They neither add independent stochastic evidence
nor change the current conclusion that no practical Golovin resolution has
yet been selected.

## 7. Applied result

The first checksum-published calculation (`adaptive_plan_v4`) intentionally
reported the boundary-touching expected-bound design. It found a
measured-cost allocation of 675/440/115 total members at
32,768/65,536/131,072 SDs, requiring 41.65 projected additional CPU-hours.
Because its two limiting \(M_6\) bounds were almost exactly 0.01, it implied
only about 50% design assurance and was not used to authorize model compute.

The amended canonical calculation (`adaptive_plan_v5`) targets 80% assurance.
Analysis-only Levante job `26556019` completed successfully and found:

| design | total members at 32,768 / 65,536 / 131,072 | new members | projected CPU-hours | raw Zarr |
|---|---:|---:|---:|---:|
| balanced | 1,325 / 1,325 / 1,325 | 3,675 | 247.71 | 257.26 GB |
| measured-cost optimized | 1,590 / 960 / 270 | 2,520 | 121.07 | 176.40 GB |

Late-time \(M_6\) remains limiting for both adjacent comparisons. Distribution
L1 and \(M_0\) are comfortably inside the planning margin at those
allocations.

The magnitude of the assurance-adjusted result is itself a decision-relevant
finding. No model job is authorized. Before spending 121 CPU-hours, use the
existing 40/60/80/100-member prefixes to test whether the fitted
\(\operatorname{Var}(\hat q_n)=a/n\) approximation is stable for the limiting
nonlinear \(M_6\) and L1 estimators. If it is not stable, the fixed-design
projection must be revised; if it is stable, the researcher can weigh the
explicit 80%-assurance cost against a prospectively justified relaxation of
the minimum-worthwhile-improvement rule.

### Existing-data model check

Before any new member is generated, apply the planner to the nested
40/60/80/100-member prefixes of the completed pool. At every registered time
and active resolution, recompute the actual nonlinear L1 estimator and the
scalar \(M_0\) and \(M_6\) estimators under 10,000 bootstrap resamples. Report:

1. the fitted slope of
   \(\log\{\operatorname{Var}(\hat q_n)\}\) against \(\log n\);
2. the stability of \(n\operatorname{Var}(\hat q_n)\);
3. the difference between the normal projected upper bound and the
   independently bootstrapped percentile bound.

This is a diagnostic, not a new acceptance gate. A slope near \(-1\), a
roughly stable variance coefficient and small normal-versus-percentile
differences would support the fixed-design approximation. The literature does
not provide a universal numerical pass threshold for these project-specific
nonlinear estimators, so the output must be interpreted quantitatively and
published without retrofitting a binary rule after seeing the result.

### Applied variance-scaling result

Checksum-published `variance_scaling_v1` reused the existing data in
analysis-only Levante job `26556375`. At 3600 s:

- \(M_6\) fitted log-variance slopes were -0.84, -1.10 and -0.93 at
  32,768/65,536/131,072 SDs;
- the corresponding \(n\operatorname{Var}(\hat q_n)\) maximum-to-minimum
  ratios over 40/60/80/100 members were 1.20, 1.10 and 1.13;
- the normal and percentile-bootstrap late-time \(M_6\) upper bounds differed
  by at most 0.0051 percentage points at 100 members.

These results support the planner's limiting \(M_6\) variance approximation.
They do not support replacing the bootstrap everywhere: for L1, the normal
upper bound was lower than the percentile-bootstrap bound by 0.05 to 0.31
percentage points across the inspected rows.

The evidence therefore does not justify a cheap variance-validation model
wave, and it does not make the 121-CPU-hour fixed design smaller. Do not launch
new Golovin members merely to force the one-percentage-point \(M_6\)
equivalence gate. Report the current result in three layers:

1. analytical validity passes at all tested high resolutions;
2. point-estimated changes across the final two doublings are below one
   percentage point;
3. strict one-sided \(M_6\) equivalence remains statistically unresolved at
   100 members, with the explicit assurance-adjusted cost published.

This is an evidence synthesis, not a declaration that the strict rule passed.
No new Golovin or Long model compute is authorized by this ADR.
