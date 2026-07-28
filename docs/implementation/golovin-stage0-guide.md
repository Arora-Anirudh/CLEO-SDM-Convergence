# Golovin Stage-0 implementation guide

This guide explains the software added before the permanent-repository Golovin
convergence study. It is written for a reader who has not followed the coding
session. It answers four questions:

1. What problem are we solving?
2. What does each new calculation mean physically and statistically?
3. How do the files move information from one CLEO member to an ensemble
   result?
4. What is implemented, tested, provisional or still unvalidated?

The governing scientific design is the
[Golovin convergence protocol](../experiments/golovin-convergence-protocol.md).
This document explains its Stage-0 software implementation. It is not a
convergence result.

## 1. Why Stage 0 is necessary

A convergence experiment cannot be repaired after model output has been
generated if its bins, seeds, thresholds or stopping rules were ambiguous. A
large ensemble is useful only when:

- every member has a complete and unique identity;
- all resolutions are compared with the same diagnostic definition;
- initialization and collision randomness are controlled and recorded
  separately;
- existing results cannot be overwritten accidentally;
- statistical summaries preserve the individual member values;
- analytical and conservation checks can expose a software error before a
  physical conclusion is made.

Stage 0 therefore builds and tests the measurement and execution machinery
before requesting production compute.

## 2. Why the existing CLEO plot is not the only convergence metric

CLEO's official Golovin validation plot is still valuable. It reads the real
model output, constructs a mass-density distribution and overlays the
analytical solution. Its numerical curve is smoothed with

\[
\sigma_{\ln r}=0.62N_\mathrm{SD}^{-1/5}.
\]

The bandwidth changes with the number of superdroplets. Consequently, changing
\(N_\mathrm{SD}\) changes both the simulation and the measuring instrument.
That is appropriate for a readable validation figure, but it can make a formal
resolution comparison unfair.

The Stage-0 implementation keeps the CLEO plot as a visual check and adds a
second, formal distribution diagnostic with:

- the same radius minimum and maximum for every run;
- the same number and edges of logarithmic-radius bins;
- no smoothing;
- explicit accounting of mass outside the registered radius range.

The two diagnostics answer different questions:

| Diagnostic | Question |
| --- | --- |
| official CLEO smoothed plot | Does the simulation have the expected overall Golovin evolution? |
| project fixed-bin L1 metric | Does numerical error decrease under one unchanged measuring rule? |

## 3. Complete data flow

```text
version-controlled YAML template
            |
            | explicit N_SD, timestep and path overrides
            v
materialized per-member config.yaml
            |
            +--> seeded Python initializer --> grid.dat + superdroplets.dat
            |
            +--> seeded CLEO executable --> setup.txt + Zarr trajectory
                                           |
                                           v
                              per-member Stage-0 analyzer
                                           |
                     +---------------------+----------------------+
                     |                                            |
          member_time_diagnostics.csv                    member_summary.csv
          one row per stored time                        one row per member
                     |                                            |
                     +---------------------+----------------------+
                                           |
                                           v
                                 ensemble summarizer
                                           |
                     +---------------------+----------------------+
                     |                                            |
             all individual values                  mean, SD, SE, Student CI,
             retained verbatim                      bootstrap CI, CV, valid n
```

At no point does analysis modify the configuration, inputs or Zarr output.

## 4. The development configuration

[`config/golovin_stage0_development.yaml`](../../config/golovin_stage0_development.yaml)
contains one visible location for the Stage-0 settings.

The current development values are:

| Setting | Development value | Meaning |
| --- | ---: | --- |
| radius range | 1-5000 μm | fixed interval used for the formal distribution |
| number of log-radius bins | 500 | same 500 edges for all members and resolutions |
| cloud-drop threshold | 40 μm | radius used by the onset mass fraction |
| larger-drop threshold | 1000 μm | provisional tail proxy |
| onset fraction | 0.10 | `t10` occurs when 10% of liquid mass is at least 40 μm |
| mass-weighted quantile | 0.99 | radius below which 99% of represented mass lies |
| confidence level | 0.95 | interval level for ensemble means |
| bootstrap resamples | 10000 | deterministic non-parametric uncertainty check |

