# CLEO `constthermo2d` fixed-grid baseline: N_cell=8 smoke

## Status

**Accepted execution and integrity gate; not a convergence result.**

The accepted model/plot/audit stage is Levante job `27663925`, completed
successfully on 2026-09-24.  It resumed only the native input artifacts created
by failed launcher job `27663824`; that earlier job did not load the executable
or write any model output.  Thus there is one initial realization, not two.

## Immutable provenance

| Item | Value |
|---|---|
| CLEO source | `/home/m/m301324/SDM/CLEO-v0691-constthermo2d-9224585d` |
| Source revision | `9224585d784e9371926db9d0a23891a4b0241e24` (v0.69.1) |
| Executable | `cleo_builds/CLEO-v0691-constthermo2d-9224585d-threads-gcc-v4/examples/constthermo2d/src/const2d` |
| Executable SHA-256 | `7d7a7dd20446bac8686af2044903e5075faf632b3e023a9bae857c1dd0f7caee` |
| Seed for radius/coordinate initialization | `2026092401` |
| Resolution | 8 SDs per initially populated grid box |
| Initially populated boxes | 120 |
| Initial total SDs | 960 |
| Model duration/output interval | 7200 s / 120 s |
| Input SHA-256 | `522519b8a0c6974de9d7aea02411f32a0f87faf9c0c3cafd79bcc354f6eadf80` |
| Final run root | `/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/smoke_ncell8_seed2026092401` |

The fixed configuration is
`config/constthermo2d_fixedgrid_baseline_v1.yaml`; implementation is in
`scripts/run_constthermo2d_seeded_case_v1.py`,
`scripts/audit_constthermo2d_case_v1.py`, and the versioned Levante wrappers.

## Execution evidence

The compile-only gate `27663786` passed in 1m32s with empty stderr.  The accepted
smoke `27663925` completed `0:0` in 48s with 10 allocated CPUs and 527,724 KiB
batch MaxRSS.  Its requested envelope was 8 CPUs, 8 GiB and 60 minutes; the
measured allocation-time product is about 0.133 CPUh.

The smoke wrote four PNGs and three GIFs, a native Zarr trajectory, setup file,
and SHA-256 receipts.  Key paths are:

- `bin/const2d_domainmassmoms.png`
- `bin/const2d_motion2d.png`
- `bin/const2d_sol.zarr`
- `trajectory_integrity.json`
- `resume_input_receipt.txt` and `resume_model_receipt.txt`

## Integrity findings

The audit passed with 61 saved output times exactly matching 0, 120, ..., 7200s.
It found 960 active SDs initially and 722 at the final saved time; reduction is
consistent with collision--coalescence reducing the count of represented
particles. All stored multiplicities and radii were positive. The radius range
was 0.003013 to 303.671 micrometres. Stored x and z coordinates remained inside
the nominal 0--1500m x 0--1500m domain, and grid-box indices covered 0--399.

This gives an initial boundary/motion check: no out-of-domain record was
observed in this one low-resolution realization. It does **not** convert a
virtual downward transport diagnostic into surface precipitation; that
interpretation still requires explicit lower-boundary treatment.

The two non-empty stderr messages are plotting warnings only. `massmom2/massmom1`
is undefined in grid boxes with zero droplet mass when the upstream plotting
routine constructs an effective-mass panel, and `coord2` is intentionally absent
in this 2-D configuration. The model returned zero and the trajectory audit
passed.

## What this establishes, and what it does not

This establishes that the project-owned source/configuration, seeded native
initialization, 2-D condensation--collision calculation, Cartesian motion,
file-driven thermodynamics, Zarr output, plotting, and integrity audit all work
together on Levante. It does not establish physical realism, a reference
solution, an ensemble uncertainty, a convergence number, or a rainfall/onset
threshold.
