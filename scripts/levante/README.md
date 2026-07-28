# Levante workflow

These scripts adapt the verified CLEO Levante toolchain to this repository.
They do not copy CLEO's user-specific example scripts.

The workflow uses Levante's GCC/OpenMPI/NetCDF/Git modules and the system CMake
3.26.5 directly. It deliberately does not call `spack load`: on 2026-07-28 the
system Spack package configuration contained a duplicate YAML key, while the
required software installations remained available through modules and their
verified absolute paths.

## Workflow layers

1. `common.sh` records machine paths, modules and runtime settings.
2. `build.sbatch` creates the locked Python environment, fetches the exact CLEO
   pin and builds both collision-box executables.
3. `run_collisions0d.sbatch` creates one non-overwriting run directory,
   materializes an absolute-path configuration, generates initial conditions,
   and runs either the Golovin or Long executable.

The permanent source and build trees are in HOME. Run-specific configuration,
input binaries and Zarr output are stored under SCRATCH.

## Build request

The build script requests:

- one node and one task;
- eight CPU cores;
- 8 GiB memory;
- 30 minutes;
- `shared` partition;
- CPU/OpenMP only, with no GPU.

The account is deliberately not committed because `bb1153` is temporary.
Supply the active account at submission:

```bash
mkdir -p /scratch/b/b383673/SDM/logs
sbatch --account=bb1153 scripts/levante/build.sbatch
```

## Single collision-box request

The model script requests:

- one node and one task;
- one CPU core;
- 2 GiB memory;
- 10 minutes;
- `shared` partition;
- one MPI rank and one OpenMP thread;
- no GPU.

For the first Golovin smoke run:

```bash
sbatch \
  --account=bb1153 \
  --export=ALL,KERNEL=golovin,INITIALIZATION_SEED=12345,RUN_LABEL=first_golovin \
  scripts/levante/run_collisions0d.sbatch
```

The job refuses to overwrite an existing `RUN_LABEL`. A Long run uses the same
workflow with `KERNEL=long`, but should only be submitted after the Golovin
validation is understood.

## Scientific and machine configuration

The scientific template is
`config/collisions0d_reference.yaml`. It contains the droplet distribution,
grid-box dimensions, number of superdroplets, collision timestep, observation
interval and end time.

`scripts/materialize_collisions0d_config.py` changes only:

- absolute paths to constants, grid, initial superdroplets and output;
- the Kokkos thread count requested by Slurm.

It does not change the scientific initialization or timesteps.
