# Levante account migration: `b383673` to `m301324`

Date started: 2026-07-30

## Purpose and safety rules

The SDM/CLEO project is moving to the researcher's new Levante identity
`m301324`. The old account remains the read-only migration source until the
new copy is complete and verified.

- Do not delete or overwrite the old HOME or SCRATCH trees during migration.
- Keep separate SSH aliases for the old and new identities.
- Determine the new Slurm project association from `sacctmgr`; do not infer it
  from the username.
- Copy scientific records and data byte-for-byte and verify checksums/counts.
- Recreate Git checkouts from GitHub where possible.
- Rebuild environments, CLEO, YAC/Yaxt and application build trees because
  compiled products embed old absolute paths.
- Keep historical manifests unchanged even when they contain
  `/home/b/b383673` or `/scratch/b/b383673`; those paths are provenance.
- Revoke any temporary cross-account ACL after the destination audit passes.

## Source inventory

The 2026-07-30 read-only inventory found:

| source | size | migration treatment |
|---|---:|---|
| `HOME/SDM/CLEO` | 552 MiB | fresh clone at the recorded commit |
| `HOME/SDM/CLEO-SDM-Convergence` | 89 MiB | fresh GitHub clone |
| `HOME/SDM/CLEO-SDM-Convergence-golovin-protocol` | 76 MiB | recreate the branch/worktree from GitHub |
| `HOME/SDM/CLEO-SDM-Convergence-records` | 114 MiB | copy and checksum |
| `HOME/SDM/CLEO_convergence` | 3.0 MiB | preserve source/patch provenance; do not treat as canonical |
| `HOME/SDM/cleo_builds` | 1.1 GiB | rebuild |
| `HOME/SDM/cleo_dependencies` | 180 MiB | rebuild |
| other HOME configs, scripts, records and trial model | about 7.6 MiB | copy, classify and checksum |
| `SCRATCH/SDM/CLEO-SDM-Convergence` | 38 GiB | copy raw scientific runs |
| `SCRATCH/SDM/cleo_convergence` | 6.8 GiB | copy legacy exploratory runs |
| SCRATCH logs and trial outputs | about 5.5 MiB | copy |

The portable SCRATCH payload is therefore about 45 GiB. The compiled HOME
payload is deliberately excluded from byte-for-byte migration and will be
recreated.

## Connection state

The Mac SSH configuration retains:

```text
levante-login   -> b383673
levante-m301324 -> m301324
```

The existing RSA public key authenticates the old identity but DKRZ reported
that it had already been registered previously and would not register it for
`m301324`. A dedicated Ed25519 key was therefore created:

```text
private key: ~/.ssh/levante_m301324_ed25519
public key:  ~/.ssh/levante_m301324_ed25519.pub
fingerprint: SHA256:boO1kf9joAqaw6pELnkcAvKJZ0cXbuhxpqaSD/zg9H8
```

Only the `levante-m301324` alias uses this key. The private file has mode 600,
the public file has mode 644, and the old `levante-login` RSA configuration is
unchanged. The new public key was activated through LUV. Passwordless SSH was
verified on 2026-07-30:

```text
alias: levante-m301324
remote identity: m301324
remote HOME: /home/m/m301324
login host observed: levante2.lvt.dkrz.de
```

Immediately after registration, the key was accepted by login nodes 0 and 2
but rejected by the other load-balanced gateway addresses. To make VS Code
reliable while DKRZ synchronizes the registration, only `levante-m301324` is
temporarily pinned to `levante0.dkrz.de` with
`HostKeyAlias levante.dkrz.de`. The old-account alias remains load-balanced
and unchanged. Return the new alias to `levante.dkrz.de` after all gateway
addresses accept the key.

## New account state

The new identity belongs to both `ka1125` and `mh0731`. Clara confirmed that
the SDM project must use Slurm account `mh0731`; future SDM jobs must therefore
request `--account=mh0731`.

The pre-migration storage audit found approximately 1.26 GiB used of the
60-GiB HOME quota and about 15 TiB available in the new SCRATCH namespace.
Both `/work/ka1125` and `/work/mh0731` were writable, but neither is needed for
this migration; the current workflow keeps durable code/compact records in
HOME and restartable raw model output in SCRATCH.

The following destinations were created:

```text
/home/m/m301324/SDM
/scratch/m/m301324/SDM
```

The canonical Git checkouts were recreated rather than copied:

| checkout | branch | verified commit |
|---|---|---|
| `CLEO-SDM-Convergence` | `main` | `dc15471b32e07583b26ce5a83065f14934cd6180` |
| `CLEO-SDM-Convergence-golovin-protocol` | `agent/golovin-convergence-protocol` | `472e37d214b49e7c7e9b2ee61be067b98b4d9702` |

Temporary ACLs grant `m301324` read/traverse access to the old SDM HOME and
SCRATCH roots. They do not grant write or delete access and must be removed
after verification.

## Staged migration protocol

1. Authenticate `levante-m301324` and record `whoami`, HOME, project
   associations, HOME/SCRATCH quotas and filesystem permissions.
2. Test whether the new identity can read the exact old SDM roots. If not,
   grant temporary, user-specific read/traverse ACLs only on those roots.
