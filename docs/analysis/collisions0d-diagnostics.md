# `collisions0d` diagnostics

`scripts/analyze_collisions0d.py` analyzes one completed collision-only CLEO
run without modifying its input or model output.

## Consistency with CLEO

The mass-distribution validation figure deliberately calls the plotting tools
from the exact CLEO source fetched by this repository:

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

The analytical and numerical curves therefore use the same definitions and
visual conventions as CLEO. This repository does not copy or silently alter
those formulas.

## Additional bulk diagnostics

A separate six-panel figure reports:

1. represented real-droplet number concentration;
2. liquid-water mass concentration;
3. relative liquid-mass drift from time zero;
4. maximum represented radius;
5. liquid-mass fractions at radii at or above 40 and 1,000 micrometres;
6. relative Golovin L1 distribution error, or the stored SD-record count for a
   Long run where no Golovin analytical solution applies.

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

The relative Golovin L1 error integrates the absolute numerical-minus-analytical
mass-distribution difference over \(\ln r\), normalized by the integrated
absolute analytical distribution. Corresponding 500-bin values are paired by
index, matching CLEO's validation error panel. CLEO reports slightly different
bin-centre coordinates for the numerical and analytical curves because the
former uses an arithmetic radius midpoint and the latter a geometric midpoint.

## Outputs

Each fresh `analysis_v1` directory contains:

- `<kernel>_mass_distribution.png`;
- `<kernel>_bulk_diagnostics.png`;
- `bulk_diagnostics.csv`;
- `diagnostic_metadata.json`;
- `SHA256SUMS` when run through the Levante batch wrapper.

The analysis refuses to overwrite an existing directory. The Levante wrapper
writes to a job-specific staging directory and renames it to `analysis_v1` only
after every output and checksum succeeds. A failed staging directory is
preserved as `analysis_failed_job<jobid>` for diagnosis.