The file says `development_only` and
`approved_for_production: false`. The matrix preparation tool refuses any
status other than `development_only`. This prevents an implementation example
from being mistaken for an approved production design.

The 1-5000 μm range and 1000 μm tail threshold are practical development
values inherited from the audited example diagnostics. They remain decisions
to confirm before production. Every member records the fraction of mass below
and above the fixed-bin range so that an inadequate range cannot remain hidden.

## 5. Fixed-bin mass-density distribution

For superdroplet \(i\):

- wet radius is \(r_i\);
- multiplicity is \(\xi_i\);
- single-droplet water-equivalent mass is \(m_i\);
- collision-box volume is \(V\).

The represented liquid mass in logarithmic-radius bin \(b\) is

\[
L_b=\sum_{i\in b}\xi_i m_i.
\]

The mass density per unit natural-log radius is

\[
g_{\mathrm{num},b}
=\frac{L_b}{V\,\Delta\ln r_b}.
\]

The code uses `numpy.histogram` with precomputed logarithmic edges. It does not
estimate a kernel-density curve and does not use \(N_\mathrm{SD}\) when
constructing the measuring grid.

For consistency with CLEO's Golovin validation utility, \(m_i\) in this
distribution is the mass of a liquid-water sphere with the stored wet radius
(`water-equivalent` mass). The separate conservation diagnostic uses CLEO's
water-mass calculation, which excludes solute mass. The reference dry radius
is negligible, but the two definitions remain explicitly separate.

The formal relative L1 error is

\[
E_{L1}
=
\frac{\sum_b |g_{\mathrm{num},b}-g_{\mathrm{ana},b}|\Delta\ln r_b}
{\sum_b |g_{\mathrm{ana},b}|\Delta\ln r_b}.
\]

Interpretation:

- \(E_{L1}=0\): numerical and analytical values are identical in every
  registered bin;
- smaller values indicate closer overall mass-distribution agreement;
- it does not show which radius range contributes the error;
- it is sensitive to the registered radius interval, so that interval is part
  of the scientific definition and is recorded.

### Overflow audit

The diagnostic separately reports:

- `fixed_bin_mass_below_range_fraction`;
- `fixed_bin_mass_above_range_fraction`.

A low L1 value is not accepted blindly if substantial simulated mass has moved
outside the registered interval.

## 6. Golovin analytical distribution

The function `golovin_analytical_mass_density()` in
[`scripts/golovin_stage0.py`](../../scripts/golovin_stage0.py) implements the
same Bessel-function Golovin solution as the pinned CLEO
`plotcleo.shima2009fig.golovin_analytical()` function, but evaluates it at the
centres of the project's fixed bins.

This was checked locally against the exact CLEO commit pinned by the project at
0, 1200, 2400 and 3600 s. For 500 bins from 1 to 5000 μm:

| Time | maximum absolute difference |
| ---: | ---: |
| 0 s | \(5.44\times10^{-15}\) g m\(^{-3}\) per unit \(\ln r\) |
| 1200 s | \(3.46\times10^{-14}\) |
| 2400 s | \(4.66\times10^{-14}\) |
| 3600 s | \(7.98\times10^{-15}\) |

All arrays passed `numpy.allclose` with relative tolerance
\(2\times10^{-13}\). These are floating-point roundoff differences, not
physical discrepancies.

## 7. Radius moments

The project uses radius moments:

\[
M_n(t)=\frac{1}{V}\sum_i \xi_i r_i^n.
\]

Radii are stored in micrometres in the diagnostic table.

