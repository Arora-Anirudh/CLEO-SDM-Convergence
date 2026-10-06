# 2-D `constthermo2d` fixed-grid pilot analysis, v1

**Status:** accepted execution and descriptive pilot analysis; **not** a
convergence selection, an onset result, or a surface-rainfall calculation.

## What was analysed

The input is the internally consistent 16-thread cohort recorded in
[`../runs/constthermo2d_fixedgrid_pilot_v3_16threads_2026-09-24.md`](../runs/constthermo2d_fixedgrid_pilot_v3_16threads_2026-09-24.md): three independent initialisations at each of

\[
N_{\rm cell}=8,\;32,\;128,\;512,
\]

where `N_cell` is the number of superdroplets in each of the 120 initially
populated grid boxes. The corresponding domain totals are 960, 3,840, 15,360
and 61,440 SDs. Every trajectory has 61 stored output times from 0 to 120 min.

The authoritative raw output remains in

```text
/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/pilot_v3_16threads/
```

The local cache deliberately contains only `time`, `raggedcount`, `radius`,
`xi`, `msol`, `coord1`, `coord3`, native mass moments and the receipt files.
This lets the analysis reconstruct the actual particles without modifying the
production archive.

## Reconstruction and audit

The script
[`../../scripts/analyze_constthermo2d_fixedgrid_pilot_v1.py`](../../scripts/analyze_constthermo2d_fixedgrid_pilot_v1.py)
uses the stored radius \(r_i\), multiplicity \(\xi_i\), solute mass and
position of every active superdroplet. Domain radius moments are reconstructed
as

\[
\lambda_p(t) = \frac{1}{V}\sum_{i\in\mathrm{active}(t)} \xi_i
\left[\frac{r_i(t)}{1\;\mu\mathrm{m}}\right]^p.
\]

Thus \(\lambda_0\) is number concentration, \(\lambda_2\) is an
area-related moment, \(\lambda_3\) is proportional to a wet-volume/mass
moment, and \(\lambda_6\) strongly weights large drops and is the
radius-moment analogue of a radar-reflectivity diagnostic. The exported total
droplet mass follows CLEO's `Superdrop::mass()` exactly:

\[
m_i = \frac{4\pi}{3}\rho_l r_i^3
       +m_{\mathrm{sol},i}\left(1-\frac{\rho_l}{\rho_{\mathrm{sol}}}\right),
\]

with the supplied dry-solute mass. This matters: a pure-water reconstruction
does not match the native `massmom1` observer at early time. With the actual
CLEO definition, reconstructed \(\lambda_0\) matches native `massmom0`
exactly and total mass matches `massmom1` to at worst \(2.7\times10^{-7}\)
relative error across all twelve members and all 61 times.

The terminal velocity is not a new parameterisation. The analysis evaluates
the same Rogers--Gunn--Kinzer relation used in `main_const2d.cpp`, written in
terms of diameter \(D\) in mm:

\[
v_t(D)=
\begin{cases}
4D\,[1-\exp(-12D)], & D<0.3725\;\mathrm{mm},\\
9.65-10.43\exp(-0.6D), & D\ge0.3725\;\mathrm{mm}.
\end{cases}
\]

The reported fall-speed curve is a total-droplet-mass-weighted mean,
\(\sum_i\xi_i m_i v_{t,i}/\sum_i\xi_i m_i\). It answers which fall speed
is carried by the mass, rather than by the numerous smallest droplets.

## Figures produced

All figures and machine-readable diagnostics are in
[`../../results/analysis/constthermo2d_fixedgrid_pilot_v1/`](../../results/analysis/constthermo2d_fixedgrid_pilot_v1/).

| File | Construction | What it can show at this stage |
|---|---|---|
| `pilot_domain_lambda_evolution.png` | three-member mean, individual lines and full range for \(\lambda_0\), \(\lambda_2\), total mass, and \(\lambda_6\) | bulk and tail-sensitive time evolution across the four pilot resolutions |
| `pilot_number_dsd_evolution.png` | domain number DSD at 0, 30, 60, 90, 120 min, averaged across members | movement of number across the radius spectrum |
| `pilot_mass_dsd_evolution.png` | corresponding total-droplet-mass DSD | where liquid/droplet mass moves in radius space |
| `pilot_altitude_resolved_mass_dsd.png` | six 250-m vertical layers at 0, 60 and 120 min for \(N_{cell}=512\) | that the evolving DSD has spatial structure; a layer curve is not a domain DSD |
| `pilot_spatial_liquid_water_maps.png` | 20x20 horizontal--vertical map from particle positions and mass at 0, 60, 120 min, averaged across the three \(N_{cell}=512\) members | the resolved redistribution of hydrometeor mass in the prescribed flow |
| `pilot_transport_and_terminal_speed.png` | lower-150-m mass fraction and mass-weighted terminal speed | a boundary-aware transport diagnostic and a physical fall-speed diagnostic |
| `pilot_final_member_spread.png` | all three 120-min members, full range and mean | how spread decreases strongly from 8 to 128--512 for several properties |

