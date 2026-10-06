# Exploratory stochastic emulation of the 2-D CLEO fixed-grid cohort

**Status, 1 October 2026:** a local feasibility benchmark, **not** a new CLEO
ensemble or a revised convergence analysis. No Levante model jobs were submitted.
The subsequent [Mac-only calibration follow-up](constthermo2d_stochastic_emulator_calibration_v2.md)
tested whole-member residual resampling and did not pass the uncertainty gate.

## Questions kept separate

1. Can a learned conditional distribution reproduce *new independent members*
   at resolutions that appeared in training?
2. Can it predict the distribution at an *entirely unseen, higher resolution*?

Passing the first test does not imply passing the second. Neither synthetic
member count nor high-resolution extrapolation is evidence of CLEO convergence.

## Source and domain

The read-only source is
`results/cache/constthermo2d_fixedgrid_production_v1/ncell*/member*.npz`.
There are 20 independent members at each resolution. This first benchmark uses
`N_cell = 128, 256, 512, 1024, 2048, 4096`, where `N_cell` means initial SDs
**per populated box**, not the domain total. It deliberately avoids the
`N_cell=8192` cohort for clean resolution extrapolation: that cohort required
a separately audited 4 nm–2 µm initial-radius support, versus 3 nm–3 µm
below it. A comparison to it would mix resolution with initialization protocol.

Each *entire 61-time-point member trajectory* is one statistical observation.
The diagnostics are λ₀, λ₂, λ₃, λ₆, mass-weighted terminal speed and
mass-weighted r₉₀. The saved 500-bin mass DSD is integrated to 25 coarse bins;
the model represents each time's **mass fractions**, not the original 500-bin
mass density. The coarse DSD is therefore a pilot shape diagnostic, not a
replacement for the primary 500-bin convergence metric. Spatial 20×20 fields
are not generated in this version.

## Models and validation

The model first transforms complete diagnostic trajectories to log space and
mass-DSD fractions to square-root space. Separate 24-component PCAs are fit
on training members only. A conditional mean is then fitted to the joint latent
representation using either (a) regularized ridge regression in resolution
features or (b) a small two-hidden-layer neural network. A shrinkage covariance
of *within-resolution member residuals*, with a fitted resolution-dependent
scale, supplies stochastic whole-trajectory draws. This is a small neural
stochastic emulator **pilot**, not yet the proposed conditional normalizing
flow or a diffusion model. The current environment lacks a working modern
flow framework; more importantly, the pilot must pass baseline tests before
increasing model capacity.

Three comparisons were predeclared in the script:

- **Seen resolution:** four member-wise folds; each fold holds out five complete
  members per resolution. No held-out member's time slices or DSD bins enter
  the training representation.
- **Higher-resolution backtests:** train below 2,048 and test all 20 genuine
  2,048 members; independently train below 4,096 and test all 20 genuine 4,096
  members. The test resolution is absent from PCA and model training.
- **Simple baseline:** resample actual members from the nearest available lower
  resolution. A neural method should be judged against this inexpensive option,
  not just against a zero-skill forecast.

The synthetic predictive intervals are computed from 300 conditional draws.
Reported coverage is descriptive across correlated members/times; the nominal
90% line is a calibration target, not a significance test. The complete
member-level score table and input SHA-256 list are in the output directory.

## What happened

The neural model fits the **mean** at an unseen high resolution fairly well.
For the 4,096 backtest, its maximum postinitial ensemble-mean symmetric errors
are 0.26% for λ₀, 2.49% for λ₆, 1.09% for mass-weighted terminal speed and
3.21% for r₉₀. Its maximum 25-bin mass-DSD total variation is 0.72%. These
small-looking values partly reflect that the underlying CLEO cohorts are
already close together at high resolution.

**The stochastic distribution is not calibrated.** At withheld 4,096, the
neural model's nominal 90% predictive interval covers only 76% of the
postinitial λ₀ member values, 81% for λ₆, 80% for terminal speed and 74% for
r₉₀. The nearest-lower-resolution empirical baseline covers 98%, 96%, 95%
and 100%, respectively. The baseline is conservatively broad, but the neural
model is clearly under-dispersed. At withheld 2,048, neural coverage is 78%,
84%, 84% and 80% for the same quantities. A successful mean curve is therefore
not sufficient grounds to generate a credible new high-resolution ensemble.

The 24-component reduction retains about 98–99% of training diagnostic
variance but only about 87–90% of coarse mass-DSD-shape variance. This is
another limitation on synthetic DSD variability. The chosen model and PCA
size are exploratory; the validation results should not be used to tune a
post-hoc model and then treated as a fresh blind test.

## Decision and next experiment

One file of 300 **explicitly labelled synthetic, non-CLEO** trajectories at a
*seen* resolution, `N_cell=1024`, was saved to test the sampling and physical
format. It does not add 300 members to the 20 real CLEO runs. No synthetic
`N_cell=8192` or 16,384 cohort was written. The higher-resolution generation
gate remains **not passed** because the uncertainty is under-dispersed and the
neural method has not clearly beaten the simple empirical baseline.

The next bounded experiment is to improve the residual distribution and its
calibration using only training-resolution member folds, then repeat the
2,048/4,096 resolution backtests *without treating them as freshly blind after
this inspection*. A truly fresh test of extrapolation to 8,192 under a common
initialization protocol would require independent CLEO members at that setting;
the existing 8,192 cohort can provide a sensitivity comparison but cannot
fully separate the radius-support change. Generation beyond the observed
ladder (e.g. 16,384) would remain a clearly labelled scenario until tested
against genuine CLEO runs. No new run is proposed or submitted here.

## Reproduce locally

From `CLEO-SDM-Convergence`:

```bash
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/private/tmp/codex-sdm-mpl \
  /opt/anaconda3/bin/python \
  scripts/explore_constthermo2d_stochastic_emulator_v1.py --draws 300
```

Outputs: `results/analysis/constthermo2d_stochastic_emulator_v1/`. The
`manifest.json` lists every input hash, split boundary and the fact that no
higher-resolution synthetic cohort was generated. See
`01_heldout_validation.png`, `02_resolution_backtest_4096.png`,
`03_predictive_coverage.png`, `heldout_scores_summary.csv` and
`alltime_resolution_backtest.csv`.

## Relation to the literature

SEEDS demonstrates generative ensemble emulation, but its two *input* seeds
must not be confused with the twenty years of retrospective forecasts used
for training: [Li et al., 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC10980268/).
Conditional generative multi-fidelity modelling of turbulent flows is a closer
structural analogue to a future lower-/higher-resolution CLEO emulator, but
does not validate this small dataset or its extrapolation:
[Geneva and Zabaras, 2020](https://arxiv.org/abs/2006.04731/).
The need to test stochastic emulators against independent replicated simulator
outputs, including dispersion rather than only means, is discussed in
[Baker et al., 2021](https://arxiv.org/abs/1902.01289/).
