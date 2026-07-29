# Controlled Golovin initialization: implementation and learning guide

- Implementation status: local numerical/unit tests and one Levante native
  CLEO write/read gate passed
- Native CLEO binary status: 4096-SD pilot validated in job `26534015`
- Frozen-bundle status: persistent 4096-SD creation/verification validated in
  job `26534596`; independent replay, the six-resolution bundle ladder and
  compiled direct reuse are implemented but not yet run
- Production status: not authorized
- Scientific decision: [ADR 0004](../decisions/0004-golovin-production-definitions.md)
- Main implementation: [`scripts/controlled_initialization.py`](../../scripts/controlled_initialization.py)
- CLEO entry point: [`scripts/prepare_collisions0d_inputs.py`](../../scripts/prepare_collisions0d_inputs.py)
- Tests: [`tests/test_controlled_initialization.py`](../../tests/test_controlled_initialization.py)

## 1. What was implemented

The new code creates one deterministic superdroplet population for a chosen
number of superdroplets, \(N_\mathrm{SD}\). It represents the same prescribed
continuous Golovin initial droplet-size distribution at every resolution.

The implementation controls:

- the physical radius support, 1–75 μm;
- the physical number concentration, \(8{,}388{,}608\,\mathrm{m^{-3}}\);
- the collision-box volume, \(10^{12}\,\mathrm{m^3}\);
- the volume-exponential scale radius, 30.531 μm;
- the exact integer number of represented physical droplets;
- the total initial liquid volume, equivalently radius moment \(M_3\);
- a maximum 1% representation error in the tail-sensitive \(M_6\);
- deterministic spatial coordinates;
- the exact binary and scientific population identity through SHA-256.

It does **not** change CLEO. A project-owned Python adapter supplies
multiplicity, wet radius, solute mass and coordinates to CLEO's own native
initial-condition writer. CLEO remains responsible for binary layout,
dimensional scaling and metadata.

## 2. Why the earlier stochastic initializer is not enough for the core ladder

The Clara-derived operational initializer samples radii and coordinates. Even
with a recorded NumPy seed, a different seed creates a different discrete
time-zero droplet population.

That is useful when asking:

> How variable is an operational SDM experiment when both its sampled initial
> population and its collision stream vary?

It is less clean when asking:

> What changes only because \(N_\mathrm{SD}\), the collision timestep, or the
> collision random stream changed?

For the second question, the initial population should not vary between
collision members at one resolution. The controlled initializer therefore has
no random seed. Repeating it with the same inputs produces exactly the same
arrays and, after native validation, should produce the same binary.

“Controlled” does not mean that different \(N_\mathrm{SD}\) values contain the
same superdroplets. They cannot: a 1024-SD population and an 8192-SD population
contain different discrete representatives. They approximate the same
continuous DSD with a documented deterministic rule. These are reproducible
and controlled comparisons, not paired droplet histories.

## 3. Continuous target distribution

The starting configuration prescribes an exponential distribution in physical
droplet volume. Let

\[
v=\frac{4\pi r^3}{3}
\]

be droplet volume and let \(v_0\) be the volume corresponding to the scale
radius \(r_0=30.531\,\mathrm{\mu m}\).

An untruncated exponential in volume is proportional to

\[
\exp(-v/v_0).
\]

Our physical radius support is finite:

\[
r_\min=1\,\mathrm{\mu m},\qquad
r_\max=75\,\mathrm{\mu m}.
\]

The distribution is therefore explicitly **conditioned on this finite
support**. If \(a\) and \(b\) are the corresponding volume limits, the
probability density is normalized by

\[
Z=\exp(-a/v_0)-\exp(-b/v_0).
\]

This distinction matters. We are not sampling an infinite exponential and
then silently deleting out-of-range droplets. The conditioned distribution is
the actual numerical target, and its number and liquid-volume integrals are
audited.

## 4. From the continuous DSD to \(N_\mathrm{SD}\) representatives

### 4.1 Make logarithmic-volume bins

