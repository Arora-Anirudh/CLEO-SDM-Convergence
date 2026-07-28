# First seeded Long diagnostic record

This directory contains the compact, checksum-verified diagnostic record for
the project-owned `collisions0d` Long run `first_long_seeded`.

- model job: `26518504`;
- diagnostic job: `26518623`;
- project commit used by the run:
  `dc15471b32e07583b26ce5a83065f14934cd6180`;
- CLEO commit: `83318c23223546d10759d202d70f4fa2f7fe4688`;
- execution: one MPI rank, one model thread, 4,096 superdroplets;
- initialization seed: `12345`;
- collision seed: `67890`;
- raw Zarr on Levante:
  `/scratch/b/b383673/SDM/CLEO-SDM-Convergence/runs/first_long_seeded/output/collisions0d_solution.zarr`;
- compact products: `analysis_v1/`.

The mass-distribution figure is generated with the plotting tools from the
pinned CLEO dependency. The bulk figure and CSV report number concentration,
liquid water, conservation, maximum radius and in-box threshold-mass fractions.
No Golovin L1 value is reported because a Golovin analytical solution is not a
reference for the Long kernel.

The diagnostic job completed with empty stderr, maximum absolute relative
liquid-mass drift `6.57539534e-09`, and verified all entries in `SHA256SUMS`.

This is a single-run Long functionality/conservation product, not convergence
evidence and not the final project configuration.
