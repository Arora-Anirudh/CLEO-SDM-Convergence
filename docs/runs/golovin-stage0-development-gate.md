# Golovin Stage-0 development gate on Levante

Date: 2026-07-28

This record explains the first execution of the new Golovin Stage-0
measurement and provenance pipeline. It is deliberately detailed so that the
scientific meaning, code path, compute use and limitations can be reconstructed
without relying on terminal history.

## 1. Question answered by this gate

The gate did **not** ask how many superdroplets are sufficient. It asked:

> Can one reviewed research commit be built against the pinned CLEO source,
> run as one registered Golovin member, analyzed with the new formal
> diagnostics, replayed deterministically, and prevented from being summarized
> as a complete ensemble when most matrix members are absent?

This must pass before a multi-member convergence experiment is scientifically
worth running.

## 2. Exact software identity

| Item | Identity |
| --- | --- |
| Research branch | `agent/golovin-convergence-protocol` |
| Research commit | `bfd3bdfb21ebcad01a6d3c8524d3fc8eb1c708ef` |
| Pinned CLEO commit | `83318c23223546d10759d202d70f4fa2f7fe4688` |
| CLEO patch | project-owned explicit collision RNG seed only |
| Patch SHA-256 | `9992759099b234d47ce9e60e28a0948417e8260e20b44feeb86ef39f3606fadb` |
| Golovin executable SHA-256 | `4807b7c63e820661f37ad573e845841b734bdc8f81ce5b26eebb064bd5a70ca6` |

