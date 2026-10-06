# 2-D `constthermo2d` fixed-grid `Ncell=8192` extension plan

## Purpose

The completed 20-member ladder (`Ncell=2,...,4096`) demonstrates approach to
resolution stability but leaves a measurable tail-sensitive difference at its
last doubling. This extension creates an independent higher-resolution
comparison cohort at `Ncell=8192`, using the unchanged fixed-grid,
normal-sampling, condensation--collision configuration.

`Ncell` is SDs per initially populated grid box. There are 120 initially
populated grid boxes, so each member has `120*8192 = 983040` initial SDs.

## Gate before cohort

The first action is exactly one fresh gate member. It uses 16 Kokkos Threads,
3 GiB memory, and a 30-minute wall-time ceiling. It has an isolated output
root and a new seed (`2026101301`) and will not be pooled into the later
20-member cohort. Acceptance requires:

1. Slurm `COMPLETED` with zero exit code;
2. `CONSTTHERMO2D_N8192_GATE_V1_PASS` in stdout;
3. `CONSTTHERMO2D_TRAJECTORY_INTEGRITY_PASS` and an integrity JSON receipt;
4. 61 outputs on the prescribed 0--7200 s / 120-s grid;
5. initial active-SD count 983040; and
6. empty stderr and measured peak memory below the 3-GiB request.

The gate has a hard allocation maximum of 8 CPU-hours. It is expected to use
about 5.8 CPU-hours based on the measured 4096-SD runtime doubled linearly.

## Conditional production cohort

Only after the gate passes will a distinct 20-member `Ncell=8192` production
cohort be prepared and submitted. It will use 16 CPUs and 3 GiB per member,
with a 25-minute wall-time limit and up to 20 concurrent members. The expected
20-member cost is about 115--125 CPU-hours; the hard scheduler allocation
ceiling is 133.3 CPU-hours. Including the gate, the announced expected
envelope is 121--131 CPU-hours, with hard maximum 141.3 CPU-hours.

No completed 4096 member, gate, pilot, or timing run will be added to the
new 20-member cohort. The subsequent analysis will compare full independent
20-member means at 4096 and 8192 and report DSD-bin sensitivity plus all
target physical diagnostics. It will pre-state any decision margins before
the comparison is interpreted as a resolution-selection result.

## v1 gate failure and approved v2 support correction

The original `Ncell=8192` gate (`27694690`) failed during input generation,
before CLEO time integration. Three of 8192 SDs were assigned zero integer
multiplicity. The original sampling support was 3 nm to 3 micrometres; this
wide log-radius range allocates a stratified SD to radii where the prescribed
bimodal physical distribution has effectively zero probability.

The approved v2 gate is isolated under `constthermo2d_fixedgrid_highres_v2`.
It changes only the initial sampling support to 4 nm--2 micrometres. It keeps
number concentration, distribution modes, all model physics, grid, output
cadence, resolution, seed protocol, and resource envelope unchanged. A
conservative 2,400-grid-box input stress test found no zero multiplicities
(minimum 69). The trimmed probability mass is 0.000052% of initial droplet
number and 0.00205% of initial liquid mass. The failed v1 case and logs are
retained as control evidence.

## v2 model completion and streaming-audit repair

The v2 gate job (`27695233`) completed its input generation and CLEO time
integration in 20m45s, writing the full 61-time output Zarr and case receipt.
The job then failed only because the legacy auditor attempted to materialise
all 57,670,984 ragged records at once and exceeded the 3-GiB job limit. The
trajectory itself is retained unchanged. A separate one-CPU, two-GiB,
30-minute streaming audit reads one stored time slice at a time and writes only
the otherwise missing integrity receipt. Its expected cost is 0.1--0.25
CPU-hours and its hard allocation maximum is 0.5 CPU-hours.

## Conditional fresh 20-member cohort

The accepted gate is not part of the production ensemble. The conditional
production array has 20 new seeds (`2026101501`--`2026101520`), independent
case roots, an immutable shared configuration preflight, and a `%20` Slurm
array cap. Every member runs CLEO and then the bounded-memory streaming audit.
The 8192-SD gate took 20m45s on 16 CPUs. Allowing the observed 38-s audit plus
operational margin, the expected cohort cost is about 114--120 allocated
CPU-hours. The 25-minute, 16-CPU member limit gives a hard array maximum of
133.3 CPU-hours. The configuration preflight has a five-minute wall limit;
the shared partition may allocate more than its nominal single CPU, so its
small hard envelope will be checked with Slurm preflight before submission and
included in the final total.
