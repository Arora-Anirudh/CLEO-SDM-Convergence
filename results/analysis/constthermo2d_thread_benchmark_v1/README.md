# 2-D `constthermo2d` Kokkos Threads check, v1

This is a one-realization operational timing check at `N_cell=512` (61,440
initial SDs). Each accepted run reused the same native input binary and full
0–7200 s output grid, but used a freshly copied YAML configuration with a
different `kokkos_settings.num_threads` value and a fresh output store.

All five accepted runs wrote 61 stored times and passed the generalized
trajectory-integrity audit. The `model_wall_seconds` column is wall time around
the executable only. `allocated_cpu_hours` uses the Slurm accounting allocation
and elapsed job time, so it includes launcher/audit overhead.

The 8-thread v1 attempt (`27666655`) is excluded because its exact-allocation
guard stopped before configuration or model execution. Its fresh v2 replacement
is the accepted 8-thread result (`27666821`).

The result is an operational trade-off, not an MPI, physical, or convergence
study. Parallel collision execution can produce different stochastic
realizations even when the native input is identical; no trajectory differences
are interpreted here.
