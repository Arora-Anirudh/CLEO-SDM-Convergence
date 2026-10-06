# 2-D constthermo2d: operational resolution-selection readout

## Decision boundary

This document applies a transparent operational rule to the completed fixed-20 normal-sampling ladder. It does not turn the 8,192-SD-per-populated-cell cohort into independent numerical truth. The resulting selection is configuration-, diagnostic-, and 20-member-ensemble-specific.

## Declared criterion applied here

For each candidate, every reported statistic is the maximum over post-initial stored times. The uncertainty value is a one-sided 95% member-bootstrap upper bound from 2,000 independent resamples of each 20-member cohort.

- Core diagnostics: 500-bin mass-DSD total variation, lambda0, lambda2, lambda3, and mass-weighted terminal speed must each be at most 5%.
- Tail diagnostics: lambda6 and mass-weighted r90 must each be at most 10%.
- A candidate must pass against the 8,192 internal comparator and across two successive doublings: N to 2N and 2N to 4N.
- The 250- and 1,000-bin DSD values remain sensitivity diagnostics; the 500-bin DSD is the primary decision statistic.

## Result

The smallest tested candidate passing every stated bootstrap gate is **Ncell = 1,024 SDs per initially populated grid box** (122,880 initial domain SDs).

It passes against the 8,192 comparator and the 1,024-to-2,048 and 2,048-to-4,096 adjacent-doubling confirmations. The next lower candidate, Ncell=512, fails the first-doubling gate because its 500-bin mass-DSD TV upper bound is just above the 5% core margin.

## Protocol-comparability audit

The 8,192 cohort used the separately audited 4 nm to 2 micrometre radius support because the original 3 nm to 3 micrometre support produces zero multiplicities at this resolution. The support scan estimated that this removes 0.000052% of initial number and 0.00205% of initial mass. At t=0, the observed 4,096-versus-8,192 500-bin mass-DSD TV is 0.035% and total-mass symmetric difference is 0.002%. These values are reported rather than treated as evidence that the two protocols are literally identical.

## What the selection supports

It supports Ncell=1,024 as the smallest tested operational resolution under this declared metric set, margins, compact 120-s output grid, and 20-member design. It does not establish universal SDM convergence, an arbitrary-member guarantee, an independently referenced numerical error, or a rainfall conclusion from this closed 2-D configuration.

## Produced evidence

- `selection_decisions.csv`: gate-level outcome for every candidate.
- `selection_pair_diagnostics.csv`: every metric, point estimate, bootstrap upper bound, tolerance, and pass status.
- `01_operational_convergence_gate_matrix.png`: compact graphical decision audit.
