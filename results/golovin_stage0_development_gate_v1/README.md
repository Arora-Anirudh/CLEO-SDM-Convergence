# Golovin Stage-0 development gate v1

This directory is the compact, checksum-verifiable record of the first
Stage-0 member run and diagnostic audit on Levante. Raw Zarr output remains on
SCRATCH and is not versioned.

## Scope

- Project commit:
  `bfd3bdfb21ebcad01a6d3c8524d3fc8eb1c708ef`
- Pinned CLEO commit:
  `83318c23223546d10759d202d70f4fa2f7fe4688`
- Kernel: Golovin
- Matrix case: 0 of the four-case development-only matrix
- \(N_\mathrm{SD}\): 1,024
- Collision timestep: 1 s
- Observation interval: 300 s
- End time: 3,600 s
- Initialization seed: `2647907423`
- Collision seed: `16394419086637823225`
- Model job: `26521080_0`
- Diagnostic job: `26521145`
- Replay job: `26521184`

This is a software/provenance gate, not a convergence experiment. The matrix
manifest deliberately records `submission_authorized=false`, and only its first
case was run.

## Files

- `cases.tsv` and `matrix_manifest.json`: the immutable prepared development
  matrix and its submission guard;
- `build_manifest.txt`: exact project/CLEO commits, patch and executable
  hashes;
- `run_manifest.txt`: complete member parameters, Slurm context and Zarr-tree
  hash;
- `replay_validation_manifest.txt`: one-thread A/A/B collision-seed replay
  result;
- `analysis_stage0_v1/`: per-time and per-member diagnostics, figures,
  metadata and checksums.
- `analysis_stage0_v2/`: checksum-verified diagnostic-only reanalysis of the
  same immutable Zarr using the generic tail-timing schema; all unchanged
  scientific values are numerically identical to v1.
- `tail_threshold_review_v1/`: literature-grounded post-gate interpretation
  that rejects the inherited 40 μm onset definition and derives the
  interval-censored 1000 μm development tail time from the immutable table.

Run the following from this directory to verify the copied manifests and
diagnostic checksum record, then verify the diagnostic products themselves:

```bash
sha256sum -c SHA256SUMS
cd analysis_stage0_v1
sha256sum -c SHA256SUMS
cd ../analysis_stage0_v2
sha256sum -c SHA256SUMS
```

## Principal observations

- maximum absolute relative liquid-mass drift:
  \(1.5111\times10^{-8}\);
- fixed-bin mass below or above the registered 1-5000 μm interval: zero at
  every stored time for this member;
- fixed-bin relative L1 error: 0.0897 at time zero and 0.6856 at 3600 s;
- relative \(M_3\) error: about \(-1.802\times10^{-4}\), almost constant;
- relative \(M_6\) error at 3600 s: \(-0.4505\);
- mass fraction at \(r\ge1000\) μm: 0 until 2700 s, then 0.4239 at 3600 s;
- mass-weighted q99 grows from 57.5 to 2216.5 μm;
- 34.25% of mass is already at \(r\ge40\) μm at time zero, so the provisional
  `t10` based on 10% mass above 40 μm is not informative for this
  initialization.

The post-gate decision is documented in
[`tail_threshold_review_v1/README.md`](tail_threshold_review_v1/README.md).
For development, the generic secondary metric
\(t_{1000\,\mu\mathrm{m},0.10}\) lies in \((3000,3300]\) s for this member.
It is called millimetre-tail formation, not rain onset.

The large unsmoothed L1 values are expected to be sensitive to sparse
fixed-bin sampling at \(N_\mathrm{SD}=1024\). One member cannot determine mean
bias, stochastic spread or convergence.

The complete interpretation, compute accounting and limitations are in
[`docs/runs/golovin-stage0-development-gate.md`](../../docs/runs/golovin-stage0-development-gate.md).
