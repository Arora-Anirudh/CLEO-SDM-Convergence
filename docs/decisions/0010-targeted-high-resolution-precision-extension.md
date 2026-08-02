# ADR 0010: targeted Golovin high-resolution precision extension

- Status: approved by the researcher for implementation; Levante submission pending final preflight and explicit resource disclosure
- Date: 2026-08-01
- Scope: controlled 0-D Golovin collision-coalescence only

## Decision

Keep the completed balanced fixed-50 result unchanged. Add exactly 100 new, independent collision members at each of 262,144 and 524,288 SDs. The two levels will then have 150 members each; the existing 1,048,576-SD ensemble remains at 50 members. No new resolution is added.

The original 50 members, their raw Zarr stores, immutable matrices and `analysis_v2` are read-only inputs. A new matrix uses member indices 50--149 and a separate seed namespace. The existing controlled binary bundle at each targeted resolution is deliberately reused byte-for-byte: it defines the same controlled initial population, while the new collision RNG streams are independent.

## Why this scope

The fixed-50 practical criterion was unresolved only because the 95% one-sided bound for the 262,144-to-524,288-SD \(M_6\) change at 3,600 s was 1.174 percentage points, slightly above the predeclared one-percentage-point margin. The point change was 0.536 percentage points. Adding members to these two independent ensembles targets the uncertainty term in the limiting comparison; more 1,048,576-SD members do not reduce that pair's uncertainty.

The update is intentionally a single frozen block, not sequential optional stopping. If the extension remains inconclusive, the result is reported as unresolved at the predefined 150/150/50 allocation and the next design is reconsidered separately.

## Interpretation boundary

This is a transparent, prospectively frozen **follow-up** prompted by an inspected fixed-50 result. It can resolve the high-resolution practical criterion for the stated box, initialization, timestep, diagnostics and error margin. It must not retroactively be described as the original balanced fixed-50 formal selection, nor as a universal SDM resolution requirement.

The two registered adjacent comparisons remain:

\[
262144 \rightarrow 524288, \qquad 524288 \rightarrow 1048576.
\]

For each, 500-bin distribution L1, signed \(M_0\), and signed \(M_6\) are checked at every registered time. The one-sided 95% percentile-bootstrap upper bound of the absolute independent-ensemble change must not exceed one percentage point. The 250- and 1000-bin results are sensitivity diagnostics, not automatic vetoes. The rejected ratio of successive improvements remains excluded.

## Computational layout

The 200 independent members are run inside one allocation, not as a Slurm array. Twenty lightweight Bash workers dispatch one actual `srun` member step at a time, with `--exclusive --mem=0 --mpi=pmix_v3`, one rank and one thread. `--hint=nomultithread` requests physical-core placement. This avoids reserving the same allocation core first for a worker and then again for its CLEO process. It is scheduling parallelism across independent stochastic histories; `collisions0d` itself is not MPI-decomposed.

## Reproducibility products

After the model and per-member Stage-0 gates pass, the analysis creates a read-only combined view consisting of an analysis-only cases table, source-provenance table and absolute symlinks to the original run directories. It does not copy or modify Zarr outputs or claim that the combined table is the matrix recorded by original member manifests.
