# `collisions0d` diagnostics

`scripts/analyze_collisions0d.py` analyzes one completed collision-only CLEO
run without modifying its input or model output.

## Consistency with CLEO

The official-style mass-distribution validation figure deliberately calls the
plotting tools from the exact CLEO source fetched by this repository:

- `cleopy.sdmout_src.pysetuptxt` reads the recorded model setup and constants;
- `cleopy.sdmout_src.pygbxsdat` reads the grid and collision volume;
- `cleopy.sdmout_src.pyzarr` reconstructs the ragged superdroplet output;
- `plotcleo.shima2009fig` calculates and plots the numerical mass distribution
  and, for Golovin, its analytical solution.

Following CLEO's `examples/boxmodelcollisions/shima2009_plotting.py`, the
distribution uses 500 bins evenly spaced in natural-log radius and Gaussian
smoothing

\[
\sigma_{\ln r}=0.62N_\mathrm{SD}^{-1/5}.
\]

The analytical and numerical curves therefore use the same visual conventions
as CLEO. This remains a visual validation product. Because its smoothing
bandwidth depends on \(N_\mathrm{SD}\), it is not the formal convergence
metric.

## Formal fixed-bin distribution diagnostic

Stage 0 adds one registered logarithmic-radius grid shared by every member,
time and resolution. The numerical mass histogram is not smoothed. The
Golovin analytical solution is evaluated at the same geometric bin centres,
and the relative L1 sum uses the exact shared bin widths. Mass fractions below
and above the registered interval are reported explicitly.

The development grid is 500 bins from 1 to 5000 μm. It is marked provisional
and must be confirmed before production.

## Additional bulk diagnostics

A separate six-panel figure reports:

1. represented real-droplet number concentration;
2. liquid-water mass concentration;
3. relative liquid-mass drift from time zero;
4. maximum represented radius;
5. liquid-mass fractions at radii at or above 40 and 1,000 micrometres;
6. formal fixed-bin relative Golovin L1 distribution error, or the stored
   SD-record count for a Long run where no Golovin analytical solution
   applies.

For superdroplet \(i\), multiplicity \(\xi_i\), radius \(r_i\), water mass
\(m_{w,i}\), and box volume \(V\):

\[
N = \frac{\sum_i \xi_i}{V},
\qquad
L = \frac{\sum_i \xi_i m_{w,i}}{V},
\qquad
\delta_L(t) = \frac{L(t)-L(0)}{L(0)}.
\]

The radius-threshold diagnostics are in-box distribution metrics. They are not
surface precipitation because the 0-D application has no sedimentation or
fallout.

The CSV retains CLEO's smoothed L1 value for compatibility, but labels the
fixed-bin value separately. The formal value integrates the absolute
numerical-minus-analytical mass-distribution difference over the registered
\(\ln r\) bins, normalized by analytical mass density on that same grid.

The per-time table additionally records radius moments \(M_0,M_3,M_6\), exact
Golovin values and relative errors, fixed-bin overflow, mass-weighted q99, and
the configured radius-threshold mass fractions. A per-member table records the
interval-censored `t10` and maximum absolute liquid-mass drift. Full formulas
and interpretation are in the
[Stage-0 implementation guide](../implementation/golovin-stage0-guide.md).

## Outputs

Each fresh `analysis_stage0_v1` directory contains:

- `<kernel>_mass_distribution.png`;
- `<kernel>_bulk_diagnostics.png`;
- `member_time_diagnostics.csv`;
- `member_summary.csv`;
- `diagnostic_metadata.json`;
- `SHA256SUMS` when run through the Levante batch wrapper.

The analysis refuses to overwrite an existing directory. The Levante wrapper
writes to a job-specific staging directory and renames it to
`analysis_stage0_v1` only after every output and checksum succeeds. A failed
staging directory is preserved as `analysis_failed_job<jobid>` for diagnosis.