| Column | Units | Physical sensitivity |
| --- | --- | --- |
| `radius_moment_0_m3` | m\(^{-3}\) | total represented real-droplet number concentration |
| `radius_moment_3_um3_m3` | μm\(^3\) m\(^{-3}\) | proportional to total liquid volume/mass |
| `radius_moment_6_um6_m3` | μm\(^6\) m\(^{-3}\) | strongly weights the rare large-drop tail; reflectivity-like |

These are not indexed the same way as mass moments \(\lambda_k\). Because
droplet mass is proportional to \(r^3\), \(M_3\) corresponds to the first mass
moment and \(M_6\) to the second mass moment.

For the untruncated exponential-in-volume Golovin initial distribution, the
exact moments used by the code are

\[
a=bN_0\frac{4\pi r_a^3}{3},
\]

\[
M_0(t)=N_0e^{-at},
\]

\[
M_3(t)=N_0r_a^3,
\]

\[
M_6(t)=2N_0r_a^6e^{2at}.
\]

Here \(b=1500\,\mathrm{m^{-3}\,s^{-1}}\), \(N_0\) is the prescribed initial
number concentration, and \(r_a\) is the volume-exponential scale radius.

The diagnostic writes both the numerical and analytical value plus signed
relative error:

\[
E_{M_n}=\frac{M_{n,\mathrm{num}}}{M_{n,\mathrm{ana}}}-1.
\]

Important caveat: the exact formula describes the ideal untruncated analytical
distribution. The operational initializer samples a finite radius interval.
Initial analytical biases must therefore be inspected; they are not
automatically interpreted as collision-algorithm errors.

## 8. Liquid-mass conservation

The analyzer also calculates

\[
\delta_L(t)=\frac{L(t)}{L(0)}-1.
\]

This answers: did collision-coalescence accidentally create or remove liquid
mass? It is a software invariant, not an SD-number convergence measure.

The per-time table contains the signed drift. The member summary contains the
maximum absolute drift over all outputs. The provisional software gate is
\(10^{-7}\), pending confirmation before production.

## 9. Tail and onset diagnostics

### Mass fraction at 40 μm

This is the represented liquid mass carried by droplets with
\(r\geq40\,\mathrm{\mu m}\), divided by total represented liquid mass.

It is not the fraction of superdroplet records and not the fraction of real
droplet number. Multiplicity and droplet mass both enter the numerator.

### `t10`

`t10` is the first time when at least 10% of represented liquid mass is carried
at \(r\geq40\,\mathrm{\mu m}\).

If output is stored at 300 and 600 s and the fraction first exceeds 0.10 at
600 s, the code records:

- status: `crossed_between_outputs`;
- lower bound: 300 s;
- upper bound: 600 s;
- first recorded crossing: 600 s.

It does not claim that the physical crossing happened exactly at 600 s and
does not use linear interpolation to invent unresolved timing. Thus, `t10`
precision can never be better than the observation interval without storing
more frequent output.

Possible status values are:

- `already_crossed_at_first_output`;
- `crossed_between_outputs`;
- `not_crossed`.

### Larger-drop mass fraction

The development threshold is 1000 μm. It is a tail proxy and remains
provisional. The threshold value is stored with every member summary.

### Mass-weighted radius q99

Superdroplets are sorted by radius after weighting each by represented liquid
mass. The diagnostic returns the smallest radius at which cumulative mass
reaches 99% of the total. This is less dominated by one extreme record than
maximum radius, while remaining sensitive to the upper tail.

None of these is surface precipitation. The 0-D box has no sedimentation or
fallout.

## 10. Ensemble statistics

[`scripts/summarize_golovin_ensemble.py`](../../scripts/summarize_golovin_ensemble.py)
discovers completed member analyses. It first concatenates the individual
tables so no member is hidden by an average.

It also requires the reviewed `cases.tsv` and refuses to summarize unless the
analyzed run labels exactly cover the matrix and their seeds/settings agree
with the corresponding rows. A partial ensemble cannot silently masquerade as
a complete one.