The support is divided into exactly \(N_\mathrm{SD}\) bins with equal width in
\(\ln v\). Because \(v\propto r^3\), this is also an equal-width
log-radius stratification.

Every bin gets exactly one superdroplet representative. Increasing
\(N_\mathrm{SD}\) therefore refines the same support rather than changing the
physical DSD.

### 4.2 Integrate physical number and liquid volume in every bin

For bin \(i=[v_i^-,v_i^+]\), the code analytically evaluates:

\[
p_i=\int_{v_i^-}^{v_i^+}p(v)\,dv,
\]

the fraction of physical droplets in that bin, and

\[
q_i=\int_{v_i^-}^{v_i^+}v\,p(v)\,dv,
\]

the liquid-volume contribution per target physical droplet.

If \(N_\mathrm{real}\) is the physical-droplet total in the box, then:

\[
X_i=N_\mathrm{real}p_i
\]

is the real-valued desired multiplicity and

\[
W_i=N_\mathrm{real}q_i
\]

is the desired total liquid volume represented by that bin.

The implementation uses `expm1` and small-bin series expansions. This avoids
subtracting nearly equal exponentials when \(N_\mathrm{SD}\) is large. Direct
subtraction was numerically unreliable near 32,768 bins; the stable formulas
pass through that resolution.

The numerical arrays explicitly use float64. NumPy `longdouble` has different
precision on different operating systems, so float64 gives a narrower and
more portable numerical contract. It does **not** guarantee identical
transcendental-function results across NumPy/libm versions. The Levante pilot
confirmed that tiny platform-level differences can change raw array bytes
while leaving every registered physical moment gate unchanged. Therefore:

- the scientific method, tolerances and moment gates define equivalence across
  software platforms;
- an array SHA-256 identifies one exact constructor output in one recorded
  environment;
- the CLEO native-binary SHA-256 identifies the exact artifact that ensemble
  members must reuse.

### 4.3 Convert desired multiplicities to exact integers

CLEO multiplicity \(\xi_i\) is an integer: one superdroplet represents
\(\xi_i\) identical physical droplets.

The collision volume contains

\[
N_\mathrm{real}
=8{,}388{,}608\,\mathrm{m^{-3}}\times10^{12}\,\mathrm{m^3}
=8{,}388{,}608{,}000{,}000{,}000{,}000
\]

physical droplets.

This is too large for ordinary float64 arithmetic to represent every adjacent
integer. A naive calculation can therefore lose hundreds of droplets while
appearing numerically close.

The code solves this by:

1. mapping bin probabilities to high-resolution integer weights;
2. calculating every quota, floor and remainder with Python integers;
3. assigning the remaining droplets to the largest fractional remainders;
4. breaking exact ties by increasing bin index order;
5. checking the exact Python-integer sum.

This is a deterministic Hamilton/largest-remainder allocation. The final
integer multiplicities obey:

\[
\sum_i \xi_i=N_\mathrm{real}
\]

exactly, not approximately.

The code also requires every \(\xi_i\) to meet the configured minimum
multiplicity. An impossible request fails rather than silently deleting a bin
or changing the DSD.

### 4.4 Preserve each bin's liquid volume

After integerization, the representative volume is

\[
\hat v_i=\frac{W_i}{\xi_i}.
\]

Therefore:

\[
\sum_i \xi_i\hat v_i=\sum_i W_i,
\]

so the analytically integrated liquid volume is preserved apart from
floating-point roundoff.

The representative radius is then

\[
\hat r_i=\left(\frac{3\hat v_i}{4\pi}\right)^{1/3}.
\]

Every \(\hat v_i\) must remain inside the volume bin from which it was derived.
If integerization would move a representative outside its source bin, the
initializer stops with an error.

## 5. Meaning of the moment gates

The project defines radius moments as

\[
M_n=\frac{1}{V}\sum_i \xi_i r_i^n.
\]

The initializer checks:

| Moment | Physical/numerical role | Treatment |
| --- | --- | --- |
| \(M_0\) | physical droplet number concentration | controlled exactly at the integer target |
| \(M_3\) | proportional to total liquid volume and liquid-water content | controlled by the bin-integrated representative volume |
| \(M_6\) | tail-sensitive, reflectivity-like quantity | checked to 1%, deliberately not forced |

