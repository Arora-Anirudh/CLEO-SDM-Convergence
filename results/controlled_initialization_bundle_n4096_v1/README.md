# Controlled initialization frozen bundle: N=4096

This directory is the compact, reviewable record of Levante job `26534596`.
The job created and independently read one persistent CLEO-native controlled
Golovin initialization bundle at:

```text
/home/b/b383673/SDM/CLEO-SDM-Convergence-records/controlled_bundles/
  golovin_controlled_N004096_v1
```

The persistent HOME bundle contains the actual native grid and superdroplet
binary files. Those binaries are intentionally not duplicated here. Their
sizes and SHA-256 checksums are recorded in `bundle_manifest.json`.

## Compute request and measured use

| Item | Value |
| --- | --- |
| account / partition | `bb1153` / `shared` |
| requested nodes / tasks / CPUs per task | 1 / 1 / 1 |
| requested memory / walltime | 940 MiB / 10 minutes |
| execution | serial input generation/readback; no model, GPU or ensemble |
| Slurm allocation | 2 CPUs |
| elapsed time | 15 seconds |
| batch MaxRSS | 3.76 MiB |
| exit code | `0:0` |
| stderr | empty |

## Main evidence

- bundle schema: `controlled_initialization_bundle_v1`;
- project commit: `e1935d7381535b793fda8b5905145ae7a9a9e8fb`;
- CLEO commit: `83318c23223546d10759d202d70f4fa2f7fe4688`;
- superdroplets: 4096;
- represented physical droplets: `8388608000000000000`;
- native superdroplet SHA-256:
  `d805fb278ed070396d8bf3bb0d655138f5f1124901d5ea917279f99e270420f2`;
- bundle-manifest SHA-256:
  `daf8c66c86df98fb0bbaf6e69bd7c832ab42e9463305e8faca7ff866ce45bdfe`;
- all 11 persistent bundle files are non-writable;
- bundle size is 290,319 bytes;
- no Zarr directory or collision-model output exists.

`population_sha256_exact_match=False` in the native readback is expected:
CLEO writes dimensionless radii and re-dimensionalizes them on read. The
registered physical gates, moments, exact represented droplet total and native
file checksum pass. Collision members will reuse the native file itself, not
reconstruct the source arrays.

This record validates bundle creation and immutability. It is not a collision
run, convergence result, production authorization or proof of same-stack
regeneration identity.
