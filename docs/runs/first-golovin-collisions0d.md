# First `collisions0d` Golovin run

This document records the first end-to-end execution of this repository's
collision-only box model. It is a **functional and physical smoke test**, not a
convergence result and not a final cloud configuration.

## What was run

The application represents one well-mixed collision volume. Superdroplets may
collide and coalesce, but they do not move through space and there is no
condensation, evaporation, sedimentation, thermodynamics or dynamical forcing.

The model used the idealized Golovin collision kernel. Golovin is useful here
because it provides a simple validation gate before experiments with the more
physical Long hydrodynamic kernel. Its rapid growth should not be interpreted as
a realistic cloud prediction.

The corrected audited run was Slurm job `26516775`, with:

- project commit `afaf8497fb6f2380b61a3ff0722a49c5040baad0`;
- CLEO commit `83318c23223546d10759d202d70f4fa2f7fe4688`;
- account `bb1153`, partition `shared`;
- one model MPI rank and one Kokkos/OpenMP model thread;
- requested memory `940M` and wall time `00:10:00`;
- elapsed Slurm time `00:00:27`;
- CLEO model duration approximately `0.80 s`.

Levante allocated two billable CPUs to the batch job even though the model step
requested and used one CPU. Requested resources, allocated resources and actual
model parallelism are therefore recorded separately.

## Code path

The run crosses four project-owned layers:

1. `src/collisions0d/main_golovin.cpp` selects `GolovinProb` and wraps it in
   CLEO's collision-coalescence process.
2. `src/collisions0d/main_impl.hpp` reads the YAML configuration, constructs
   one Cartesian gridbox, loads the superdroplets, uses null dynamics and null
   movement, creates the Zarr observers, and advances CLEO to the configured end
   time.
3. `scripts/prepare_collisions0d_inputs.py` creates the binary grid and
   superdroplet initial conditions from the YAML parameters and an explicit
   Python initialization seed.
4. `scripts/levante/run_collisions0d.sbatch` materializes a unique run
   directory, calls the initializer, launches the executable with Slurm, and
   records provenance and SHA-256 checksums.

The model is called “0-D” because there is no transport or spatial evolution.
The initializer still assigns three coordinates inside the single box, matching
the reference `collisions0d` implementation; these coordinates do not cause
movement.

## Prescribed conditions

The version-controlled starting point is
`config/collisions0d_reference.yaml`.

| Quantity | Value | Meaning |
| --- | ---: | --- |
| Gridboxes | 1 | One well-mixed collision volume |
| Box side length | 10,000 m | Gives a volume of \(10^{12}\,\mathrm{m^3}\) |
| Superdroplets | 4,096 | Computational particles |
| Represented number concentration | 8,388,608 m\(^{-3}\) | 8.388608 cm\(^{-3}\) real droplets |
| Initial wet-radius range | 1–75 μm | One random radius per logarithmic bin |
| Dry radius | \(10^{-16}\) m | Effectively pure-water droplets |
| Minimum multiplicity | 10 | Smallest represented number of real droplets |
| Volume-exponential scale | 30.531 μm | Controls the initial size-distribution weighting |
| Initialization seed | 12,345 | Makes Python sampling exactly repeatable |
| Collision interval | 1 s | Collision-coalescence is evaluated every second |
| Observation interval | 300 s | State is written every five minutes |
| End time | 3,600 s | One simulated hour |

The initialization contains approximately \(1\,\mathrm{g\,m^{-3}}\) of liquid
water. The diagnostic calculated with CLEO's liquid-water density
\(998.203\,\mathrm{kg\,m^{-3}}\) gives \(0.998253\,\mathrm{g\,m^{-3}}\).

The YAML also contains condensation, motion and coupling intervals because CLEO
uses a common configuration structure. They do not activate those processes:
the compiled application explicitly supplies null motion and null dynamics and
only constructs collision-coalescence microphysics.

## How it was run

After the pinned CLEO dependency and both executables had been built, the
audited run was submitted from the repository root with the project account
supplied explicitly:

```bash
sbatch \
  --account=bb1153 \
  --export=ALL,KERNEL=golovin,RUN_LABEL=first_golovin_serial,INITIALIZATION_SEED=12345,MODEL_THREADS=1 \
  scripts/levante/run_collisions0d.sbatch
```

This is the historical command for project commit
`afaf8497fb6f2380b61a3ff0722a49c5040baad0`. The current runner also requires
`COLLISION_SEED`; see ADR 0002. No collision seed can be retroactively assigned
to this first run.

The batch script deliberately refuses to overwrite an existing run label. The
result is therefore an immutable run directory:

```text
/scratch/b/b383673/SDM/CLEO-SDM-Convergence/runs/first_golovin_serial
```

It contains the exact materialized YAML, binary inputs, setup record, Zarr
dataset and a manifest with commits, seeds and checksums.

The same initialization was generated in an earlier run with the same seed. Its
superdroplet binary had the identical SHA-256 checksum, confirming exact
initialization replay.

## Raw output

The Zarr dataset contains:

| Array | Meaning |
| --- | --- |
| `time` | 13 observations from 0 to 3,600 s |
| `radius` | Wet radius of every computational superdroplet |
| `xi` | Multiplicity: number of real droplets represented |
| `msol` | Solute mass |
| `sdId` | Superdroplet identifier |
| `raggedcount` | Number of stored superdroplet records at each time |

There are 4,096 records at every output time. This does **not** mean that the
physical droplet number remains constant. In the superdroplet method,
coalescence changes radii and multiplicities while the computational particle
slots may remain present. The physical number concentration is obtained by
summing multiplicities and dividing by the box volume.

## Physical result

| Time (s) | Number (cm\(^{-3}\)) | Water (g m\(^{-3}\)) | Maximum radius (μm) | Mass at \(r\geq40\) μm | Mass at \(r\geq1000\) μm |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 8.388608 | 0.998253243 | 74.997 | 0.342207 | 0 |
| 600 | 3.453900 | 0.998253241 | 153.013 | 0.787644 | 0 |
| 1,200 | 1.428849 | 0.998253246 | 298.009 | 0.917919 | 0 |
| 1,800 | 0.576150 | 0.998253244 | 465.754 | 0.968299 | 0 |
| 2,400 | 0.234028 | 0.998253240 | 868.553 | 0.987478 | 0 |
| 3,000 | 0.094069 | 0.998253242 | 1,725.502 | 0.994977 | 0.144485 |
| 3,600 | 0.038169 | 0.998253242 | 2,688.212 | 0.997950 | 0.561498 |

The result has the expected collision-coalescence signatures:

- physical number concentration decreases because two droplets become one;
- mass shifts toward larger radii;
- millimetre-sized drops appear late in the simulated hour;
- total liquid mass is conserved, with a maximum relative drift of about
  \(7.95\times10^{-9}\).

The “mass at or above 1,000 μm” diagnostic is not precipitation in this model.
There is no sedimentation or box fallout, so large drops remain in the box.

## What this validates—and what it does not

This run validates that the repository can:

- fetch and build the pinned CLEO version on Levante;
- generate the intended reference initialization;
- run the project-owned collision-box application;
- write a readable scientific dataset;
- produce physically consistent coalescence and excellent mass conservation;
- preserve exact initialization provenance.

It does not determine convergence, an adequate superdroplet count, a realistic
cloud evolution, or a final project configuration.

The initialization seed controls the Python sampling of the initial population.
The current collision engine is initialized from `std::random_device`, so the
collision random stream is not yet under an explicit project-controlled seed.
That control is required before the later reproducible ensemble and convergence
experiments.

The project-owned diagnostic implementation is documented in
`docs/analysis/collisions0d-diagnostics.md`. The remaining scientific steps are
to establish explicit collision-stream control, repeat the Golovin validation
over controlled ensembles and resolutions, and only then transfer the verified
workflow to the Long kernel.

The checksum-verified compact output from final diagnostic job `26517314` is
versioned under `results/first_golovin_serial/analysis_v1/`. The raw Zarr remains
on Levante SCRATCH.
