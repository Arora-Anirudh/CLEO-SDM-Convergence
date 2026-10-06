# Shared 2-D CLEO `constthermo2d` fixed-grid experiment

This branch is a reproducibility-oriented record of the 2-D, fixed-grid
condensation--collision experiment. It is intended for inspection, reuse of
the workflow, and discussion with CLEO developers. It does **not** claim that
the tracked figures alone reproduce a new model trajectory: the raw CLEO Zarr
stores remain outside Git because they are large run products.

## Scientific configuration

- **CLEO source:** isolated upstream v0.69.1 source at commit
  `9224585d784e9371926db9d0a23891a4b0241e24`.
- **Domain:** 1,500 m by 1,500 m x--z domain, 20 by 20 native grid, with a
  20 m transverse extent.
- **Microphysics:** condensation/evaporation, Long collision--coalescence,
  Cartesian motion, and Rogers--Gunn--Kinzer terminal velocity.
- **Duration and output:** 0--7,200 s, with stored snapshots every 120 s.
- **Resolution convention:** `N_cell` is the number of superdroplets in each
  of the 120 initially populated grid boxes; each member therefore starts
  with `120 * N_cell` superdroplets.

The exact settings are in
[`config/constthermo2d_fixedgrid_baseline_v1.yaml`](../../config/constthermo2d_fixedgrid_baseline_v1.yaml).

## What is included

| Material | Location |
|---|---|
| Native input generation, model-run wrapper, integrity audits, aggregation and analysis | `scripts/*constthermo2d*.py` |
| Levante build, preparation, model, audit and analysis submissions | `scripts/levante/*constthermo2d*` and `scripts/levante/run_constthermo2d_pilot_member_v*.sh` |
| Resolution/seed manifests and baseline configuration | `config/constthermo2d_fixedgrid_*` |
| Design, execution and analysis records | `docs/experiments/constthermo2d_*`, `docs/runs/constthermo2d_*`, and `docs/analysis/constthermo2d_*` |
| Final report and supervisor presentation | `docs/reports/Two_Dimensional_CLEO_Condensation_Collision_Convergence_Report_2026-09-28_layout_fixed.docx` and `docs/presentations/Two_Dimensional_CLEO_Constthermo2d_Convergence_2026-09-28/Two_Dimensional_CLEO_Constthermo2d_Convergence_for_Supervisor_2026-09-28_v4_layout_fixed.pptx` |
| Final figures, tables and animations | `results/analysis/constthermo2d_*` directories selected below |

The tracked final analysis products are deliberately curated to avoid storing
several intermediate layout versions of the same figure. They include the
physical-diagnostic suite, the multitime member-variability plots, bootstrap
readout, operational-selection readout, DSD/size-class animation, and spatial
liquid-mass animation.

## Build provenance and external source

For this 2-D experiment the CLEO source was kept in a separate, clean clone;
the project does not vendor a modified CLEO checkout. The final build wrapper
is
[`scripts/levante/build_constthermo2d_fixedgrid_v4.sbatch`](../../scripts/levante/build_constthermo2d_fixedgrid_v4.sbatch).
It verifies the source commit, uses CLEO's maintained Levante build helper,
builds only `const2d`, and writes a build receipt containing the executable
hash.

The older project-level `FetchContent` example is retained separately under
`src/extern/cleo/`; it is useful for showing how a research application can
fetch a pinned CLEO revision as an external CMake dependency, but it is not the
specific v0.69.1 build used here.

## Raw-output boundary

The raw model data are excluded by `.gitignore` (`*.zarr/` and
`results/raw/`). This protects the Git repository from large binary simulation
stores. The tracked analysis products preserve the figures, summary tables,
metadata, and the scripts that read the raw Zarr data. The run records identify
the original Levante locations, build/source hashes, ensemble definitions and
audit checks needed to regenerate them.

## Interpretation boundary

This idealised example uses a periodic horizontal direction and
`NullBoundaryConditions`; it does not simulate a physically defined surface
rain-out boundary. Therefore spatial liquid-mass and fast-drop diagnostics are
in-domain diagnostics, not observations of surface precipitation.
