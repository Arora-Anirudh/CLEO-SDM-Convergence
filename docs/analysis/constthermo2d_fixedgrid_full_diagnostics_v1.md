# 2-D constthermo2d: complete fixed-20 diagnostic audit

## Purpose and status

This document closes the analysis of the completed normal-sampling, fixed-20
ensemble resolution ladder for the 2-D CLEO constthermo2d configuration. It
combines numerical convergence, DSD and radius evolution, spatial snapshots,
and the physical terminal-speed and mass-transport diagnostics added after the
Bjorn discussion.

No new CLEO trajectory was run for this report. Every plot is reconstructed
from the audited compact cache, with 20 independent members at each completed
resolution:

\[
N_{\rm cell}=2,4,8,\ldots,8{,}192.
\]

Here \(N_{\rm cell}\) is the number of superdroplets initially sampled in each
populated 2-D grid box. There are 120 initially populated grid boxes, so
\(N_{\rm cell}=1{,}024\) means 122,880 initial SDs in the domain. Outputs are
stored every 120 s from 0 to 120 min. Each ensemble-mean curve uses all
20 members at its resolution.

This is an operational selection for this exact 120-minute configuration. It
is not a proof against an independent numerical solver, an infinitely resolved
SDM calculation, or a general requirement for another CLEO configuration.

## Inputs and reconstruction

The source is the audited compact cache at
results/cache/constthermo2d_fixedgrid_production_v1/. The generator is
scripts/analyze_constthermo2d_fixedgrid_physical_v1.py and its versioned output
directory is results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/.

The cache contains multiplicity-weighted DSDs on common 250-, 500-, and
1,000-bin radius meshes; the moments \(\lambda_0,\lambda_1,\lambda_2,\lambda_3\),
and \(\lambda_6\); total mass; mass-weighted radii; terminal-speed summaries;
active-SD counts; and selected spatial liquid-mass fields. The fixed common
radius mesh means that the visual comparisons are not changed by
resolution-dependent binning or smoothing.

## Earlier ensemble and numerical-convergence products retained in this audit

The physical suite is an addition to, rather than a replacement for, the
earlier fixed-20 convergence analysis. The following figures are retained as
part of the complete evidence record.

![Member-level diagnostic violins](../../results/analysis/constthermo2d_fixedgrid_with8192_descriptive_v3/04_member_violin_diagnostics_at_multiple_times.png)

**Existing Figure A — Member-level distributions at several times.** These
violins retain the individual-member view that is hidden when only the
20-member means are plotted. They show both the resolution trend and the
finite-ensemble spread of the core diagnostics at each stored diagnostic time.

![Resolution and ensemble precision surface](../../results/analysis/constthermo2d_fixedgrid_with8192_descriptive_v3/05_resolution_ensemble_precision_surface.png)

**Existing Figure B — Resolution–ensemble precision surface.** This separates
two effects: moving upward reduces discretisation/sampling error, while moving
right shows the precision gained by averaging more independently random
members. It is descriptive rather than a fitted extrapolation.

![Original operational convergence gate](../../results/analysis/constthermo2d_fixedgrid_operational_selection_v5/01_operational_convergence_gate_matrix.png)

**Existing Figure C — Original multi-metric operational gate.** The original
selection tests the primary 500-bin mass DSD, moments, radius and
mass-weighted terminal speed both against 8,192 and across two adjacent
doublings. The new physical transport audit below intentionally adds an
independent check to this existing decision framework.

## Moment meanings

For wet radius \(r_i\), multiplicity \(\xi_i\), and domain volume \(V\),

\[
\lambda_k(t)=\frac{1}{V}\sum_i\xi_i r_i(t)^k.
\]

Thus \(\lambda_0\) is number concentration, \(\lambda_1\) weights radius
linearly, \(\lambda_2\) weights surface area, \(\lambda_3\) weights liquid
volume, and \(\lambda_6\) strongly weights rare large drops. These are
multiplicity-weighted physical estimates, not unweighted counts of
computational particles.

![All moments and total mass](../../results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/01_all_moments_and_mass_evolution.png)

**Figure 1 — Moment and mass evolution.** The smallest resolutions depart most
clearly in the number and tail-sensitive histories. The trajectories group
tightly as \(N_{\rm cell}\) increases. The sixth moment is deliberately
tail-sensitive because a rare large drop enters as \(r^6\).