Not forcing \(M_6\) is important. \(M_6\) should reveal whether the discrete
population resolves the large-drop tail. If all three moments were optimized
to match by construction, a weakness in the tail representation could be
hidden.

For the current 4096-SD population, the macOS local calculation gives:

| Quantity | Value |
| --- | ---: |
| exact represented physical droplets | `8388608000000000000` |
| represented \(M_0\) | `8388608 m-3` |
| relative \(M_0\) error | `0` |
| relative \(M_3\) error | `0` at printed precision |
| relative \(M_6\) error | `-8.33e-7` |
| liquid-water content | `0.99823635 g m-3` |
| smallest representative radius | `1.00053 μm` |
| largest representative radius | `74.96021 μm` |
| population SHA-256 | `c2d02c94...551205` |

The liquid-water content is a consequence of the finite-support conditioned
DSD. It is not independently rescaled to exactly \(1\,\mathrm{g\,m^{-3}}\).

The Levante NumPy 2.5.1 constructor gives the same printed physical values and
passes the same gates, but its source-array fingerprint is
`11d4871d...c5d08`. A direct comparison found 86 multiplicities differing by
small integer redistributions and radius differences no larger than
`1.60e-18 m` (`2.34e-13` relative). This is why the production workflow will
freeze and reuse one Levante-native bundle per resolution instead of asking
every member to regenerate it.

As a deliberate negative test, \(N_\mathrm{SD}=16\) gives about a 4.55% \(M_6\)
error and is rejected by the 1% gate. This proves the gate can fail an
under-resolved representation.

## 6. How the code is organized

### `ControlledPopulation`

This immutable data object stores:

- bin edges;
- desired and integer multiplicities;
- representative radii;
- target liquid volume by bin;
- configuration values;
- target and represented moments;
- relative moment errors.

Keeping the complete scientific population separate from CLEO makes the
numerical construction inexpensive to unit-test.

### `build_controlled_population`

This is the main scientific function. It:

1. validates the requested physical inputs;
2. creates logarithmic-volume edges;
3. evaluates stable analytical bin integrals;
4. performs exact integer allocation;
5. constructs representative radii;
6. applies source-bin and moment gates;
7. returns a `ControlledPopulation`.

It contains no CLEO imports.

### `ControlledAttrsGenerator`

CLEO's native writer asks an attribute generator for:

- multiplicity;
- wet radius;
- solute mass;
- spatial coordinates.

`ControlledAttrsGenerator` implements that interface. It checks that CLEO asks
for the same \(N_\mathrm{SD}\), number concentration and gridbox volume used to
construct the population. It then returns arrays with CLEO's expected native
NumPy dtypes.

The negligible dry radius from the reference configuration is used to
calculate solute mass. It does not materially change the wet-radius DSD.

### `prepare_collisions0d_inputs.py`

The existing script now supports two explicit paths:

```text
operational_stochastic
    -> sampled radii + sampled coordinates + required/reported NumPy seed

controlled
    -> deterministic quadrature radii/multiplicities + deterministic coordinates
    -> no initialization seed
    -> mandatory controlled-config YAML
    -> mandatory audit creation
```

The default remains `operational_stochastic`, so existing development and
replay scripts do not silently change scientific meaning.

The controlled path calls CLEO's own
`generate_initial_superdroplet_conditions`. The project does not duplicate or
reverse-engineer CLEO's binary file format.

## 7. Why coordinates are deterministic

The box keeps three coordinates because the Clara-derived `collisions0d`
configuration is written as one three-dimensional gridbox. The model has null
motion and null dynamics, so coordinates have no physical evolution and do
not affect well-mixed collision pairing inside the single gridbox.

Nevertheless, random coordinates would make two otherwise identical binary
files differ. The controlled path uses CLEO's deterministic
`SampleCoordGen(False)`, which places coordinates with `linspace` inside the
box. This removes irrelevant binary variability while retaining CLEO's native
format.

