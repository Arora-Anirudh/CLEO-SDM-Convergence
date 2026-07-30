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

The existing RSA public key authenticates the old identity but was initially
rejected for `m301324`. DKRZ requires the public key to be registered for the
new identity through LUV before SSH and VS Code Remote SSH can connect.

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

## Pending gates

- Public-key registration for `m301324`.
- New account/project association and quotas.
- Cross-account read permission test.
- Destination inventory and checksum report.
- Rebuild and smoke-test report.
