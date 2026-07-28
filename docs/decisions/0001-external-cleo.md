# ADR 0001: Consume CLEO as a pinned external dependency

- Status: accepted
- Date: 2026-07-28

## Context

The scientific application and its experiment history must live in a
researcher-owned repository rather than inside a clone of upstream CLEO.
Clara Bayley's PerformanceTestingCLEO project demonstrates the required CMake
composition pattern, but its dependency points to a legacy CLEO v0.39.0
performance-testing branch.

## Decision

Use CMake `FetchContent` with the canonical repository
`https://github.com/yoctoyotta1024/CLEO.git` and an exact commit SHA. The
initial pin is:

`83318c23223546d10759d202d70f4fa2f7fe4688`

This was the head of CLEO `main` when the repository was scaffolded.

## Consequences

- Builds are reproducible and do not change when upstream `main` advances.
- CLEO upgrades require an explicit reviewed commit.
- Experiment manifests must record the CLEO pin.
- Project code can evolve independently without modifying upstream CLEO.