![Radii, speed, location, and active SDs](../../results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/02_radius_transport_and_population_evolution.png)

**Figure 2 — Radius, speed, location, and computational population.** The
upper row gives mass-weighted \(r_{50}\), \(r_{90}\), and \(r_{99}\). The lower
left is liquid-mass-weighted terminal speed. The lower middle is the liquid
mass located below 150 m, an in-domain location diagnostic; null boundaries
mean it is not accumulated surface rainfall. Active SDs are useful for
interpreting sampling depletion but are not a physical droplet concentration.

## Distribution evolution

![Number DSD evolution](../../results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/03_number_dsd_evolution.png)

**Figure 3 — Number DSD.** Each panel is a full 20-member mean at one
resolution, with a curve for each stored time. The 2-SD spectrum is jagged
because very few SDs support the estimate. From 512 through 8,192 the shapes
are visually very similar, confirming that the selection is not merely a
moment-level coincidence.

![Mass DSD evolution](../../results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/04_total-droplet-mass_dsd_evolution.png)

**Figure 4 — Mass DSD.** This reweights the distribution by liquid mass and
therefore makes transfer into larger drops explicit. The 500-bin mass DSD is
the primary convergence distribution because it measures the mass
redistribution most relevant to collision–coalescence. The 250- and 1,000-bin
versions remain bin-resolution sensitivity checks.

## Physical meaning of r2, r3, and r6

Three physically interpretable re-expressions were built from the stored
moments:

\[
A=4\pi\lambda_2,\qquad
L=\rho_w\frac{4\pi}{3}\lambda_3,\qquad
Z=64\lambda_6^{(r,\mathrm{mm})}.
\]

\(A\) is geometric droplet surface-area density in m\(^{-1}\), relevant to
condensation capacity but not a radiative-transfer extinction coefficient.
\(L\) is liquid-equivalent water content in g m\(^{-3}\). \(Z\) is a Rayleigh
reflectivity-factor proxy shown as dBZ, not a radar forward simulation.

![Physical moment proxies](../../results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/05_physical_moment_proxies_evolution.png)

**Figure 5 — Physical moment proxies.** Surface area and liquid-equivalent
water converge relatively smoothly with resolution. The \(Z\) proxy separates
the low-resolution ensembles more strongly, as expected from the large-drop
\(r^6\) weighting.

## Terminal speed and virtual transport

The speed coordinate uses the Rogers–Gunn–Kinzer radius-speed relation used by
this 2-D setup. The Bjorn-motivated transport diagnostic is

\[
\mathcal P(t)=\frac{1}{V}\sum_i\xi_i m_i v_t(r_i),
\]

in g m\(^{-2}\) s\(^{-1}\). It is the instantaneous downward transport that
would occur if each represented droplet travelled at terminal speed. It is a
proxy rather than surface mass flux because this configuration has null
boundaries: no liquid exits the domain and no lower surface intercepts it.

![Virtual flux and fast-drop fractions](../../results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/06_virtual_flux_and_fastdrop_evolution.png)

**Figure 6 — Terminal-speed transport and fast-drop classes.** The left panel
shows the mass-transport proxy for every resolution. The right panel compares
the 1,024 and 8,192 ensembles for liquid-mass fractions above 0.25, 0.5, and
1 m s\(^{-1}\). They are nearly coincident. Speeds of 2 or 4 m s\(^{-1}\) do
not have useful liquid mass by 120 min, so a multi-metre-per-second rain
threshold would be arbitrary.

![Terminal-speed mass spectra](../../results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/07_terminal_speed_mass_spectrum.png)

**Figure 7 — Mass spectrum in speed coordinates.** This is the mass DSD
remapped from radius to terminal speed, not an independently simulated
velocity PDF. It shows that the occupied fast-drop tail is mainly sub- to
approximately 1 m s\(^{-1}\).

For a descriptive timing indicator, the first stored time at which at least
1% of liquid mass has \(v_t\geq1\) m s\(^{-1}\) was measured. Its timing
precision is limited by the 2-minute output grid.

![Fast-drop development times](../../results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/10_fastdrop_development_time.png)

**Figure 8 — Fast-drop development time.** Dots are members and black bars are
member means. Scatter shrinks sharply as resolution rises: 2 SDs span
62–84 min, while the high-resolution levels lie near 68–70 min. This is a
useful resolution-sensitive emergence indicator, not rainfall onset.

## Spatial evolution