## 8. Audit and SHA-256

Every controlled initialization writes a new JSON audit. It includes:

- scientific method and distribution convention;
- support, scale, number concentration and collision volume;
- \(N_\mathrm{SD}\);
- exact physical-droplet total;
- multiplicity and radius ranges;
- target, represented and relative-error values for \(M_0,M_3,M_6\);
- liquid-water content;
- population SHA-256;
- paths and SHA-256 hashes for the runtime YAML, controlled YAML, grid binary,
  superdroplet binary and initializer source.

SHA-256 maps file bytes to a 64-character hexadecimal fingerprint. Identical
hashes provide strong evidence that files are byte-identical; different hashes
prove that at least one byte differs. A checksum does not explain a scientific
difference and does not make incorrect data correct. It is a provenance and
identity check.

The audit writer refuses to overwrite an existing file. A previous experiment
cannot be silently replaced by a newly generated population.

## 9. Frozen initialization workflow

The scientific constructor and native reader gate are complete. The
project-owned frozen-artifact layer now implements:

1. `prepare_controlled_bundle.sbatch` generates one controlled grid and
   superdroplet binary for one \(N_\mathrm{SD}\);
2. CLEO's reader writes the creation audit and native-readback report;
3. `controlled_bundle.py finalize` checks their agreement and writes
   `bundle_manifest.json`;
4. every required file size and SHA-256 is recorded;
5. the normalized scientific definition is recorded separately from absolute
   paths and documentation-only status metadata;
6. source snapshots and Python/NumPy/platform provenance are retained;
7. write bits are removed from every bundle file;
8. `run_collisions0d.sbatch` verifies the bundle before and after a controlled
   Golovin member;
9. the member configuration points directly at the frozen files and no
   member-local initialization is generated;
10. resolution, CLEO pin, scientific-definition, checksum, size and read-only
    mismatches stop the run.

The persistent layout is:

```text
controlled_bundles/<bundle label>/
├── bundle_manifest.json
├── config.yaml
├── source_reference_config.yaml
├── source_controlled_config.yaml
├── controlled_initialization_audit.json
├── native_readback.json
├── inputs/
│   ├── grid.dat
│   └── superdroplets.dat
├── output/                       # remains empty during bundle creation
└── provenance/
    ├── controlled_initialization.py
    ├── prepare_collisions0d_inputs.py
    └── validate_controlled_initialization_binary.py
```

The matrix generator still accepts only `operational_stochastic`. This is
intentional: single-bundle creation and one compiled member must pass on
Levante before controlled array execution is enabled.

## 10. What has and has not been validated

Validated locally:

- stable analytical integration through \(N_\mathrm{SD}=32768\);
- exact integer physical-droplet total;
- \(M_0\), \(M_3\), \(M_6\) gates;
- source-bin containment;
- repeatable population arrays and hash in the same tested environment;
- CLEO-compatible multiplicity/radius/solute-mass dtypes;
- deterministic coordinate generation contract;
- audit content, artifact hashes and overwrite refusal;
- deliberate failure for an under-resolved 16-SD case.
- frozen-manifest creation and same-definition verification;
- wrong-resolution and changed-byte refusal;
- file write-bit removal;
- member configuration referencing frozen inputs without copying;
- refusal when only one frozen input path is supplied;
- source-level run contract separating controlled reuse from operational
  generation.

Validated on Levante in input-only job `26534015`:

- CLEO wrote one 4096-SD controlled native binary;
- CLEO's own reader recovered 4096 complete attribute records;
- the binary checksum matched the initializer audit;
- the exact `8388608000000000000` physical-droplet total survived round-trip;
- read-back \(M_0\), \(M_3\) and \(M_6\) matched the audit;
- all droplets belonged to the one box and all coordinates lay inside it;
- no model executable or Zarr output was created;
- stderr was empty.

Not yet validated:

- creation of the new persistent bundle layout on Levante;
- pre/post identity when one compiled member reuses the bundle;
- byte identity of two independently written native binaries in one pinned
  environment, if regeneration replay is retained as an additional check;
