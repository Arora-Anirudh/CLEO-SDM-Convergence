# 2-D `constthermo2d` 8192-SD compact aggregation, v2

## Why a new reducer is required

The fresh 20-member `Ncell=8192` cohort stores 61 time records and roughly
57.7 million ragged superdroplet records per member. The original v1 compact
extractor reads every ragged coordinate, radius, multiplicity, and solute-mass
array into memory at once. That design was appropriate for the 2--4096 ladder
but is not safe for this extension.

The v2 reducer reads one stored time slice at a time. It reconstructs the same
compact schema used by the existing 2--4096 cache: 250/500/1000-bin number and
mass DSDs, \(\lambda_0,\lambda_1,\lambda_2,\lambda_3,\lambda_6\), exact
droplet mass, mass-weighted terminal speed and radius quantiles, lower-150-m
mass fraction, and selected spatial mass maps. It independently compares
reconstructed \(\lambda_0\) and mass with CLEO's native observers.

## Staging and acceptance

One completed production member is first reduced into a separate gate output.
It must create a compact NPZ and JSON audit, produce an explicit pass marker,
have empty stderr, and demonstrate acceptable memory/time before the remaining
20 production members are aggregated. The gate aggregate is not pooled into
the final production cache. Raw Zarr trajectories remain unmodified.

## Gate result

The one-member aggregation gate (`27721698`) completed in 45 seconds with
empty stderr. Its compact NPZ is 1.2 MiB. Reconstructed \(\lambda_0\) agrees
exactly with CLEO's native `massmom0`; reconstructed total mass differs from
native `massmom1` by at most \(3.36\times10^{-6}\) relatively. The full
20-member array will write a separate `analysis_production_v2` cache; the gate
output is deliberately not pooled into it.
