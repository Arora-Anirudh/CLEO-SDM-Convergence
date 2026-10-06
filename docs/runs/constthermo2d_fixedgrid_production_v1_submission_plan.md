# 2-D `constthermo2d` fixed-grid normal-sampling production cohort, v1

## Purpose

This is the first convergence ensemble for the upstream `constthermo2d`
configuration. It uses ordinary native sampling, not alpha sampling. The
accepted 2048 and 4096 execution gates establish that the selected source,
initialisation, output cadence, and one-rank Kokkos Threads execution can
complete at the top two initially planned resolutions. They are not members of
this cohort.

## Cohort

For every resolution, `N_cell` is the number of superdroplets in each of the
120 initially populated grid boxes. The initial domain total is therefore
`120*N_cell`. The cohort consists of 20 fresh, independently seeded members
at each of:

\[
N_{\rm cell}=2,4,8,16,32,64,128,256,512,1024,2048,4096.
\]

This is 240 new simulations. Seeds and expected initial domain totals are
explicitly recorded in
`config/constthermo2d_fixedgrid_production_v1.csv`. No result from an earlier
smoke, pilot, timing test, or high-resolution gate will be pooled into this
cohort.

## Execution shape

Each array element has one Slurm task, 16 Kokkos Threads, 2 GiB memory, and
one complete 0--7200 s trajectory. `main_const2d.cpp` rejects multi-rank MPI
execution; 16 Threads is the measured cost-efficient supported path. The
array concurrency cap is 20, so at most 20 members run concurrently.

Each case receives a newly materialised configuration with the linked
`nsupers_pergbx=N_cell` and `maxnsupers=120*N_cell` settings, a fresh seeded
binary input, immutable configuration/executable receipts, and the trajectory
integrity audit. A pre-existing case directory is treated as an error rather
than overwritten.

### Initial submission and preparation repair

The initially submitted `N_cell=2` wave (`27681393`) completed all 20 members
and all 20 case audits passed. Its 20-member result is retained. The next
`N_cell=4` wave (`27681394`) revealed a control-plane race: concurrent tasks
could each observe an absent shared materialised configuration, while all but
one then failed correctly when the materialiser refused to overwrite the file.
Six members stopped at this guard with `FileExistsError`; this occurred before
CLEO execution and is not a model failure. The dependency chain consequently
cancelled all later waves before they began.

The repair preserves the failed logs and changes the protocol rather than
weakening the materialiser's no-overwrite protection. A one-task preflight now
materialises all twelve immutable resolution YAMLs before member arrays begin,
records their SHA-256 checksums, and the member wrapper requires the relevant
pre-existing YAML. The incomplete `N_cell=4` wave will be repaired only for
its six absent members; all later resolution waves will be submitted only
after the preflight receipt and repaired `N_cell=4` audit succeed.

The preflight was submitted as `27681503` and completed `0:0` in two seconds;
it wrote the twelve configuration hashes and the explicit
`CONSTTHERMO2D_PRODUCTION_CONFIG_PREFLIGHT_V1_PASS` receipt. The targeted
repair array (`27681506`, tasks 5, 6 and 16--19) completed `0:0`; the
`N_cell=4` output root then contained 20 integrity receipts.

The live post-repair dependency chain is: `27681521` (`N_cell=8`),
`27681522` (16), `27681523` (32), `27681524` (64), `27681525` (128),
`27681526` (256), `27681527` (512), `27681528` (1024), `27681529` (2048),
and `27681530` (4096). Every array is capped at 20 tasks and each later array
depends on successful completion of the preceding resolution. The initial
cancelled arrays remain retained as failure-control evidence and are not part
of the production cohort.

## Completion record

The repaired v1 cohort completed on 24 September 2026. Every resolution from
`N_cell=2` through 4096 has exactly 20 trajectory-integrity receipts: **240
of 240 passed**. The final post-repair production-wave stderr files are empty.
The completed physical members used **123.502 allocated CPU-hours**, inside
the pre-submission 115--130 CPU-hour expectation and far below the 730.7
CPU-hour hard scheduler envelope. This establishes a complete simulation
matrix for analysis; it does not itself establish a convergence result.

## Resource estimate before submission

Measured 16-thread execution gates cost 0.373 allocated CPU-hours at
`N_cell=512`, 1.48 at 2048, and 2.80 at 4096. A linear-in-resolution planning
fit across those accepted measurements gives about **115 allocated CPU-hours**
for all 240 members. The stated expectation is approximately **115--130
allocated CPU-hours**, because initialisation, output and scheduler overhead
are not perfectly linear at the smallest resolutions.

The deliberately conservative time limits are 10 min for `N_cell<=512`, 12
min at 1024, 15 min at 2048, and 20 min at 4096. With 16 CPUs each, the hard
scheduler allocation ceiling is:

| Resolutions | Members | Time/member | Hard CPU-hours |
|---|---:|---:|---:|
| 2--512 (nine resolutions) | 180 | 10 min | 480.0 |
| 1024 | 20 | 12 min | 64.0 |
| 2048 | 20 | 15 min | 80.0 |
| 4096 | 20 | 20 min | 106.7 |
| **All v1 production members** | **240** | — | **730.7** |

The hard ceiling is not an expected cost. It is the maximum if every member
runs to its requested limit. The observed 4096 gate used 10m30s and about
665 MiB RSS, so 2 GiB remains a threefold memory margin while avoiding the
previous unnecessary 8 GiB request.

## Analysis boundary

After the cohort is complete, analysis will construct domain, cloud-layer, and
altitude-resolved number/mass DSDs; \(\lambda_0,\lambda_2,\lambda_3,\lambda_6\);
mass-weighted terminal speed; and the boundary-aware lower-layer transport
proxy. It will test DSD-bin sensitivity at 250, 500 and 1000 bins. The
highest-resolution cohort mean will be an internal operational reference only
unless diagnostic stability supports it. No convergence number or rainfall
claim is pre-authorised by this submission.
