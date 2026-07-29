# ADR 0006: Extend controlled Golovin resolution and ensemble size before Long

- Status: accepted for preparation; compute not yet submitted
- Date: 2026-07-29

## Context

The first registered controlled Golovin matrix completed all 120 model
members and all analysis/provenance gates but selected no resolution. At
16,384 superdroplets the registered \(M_0\) and \(M_6\) analytical and
precision gates pass at every decision time. The fixed-bin distribution L1
does not: finer bins retain larger error, bootstrap intervals remain slightly
too wide, and no adjacent-resolution pair satisfies the ±0.01 L1-equivalence
interval at every time and bin count.

The literature distinguishes convergence of ensemble-mean or bulk quantities
from convergence of a detailed DSD and its variance. It also uses ensembles
from tens to thousands of realizations depending on the diagnostic.
Shima et al. display substantially improved Golovin agreement at 131,072
superdroplets; Zmijewski et al. use an ensemble near 100 at
\(N_\mathrm{SD}=10^5\), with much larger ensembles at lower resolutions.
No reviewed source defines the exact fixed-bin all-time L1 rule used here.

## Decision

1. Do not begin a Long-kernel convergence experiment.
2. Preserve the completed 512–16,384 by 20 matrix's compact,
   checksum-published result and its formal
   `no_resolution_accepted_in_initial_matrix` decision. Delete its raw
   SCRATCH member stores after verifying the exact path; they are not inputs
   to the follow-up.
3. Prepare a distinct follow-up matrix with active resolutions
   16,384, 32,768, 65,536 and 131,072.
4. Target 100 fresh independent collision streams per active resolution:
   400 new model members in total. Reuse no member, collision seed, run label,
   raw output path or controlled-bundle label from the previous matrix.
5. Keep the controlled initialization definition, 0.1 s collision timestep,
   output/decision times, 250/500/1000 fixed bins, all accuracy/precision/
   conservation/coverage margins, independent-resolution bootstrap and
   N/2N/4N stopping rule unchanged.
6. Analyze after 100 members. Add members toward 200 only where interval width
   remains limiting. Add 262,144 superdroplets if high-resolution point bias
   or adjacent differences—not interval width—remain limiting.
7. Require a new explicit compute disclosure before any Levante model or
   analysis submission.

## Rationale

Increasing members alone addresses sampling precision but cannot remove
finite-resolution bias or make a true adjacent difference larger than 0.01
equivalent. Increasing resolution alone leaves the fine-bin ensemble estimate
needlessly noisy. The joint extension addresses both observed limitations.

The high-resolution-only allocation avoids spending additional compute at
512–8192, where analytical distribution bias is already far from the
registered margins. Extending through 131,072 creates two complete
confirmation triples: 16,384/32,768/65,536 and
32,768/65,536/131,072.

One hundred members is a pre-analysis target, not a universal truth. It is
larger than the first screen, exceeds common 50-member practice, matches the
order used by a recent box-convergence study near \(10^5\) superdroplets, and
is expected to bring the observed final-time interval half-widths below 0.01.
The registered empirical interval-width rule, not the literature count,
determines whether more members are required.

## Consequences

- The follow-up requires 400 new CLEO members and approximately 28.0 GB
  (26.1 GiB) of raw SCRATCH output.
- Planning-level model cost is approximately 6.25 CPU-hours; actual Slurm
  resources will be disclosed and approved separately.
- The existing compact decision remains citable and checksum-verifiable; its
  raw Zarr stores are deliberately not retained or reused.
- Long remains blocked until Golovin is formally accepted or a separate,
  prospectively justified protocol decision changes that requirement.

## Evidence

The detailed paper-by-paper review, numerical extrapolation and limitations
are recorded in
[the Golovin extension literature review](../literature/golovin-convergence-extension-review.md).
The immutable first result is recorded in
[`results/golovin_controlled_resolution_convergence_v1`](../../results/golovin_controlled_resolution_convergence_v1/README.md).
