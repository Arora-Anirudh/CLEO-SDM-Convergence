# Controlled Golovin collision-timestep screen

This directory is the compact permanent record of the completed
pre-convergence timestep gate. It is **not** a superdroplet-resolution
convergence result.

## Decision

- tested collision timesteps: 2, 1, 0.5, 0.25 and 0.1 s;
- controlled resolution: 16,384 superdroplets;
- members per timestep: 5 common collision-stream labels;
- selected timestep: **0.1 s**;
- all coarser candidates failed at least one registered equivalence gate;
- every timestep passed the liquid-mass-drift and fixed-bin-range gates.

The formal distribution estimand is relative L1 error of the ensemble-mean
fixed-bin distribution. Candidate-versus-reference equivalence was required
independently at 250, 500 and 1000 bins. Absolute L1 differences between those
bin grids are descriptive sensitivity information, not an additional
acceptance gate.

## Provenance

- model project commit:
  `1e335823f132439e61bc8d1f0ad21ea934e65772`;
- analysis project commit:
  `baf4cd33155ba4af9391efcf47471c6c016edf9f`;
- model Slurm job: `26535953`;
- successful aggregation Slurm job: `26536377`;
- raw Zarr inventory: 25 stores and 1,750,043,600 bytes;
- compact files: `analysis_v1/` plus `model_inventory.json`.

`analysis_v1/SHA256SUMS` validates every compact analysis file. Raw member
Zarr stores remain on Levante SCRATCH and are deliberately not committed.

The human-readable selection is
[`analysis_v1/screen/timestep_selection.json`](analysis_v1/screen/timestep_selection.json).
