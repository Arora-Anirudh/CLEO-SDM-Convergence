# Literature review for extending the controlled Golovin convergence experiment

Date: 2026-07-29

## 1. Decision in one sentence

Do not begin a Long-kernel convergence experiment yet. Extend the controlled
Golovin experiment at the high-resolution end to

```text
N_SD = 16,384, 32,768, 65,536, 131,072
target ensemble size = 100 collision streams per resolution
```

while retaining the current initialization, collision timestep, diagnostic
times, 250/500/1000-bin calculations and all registered acceptance margins.
No previous member is reused: the first extension contains 400 fresh model
members under a new seed namespace, run root and bundle labels. If the
registered confidence intervals remain too wide, members are added
adaptively at the affected resolutions; if the highest-resolution adjacent
difference remains too large, the next resolution is 262,144.

This is a staged recommendation, not a claim that 100 members or 131,072
superdroplets must be sufficient.

## 2. What the first controlled matrix actually established

The completed experiment used six resolutions from 512 to 16,384
superdroplets, 20 independent collision streams at each resolution, one
frozen controlled initialization per resolution and a 0.1 s collision
timestep. All 120 model members, conservation checks, range checks and
analysis steps passed. The formal result was:

```text
no_resolution_accepted_in_initial_matrix
```

This is a scientific non-acceptance, not a failed run. The result separates
into two regimes:

- **bulk moments:** at 16,384, both relative \(M_0\) and \(M_6\) pass the
  analytical-accuracy and precision gates at all six decision times;
- **full distribution:** the fixed-bin L1 error decreases consistently with
  resolution, but its confidence bounds and adjacent-resolution differences
  do not satisfy the registered all-time/all-binning requirements.

At 3600 s the ensemble-mean L1 estimates are:

| \(N_\mathrm{SD}\) | 250 bins | 500 bins | 1000 bins |
| ---: | ---: | ---: | ---: |
| 512 | 0.2233 | 0.2614 | 0.3610 |
| 1024 | 0.1331 | 0.1720 | 0.2330 |
| 2048 | 0.0871 | 0.1333 | 0.1830 |
| 4096 | 0.0618 | 0.0790 | 0.1140 |
| 8192 | 0.0458 | 0.0619 | 0.0857 |
| 16,384 | 0.0397 | 0.0500 | 0.0666 |

The primary 500-bin point estimate at 16,384 is 0.04996, but its bootstrap
95% interval is [0.05577, 0.07815]. The registered rule uses the upper interval
bound, not the visually favourable point estimate. Its interval half-width is
0.01119, just above the 0.01 precision limit.

At 3600 s the 8192-to-16,384 L1 point differences are approximately:

| Bins | L1 difference | 95% interval |
| ---: | ---: | ---: |
| 250 | 0.00617 | [-0.00341, 0.03344] |
| 500 | 0.01193 | [0.00096, 0.04092] |
| 1000 | 0.01908 | [0.00687, 0.05540] |

More members can narrow these intervals, but they cannot make a true
0.019 difference fit inside the registered ±0.01 equivalence margin. Higher
resolution is therefore necessary as well.

## 3. What the literature says

No reviewed paper uses this project's exact formal rule: fixed 250, 500 and
1000 logarithmic bins, L1 after binwise ensemble averaging, all-time
confidence-bound accuracy, and adjacent-resolution equivalence. Published
thresholds therefore cannot be copied directly into this experiment. The
papers nevertheless provide a consistent explanation for the result and a
strong basis for the extension.

### 3.1 Shima et al. (2009)

Shima et al. introduced the SDM/AON method and used the Golovin analytical
solution as a collision-coalescence test. In their Golovin comparison,
\(2^{13}=8192\) superdroplets gave fairly good agreement and
\(2^{17}=131,072\) improved it substantially. A more difficult
hydrodynamic-kernel case required \(2^{21}\) superdroplets to sample the
important right tail adequately.

Their plotted distribution used a Gaussian kernel-density estimate with
bandwidth proportional to \(N_\mathrm{SD}^{-1/5}\). It is visually smoother
and is not equivalent to this project's common-edge fixed-bin L1 statistic.
The paper therefore supports extending toward 131,072 and expecting tail
sampling to be the limiting issue, but it does not establish that our formal
criterion will pass there.