The DSD display uses a fixed 100-bin logarithmic mesh. This is a plotting
choice only: with 500 bins, sparse high-radius sampling appears as distracting
vertical spikes. Values below \(10^{-6}\) of the shared panel maximum are
masked in the display; the raw particle data and moment calculations are not
masked.

## Boundary-aware interpretation

The upstream C++ example sets `NullBoundaryConditions`. No physically defined
surface outlet is therefore present in this experiment. The quantity

\[
f_{z<150\,\mathrm{m}}(t)=
\frac{\sum_{z_i<150\,\mathrm{m}}\xi_i m_i}
     {\sum_i\xi_i m_i}
\]

is deliberately called the **lower-150-m total-droplet-mass fraction**. It is
useful for seeing whether mass is close to the lower domain, but it is not a
surface mass flux, precipitation rate, rainfall onset, or accumulated rain.
Its relative differences can become very large when the fraction itself is
near zero, so it should only be used alongside the absolute mass and
fall-speed diagnostics.

## Pilot evidence

The following comparison is descriptive only: the three-member mean at each
pilot resolution is compared to the three-member mean at \(N_{cell}=512\) at
the same stored time. It is not an independent high-resolution reference.

| Compared resolution | Largest \(\lambda_0\) deviation | Largest total-mass deviation | Largest \(\lambda_6\) deviation | Largest mass-weighted-speed deviation |
|---:|---:|---:|---:|---:|
| 8 | 6.59% | 22.75% | 132.00% | 59.12% |
| 32 | 4.50% | 7.99% | 43.28% | 21.39% |
| 128 | 0.90% | 2.95% | 12.55% | 2.13% |

At 120 min, the coefficient of variation among the three members decreases
from 46.1% to 5.5% for \(\lambda_6\), and from 12.6% to 2.0% for the
mass-weighted terminal speed, when moving from \(N_{cell}=8\) to 512. The
bulk measures are already close between 128 and 512, while the large-drop
diagnostic remains the most demanding one. This is exactly the expected
reason to retain both bulk and tail/transport observables in the later
convergence decision.

## Consequence for the production design

The pilot justifies a broad normal-sampling resolution ladder beginning below
the source default, but it does **not** yet justify choosing 128 or 512 as a
converged resolution. A defensible next stage is:

1. Run a single-member performance/trajectory gate at larger `N_cell` before
   committing a large ensemble. It must test the linked `maxnsupers=120*N_cell`
   setting, 61-output integrity, memory use and actual 16-versus-64-thread
   cost at a useful high resolution.
2. After that gate, freeze a fixed-20 normal-sampling ladder at
   \(N_{cell}=2,4,8,16,32,64,128,256,512,1024,2048,4096\). This preserves the
   factor-of-two resolution logic and includes the 2 and 4 SD-per-cell cases
   that have so far passed only native-input preflight.
3. Do not choose the ultimate internal reference in advance. The 512 pilot is
   only 61,440 domain SDs. If 4,096 per populated box is insufficient for the
   \(\lambda_6\), DSD-tail and transport comparisons, extend the reference
   gate to 8,192 or 16,384 per populated box (about 0.98 or 1.97 million
   initial domain SDs). The appropriate endpoint must be set from measured
   timing, memory and the pilot's high-resolution diagnostic stability.
4. Pre-register the estimator and margin only after a genuinely higher
   internal reference and bin-sensitivity check (for example 250/500/1000
   bins) exist. A criterion should combine distribution distance, \(\lambda_0\),
   \(\lambda_2\), \(\lambda_3\), \(\lambda_6\), terminal speed and the
   bounded transport proxy, while keeping distribution-bin sensitivity
   separate from a formal SD-resolution claim.

No new Levante job is included in this analysis record. The next performance
gate requires the researcher's explicit approval and a CPU-hour estimate first.
