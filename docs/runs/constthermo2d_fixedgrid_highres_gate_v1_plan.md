# 2-D `constthermo2d` high-resolution gate, v1 — planned only

## Purpose

This is one seeded trajectory at \(N_{\rm cell}=2048\), or 245,760 initial
domain SDs. It tests runtime, maximum resident memory, full-output integrity
and the linked `maxnsupers=120*N_cell` setting before committing any fixed-20
convergence ensemble. It does not estimate member spread, establish an
internal reference or select a converged resolution.

## Frozen setup

It reuses the accepted `constthermo2d` v0.69.1 source, build, grid,
initialisation protocol, 0--7200-s duration, 120-s output cadence, prescribed
thermodynamics, condensation, Long collision--coalescence and null boundary
conditions. It uses one MPI rank and 16 Kokkos Threads, with one new
initialisation seed (`2026092901`).

## Resource estimate before submission

The accepted 16-thread \(N_{\rm cell}=512\) pilot cost about 83 seconds per
member, or 0.37 allocated CPU-hours. Its 128-to-512 runtime increase was
about 3.2-fold for a four-fold SD increase. Applying that local scaling to
\(N_{\rm cell}=2048\) gives roughly 4.5 minutes and **about 1.2 allocated
CPU-hours** for this gate. This is an estimate, not an assurance.

The submitted envelope would be 16 CPUs, 8 GiB and 20 minutes: a hard maximum
of **5.33 CPU-hours** if the allocation ran to its time limit. The 8-GiB
memory request is a safety margin; the exact memory requirement is one of the
questions this gate measures.

## Submission record

The researcher approved this gate after receiving the estimate above. The
checksum-verified wrapper was submitted as Levante job `27669972` on 24
September 2026.

It completed `0:0` in 5m33s on 16 allocated CPUs: **1.48 allocated CPU-hours**.
`sacct` reports 1h11m37s TotalCPU and a batch MaxRSS of 557,636 KiB (about
545 MiB). The output is therefore comfortably inside the 8-GiB request and
the 20-minute, 5.33-CPU-hour hard envelope.

The 61-output trajectory-integrity audit passed with exactly 245,760 initial
SDs, 186,956 final active SDs, positive radii/multiplicities, grid indices
0--399, and zero records outside the nominal x--z domain. The final radius
range was 0.0030001--273.906 micrometres. The empty stderr file and the
case/member receipts are under
`/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/highres_gate_v1/ncell2048/member001/`.

This accepts the gate as execution/performance evidence only. One member does
not provide a reference, member spread, or a convergence result.
