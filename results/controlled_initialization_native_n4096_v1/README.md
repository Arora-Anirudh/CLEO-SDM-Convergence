# Controlled initialization native gate: 4096 SDs

This is the compact permanent record of the first project-owned controlled
initialization written and read through CLEO's native binary interface.

## Scope

- input generation and readback only;
- one controlled 4096-superdroplet bundle;
- no collision executable;
- no Zarr model output;
- no ensemble and no convergence claim.

## Provenance

| Item | Value |
| --- | --- |
| Slurm job | `26534015` |
| project commit used by job | `2f529cb15e8ed32581a88ca14bb54db4d2c202cc` |
| pinned CLEO commit | `83318c23223546d10759d202d70f4fa2f7fe4688` |
| account / partition | `bb1153` / `shared` |
| requested | 1 node, 1 task, 1 CPU, 940 MiB, 10 min |
| allocated | 2 CPUs, 940 MiB |
| measured | 11 s elapsed, 3916 KiB batch `MaxRSS` |
| stderr | empty |
| raw result size | 248 KiB |

Raw location at validation time:

```text
/scratch/b/b383673/SDM/CLEO-SDM-Convergence/runs/
  controlled_initialization_validation/controlled_init_n4096_v1
```

SCRATCH is temporary. The checksums and numerical facts below are the compact
permanent evidence; the native binaries are deliberately not committed.

## Gates that passed

- CLEO-native binary checksum matched the creation audit;
- all seven native attribute arrays had 4096 entries;
- all superdroplets belonged to gridbox 0;
- all dimensional attributes were finite and coordinates were in bounds;
- represented physical-droplet total was exactly
  `8388608000000000000`;
- read-back \(M_0\), \(M_3\) and \(M_6\) matched the creation audit;
- no model output existed.

Key numerical values:

| Quantity | Value |
| --- | ---: |
| \(M_0\) | `8388608.0 m-3` |
| \(M_3\) | `238740390128.70804 um3 m-3` |
| \(M_6\) | `1.358817751738688e16 um6 m-3` |
| \(M_6\) target-relative initialization error | `-8.333014756e-7` |
| liquid-water content | `0.9982363476244527 g m-3` |
| radius range | `1.00052759–74.96020570 um` |
| multiplicity range | `146643540107–9758949507368174` |

## Artifact checksums

| Artifact | SHA-256 |
| --- | --- |
| materialized config | `10493588a083a3033c449ca4749ae62b75a693ba2f08dae8df93ceadb2add990` |
| grid binary | `90835b0f88c77e768281bcba9d4cf5d546810895c8a7c4902096679491279ea7` |
| superdroplet binary | `d805fb278ed070396d8bf3bb0d655138f5f1124901d5ea917279f99e270420f2` |
| creation audit | `328ca39963126f5153521398be20770767e317744ef62385609dab5f89786e2a` |
| native readback JSON | `52e4288e4f85b696d9c3fb386885158c344183d244a4cc309c80771c0a816c15` |
| validation manifest | `6c79c0b8a44eba1b019d77fd00acd30e21cb43c7850f75ad24519cb1b8e8ebdc` |

## Important limitation discovered

The macOS and Levante source-array hashes differ even though the physical
gates pass. NumPy/libm versions can change the final bits of exponential and
cube-root calculations; CLEO's dimensionless binary round-trip can also
change radius bytes while preserving the checked values.

This result therefore supports the intended production design: create one
native bundle per resolution on the pinned Levante environment, preserve its
checksum, and reuse that exact file for all collision-stream members. It does
not support regenerating “equivalent” binaries inside every member directory.
