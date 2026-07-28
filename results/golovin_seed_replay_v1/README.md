# Golovin one-thread collision-seed replay gate

This compact record verifies explicit collision-stream control for the
project-owned `collisions0d_golovin` application. It is a reproducibility test,
not a convergence experiment.

## Design

| Case | Initialization seed | Collision seed |
| --- | ---: | ---: |
| `replay_a` | 12345 | 67890 |
| `replay_b` | 12345 | 67890 |
| `different_seed` | 12345 | 98765 |

All cases used:

- one MPI rank;
- one Kokkos/OpenMP thread;
- the 4,096-SD reference configuration;
- Golovin collision-coalescence only;
- project commit `151fe8765d3805c035bebafe5bd938a780f36155`;
- CLEO commit `83318c23223546d10759d202d70f4fa2f7fe4688`.

## Result

Validation job `26518192` completed with exit code `0:0` and empty stderr.

All three time-zero superdroplet binaries had the same SHA-256:

```text
234c001863b05d529ef7151f9573045f2005aa1e1bffda5c4d55697b01eb384b
```

Each Zarr store contained 20 files. The SHA-256 values of the three 20-line
Zarr checksum manifests were:

| Case | Zarr-manifest SHA-256 |
| --- | --- |
| `replay_a` | `16ec4ed0ef52da20052177c827b1d007b281e8c9f58b099c7102f79785db7a05` |
| `replay_b` | `16ec4ed0ef52da20052177c827b1d007b281e8c9f58b099c7102f79785db7a05` |
| `different_seed` | `52392a45979864c878228c93b7ebffb5c279f8456a665146454822a289d02987` |

Therefore:

```text
same initialization + same collision seed -> byte-identical Zarr store
same initialization + different collision seed -> different Zarr store
```

The different seed changed the data chunks for `radius`, `xi`, `sdId`, and
`msol`, as expected when the shuffle/event history changes.

## Compute accounting

The script requested:

- account `bb1153`, partition `shared`;
- one node, one task and one CPU;
- 940 MiB;
- 10 minutes;
- three sequential one-rank/one-thread model steps;
- no GPU.

Measured:

- root elapsed time: 20 s;
- root `AllocCPUS`: 2 under Levante accounting;
- each model step: one CPU and 2–3 s;
- model-step peak memory: 6.6–6.7 MiB;
- batch peak memory: about 19.7 MiB.

## Interpretation and limit

This proves exact collision-history replay for the tested one-thread Golovin
application. The same adapter is compiled into the Long executable, but Long
runtime replay remains a separate later gate. This result does not demonstrate
multi-thread byte replay, physical realism, resolution convergence, or an
adequate ensemble size.

The raw 49 MiB validation tree remains on Levante SCRATCH at:

```text
/scratch/b/b383673/SDM/CLEO-SDM-Convergence/runs/seed_validation/golovin_seed_replay_v1
```
