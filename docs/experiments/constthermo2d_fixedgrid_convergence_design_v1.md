# 2-D CLEO `constthermo2d` fixed-grid convergence design, v1

## Scope and provenance

This is a new configuration-specific convergence study.  It must not inherit a
resolution choice from either the historical Long 0-D experiment or the 0-D
condensation--collision experiment.

The baseline is the upstream CLEO `examples/constthermo2d` example at commit
`9224585d784e9371926db9d0a23891a4b0241e24` (v0.69.1).  The project copy of
the configuration is `config/constthermo2d_fixedgrid_baseline_v1.yaml`.
Upstream source remains untouched.

## Fixed physical/numerical setup

| Item | Fixed value |
|---|---:|
| Domain | 1500 m vertical x 1500 m horizontal x 20 m transverse |
| Grid | 20 x 20 x--z grid boxes; 75 m x 75 m x 20 m each |
| Initialized cloud layer | boxes whose upper z boundary is at most 500 m |
| Populated boxes | 120 (= 6 vertical layers x 20 horizontal boxes) |
| Initial droplet number concentration | 1e7 m^-3 |
| Radius proposal | log-uniform in log10(r), 3 nm to 3 micrometres |
| Multiplicity target | prescribed bimodal lognormal distribution; pressure-scaled (`xi_by_pressure=true`) |
| Thermodynamics | dry hydrostatic-adiabatic, prescribed from file; saturation ratio 0.99 below 750 m and 1.0025 above |
| Processes | condensation/evaporation solver plus Long collision--coalescence, Rogers--Gunn--Kinzer terminal velocity and Cartesian motion |
| Thermodynamic feedback | disabled (`do_alter_thermo=false`) |
| Runtime | 0--7200 s; condensation/collision 1 s, motion 2 s, output 120 s |

`N_cell` always means superdroplets **per initially populated box**.  Thus the
initial domain total is `N_total = 120 N_cell`; the source-default baseline is
`N_cell=8`, `N_total=960`.

## Execution gates

1. **Remote source and build gate.** Stage a fresh source tree at the recorded
   v0.69.1 commit; do not use the older, dirty default Levante checkout. Build
   only `const2d` with thread backend, Cartesian domain and file-driven dynamics.
2. **Exact 8-SD-per-populated-box smoke.** Generate one seeded native input,
   execute the complete 120-min trajectory, write the upstream plots, and audit
   dimensions, output cadence, finite values, IDs, coordinates, multiplicities
   and expected initial domain count of 960.
3. **Boundary/motion audit.** The C++ example uses `NullBoundaryConditions`.
   Therefore vertical transport or the virtual flux diagnostic is not a surface
   rainfall flux until the stored positions/grid indices establish what happens
   when drops reach a domain boundary.

The first smoke has seed 2026092401 solely as an auditable input realization.
It is not a convergence member and establishes no physical conclusion.

## Authorized pilot implementation, 24 September 2026

The first resolution-changing gate is deliberately separated into two jobs.
The native-input-only preflight writes fresh `N_cell=2` and `N_cell=4` cases,
then verifies the binary SD records directly: 120 populated grid boxes, exactly
`N_cell` SDs in each populated box, positive multiplicities, and totals of 240
and 480 SDs. It does not run the CLEO executable.

The first complete dynamic-resolution case is one fresh `N_cell=32` member
(seed `2026092601`, initial total 3840). It uses the same source, grid,
physics, duration, output cadence, and initialization method as the 8-SD
smoke. It changes only the linked pair

\[
N_{\rm cell}=32, \qquad {\tt maxnsupers}=120N_{\rm cell}=3840.
\]

Every materialized configuration, native input, executable, and trajectory
audit is hashed or recorded below its own initially absent case directory.
The generalized trajectory audit accepts the expected initial count explicitly,
so it cannot silently apply the old 960-SD condition to a new resolution.

### Parallel execution boundary

This upstream executable does use shared-memory Kokkos host threads. The
pilot requests one Slurm task and eight host threads, and the copied YAML sets
`kokkos_settings.num_threads: 8`. This is the supported parallel path for the
example; its internal kernels can use those threads across the domain.

It must **not** be launched with multiple MPI ranks. `main_const2d.cpp`
explicitly tests communicator size and throws when it exceeds one because this
example has no prepared MPI domain decomposition. A future MPI implementation
would require source changes and tests for the exchange of moving SDs across
rank boundaries. Before any production choice, a dedicated 1/2/4/8/16-thread
timing test at a useful resolution will measure whether more host threads are
actually efficient.

### Upstream Levante precedent

The upstream v0.69.1 repository supplies
`scripts/levante/examples/constthermo2d.sh` for this exact example. Its Slurm
directives request one node, one task, 128 CPUs per task, 10 GiB and 10 minutes
in the `compute` partition. It sets `buildtype="threads"`; the corresponding
CLEO build helper enables `Kokkos_ENABLE_THREADS=ON`, rather than the OpenMP
backend. The upstream YAML similarly sets `num_threads: 128`.

This verifies that multithreaded, one-rank execution is the intended upstream
mode. It does **not** validate an MPI-rank decomposition, and it does not show
that 128 threads is efficient for this particular 400-box, (N_{\rm cell}\)
resolution study. The present executable was independently checked at runtime:
`Kokkos_ENABLE_THREADS=ON`, `Kokkos_ENABLE_OPENMP=OFF`. We will therefore
benchmark thread count before altering the production resource shape.

### First operational thread-scaling check

The accepted `N_cell=512` native input (61,440 initial SDs) was reused once at
each Kokkos Threads setting, with a fresh output store and copied YAML. Every
accepted run completed all 61 stored times and passed the trajectory audit.
Model-only wall times were 131, 79, 50, 30 and 39 s at 8, 16, 32, 64 and 128
threads, respectively. The associated Slurm allocated CPU-hours were 0.392,
0.373, 0.489, 0.640 and 1.778.

Thus 64 threads was fastest in wall time, while 16 threads used the least
measured scheduler CPU-time. This is a single-realization operational result,
not a formal performance study: thread scheduling and collision execution can
change operation order, so the trajectories are not compared physically. For
the small resolution pilot, 16 threads is the prudent cost-efficient default;
if wall-clock latency dominates, 64 threads is the informed alternative. A
larger-resolution timing recheck is needed before extrapolating this choice to
a production ladder.

## Subsequent, not-yet-authorized stages

After the smoke is clean, run a small pilot at `N_cell = 8, 32, 128, 512` with
3--5 independently seeded members.  It determines whether domain-total output,
cloud-layer and spatially resolved diagnostics are numerically usable.  Only
then define the full fixed-20 ladder, beginning at 2 SD per populated box and
extending through 2048 or 4096 per populated box if indicated.

The diagnostics must include spatial DSDs, lambda_0/lambda_2/lambda_3/lambda_6,
number/mass concentration, mass-weighted terminal speed and a clearly labelled
boundary-aware transport proxy.  A separate alpha-sampling study comes only
after the normal-sampling reference workflow and criterion are established.