![Spatial liquid-mass fields](../../results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/08_spatial_total_droplet_mass_fields.png)

**Figure 9 — Spatial liquid-mass fields.** Rows are full-20 means at
\(N_{\rm cell}=2\), 1,024, and 8,192; columns are 0, 60, and 120 min. The
fields show in-domain liquid-mass redistribution, not rain-out. The 1,024 and
8,192 patterns agree substantially more closely than the 2-SD field.

## Convergence audit and physical corroboration

For positive scalar diagnostics, the all-time comparison uses the symmetric
percentage difference

\[
\delta(t)=\frac{200|A(t)-B(t)|}{|A(t)|+|B(t)|}.
\]

The 500-bin mass-DSD statistic is total variation after normalising to unit
liquid mass:

\[
\mathrm{TV}(t)=50\sum_b|p_b(t)-q_b(t)|.
\]

At each comparison, the 20 members on both sides are independently resampled
with replacement 2,000 times. The criterion is the one-sided 95% bootstrap
upper bound of the maximum over post-initial stored times. Each candidate must
pass against the 8,192 internal comparator and across both
\(N\rightarrow2N\) and \(2N\rightarrow4N\).

The primary gate uses a 5% margin for the 500-bin mass DSD, \(\lambda_0\),
\(\lambda_2\), \(\lambda_3\), and mass-weighted terminal speed. It uses a
10% tail margin for \(\lambda_6\) and \(r_{90}\). The physical audit applies
the same 5% core margin to geometric area, liquid-equivalent water,
mass-weighted terminal speed, and transport; the \(Z\) proxy uses the 10%
tail margin.

![Physical reference ladder](../../results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/09_physical_diagnostics_reference_ladder.png)

**Figure 10 — Physical reference ladder.** Dots are observed full-20 all-time
differences from 8,192. Vertical bars are one-sided 95% member-bootstrap upper
bounds. Red dashed lines are the metric margins. It quantifies precision
relative to an internal high-resolution comparator, not independent numerical
truth.

| comparison | A upper | L upper | Z upper | speed upper | flux upper | outcome |
|---|---:|---:|---:|---:|---:|---|
| 512 vs 1,024 | 1.66% | 3.21% | 8.94% | 3.90% | **6.46%** | fail: flux exceeds 5% |
| 1,024 vs 8,192 | 1.00% | 1.88% | 5.71% | 2.35% | 3.53% | pass |
| 1,024 vs 2,048 | — | — | — | — | 3.00% | pass flux check |
| 2,048 vs 4,096 | — | — | — | — | 3.40% | pass flux check |

For 1,024 versus 8,192 the largest physical
upper-bound/tolerance ratio is \(0.707\), controlled by transport:
3.53% divided by the 5% margin. For 512 to 1,024 the flux bound is 6.46%,
or 1.292 times the margin. The physical metrics therefore independently
reject 512 and corroborate

\[
\boxed{N_{\rm cell}=1{,}024}
\]

as the smallest tested operational resolution for this trajectory and metric
suite. The binned flux was checked against total liquid mass multiplied by
liquid-mass-weighted terminal speed; their largest difference in the 8,192
ensemble mean is only 0.005%.

## Final statement and limits

The complete requested analysis is now available: number and mass DSDs;
\(\lambda_0\) through \(\lambda_6\); mass, radius, speed, and active-SD
histories; physical \(r^2\), \(r^3\), and \(r^6\) proxies; terminal-speed
transport; fast-drop timing; spatial fields; and bootstrap convergence
checks.

For the audited fixed-20 normal-sampling constthermo2d experiment over
120 minutes, **1,024 SDs per initially populated grid box** is the smallest
tested level that meets the stated distribution, moment, radius,
terminal-speed, and physical-transport checks against 8,192 and through two
adjacent doublings.

It must not be described as surface-rainfall convergence. Establishing surface
flux or rainfall onset would require sedimenting outflow and an explicitly
defined lower-boundary measurement.

## Reproducibility products

- Generator: scripts/analyze_constthermo2d_fixedgrid_physical_v1.py
- Full figure suite: results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/
- Physical bootstrap rows:
  results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/physical_reference_and_adjacent_bootstrap.csv
- Fast-drop table:
  results/analysis/constthermo2d_fixedgrid_physical_diagnostics_v3/fastdrop_development_times.csv
- Original operational selection:
  docs/analysis/constthermo2d_fixedgrid_operational_selection_v1.md