Reference: Shima, S. et al. (2009), *QJRMS*,
[doi:10.1002/qj.441](https://doi.org/10.1002/qj.441).

### 3.2 Unterstrasser et al. (2017)

This rigorous box-model comparison shows that the initialization method and
the representation of rare large droplets strongly affect apparent
convergence. Their standard statistics use 50 realizations; some displayed
DSDs remain visibly noisy with 50 and become substantially smoother when
500 are used. Reusing one initialization reduces part of the spread but does
not remove the stochastic AON contribution.

The lesson is not that every CLEO result requires exactly 500 members. It is
that 20 is an initial screen rather than a strong final basis for a fine DSD,
and that initialization variability must remain separated from
collision-stream variability. Our controlled frozen-initialization design
already performs that separation.

Reference: Unterstrasser, S. et al. (2017), *GMD*,
[doi:10.5194/gmd-10-1521-2017](https://doi.org/10.5194/gmd-10-1521-2017).

### 3.3 Unterstrasser et al. (2020)

The column study normally uses 20 realizations, but its no-sedimentation
box-emulation averages 50 grid boxes over 20 realizations: 1000 statistically
independent boxes. The authors state that this is more than sufficient for
robust mean values. They also show that exchange between boxes by
sedimentation or redistribution can reduce the number of computational
particles needed per box.

Our 0-D box has no transport or box-to-box mixing. The favourable particle
counts in an interacting column therefore cannot be transferred to it. The
large effective sample used for the box-like mean supports increasing our
ensemble when the diagnostic of interest is the detailed mean DSD.

Reference: Unterstrasser, S. et al. (2020), *GMD*,
[doi:10.5194/gmd-13-5119-2020](https://doi.org/10.5194/gmd-13-5119-2020).

### 3.4 Morrison et al. (2024)

Morrison et al. use a deterministic initialization specifically to remove
initial-condition variability and isolate stochastic collision-coalescence,
which is conceptually aligned with our controlled frozen bundles. Their
ensembles generally contain 50 members; the more expensive full-sampling SDM
uses 20. They find that the relative ensemble spread decreases approximately
as \(N_\mathrm{SD}^{-1/2}\), while a box-model rain-initiation mean changes by
less than about 3% between 2048 and 8192 in their Hall-kernel configuration.

That result concerns a threshold time and a different kernel, DSD and
initialization. It supports a 50-or-more member precision study and the
expected inverse-square-root reduction in sampling error, but it does not
establish convergence of our complete Golovin DSD.

Reference: Morrison, H. et al. (2024), *JAS*,
[doi:10.1175/JAS-D-23-0132.1](https://doi.org/10.1175/JAS-D-23-0132.1).

### 3.5 Zmijewski et al. (2024)

This is the most directly relevant recent convergence study. In their box,
the mean DSD converges at approximately \(10^3\) superdroplets with their
log-bin initialization and a 0.1 s collision timestep, but DSD variance does
not converge to the one-to-one result: it decreases approximately as
\(N_\mathrm{SD}^{-1/2}\), even through \(10^5\) superdroplets.

Their ensemble size is deliberately coupled to resolution:

\[
\Omega =
\begin{cases}
10^6/N_\mathrm{SD}, & N_\mathrm{SD}\leq 100,\\
10^7/N_\mathrm{SD}, & N_\mathrm{SD}>100.
\end{cases}
\]

Thus the mean DSD is supported by an approximately fixed aggregate sampling
budget. Examples are 10,000 realizations at \(10^3\), 1000 at \(10^4\), and
100 at \(10^5\). Their published statement that the mean DSD converges at
\(10^3\) is therefore not evidence that 20 realizations are sufficient for
every DSD metric.

The paper's pattern is closely analogous to ours: low-order or ensemble-mean
quantities may look stable while the distributional variability continues to
shrink with resolution. It also confirms that convergence is
implementation-, initialization- and metric-dependent.

Reference: Zmijewski, P. et al. (2024), *GMD*,
[doi:10.5194/gmd-17-759-2024](https://doi.org/10.5194/gmd-17-759-2024).

### 3.6 Dziekan and Pawlowska (2017)

For stochastic-coalescence statistics, this study uses at least 1000
realizations for several threshold-time comparisons and 10,000 realizations
for a one-to-one reference distribution. Roughly \(10^3\) superdroplets can
give a good mean threshold time in their setup, while variability remains a
separate and more demanding target. Their analysis also motivates
logarithmically stratified initialization to represent rare large droplets.

This reinforces the distinction between convergence of a scalar mean and
convergence of a detailed distribution or its variance.

Reference: Dziekan, P. and Pawlowska, H. (2017), *ACP*,
[doi:10.5194/acp-17-13509-2017](https://doi.org/10.5194/acp-17-13509-2017).

### 3.7 Schwenkel et al. (2018)

Their box calculations average 25,344 boxes to obtain adequate statistics.
Without a splitting method, 500–1000 superdroplets per box are needed for
acceptable results in that configuration, and constant-weight initialization
gives large realization-to-realization differences because rare large
particles are poorly represented.

The numerical values are not portable to CLEO's controlled initialization,
but the study is strong evidence that detailed box-model DSD statistics can
require far more effective realizations than a scalar bulk diagnostic.

Reference: Schwenkel, J. et al. (2018), *GMD*,
[doi:10.5194/gmd-11-3929-2018](https://doi.org/10.5194/gmd-11-3929-2018).

### 3.8 Current CLEO validation

The CLEO numerical-methods paper reproduces the Shima et al. Golovin
distribution and distinguishes superdroplet counts by line width. It validates
the implementation qualitatively against the analytical curve, but does not
define a confidence-bound L1 threshold or an adjacent-resolution equivalence
rule. Our formal test is consequently stricter than the standard CLEO example.

Reference: Bayley, C. J. et al. (2026), *GMD*,
[doi:10.5194/gmd-19-6121-2026](https://doi.org/10.5194/gmd-19-6121-2026).

## 4. Interpretation of our result in light of the literature

Four conclusions are well supported.

1. **Moments can converge before a fine DSD.** Our all-time \(M_0\)/\(M_6\)
   success at 16,384 is compatible with the literature; it does not imply that
   every distribution bin or the distribution's variance has converged.
2. **Fine-bin L1 mixes residual bias and finite-ensemble roughness.** Finer
   binning exposes more stochastic structure, which explains the systematic
   250 < 500 < 1000-bin error ordering.
3. **Twenty members were appropriate for the first screen, not necessarily
   for the final DSD decision.** Several studies use 50, 100, 500, 1000 or far
   larger effective ensembles depending on the estimand.
4. **There is no universal literature threshold.** Statements such as
   “\(10^3\) SDs are converged” are conditional on kernel, initialization,
   collision volume, sampling algorithm, diagnostic, smoothing, time and
   ensemble size. They cannot override our registered test on a different
   controlled configuration.

An explicit web and paper search found no primary SDM study using this
project's exact all-time, all-bin-count L1 confidence-and-equivalence rule.
That rule remains useful because it is reproducible and difficult to satisfy,
but it must be described as project-specific rather than literature-standard.

## 5. Why the proposed extension uses 100 members

At 16,384 and 3600 s, scaling the observed interval half-width by the usual
\(1/\sqrt{\Omega}\) approximation gives:

| Bins | Current half-width, 20 | Expected at 50 | Expected at 100 |
| ---: | ---: | ---: | ---: |
| 250 | 0.01030 | 0.00651 | 0.00461 |
| 500 | 0.01119 | 0.00708 | 0.00500 |
| 1000 | 0.01364 | 0.00862 | 0.00610 |

These are planning estimates, not guaranteed bootstrap results. Fifty members
would probably satisfy the standalone 0.01 precision threshold at this one
time, but 100 provides:

- a safer margin across six times and three bin counts;
- a number at or above the common 50-member practice;
- consistency with Zmijewski et al.'s order-of-100 ensemble near
  \(N_\mathrm{SD}=10^5\);
- room to diagnose whether remaining failure is bias rather than interval
  width.

The stopping rule remains empirical: if 100-member intervals are still wider
than the registered limit, add members only at the limiting resolutions.

## 6. Why the proposed ladder extends to 131,072

A descriptive log-log fit to the final-time L1 values gives approximate
high-resolution decay exponents of \(N_\mathrm{SD}^{-0.32}\) to
\(N_\mathrm{SD}^{-0.39}\). Extrapolated point estimates are:

| \(N_\mathrm{SD}\) | 250 bins | 500 bins | 1000 bins |
| ---: | ---: | ---: | ---: |
| 32,768 | about 0.029–0.031 | about 0.034–0.040 | about 0.046–0.051 |
| 65,536 | about 0.022–0.025 | about 0.025–0.031 | about 0.033–0.039 |
| 131,072 | about 0.017–0.020 | about 0.018–0.025 | about 0.024–0.030 |

These values are descriptive projections, not acceptance evidence. They show
why stopping at 32,768 would be premature: the fine-bin accuracy and adjacent
equivalence gates are likely still close to or outside their margins.

The registered N/2N/4N confirmation rule also matters:

- 16,384 can be tested as a candidate only when 32,768 and 65,536 exist;
- 32,768 can be tested as a candidate only when 65,536 and 131,072 exist.

Extending through 131,072 therefore creates two complete candidate triples.
It also aligns with the improved Golovin resolution displayed by Shima et al.

## 7. Pre-registered follow-up design

### 7.1 Fixed elements

The extension must not change:

- collision kernel: Golovin;
- active physics: collision-coalescence only;
- controlled continuous initial DSD and moment constraints;
- one immutable CLEO-native bundle per resolution;
- collision timestep: 0.1 s;
- end time: 3600 s;
- stored output interval: 300 s;
- decision times: 600, 1200, 1800, 2400, 3000 and 3600 s;
- radius range: 1–5000 μm;
- fixed bin counts: 250, 500 and 1000;
- analytical, precision, conservation, coverage and adjacent-equivalence
  margins;
- independent-resolution bootstrap and N/2N/4N confirmation rule.

Keeping these fixed prevents a post hoc redefinition of convergence after
seeing the first matrix.

### 7.2 Active resolutions and members

| Resolution | Previous members used | New members | Final target |
| ---: | ---: | ---: | ---: |
| 16,384 | 0 | 100 | 100 |
| 32,768 | 0 | 100 | 100 |
| 65,536 | 0 | 100 | 100 |
| 131,072 | 0 | 100 | 100 |
| **Total** | **0** | **400** | **400** |

The completed 512–8192 results remain part of the archived baseline. They do
not receive additional members because their observed distribution bias is
well outside the acceptance limits; narrowing those intervals cannot make
them plausible candidates.

### 7.3 Staged stopping

1. Complete and analyze the four-level, 100-member active matrix.
2. If a candidate satisfies every registered rule, stop the Golovin extension
   and document the smallest accepted candidate.
3. If only confidence width fails, expand the affected resolutions from 100
   toward 200 members.
4. If the high-resolution point differences or accuracy remain outside the
   margins, add 262,144 superdroplets with 100 members so that 65,536 obtains
   an N/2N/4N confirmation triple.
5. Do not begin Long until a Golovin resolution is formally accepted or the
   project explicitly revises the scientific definition in a new,
   prospectively registered protocol.

## 8. Planning-level compute and storage estimate

The first 120-member experiment measured an approximately linear increase in
model wall time at the high-resolution end. A planning extrapolation gives
roughly:

- 16,384: 15 s per member;
- 32,768: 30 s per member;
- 65,536: 60 s per member;
- 131,072: 120 s per member.

The proposed 400 new members therefore represent about 6.25 CPU-hours of model
integration before queue/startup and analysis overhead. Running four
independent serial members concurrently in one restartable Slurm allocation
would ideally take about 1.5 hours; the eventual request should include
substantial overhead rather than assume ideal scaling.

Each existing Zarr member is about 70 MB because full superdroplet state is
stored. The fresh extension is therefore expected to create approximately
28.0 GB (26.1 GiB) of raw SCRATCH output. Compact diagnostics are much
smaller.

These are estimates only. Before any Levante submission, the exact account,
partition, nodes, tasks, CPUs, memory, walltime, concurrency, expected
storage, and absence of GPU use must be disclosed to the researcher.

## 9. Limitations

- A 100-member ensemble cannot guarantee that a strict all-time
  adjacent-equivalence interval will fit within ±0.01.
- Extrapolating L1 with a power law across three or four resolutions is a
  planning tool, not a physical convergence theorem.
- The controlled initialization removes initialization randomness within one
  resolution but not deterministic representation error between resolutions.
- This result will calibrate the CLEO/Golovin workflow. Its accepted
  \(N_\mathrm{SD}\) and member count still must not be transferred directly to
  Long, KiD, ICON or LES configurations.