The branch was first reviewed locally, where 29 tests, Ruff lint/format,
Python compilation, command-line smoke checks and Bash syntax checks passed.
The work was published as draft pull request
[#3](https://github.com/Arora-Anirudh/CLEO-SDM-Convergence/pull/3).

The Levante checkout is a separate detached worktree at the exact commit:

```text
/home/b/b383673/SDM/CLEO-SDM-Convergence-golovin-protocol
```

The permanent `main` checkout and previous runs were not modified.

## 3. Isolated Levante paths

```text
source:
  /home/b/b383673/SDM/CLEO-SDM-Convergence-golovin-protocol

build:
  /home/b/b383673/SDM/cleo_builds/CLEO-SDM-Convergence/golovin_stage0

raw run:
  /scratch/b/b383673/SDM/CLEO-SDM-Convergence/golovin_stage0_runs/
    golovin_stage0_development_N001024_dt1_m000

replay:
  /scratch/b/b383673/SDM/CLEO-SDM-Convergence/golovin_stage0_runs/
    seed_validation/golovin_stage0_replay_bfd3bdf_v1

matrix record:
  /home/b/b383673/SDM/cleo_convergence_records/
    golovin_stage0_development_v1/matrix
```

Raw model output stays on SCRATCH. Compact tables, figures, manifests and
checksums are copied to
[`results/golovin_stage0_development_gate_v1`](../../results/golovin_stage0_development_gate_v1).

## 4. Development matrix

`prepare_golovin_matrix.py` created four deterministic cases:

| Case | \(N_\mathrm{SD}\) | Member | Initialization seed | Collision seed |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 1,024 | 0 | `2647907423` | `16394419086637823225` |
| 1 | 1,024 | 1 | `2859588524` | `13686403842123650899` |
| 2 | 2,048 | 0 | `4171909926` | `15754682587062949726` |
| 3 | 2,048 | 1 | `3476038967` | `6863401412257972266` |

The seed mapping is deterministic and role-separated: initialization seeds are
32-bit inputs to the Python initializer, while collision seeds are 64-bit
inputs to CLEO's collision RNG pool. Different \(N_\mathrm{SD}\) cases are
independent, reproducible members; they are not described as paired stochastic
histories.

The matrix SHA-256 is:

```text
f0462dc951d4a5f3f6dce14fab3b5ea5d27e11b1c814edfe3bc380532c987a63
```

Its manifest says `submission_authorized=false`. Only case 0 was submitted.

## 5. Launcher failure found before the model

The first build job, `26520897`, failed after 10 seconds before compilation.
The new Slurm scripts tried to locate `common.sh` beside `BASH_SOURCE[0]`.
Slurm had copied the submitted script to `/var/spool/slurmd/...`, so that path
did not contain the project helper.

The correction makes every entrypoint resolve the helper in this order:

1. explicit `CLEO_SDM_PROJECT_ROOT`;
2. a valid `SLURM_SUBMIT_DIR`;
3. the script directory for direct non-Slurm execution.

A repository-contract test now protects this behavior. Local validation rose
from 28 to 29 passing tests. The fix was committed and pushed as
`bfd3bdf`.

This failure is useful evidence for the staged design: no model output or
scientific result was produced by the faulty launcher.

Build job `26520933` was then submitted on `shared` but remained pending with a
zero-compute, 17:50 estimated start. It was cancelled before allocation and
replaced once on `interactive`; no duplicate build ran.

## 6. Compute accounting

All jobs used temporary account `bb1153`. The model, diagnostic and replay
scripts requested one MPI rank and one OpenMP thread.

| Purpose | Job | Partition | Requested | Allocated | Elapsed | Peak batch RSS |
| --- | --- | --- | --- | --- | ---: | ---: |
| Failed launcher gate | `26520897` | shared | 8 CPUs, 8 GiB, 30 min | 10 CPUs | 10 s | 3.8 MiB |
| Cancelled pending build | `26520933` | shared | 8 CPUs, 8 GiB, 30 min | none | 0 s | none |
| Successful build | `26520981` | interactive | 8 CPUs, 8 GiB, 30 min | 8 CPUs | 4:53 | 1.64 GiB |
| Member case 0 | `26521080_0` | interactive | 1 CPU, 940 MiB, 10 min | 2 CPUs | 6:07 | 54.3 MiB |
| Member diagnostic | `26521145` | interactive | 1 CPU, 940 MiB, 10 min | 2 CPUs | 18 s | 157.6 MiB |
| A/A/B replay | `26521184` | interactive | 1 CPU, 940 MiB, 10 min | 2 CPUs | 12 s | 11.9 MiB |

The interactive partition allocated two CPUs to the one-CPU root jobs because
of Levante's scheduler policy. Each actual `collisions0d_golovin` step still
used one CPU and about 6.7 MiB RSS.

The member's unusual 6:07 Slurm elapsed time was almost entirely node
startup/prolog. The project manifest measures seven seconds from the beginning
of the batch script to completed checksums, and CLEO reports 0.473 seconds for
the integration itself. These three timings answer different questions and
must not be conflated:

- Slurm elapsed: allocation occupied, including startup;
- project job wall time: script workflow after it begins;
- CLEO duration: the model integration only.

## 7. Conditions of the one-member run

| Quantity | Value |
| --- | ---: |
| Kernel | Golovin |
| \(N_\mathrm{SD}\) | 1,024 |
| Initialization family | `operational_stochastic` |
| Initialization seed | `2647907423` |
| Collision seed | `16394419086637823225` |
| Gridboxes | 1 |
| Box volume | \(10^{12}\,\mathrm{m^3}\) |
| Initial represented number concentration | \(8.388608\,\mathrm{cm^{-3}}\) |
| Target liquid water | \(1\,\mathrm{g\,m^{-3}}\) |
| Collision timestep | 1 s |
| Observation interval | 300 s |
| End time | 3,600 s |
| Active microphysics | collisions and coalescence only |

The current initializer is inherited from Clara's `collisions0d` reference. It
samples one radius in each logarithmic bin and derives multiplicities from an
exponential-in-volume target distribution. It is useful for this software gate
but is not yet the controlled/mass-matched production initializer.

The completed run manifest records the matrix row, seeds, commits, module
stack, all materialized parameters, input/config/executable checksums and the
complete Zarr-tree SHA-256:

```text
b3d73b1abd52023a0d4d2f826d1172b6ee5de99e8d0007da5b2e6bef0410818e
```

## 8. Diagnostic products

The analyzer read the fresh Zarr output with CLEO's pinned readers and wrote:

- a CLEO-style smoothed Golovin validation figure;
- a six-panel bulk diagnostic figure;
- `member_time_diagnostics.csv`;
- `member_summary.csv`;
- diagnostic metadata;
- a verified `SHA256SUMS`.

The formal convergence diagnostic is the separate unsmoothed, fixed-bin L1
metric on 500 common bins from 1 to 5000 μm. The smoothed figure remains a
visual check and is not used as the formal statistic.

## 9. Selected numerical results

Small differences between requested times and stored floating-point times,
such as 1200.0000477 s, arise from CLEO's dimensionless time conversion.

| Nominal time | Fixed-bin L1 | Relative \(M_0\) error | Relative \(M_3\) error | Relative \(M_6\) error | q99 / μm |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 s | 0.08969 | \(-1.1\times10^{-16}\) | \(-1.8023\times10^{-4}\) | \(-2.2040\times10^{-4}\) | 57.5 |
| 1200 s | 0.54313 | -0.02099 | \(-1.8021\times10^{-4}\) | -0.00530 | 247.5 |
| 2400 s | 0.60647 | +0.02007 | \(-1.8021\times10^{-4}\) | -0.21283 | 784.5 |
| 3600 s | 0.68559 | +0.05399 | \(-1.8023\times10^{-4}\) | -0.45051 | 2216.5 |

Additional observations:

- maximum absolute liquid-mass drift:
  \(1.5111\times10^{-8}\);
- fixed-bin mass below 1 μm: zero at every stored time;
- fixed-bin mass above 5000 μm: zero at every stored time;
- mass fraction above 1000 μm: zero through 2700 s, 0.0706 at 3000 s,
  0.2128 at 3300 s and 0.4239 at 3600 s;
- mass fraction above 40 μm: 0.3425 at time zero and 0.9982 at 3600 s.

## 10. How to interpret these numbers

### Liquid mass and \(M_3\)

The nearly constant \(M_3\) error and \(10^{-8}\)-scale drift show that the
closed-box coalescence workflow conserves represented liquid water to numerical
precision. The \(-1.8\times10^{-4}\) offset is already present at time zero and
comes from this sampled initialization relative to the exact analytical
target; it is not time-growing model mass loss.

### Number moment \(M_0\)

\(M_0\) is number concentration. It should decline as droplets merge. The
single member is within about 2% of the analytical value at 1200 and 2400 s
and 5.4% high at 3600 s. One stochastic member cannot tell us whether this is
mean bias or random variation.

### Sixth moment \(M_6\)

\(M_6\) heavily weights the largest droplets. Its -45% error at 3600 s shows
that this N=1024 member under-represents the analytical far tail. This is
precisely the kind of tail-sensitive behavior for which higher resolution and
ensembles are required.

### Fixed-bin L1

The L1 value rises to 0.686 by 3600 s. This does not contradict the visually
reasonable smoothed plot:

- the formal L1 uses no smoothing;
- it uses 500 fixed bins;
- only 1024 superdroplets populate those bins;
- the evolving tail is increasingly sparse and stochastic.

The result validates that the metric can be calculated and is sensitive. It
does not say the method diverges with resolution; there is only one low
resolution and one member.

### Tail metrics

The mass-weighted q99 and mass fraction above 1000 μm show the distribution
moving into the large-drop tail. They are more stable concepts than maximum
radius, but their sampling uncertainty still needs an ensemble.

### The inherited `t10` is not useful under this initialization

The provisional onset diagnostic asked for the first output with at least 10%
of mass at \(r\ge40\) μm. The initialization already has 34.25% there, so the
analyzer honestly reports `already_crossed_at_first_output`.

This is not a code failure. Morrison et al. (2024) used this definition with
an initial DSD truncated to 1-25 μm. The present initializer extends to 75 μm,
so the definition cannot be copied independently of its initial condition.

For reference, 10% mass above 1000 μm would be interval-censored between 3000
and 3300 s in this member. After the gate, ADR 0003 adopted the generic
\(t_{R,f}\) notation and registered \(R=1000\,\mathrm{\mu m}\), \(f=0.10\) for
development. It is a secondary millimetre-tail formation metric, not rain
onset, and the historical Stage-0-v1 outputs remain unchanged.

## 11. One-thread replay audit

Replay job `26521184` ran:

| Case | Initialization seed | Collision seed |
| --- | ---: | ---: |
| A | `2647907423` | `16394419086637823225` |
| B | `2647907423` | `16394419086637823225` |
| different | `2647907423` | `13686403842123650899` |

All three initialization binaries had SHA-256:

```text
20b9bbcbf39b06bb989bd311a0267dbbacaab9ea24fd8defe18e64adec5735b0
```

The complete Zarr checksum-manifest hashes were:

```text
A:         fb1a8bb3dd0515098fdeeeb7e6aa6728c2f445ce1c43aa30d9549a10cb9857f0
B:         fb1a8bb3dd0515098fdeeeb7e6aa6728c2f445ce1c43aa30d9549a10cb9857f0
different: ec095fd6abe7437d1e3e90a3cd09a453476d5b8da420d0404761904ee47cabb6
```

Therefore the same one-thread inputs replay byte-identically, while changing
only the collision stream changes the output. This validates controlled
one-thread stochastic replay; it does not promise byte identity for a
multi-thread ordering.

## 12. Incomplete-ensemble refusal

The ensemble summarizer was deliberately pointed at the one completed analysis
and the full four-case matrix. It failed before creating an output directory
and named the three missing run labels.

This is a passed safety check: a partial matrix cannot silently become an
ensemble conclusion.

## 13. Storage

| Product | Size |
| --- | ---: |
| One member including analysis | 68 MiB |
| Three replay cases | 202 MiB |
| Isolated build tree | 84 MiB |
| Matrix metadata | 3.5 KiB |
| Versioned compact gate record | 1.1 MiB |

The Zarr writer allocates about 67 MiB for one store in this configuration,
largely independent of the low N=1024 member count. Production storage must
therefore be estimated from measured stores, not only from superdroplet count.

## 14. What this gate proves

- exact research and CLEO commits can be rebuilt in isolation;
- the corrected Slurm entrypoints work;
- a deterministic matrix row reaches the model with the intended parameters;
- the run manifest is complete and checksum-verifiable;
- the fresh Zarr output is readable by the Stage-0 analyzer;
- conservation, fixed-bin distribution, moment, tail and quantile diagnostics
  are calculated;
- one-thread collision RNG replay and differentiation work;
- incomplete matrix coverage is rejected.

## 15. What it does not prove

- no \(N_\mathrm{SD}\) is converged;
- no timestep is adequate;
- no ensemble mean or stochastic spread has been estimated;
- the 1-5000 μm bin interval is not approved for production;
- the 1000 μm tail threshold is provisional;
- the historical 40 μm `t10` definition is unsuitable for this initialization;
- the operational initializer is not mass-matched across resolutions;
- the current 10-km box and reference DSD are not the final cloud
  configuration;
- Long-kernel behavior has not been tested by this Stage-0 member;
- the permanent Levante project account is still unknown.

## 16. Next scientific decision

The tiny four-case matrix should not be expanded automatically. The next
meeting should decide:

1. the controlled/mass-matched initialization constraints;
2. the production radius interval and bin count;
3. the physically meaningful tail and onset definitions;
4. acceptable numerical-equivalence margins;
5. the permanent Levante account and record location.

After those are fixed, the production path remains:

1. Golovin collision-timestep screening;
2. Golovin \(N_\mathrm{SD}\) ladder with enough independent members;
3. ensemble-precision assessment;
4. controlled-initialization sensitivity;
5. only then transfer the accepted measurement framework to Long.
