# First seeded `collisions0d` Long run

This document records the first Long-kernel execution in the permanent
research repository. It is a **functional, conservation and diagnostic gate**.
It is not a convergence result and it is not yet the final cloud-relevant box
configuration.

## Why this run was made

Golovin is useful for checking the numerical pipeline because an analytical
distribution is available. The project will ultimately focus on the more
physical Long hydrodynamic collision kernel. Before designing a Long ensemble,
the project needed to demonstrate that:

1. the Long application builds against the pinned CLEO source;
2. the explicit initialization and collision seeds reach the executable;
3. the same collision-only box can run to completion;
4. its output can be read by the CLEO plotting tools;
5. collision-coalescence conserves liquid water numerically.

Using the same initialization as the current Golovin software gate isolates the
intended code-level change: `GolovinProb` is replaced by `LongHydroProb`.
This is a controlled implementation comparison, not a claim that the starting
population is the final scientific one.

## Code path

`src/collisions0d/main_long.cpp` constructs:

```cpp
const PairProbability auto probability = LongHydroProb();
return SeededCollCoal(
    tsteps.get_collstep(), &step2realtime, probability, seed
);
```

The common implementation in `src/collisions0d/main_impl.hpp` then:

1. reads the materialized YAML configuration;
2. reads one binary grid and one binary superdroplet population;
3. creates null dynamics and null movement;
4. creates only the seeded collision-coalescence microphysical process;
5. records time, radius, multiplicity, solute mass and superdroplet ID;
6. advances the model for one simulated hour.

The collision seed initializes CLEO's collision RNG pool. The Python
initialization seed independently controls the sampled time-zero population.
The model was run with one thread because that is the mode in which exact
collision-stream replay has been validated.

## Prescribed conditions

The run used `config/collisions0d_reference.yaml`, inherited from the
`PerformanceTestingCLEO/collisions0d` starting point selected by Clara:

| Quantity | Value | Interpretation |
| --- | ---: | --- |
| Gridboxes | 1 | One well-mixed collision volume |
| Box dimensions | 10 km × 10 km × 10 km | Volume \(10^{12}\,\mathrm{m^3}\) |
| Superdroplet records | 4,096 | Computational particle records |
| Initial represented number | 8.388608 cm\(^{-3}\) | Sum of multiplicities divided by box volume |
| Initial wet-radius range | 1–75 μm | One sampled radius per logarithmic bin |
| Initial liquid water | 0.998253 g m\(^{-3}\) | Reconstructed from radii and multiplicities |
| Collision timestep | 1 s | Long collision-coalescence is evaluated each second |
| Observation interval | 300 s | Thirteen stored states including time zero |
| End time | 3,600 s | One simulated hour |
| Initialization seed | 12,345 | Replays the time-zero SD population |
| Collision seed | 67,890 | Replays the tested one-thread collision stream |

No condensation, evaporation, transport, sedimentation, fallout,
thermodynamics or dynamical forcing is active. Configuration entries for other
process timesteps do not activate those processes; the compiled application
constructs null dynamics and null movement.

## Levante execution

Model job `26518504` used project commit
`dc15471b32e07583b26ce5a83065f14934cd6180` and pinned CLEO commit
`83318c23223546d10759d202d70f4fa2f7fe4688`.

Requested resources:

- account `bb1153`, partition `shared`;
- one node, one task and one CPU per task;
- one MPI rank and one Kokkos/OpenMP thread;
- `940M` memory and 10 minutes walltime;
- no GPU.

The root Slurm job was allocated two CPUs by Levante, but the model step
requested and used one CPU. The full job completed in 20 seconds, while CLEO
reported 1.61 seconds of model duration. The model step peaked near 6.8 MiB
resident memory. Stderr was empty.

The immutable raw run is:

```text
/scratch/b/b383673/SDM/CLEO-SDM-Convergence/runs/first_long_seeded
```

Its manifest records the seeds, commits, resource mode and checksums. The
initial-superdroplet SHA-256 is
`234c001863b05d529ef7151f9573045f2005aa1e1bffda5c4d55697b01eb384b`,
the same verified initialization used in the seeded Golovin replay gate.

## Diagnostic execution

Diagnostic job `26518623` requested the same account, partition, node, task,
CPU, memory and walltime. It is a serial Python analysis, not a second model
simulation. Levante again allocated two CPUs to the root job; the job completed
in 22 seconds with batch peak memory about 3.8 MiB and empty stderr.

The analysis:

- reads CLEO's setup, grid and ragged Zarr output with pinned `cleopy`;
- plots the numerical distribution with CLEO's
  `plotcleo.shima2009fig` machinery;
- calculates number concentration, liquid water, relative mass drift, maximum
  radius and two in-box radius-threshold mass fractions;
- deliberately leaves `golovin_l1_relative` undefined (`NaN`) because no
  Golovin analytical reference applies to a Long run;
- stages, checksums and atomically installs the compact products.

## Numerical result

| Time (s) | Number (cm\(^{-3}\)) | Water (g m\(^{-3}\)) | Maximum radius (μm) | Mass at \(r\geq40\) μm | Mass at \(r\geq1000\) μm |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 8.388608 | 0.998253243 | 74.997 | 0.342207 | 0 |
| 600 | 0.264494 | 0.998253241 | 572.282 | 0.987620 | 0 |
| 1,200 | 0.006596 | 0.998253243 | 1,946.867 | 0.999761 | 0.471054 |
| 1,800 | 0.000454 | 0.998253244 | 2,966.958 | 0.999987 | 0.875355 |
| 2,400 | 0.000088 | 0.998253244 | 3,360.549 | 0.999999 | 0.963769 |
| 3,000 | 0.000039 | 0.998253242 | 3,410.766 | 1.000000 | 0.988789 |
| 3,600 | 0.000029 | 0.998253241 | 3,439.935 | 1.000000 | 0.996297 |

The maximum absolute relative liquid-mass drift was
\(6.58\times10^{-9}\). The tiny signed changes are floating-point/reconstruction
noise, not a physical source or sink.

The physical signatures are internally consistent with collision-coalescence:

- represented droplet number falls as droplets merge;
- liquid mass moves rapidly to larger radii;
- nearly all in-box mass is in millimetre-scale drops by the end;
- total liquid water remains constant.

The stored superdroplet record count remains 4,096. That does not mean the
physical droplet number remains fixed: multiplicities and radii evolve inside
the computational records.

The distribution figure's 3,600 s peak exceeds the inherited CLEO y-axis limit
and is clipped at the top. The numerical dataset and bulk diagnostics are
unaffected. Any later publication-quality comparison may choose a shared
data-driven y-limit, but this first record preserves the CLEO reference plotting
convention.

## Interpretation boundary

This run proves that the seeded Long application and analysis pipeline work in
the tested one-thread mode and that the implemented coalescence conserves
liquid water.

It does **not** prove:

- convergence with respect to \(N_\mathrm{SD}\);
- that one realization represents the ensemble mean or variability;
- that 4,096 superdroplets are sufficient;
- that the one-second collision timestep is adequate for the eventual case;
- that the rapid millimetre-drop production is cloud-realistic;
- surface precipitation, because there is no sedimentation or fallout;
- suitability of the present box size, DSD, number concentration or duration
  for the final project.

The next scientific task is therefore not to call this a Long convergence
result. It is to define the project experiment matrix—controlled initialization
families, \(N_\mathrm{SD}\) levels, collision timestep sensitivity, ensemble
members and convergence metrics—before launching an ensemble.

Checksum-verified compact products are stored under
`results/first_long_seeded/analysis_v1/`; the large raw Zarr remains on
Levante SCRATCH.
