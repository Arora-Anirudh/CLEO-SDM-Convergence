# ADR 0003: Separate Golovin tail growth from rain onset

- Status: accepted for the development protocol; production threshold remains provisional
- Date: 2026-07-28

## Context

The first Stage-0 diagnostic copied the \(t_{10}\) definition used by Morrison
et al. (2024): the first time at which at least 10% of liquid mass is carried
by drops with radius \(r\geq40\,\mathrm{\mu m}\). That paper initializes its
box model from a gamma distribution truncated to 1-25 μm. Its 40 μm rain-size
class is therefore empty initially.

This project's starting configuration is different. Following Clara Bayley's
direction, `collisions0d_reference.yaml` inherits the
`PerformanceTestingCLEO/collisions0d` initializer with a sampled radius span of
1-75 μm. The audited Stage-0 member consequently begins with 34.25% of its
liquid mass at \(r\geq40\,\mathrm{\mu m}\). A 10%-above-40-μm time is already
crossed at time zero and cannot measure collision-driven onset.

The 40 μm separation is also not precipitation in this application. The 0-D
box has neither sedimentation nor fallout.

## Decision

The Golovin convergence protocol will not use the inherited \(t_{10}\) as a
primary convergence metric.

The 40 μm mass fraction remains a descriptive partition of the in-box
distribution. Optional tail timing is expressed generically as

\[
F_{\ge R}(t)
=
\frac{\sum_{i:r_i\ge R}\xi_i m_i}
     {\sum_i \xi_i m_i},
\qquad
t_{R,f}
=
\inf\{t:F_{\ge R}(t)\ge f\}.
\]

The development configuration uses \(R=1000\,\mathrm{\mu m}\) and \(f=0.10\).
The result is called a **millimetre-tail formation time**, not rain onset or
precipitation. It remains interval-censored by the output interval.

Primary Golovin convergence evidence remains:

1. fixed-bin, no-smoothing L1 error against the analytical distribution;
2. relative analytical errors in radius moments \(M_0\), \(M_3\), and \(M_6\);
3. liquid-mass conservation as a software invariant.

The mass fraction above the registered large-drop threshold, mass-weighted
q99, and \(t_{R,f}\) are secondary tail diagnostics. The production value of
\(R\), the fraction \(f\), and the observation interval remain subject to
scientific review.

## Literature basis

- Unterstrasser et al. (2017), Sect. 2.1 and results: initialization and
  representation of the large-drop tail materially affect collision outcomes;
  moments and mass-density distributions are the main evaluation quantities.
- Morrison et al. (2024), Sect. 3: \(t_{10}\) at 40 μm is paired with an
  initial DSD truncated to 1-25 μm. The definition cannot be transferred while
  changing the initial support.
- Zmijewski et al. (2024): higher moments and the large-droplet end converge
  more slowly than low moments, supporting separate tail diagnostics rather
  than one universal convergence number.

## Consequences

Positive:

- the timing metric is not already crossed by construction;
- threshold and fraction are explicit in every member record;
- historical Stage-0-v1 results remain immutable and interpretable;
- the code no longer labels an in-box size threshold as precipitation.

Limits:

- 1000 μm and 10% are development choices, not a universal physical
  definition;
- \(t_{R,f}\) can still be noisy or censored and requires its own ensemble-size
  assessment;
- the Long-kernel study must register its own tail/onset estimands rather than
  inherit Golovin's numerical threshold automatically.