3. Create destination roots under `/home/m/m301324/SDM` and
   `/scratch/m/m301324/SDM`.
4. Recreate canonical Git repositories from GitHub and verify commits,
   branches and remotes.
5. Copy permanent records, legacy source/configuration material and raw
   SCRATCH runs with restartable `rsync`; record file counts and byte totals.
6. Verify existing SHA-256 manifests and create migration inventories for
   trees without manifests.
7. Recreate the Python tool environment, project virtual environment,
   YAC/Yaxt and exact CLEO/application builds under new absolute paths.
8. Run unit tests, seed-replay checks and one small no-model/serial smoke gate.
   Any future Slurm job requires a separate compute disclosure and the new
   verified project account.
9. Update path defaults, runbooks and provenance documentation for future
   runs. Do not rewrite historical result manifests.
10. Revoke temporary ACLs. Retain old data until the researcher separately
    authorizes retirement after the full destination audit.

## Transfer implementation

The restartable script
`scripts/levante/migrate_b383673_to_m301324.sbatch` copies portable HOME
records and the complete old SCRATCH SDM tree without `--delete`. It excludes
old Git checkouts, compiled builds, dependencies and environments from the
HOME copy. For each copied tree it records regular-file counts, byte totals,
symlinks and SHA-256 checksums, then requires source and destination
inventories to match.

## Verified transfer result

Migration job `26573393` ran under `mh0731/shared` and completed with exit
status `0:0` in 1:11:56. Slurm reported four allocated logical CPUs for the
one-CPU request and a batch maximum RSS of 158,780 KiB. The destination passed
all per-tree summary, symlink and SHA-256 comparisons.

The complete SCRATCH result is:

| property | old source | new destination |
|---|---:|---:|
| regular files | 18,391 | 18,391 |
| regular-file bytes | 47,574,445,774 | 47,574,445,774 |
| directories | 6,402 | 6,402 |
| symlinks | 0 | 0 |

All eight selected HOME record/source trees also passed exact inventories.
The authoritative audit is retained at:

```text
/home/m/m301324/SDM/account_migration/b383673_to_m301324/job_26573393
```

No source file was deleted or modified.

## Rebuilt software result

`scripts/levante/bootstrap_software.sbatch` recreated account-local software
instead of copying compiled files containing old absolute paths. The final
validation job `26575611` completed `0:0` and wrote
`SOFTWARE_BOOTSTRAP_PASS=1`. The verified stack is:

| component | verified state |
|---|---|
| upstream CLEO | detached commit `83318c23223546d10759d202d70f4fa2f7fe4688` |
| CLEO Python | 3.13.14 |
| `uv` | 0.12.0 |
| Doxygen | 1.17.0 |
| `mpi4py` | 4.1.2, source-built against Levante OpenMPI 4.1.2 |
| `plotcleo` | import passed |
| YAXT/YAC | rebuilt under `/home/m/m301324/SDM/cleo_dependencies/yacyaxt/gcc`; link and one-rank PMIx import checks passed |
| trial `sdm_work` environment | Python 3.12.13; scientific-package import check passed |

Three bounded failed attempts are retained as provenance:

- `26573866` reached the archive stage and encountered HTTP 429;
- `26575381` exposed that Levante's `curl 7.61.1` lacks
  `--retry-all-errors`; and
- `26575547` completed the dependency builds but exposed a validation-order
  bug because `ldd` ran before the new runtime path was exported.

The final script uses a version-compatible explicit retry loop, reuses
validated Python components on restart, and exports runtime paths before link
checks. These failures did not run CLEO model simulations.

## Application and smoke validation

The account-neutral workflow was committed and pushed as
`12dabc65a9d115ce2668746f95790667fc5089c5`. A clean detached worktree at that
exact commit was used for all final validation.

Build job `26575663` completed `0:0` in 1:53 with eight requested and allocated
CPUs, 4 GiB requested memory and 1,397,988 KiB maximum batch RSS. It recorded
`BUILD_PASS=1` and produced both `collisions0d_golovin` and
`collisions0d_long`. The build manifest confirms the exact project commit,
pinned CLEO commit and collision-seed patch checksum.

Migration-gate job `26575749` completed `0:0` in 55 seconds:

- all 99 repository tests passed in 30.10 seconds;
- one serial, seeded, 1,024-SD Golovin box ran from 0 to 600 seconds;
- initialization and timestepping both passed;
- the model duration was 1.3765 seconds;
- `RUN_PASS=1` and a complete manifest/Zarr checksum were written; and
- stderr was empty.

The smoke is a software/path/provenance check only. It is not a convergence
experiment and does not change any Golovin scientific conclusion.

## Completion and old-account boundary

After every transfer, software, build, test and smoke gate passed, the named
`m301324` ACL was removed recursively from the two old SDM trees and from the
old HOME/SCRATCH parent directories. Fresh-connection checks return
`Permission denied` to `m301324` for both old roots. The old trees remain
present and owned by `b383673`; no old data were deleted.

The migration is complete. Future SDM work uses:

```text
SSH alias:     levante-m301324
Slurm account: mh0731
HOME root:     /home/m/m301324/SDM
SCRATCH root:  /scratch/m/m301324/SDM
```
