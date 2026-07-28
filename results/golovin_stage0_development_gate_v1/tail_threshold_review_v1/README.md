# Post-gate tail-threshold review

This is a derived interpretation of the immutable Stage-0-v1 member table. It
does not modify or replace the historical analysis.

## Why the original onset metric was rejected

Morrison et al. (2024) define \(t_{10}\) as the time when 10% of liquid mass is
in drops with \(r\geq40\,\mathrm{\mu m}\), using an initial DSD truncated to
1-25 μm. This project's Clara-derived `collisions0d` initializer samples radii
from 1-75 μm. The audited member already has 34.2468% of its mass above 40 μm
at time zero, so the copied \(t_{10}\) is crossed initially.

ADR 0003 therefore:

- retains the 40 μm mass fraction as a descriptive distribution partition;
- removes it as a Golovin convergence-onset criterion;
- defines optional tail timing generically as \(t_{R,f}\);
- registers \(R=1000\,\mathrm{\mu m}\), \(f=0.10\) for development;
- labels the result millimetre-tail formation, not rain onset or
  precipitation.

## Existing-member result

For this member, the mass fraction at \(r\geq1000\,\mathrm{\mu m}\) is
0.070577 at 3000 s and 0.212829 at the next stored output near 3300 s.
Therefore:

\[
t_{1000\,\mu\mathrm{m},0.10}\in(3000,3300]\ \mathrm{s}.
\]

The first recorded crossing is 3300 s. No interpolation is used. This
single-member value validates calculation only; it is not an ensemble estimate
or convergence result.

## Provenance

Source:
`../analysis_stage0_v1/member_time_diagnostics.csv`

Source SHA-256:
`c486b2f40225498e53a10d27361e1d396c19ff53d3c9686173b5f635c08f7067`

Decision:
[`docs/decisions/0003-tail-growth-not-rain-onset.md`](../../../docs/decisions/0003-tail-growth-not-rain-onset.md)

From this directory, verify the derived CSV with:

```bash
sha256sum -c SHA256SUMS
```
