# Golovin pre-convergence gates: implementation and execution guide

- Status: implemented locally; Levante execution pending
- Scope: the last controlled checks before the actual multi-resolution
  Golovin convergence ensemble
- Production conclusion: none
- Actual convergence compute: not submitted

## 1. Why these gates exist

The goal is not merely to make CLEO run. The goal is to measure how the
ensemble-mean Golovin solution and its stochastic uncertainty change with
superdroplet resolution without silently changing the initial physical
population, collision timestep, diagnostic definition or software stack.

Five questions must therefore be answered before the resolution ladder:

1. Can the controlled initializer reproduce the same CLEO-native bytes when it
   is independently rerun on the same Levante stack?
2. Does the formal distribution error remain stable when its logarithmic bin
   count changes?
3. Can an exact project commit be rebuilt and run while consuming a read-only
   controlled bundle directly?
4. Which collision timestep is sufficiently close to the 0.1 s numerical
   reference at high superdroplet resolution?
5. Do immutable controlled bundles exist for every resolution in the planned
   ladder?

Passing these gates does not establish convergence. It makes the next
submission scientifically interpretable as the convergence experiment.

## 2. Gate A: same-stack native-byte replay

Script:

```text
scripts/levante/validate_controlled_bundle_replay.sbatch
```

The job verifies the canonical 4096-SD bundle, independently invokes the same
bundle constructor in a fresh SCRATCH directory, verifies the replay bundle
and compares:

```text
inputs/grid.dat
inputs/superdroplets.dat
```

with `cmp --silent`. SHA-256 values are also recorded.

This is stricter than comparing moments. Two files can have the same
\(M_0,M_3,M_6\) while containing different droplet representatives. Exact byte
identity proves deterministic replay for the pinned project commit, CLEO pin,
Python/NumPy environment and Levante software stack.

The replay copy is a validation artifact, not an ensemble input. Actual
members continue to reuse the canonical read-only bundle.

## 3. Gate B: immutable resolution-bundle ladder

Script:

```text
scripts/levante/prepare_controlled_bundle_ladder.sbatch
```

The planned ladder is:

```text
N_SD = 512, 1024, 2048, 4096, 8192, 16384
```

The existing validated 4096 bundle is verified and reused. The script creates
only the five missing bundles:

```text
golovin_controlled_N000512_v1
golovin_controlled_N001024_v1
golovin_controlled_N002048_v1
golovin_controlled_N008192_v1
golovin_controlled_N016384_v1
```

Every bundle:

- approximates the same registered continuous initial DSD;
- has an exact represented real-droplet total;
- preserves registered \(M_0\) and \(M_3\) gates and checks \(M_6\);
- is written with CLEO's native binary writer and read back with CLEO;
- records source, configuration, commit and environment provenance;
- records size and SHA-256 for every required file;
- has all write bits removed after finalization;
- is non-overwriting.

Different resolutions do not contain the same individual superdroplets. They
are deterministic refinements of the same continuous DSD. The resolution
comparison is controlled and reproducible, not a pairing of droplet histories.

## 4. Gate C: diagnostic-bin robustness

The primary analytical-distribution diagnostic remains:

```text
500 logarithmic radius bins from 1 to 5000 micrometres
no smoothing
```

`scripts/analyze_collisions0d.py` now repeats the exact same mass-density and
Golovin analytical calculation at 250, 500 and 1000 bins. Every member/time
row records:

- relative L1 error at each bin count;
- liquid-mass fraction below the registered radius range;
- liquid-mass fraction above the registered radius range.

For bin count \(B\), the single-member diagnostic is

\[
E_{L1,B}(t)=
\frac{\sum_b |g_{\mathrm{num},b}-g_{\mathrm{ana},b}|\Delta\ln r}
     {\sum_b |g_{\mathrm{ana},b}|\Delta\ln r}.
\]

Each analysis also stores the numerical and analytical fixed-bin
distributions in `fixed_bin_distributions.npz`. The ensemble statistic is
computed in the required order:

\[
\overline{g}_{\mathrm{num},b} =
\frac{1}{J}\sum_{j=1}^{J}g_{\mathrm{num},j,b},
\qquad
E_{L1,B}^{\mathrm{ensemble}} =
\frac{\sum_b |\overline{g}_{\mathrm{num},b}-g_{\mathrm{ana},b}|
\Delta\ln r}
{\sum_b |g_{\mathrm{ana},b}|\Delta\ln r}.
\]

This is deliberately **not** the mean of the members' L1 values. Absolute
value makes L1 nonlinear, so averaging scalar member errors would answer a
different question and would not measure the error of the ensemble-mean
distribution.

The registered robustness policy is:

- 500 bins remains the primary diagnostic;
- collision-timestep equivalence must pass independently at 250, 500 and 1000
  bins;
- absolute L1 changes from the 500-bin value are reported but are not
  independent acceptance gates;
- the combined below-range and above-range mass fraction of every member is at
  most \(10^{-6}\).

This guards against declaring convergence because of one convenient histogram
grid while acknowledging that finer bins expose more finite-ensemble
roughness. The empirical reason for replacing the earlier absolute 0.005
cross-bin condition is documented in
[ADR 0005](../decisions/0005-ensemble-l1-bin-sensitivity.md). CLEO's smoothed
validation figure is still produced for human visual inspection, but it is
not the formal convergence statistic because its bandwidth changes with
\(N_\mathrm{SD}\).

## 5. Gate D: exact-commit build and direct frozen-bundle member

The build gate uses:

```text
scripts/levante/build.sbatch
```

in a fresh, isolated build root. The build manifest must contain the exact
project commit used by all following jobs and the pinned CLEO commit:

```text
83318c23223546d10759d202d70f4fa2f7fe4688
```

One 4096-SD controlled Golovin member then runs through
`run_collisions0d.sbatch` with:

- one rank and one thread;
- the canonical read-only bundle;
- no initialization seed;
- one explicit 64-bit collision seed;
- collision timestep 1 s;
- observations every 300 s;
- end time 3600 s.

The member runner verifies the bundle before and after CLEO. It never calls
the initializer and never creates member-local input binaries. Its
configuration points directly to the frozen grid and superdroplet files.

The subsequent diagnostic job checks:

- formal 250/500/1000-bin distribution metrics;
- \(M_0,M_3,M_6\);
- liquid-mass drift;
- descriptive tail quantities;
- official CLEO-style distribution figure;
- runtime, Zarr size and provenance.

This is a compiled-path audit, not an ensemble.

## 6. Gate E: controlled collision-timestep screen

Registered inputs:

| Quantity | Value |
| --- | ---: |
| \(N_\mathrm{SD}\) | 16,384 |
| frozen initialization | `golovin_controlled_N016384_v1` |
| timesteps | 2, 1, 0.5, 0.25, 0.1 s |
| collision streams per timestep | 5 |
| total members | 25 |
| observation interval | 300 s |
| end time | 3600 s |
| formal decision times | 600, 1200, 1800, 2400, 3000, 3600 s |
| numerical reference | 0.1 s |

The screen is deliberately at 16,384 SDs, as registered in the scientific
protocol. A low-resolution screen could hide a timestep error behind
finite-\(N_\mathrm{SD}\) noise.

The five 64-bit collision-seed **labels** are reused at every timestep. This
reduces unrelated random-stream variation in the numerical comparison.
Changing the timestep changes how often the collision operator is called, so
these are common-stream comparisons, not paired event histories.

For signed relative \(M_0\) and \(M_6\), the code calculates five
common-stream member differences against 0.1 s:

\[
d_j=D_j(\Delta t)-D_j(0.1\,\mathrm{s}).
\]

It forms a two-sided Student 95% confidence interval for each mean moment
difference.

For L1, the code first forms each timestep's ensemble-mean fixed-bin
distribution. It then uses a common-stream percentile bootstrap: every
bootstrap replicate resamples the same five stream indices for the candidate
and 0.1-s reference, recalculates both ensemble distributions and takes the
difference between their nonlinear L1 values. The entire interval must lie
inside:

| Diagnostic | Equivalence interval |
| --- | ---: |
| fixed-bin relative L1 | \([-0.01,+0.01]\) |
| signed relative \(M_0\) error | \([-0.05,+0.05]\) |
| signed relative \(M_6\) error | \([-0.10,+0.10]\) |

Every diagnostic must pass at every decision time. In addition, every member
must pass liquid-mass conservation and fixed-bin range coverage, and the
250/500/1000-bin decision must be robust.

The selected value is the **largest** timestep passing every registered gate.
If five members are too imprecise to decide, the result is ambiguity, not
permission to choose the cheaper timestep; only ambiguous cells are extended.

Files:

```text
config/golovin_controlled_timestep_screen.yaml
experiments/golovin_controlled_timestep_screen_v1/cases.tsv
scripts/levante/run_golovin_timestep_screen.sbatch
scripts/levante/analyze_golovin_timestep_screen.sbatch
scripts/analyze_golovin_timestep_screen.py
```

The 25-row matrix is deterministic and records only five unique collision
seeds, one per stream index reused across all five timesteps. Its manifest
states `submission_authorized=false`; preparing metadata never submits
compute.

## 7. Refusal, restart and provenance behavior

All persistent paths are non-overwriting. A retry:

- skips only members with an explicit completed manifest when
  `RESUME_COMPLETED=1`;
- refuses incomplete pre-existing member paths;
- refuses a matrix whose checksum differs from the persistent screen record;
- refuses a build whose manifest does not match the exact checked-out commit;
- refuses writable or checksum-changed controlled bundles;
- preserves failed analysis staging under a visibly failed name.

Raw Zarr remains on SCRATCH. Compact matrices, inventories, summaries,
figures, logs and checksums go to persistent HOME records and then into a
versioned repository result directory.

## 8. What becomes the next step after these gates pass

The next step is the actual controlled Golovin resolution experiment:

```text
6 resolutions x 20 initial collision streams = 120 members
```

It will use:

- the collision timestep selected by Gate E;
- one frozen bundle per resolution;
- new independent collision seeds per resolution/member;
- the same physical box, decision times and diagnostic definitions;
- adaptive extension only where confidence-interval precision is inadequate.

The different-resolution members are not called paired. Unknown or reused
numeric seeds do not create paired droplet histories. The controlled design
means that each run is exactly replayable and changes are attributable to the
registered factors.

The 120-member matrix will be prepared with
`submission_authorized=false`. A separate compute disclosure and explicit
researcher approval remain required before it is submitted.

## 9. Local validation boundary

The new Bash files pass `bash -n`, the Python files compile, `git diff --check`
passes and the locally runnable targeted suite currently reports 38 passing
tests. Five diagnostic-module tests cannot run in the macOS base Python
because that interpreter lacks `awkward`; this is an environment limitation,
not a test failure in the project environment. The complete locked
Python-environment suite and Ruff checks remain required in GitHub Actions and
on the exact Levante checkout before model execution.