- a compiled model run using the controlled binary;
- runtime and storage scaling;
- any convergence result.

The native gate used one serial Slurm allocation but no model compute.

## 11. Completed Levante pilot

The request was disclosed to Anirudh before submission:

- temporary account: `bb1153`;
- partition: `shared`;
- nodes: 1;
- MPI tasks: 1;
- CPUs per task: 1;
- memory: 940 MiB;
- walltime: 10 minutes;
- action: generate and read one 4096-SD controlled binary;
- no collision model and no ensemble.

Job `26534015` completed in 11 seconds. Slurm recorded one requested CPU but
allocated two CPUs under the shared-partition policy; the code remained
serial with `OMP_NUM_THREADS=1`. Requested memory was 940 MiB and batch
`MaxRSS` was 3916 KiB. The complete input-only directory is 248 KiB:

```text
/scratch/b/b383673/SDM/CLEO-SDM-Convergence/runs/
  controlled_initialization_validation/controlled_init_n4096_v1
```

The native superdroplet binary SHA-256 is
`d805fb278ed070396d8bf3bb0d655138f5f1124901d5ea917279f99e270420f2`.
The compact result record is
[`results/controlled_initialization_native_n4096_v1/`](../../results/controlled_initialization_native_n4096_v1/).

## 12. Completed persistent frozen-bundle validation

After explicit approval, job `26534596` used `bb1153/shared`, one requested
node/task/CPU, 940 MiB and 10 minutes. It ran serially, created/read/finalized
one 4096-SD bundle, and ran no collision model or ensemble.

It completed `0:0` in 15 seconds with empty stderr. Slurm allocated two CPUs
despite the one-CPU request; batch MaxRSS was 3.76 MiB. Independent
post-completion verification passed. The 11-file, 290,319-byte bundle has no
writable files and no Zarr output.

The bundle records project commit `e1935d7`, pinned CLEO `83318c23`, the exact
`8388608000000000000` represented physical droplets and native superdroplet
SHA-256
`d805fb278ed070396d8bf3bb0d655138f5f1124901d5ea917279f99e270420f2`.
The compact review record is
[`results/controlled_initialization_bundle_n4096_v1/`](../../results/controlled_initialization_bundle_n4096_v1/).

This validates persistent creation and immutability. Same-stack independent
regeneration and a compiled controlled member remain separate gates. No
controlled matrix has been authorized.

## 13. How to explain this to Clara

A concise explanation is:

> I implemented the pre-registered controlled Golovin initializer outside
> CLEO. It conditions the prescribed volume-exponential DSD on the fixed
> 1–75 μm support, puts one superdroplet in each log-volume bin, allocates the
> exact physical-droplet total with deterministic integer largest remainders,
> and sets each representative volume to preserve its bin-integrated liquid
> volume. Thus \(M_0\) and \(M_3\) are controlled, while \(M_6\) is checked but
> not forced. The object is passed to CLEO's native binary writer through its
> existing attribute-generator interface. Local numerical and unit tests pass;
> the native binary, frozen-artifact reuse, and one-run Levante pilot remain.

Likely questions and answers:

**Why not use the same random seed?**

The same seed reproduces one random sample, but the controlled family removes
initial sampling as a source of variability and makes the quadrature rule
explicit.

**Why is \(M_6\) not exact?**

It is the tail-resolution diagnostic. Forcing it could mask the error we want
to measure.

**Why condition on 1–75 μm?**

The reference setup has finite support. Conditioning makes the represented
continuous target unambiguous. This Golovin calibration support is not
automatically the later Long/cloud configuration.

**Why are there about \(8.39\times10^{18}\) droplets?**

The collision volume is \(10^{12}\,\mathrm{m^3}\), so the configured
\(8.388608\times10^6\,\mathrm{m^{-3}}\) concentration implies that physical
total. Superdroplets represent this population through large integer
multiplicities.

**Does this prove convergence?**

No. It provides a controlled and audited time-zero population required to run
the planned convergence experiment.