For every experiment cell, time and metric, it records:

- total member count;
- finite/valid member count;
- sample mean;
- sample standard deviation;
- standard error;
- two-sided Student-\(t\) 95% confidence interval for the mean;
- deterministic percentile-bootstrap 95% interval for the mean;
- coefficient of variation when defined.

For member values \(x_e\), \(e=1,\ldots,n\):

\[
\bar{x}=\frac{1}{n}\sum_e x_e,
\]

\[
s=\sqrt{\frac{1}{n-1}\sum_e(x_e-\bar{x})^2},
\]

\[
\mathrm{SE}=\frac{s}{\sqrt n}.
\]

The Student interval is

\[
\bar{x}\pm t_{0.975,n-1}\mathrm{SE}.
\]

The bootstrap repeatedly resamples the observed members with replacement and
uses the 2.5th and 97.5th percentiles of the resampled means.

Why both?

- Student intervals are familiar and efficient when the mean behaves
  approximately normally;
- onset and tail metrics can be skewed or censored;
- a materially different bootstrap interval warns that a small ensemble or
  non-Gaussian metric needs more care.

A narrow confidence interval is evidence about ensemble-mean precision. It
does not by itself prove small bias, adjacent-resolution equivalence or
physical adequacy.

## 11. Separate stochastic seeds

Every operational member records two seeds:

| Seed | Controls |
| --- | --- |
| initialization seed | Python sampling of the time-zero superdroplet population |
| collision seed | CLEO collision pairing/event random-number pool |

They must be separate because one source changes what population enters the
simulation and the other changes stochastic collision history after time zero.

The matrix generator hashes:

- a versioned seed namespace;
- stochastic role;
- \(N_\mathrm{SD}\);
- collision timestep;
- member index.

It takes 32 bits for the NumPy initialization seed and 64 bits for the CLEO
collision seed. Generated seeds and run labels are checked for uniqueness.

The hash is a reproducible identifier generator, not a claim that histories at
different \(N_\mathrm{SD}\) are paired. Populations at different resolutions
contain different superdroplet representations.

## 12. Matrix preparation

[`scripts/prepare_golovin_matrix.py`](../../scripts/prepare_golovin_matrix.py)
reads the development YAML and creates:

- `cases.tsv`: one immutable row per member;
- `source_config.yaml`: byte copy of the input settings;
- `matrix_manifest.json`: case count, SHA-256 checksums and array bounds.

The current tiny development matrix has:

- \(N_\mathrm{SD}=1024,2048\);
- collision timestep 1 s;
- two operational members per cell;
- four total rows.

It exists only to test the pipeline structure. It is not large enough to
support a convergence conclusion.

Example local metadata-only command:

```bash
python scripts/prepare_golovin_matrix.py \
  --config config/golovin_stage0_development.yaml \
  --output-directory /fresh/path/golovin_stage0_matrix
```

This command requests no compute and runs no model. It refuses if the output
directory already exists.

## 13. Non-destructive Levante execution

[`scripts/levante/run_golovin_matrix.sbatch`](../../scripts/levante/run_golovin_matrix.sbatch)
maps one Slurm array index to exactly one `cases.tsv` row.

Safety rules:

1. The header must exactly match the registered schema.
2. The row's `case_index` must equal `SLURM_ARRAY_TASK_ID`.
3. Only a Golovin row is accepted.
4. A missing run path is owned by that row.
5. An existing path fails by default.
6. With `RESUME_COMPLETED=1`, a path is skipped only if its final manifest says
   `status=completed`.
7. An incomplete/failed path is never overwritten or silently restarted.

CLEO does not currently resume a partially written 0-D Zarr trajectory.
Therefore “resume” means safely skip completed cases and identify unfinished
ones; it does not mean append to partial model output.

The underlying single-member runner now accepts explicit:

- maximum superdroplets;
- collision timestep;
- observation interval;
- end time;
- member and matrix identity.

It refuses dirty tracked source files and refuses a build manifest from a
different project commit.

### Failure and success manifests

At start, the runner writes `manifest.inprogress.txt`. If a command fails, an
exit trap changes its status to `failed` and records the exit code/time. On
success it writes `manifest.txt` with:

- project and CLEO commits;
- initialization and collision seeds;
- complete model settings;
- matrix/member identity;
- Slurm allocation fields;
- module list;
- job wall seconds;
- SHA-256 of configuration, grid, initialization, setup, executable and build
  manifest;
- one deterministic SHA-256 digest of the Zarr file tree.

The successful final manifest replaces no previous experiment because the run
directory had to be absent.

## 14. What SHA-256 does here

SHA-256 maps file bytes to a 64-character hexadecimal fingerprint. If one byte
changes, the fingerprint is overwhelmingly likely to change.

It is used to answer:

- Was the frozen initialization actually the same file?
- Did a config or executable change between runs?
- Is a copied matrix identical to the reviewed matrix?
- Did an output tree change after the manifest was written?

SHA-256 is provenance and integrity checking. It does not prove that a file is
scientifically correct.

## 15. File-by-file map

| File | Responsibility |
| --- | --- |
| `config/golovin_stage0_development.yaml` | visible development definitions and unresolved-production flag |
| `scripts/golovin_stage0.py` | pure fixed-bin, analytical, moment, quantile and onset formulas |
| `scripts/analyze_collisions0d.py` | read one real CLEO output and write member diagnostics |
| `scripts/summarize_golovin_ensemble.py` | combine member tables and calculate uncertainty summaries |
| `scripts/prepare_golovin_matrix.py` | create immutable cases and deterministic seeds; no compute |
| `scripts/materialize_collisions0d_config.py` | make one complete absolute-path member config with explicit overrides |
| `scripts/levante/run_collisions0d.sbatch` | execute one member and record provenance |
| `scripts/levante/run_golovin_matrix.sbatch` | safely map one array index to one member |
| `scripts/levante/analyze_collisions0d.sbatch` | analyze one member into a fresh staging directory, checksum, then publish |
| `tests/test_golovin_stage0.py` | formula/statistics tests |
| `tests/test_golovin_matrix.py` | deterministic matrix and refusal/resume tests |

## 16. Per-member outputs

Every fresh `analysis_stage0_v1` directory contains:

### `member_time_diagnostics.csv`

One row per stored output time. It includes:

- complete member identifiers and seeds;
- model resolution and timesteps;
- number concentration and liquid water;
- \(M_0\), \(M_3\), \(M_6\);
- analytical moment values and signed errors for Golovin;
- fixed-bin L1;
- official CLEO smoothed L1 retained as a visual-compatibility diagnostic;
- fixed-bin overflow fractions;
- 40 μm and larger-threshold mass fractions;
- q99;
- mass drift and maximum radius.

### `member_summary.csv`

One row per member. It includes:

- member identifiers;
- interval-censored `t10`;
- maximum absolute liquid-mass drift;
- the threshold and quantile definitions used.

### Figures and metadata

- official-style mass-distribution validation figure;
- project bulk diagnostic figure using fixed-bin L1;
- JSON metadata defining bins, thresholds, smoothing status and paths;
- SHA-256 manifest when run through the batch wrapper.

## 17. Ensemble outputs

The ensemble summarizer writes:

- `all_member_time_diagnostics.csv`;
- `all_member_summaries.csv`;
- `ensemble_time_summary.csv`;
- `ensemble_member_summary.csv`;
- `ensemble_metadata.json`.

The first two are the audit trail. The next two are long-form statistical
tables. The JSON records source paths/checksums, bootstrap settings and onset
status counts.

After every matrix row has a completed member analysis, the command shape is:

```bash
python scripts/summarize_golovin_ensemble.py \
  --run-root /scratch/.../runs \
  --matrix-file /home/.../matrix/cases.tsv \
  --output-directory /fresh/home/.../ensemble_summary
```

The command refuses an existing output directory and refuses missing,
unexpected or matrix-inconsistent members.

## 18. Validation completed locally

The local quality gate currently reports:

- 28 Python/repository tests passed;
- Ruff lint passed;
- Ruff formatting check passed;
- Bash syntax checks passed for both model runners;
- the analytical mass-density implementation matches pinned CLEO to
  floating-point precision at all four checked times;
- a four-case metadata-only matrix was created successfully and declared
  `submission_authorized=false`.

Tests explicitly cover:

- identical distributions give fixed-bin L1 zero;
- a known perturbation gives the expected nonzero L1;
- binned mass plus underflow/overflow is accounted for;
- exact Golovin \(M_0,M_3,M_6\) behavior;
- finite analytical fixed-bin output;
- honest `t10` interval reporting;
- mass-weighted q99;
- deterministic ensemble bootstrap;
- deterministic unique seeds;
- matrix writer refusal on an existing path;
- explicit config overrides only;
- completed-case skip only under explicit resume;
- incomplete-case refusal even under resume.

## 19. What is not validated or concluded

No Levante job was submitted during this implementation session. Therefore:

- the updated member runner has not yet been smoke-tested on Levante;
- the new analyzer has not yet read a fresh Stage-0 Zarr member on Levante;
- storage and total job time for the new output cadence have not been measured;
- same-seed byte replay must be rechecked after the branch is built;
- the controlled/frozen mass-matched initializer is not implemented;
- the exact production bin range, larger threshold and observation interval
  remain provisional;
- no value of \(N_\mathrm{SD}\) has been declared converged;
- no production matrix is authorized.

The next safe step is one small development member plus analysis, after an
explicit compute disclosure and synchronization of the reviewed commit to
Levante.

## 20. How to explain this to Clara

A concise explanation is:

> I separated CLEO's smoothed validation plot from the formal convergence
> statistic. The new metric uses one fixed logarithmic-radius grid for every
> member and resolution, reports mass outside the grid, and compares against
> the same pinned Golovin analytical solution. Each member also reports exact
> Golovin radius-moment errors, conservation, interval-censored `t10`, tail
> mass fractions and q99. I added immutable matrix/seed generation and
> non-overwriting Slurm-array semantics, plus Student and bootstrap ensemble
> summaries. The local formula, refusal and statistics tests pass, but I have
> not submitted production compute. We still need to agree on the controlled
> initializer, production radius/tail thresholds, `t10` output interval and
> numerical margins.

Useful review questions are:

1. Should the formal distribution interval remain 1-5000 μm, or should it be
   wider for the intended 3600 s Golovin calibration?
2. Is 1000 μm the desired larger-radius tail proxy, or should the metric be
   tied to a different physical size?
3. What `t10` precision is scientifically useful, and therefore what
   observation interval should be stored?
4. For the controlled initialization, which moments must match exactly or to
   integer-multiplicity tolerance?
5. Are the provisional 5% core and 10% onset/tail equivalence margins
   acceptable?
6. Which new Levante project account and permanent record location should be
   used?

## 21. Immediate next gate

Before any model submission:

1. review and commit the Stage-0 implementation;
2. synchronize that exact commit to Levante;
3. rebuild so `build_manifest.txt` matches the commit;
4. state the requested account, partition, nodes, tasks, CPUs, memory,
   walltime, execution mode, member count and storage estimate;
5. run one development member only;
6. audit its manifest, Zarr, diagnostics, `sacct`, wall time and storage;
7. rerun the one-thread replay gate;
8. only then decide whether the tiny four-case development matrix is useful.

Production timestep and resolution stages remain blocked until their
provisional scientific decisions are resolved.
