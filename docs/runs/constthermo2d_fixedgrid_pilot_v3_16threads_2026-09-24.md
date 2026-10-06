# 2-D `constthermo2d` small resolution pilot: accepted execution record

**Date:** 24 September 2026  
**Purpose:** first small, internally thread-consistent resolution pilot; not a
convergence calculation or physical result.

## Fixed execution protocol

The cohort uses the project-owned 2-D `constthermo2d` baseline derived from
CLEO v0.69.1 source commit `9224585d784e9371926db9d0a23891a4b0241e24`.
Each member uses one MPI rank, the Kokkos Threads backend, and exactly 16 host
threads. The domain, grid, initial droplet target, pressure-scaled multiplicity
calculation, prescribed thermodynamics, condensation, Long collision--
coalescence, motion, 0--7200 s duration and 120 s output cadence are fixed.

`N_cell` denotes SDs per initially populated grid box. There are 120 initially
populated boxes, so each member begins with `120*N_cell` SDs.

| `N_cell` | Initial domain SDs | Members | Seeds |
|---:|---:|---:|---|
| 8 | 960 | 3 | 2026092501--03 |
| 32 | 3,840 | 3 | 2026092601--03 |
| 128 | 15,360 | 3 | 2026092701--03 |
| 512 | 61,440 | 3 | 2026092801--03 |

The separately accepted 8-thread `N_cell=32` and 512 trajectories are health
gates only. They are deliberately excluded from this pilot because a numerical
ensemble should not silently mix host-thread configurations.

## Slurm execution evidence

Array job `27667054` used four concurrent array tasks, one resolution per task,
with three members run serially inside each task. All elements completed `0:0`:

| Array task / `N_cell` | Elapsed | Allocated CPUs | Requested memory |
|---|---:|---:|---:|
| 0 / 8 | 1:00 | 16 | 8 GiB |
| 1 / 32 | 0:37 | 16 | 8 GiB |
| 2 / 128 | 1:19 | 16 | 8 GiB |
| 3 / 512 | 4:09 | 16 | 8 GiB |

The sum of the four elapsed allocation products is approximately 1.89
allocated CPU-hours. Every task emitted its completion marker, and all four
task stderr files are empty.

## Receipt-level audit

Each of the 12 case directories contains a case receipt, a member receipt and
a trajectory-integrity receipt. All 12 integrity receipts report:

- status `passed_trajectory_integrity_no_convergence_claim`;
- 61 stored output times over 0--7200 s;
- the expected initial SD count for their resolution;
- positive multiplicities and radii, unique active IDs at stored times, and
  agreement between ragged and per-grid-box SD counts;
- no records outside the nominal 0--1500 m by 0--1500 m x--z domain; and
- `num_threads: 16` in each runtime configuration.

Final active SD counts across members were 745/696/697, 2865/2936/2902,
11665/11774/11680 and 46969/47044/46958 for `N_cell=8,32,128,512`,
respectively. These are descriptive execution checks, not convergence metrics.

## Locations

- Cohort outputs: `/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/pilot_v3_16threads/`
- Array logs: `/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/pilot-remaining-v1-27667054_<task>.{out,err}`
- Submission wrapper: `scripts/levante/run_constthermo2d_fixedgrid_pilot_remaining_v1.sbatch`

## Next analytical gate

The cohort is sufficient to construct pilot-only spatial and domain diagnostics
and quantify member spread. It is insufficient for a resolution-convergence
selection: the next decision should use the pilot diagnostics to define the
reference ladder, ensemble size, and boundary-aware observables before any
fixed-20 production run.
