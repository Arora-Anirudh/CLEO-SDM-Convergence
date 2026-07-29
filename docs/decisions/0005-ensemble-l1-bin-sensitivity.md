# ADR 0005: Ensemble L1 order and fixed-bin sensitivity policy

- Status: accepted
- Date: 2026-07-29
- Scope: Golovin collision-timestep screen and resolution convergence
- Supersedes: the absolute 0.005 cross-bin L1 condition in ADR 0004

## Context

The formal distribution estimand is the relative L1 error of the
ensemble-mean numerical mass distribution. L1 is nonlinear:

```text
L1(mean(g_j)) is generally not equal to mean(L1(g_j)).
```

The first analyzer implemented the second expression. A compiled pilot
revealed the mismatch before the timestep screen was submitted. Diagnostic
schema 3 now stores every member's fixed-bin numerical and analytical arrays
so the ensemble mean can be formed before L1 is evaluated.

ADR 0004 also required the 250- and 1000-bin ensemble L1 values to differ from
the primary 500-bin value by at most 0.005. The corrected 5-member,
16,384-SD timestep screen showed that even the 0.1-s numerical reference could
not satisfy that condition. Across the six registered decision times, its
absolute differences from the 500-bin value were:

```text
250 versus 500 bins:  0.0106 to 0.0222
1000 versus 500 bins: 0.0215 to 0.0327
```

The reason is structural. A finite superdroplet ensemble is a discrete sample.
Increasing the histogram resolution exposes more finite-ensemble roughness,
so the absolute L1 value can increase even when the simulation and analytical
solution are unchanged. Requiring equal scalar L1 magnitudes across bin counts
therefore mixes histogram sampling noise with collision-timestep bias.

## Decision

1. Every Golovin member stores numerical and analytical distributions on the
   registered 250-, 500- and 1000-bin logarithmic-radius grids.
2. Numerical distributions are averaged bin by bin across members before L1
   is calculated.
3. The primary reported and convergence metric remains the 500-bin L1.
4. For collision-timestep selection, candidate-versus-reference equivalence
   must pass independently at 250, 500 and 1000 bins at every registered time.
5. Absolute L1 differences among the three grids remain reported sensitivity
   diagnostics, but are not independent acceptance gates.
6. A timestep is not accepted merely because one bin grid passes.
7. The same policy applies to the resolution experiment: the primary
   conclusion is made on 500 bins and must not reverse on 250 or 1000 bins.

This tests robustness of the **scientific decision** to histogram resolution
without requiring a discrete finite ensemble to have identical scalar
histogram errors at different bin widths.

## Consequences

- The 0.1-s reference can serve as a conservative fallback when no coarser
  timestep has sufficiently precise equivalence evidence.
- Cross-bin L1 differences remain visible in `bin_robustness.csv` and plots.
- A decision reversal at 250 or 1000 bins still blocks selection.
- More members may be added adaptively when a coarser timestep is scientifically
  desirable but its equivalence interval is too wide.
- Existing raw model outputs do not need to be rerun; the schema-3 member
  archives contain the required distributions.

## Validation

Tests include:

- a constructed case where mean member L1 equals 1 while ensemble-mean L1
  equals 0;
- identical candidate/reference stacks with exactly zero bootstrap difference;
- a case with cross-bin L1 sensitivity greater than 0.005 but unchanged
  candidate/reference equivalence;
- a case where alternate-bin equivalence fails and blocks the coarser
  timestep.
