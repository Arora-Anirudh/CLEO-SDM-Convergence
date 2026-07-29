# Controlled Golovin superdroplet-resolution convergence

## Outcome

The first registered resolution matrix completed successfully, but it did
**not** establish formal convergence:

```text
decision: no_resolution_accepted_in_initial_matrix
tested N_SD: 512, 1024, 2048, 4096, 8192, 16384
collision members per N_SD: 20
```

This is a valid scientific result. All 120 CLEO members completed and the
diagnostic pipeline passed; “not accepted” means that no tested resolution
satisfied every pre-registered accuracy, precision, adjacent-equivalence,
conservation and confirmation gate at every required time and bin count.

## Experiment

| Property | Value |
| --- | --- |
| model | CLEO `collisions0d` |
| active microphysics | collision–coalescence only |
| collision kernel | Golovin |
| collision timestep | 0.1 s |
| simulated duration | 3600 s |
| stored output interval | 300 s |
| decision times | 600, 1200, 1800, 2400, 3000, 3600 s |
| resolutions | 512–16,384 superdroplets, powers of two |
| ensemble | 20 independent collision streams per resolution |
| initialization | one deterministic frozen CLEO-native bundle per resolution |
| distribution grids | 250, 500 and 1000 fixed logarithmic-radius bins |

Members at one resolution reuse exactly the same frozen initial binary and
differ only in collision RNG seed. Different resolutions are deterministic
refinements of the same prescribed continuous droplet-size distribution, but
they do not contain identical individual superdroplets and are not paired
histories.

## Registered decision rule

A resolution \(N\) can be selected only if:

1. \(N\), \(2N\) and \(4N\) each pass all analytical-agreement and precision
   gates;
2. both adjacent pairs \(N\)-\(2N\) and \(2N\)-\(4N\) pass all equivalence
   gates;
3. every gate passes at all six decision times;
4. distribution gates pass for all 250-, 500- and 1000-bin diagnostics;
5. liquid-mass drift and fixed-bin range coverage pass.

The principal margins were:

- upper 95% interval bound of ensemble-mean distribution L1 no larger than
  0.05;
- distribution-L1 95% interval half-width no larger than 0.01;
- relative \(M_0\) interval contained within ±0.05, with half-width at most
  0.025;
- relative \(M_6\) interval contained within ±0.10, with half-width at most
  0.05;
- adjacent distribution-L1 difference interval contained within ±0.01;
- maximum relative liquid-mass drift \(10^{-7}\);
- maximum out-of-range mass fraction \(10^{-6}\).

The independent-resolution bootstrap does not pair member indices across
resolutions.

## What passed and failed

There are 30 analytical rows per resolution: six times multiplied by three
distribution grids plus \(M_0\) and \(M_6\).

| \(N_\mathrm{SD}\) | accuracy passes | precision passes | both pass |
| ---: | ---: | ---: | ---: |
| 512 | 0/30 | 3/30 | 0/30 |
| 1024 | 6/30 | 2/30 | 2/30 |
| 2048 | 9/30 | 8/30 | 8/30 |
| 4096 | 12/30 | 10/30 | 10/30 |
| 8192 | 13/30 | 14/30 | 11/30 |
| 16,384 | 18/30 | 25/30 | 18/30 |

The trend with resolution is clear, but the all-gates rule is not met.

At 16,384 superdroplets:

- \(M_0\) passes accuracy and precision at all 6 times;
- \(M_6\) passes accuracy and precision at all 6 times;
- 250-bin L1 passes both gates at 4/6 times;
- 500-bin L1 passes both gates at 2/6 times;
- 1000-bin L1 passes the accuracy gate at 0/6 times.

At 3600 s for the primary 500-bin distribution:

| \(N_\mathrm{SD}\) | L1 estimate | bootstrap 95% interval |
| ---: | ---: | ---: |
| 512 | 0.2614 | [0.2942, 0.4087] |
| 1024 | 0.1720 | [0.2070, 0.2966] |
| 2048 | 0.1333 | [0.1461, 0.2132] |
| 4096 | 0.0790 | [0.0940, 0.1393] |
| 8192 | 0.0619 | [0.0716, 0.1038] |
| 16,384 | 0.0500 | [0.0558, 0.0781] |

The 16,384 point estimate is approximately 0.05, but the registered rule uses
the **upper confidence bound**, which remains above 0.05. Its interval
half-width is 0.0112, also slightly wider than the 0.01 precision margin.

The bootstrap interval need not be centred on, or contain, the observed
ensemble-mean L1 estimate. L1 is nonlinear and the resampled ensemble means
have a finite-sample distribution; the plot therefore draws the estimate and
interval endpoints independently.

No adjacent pair passed all 30 equivalence rows:

| adjacent pair | equivalence passes |
| --- | ---: |
| 512–1024 | 0/30 |
| 1024–2048 | 3/30 |
| 2048–4096 | 8/30 |
| 4096–8192 | 11/30 |
| 8192–16,384 | 11/30 |

For the two highest pairs, \(M_0\) passes at 6/6 times and \(M_6\) at 5/6
times. Distribution-L1 equivalence passes at 0/18 time/bin combinations for
every pair. The ±0.01 distribution-equivalence interval is therefore the
dominant adjacent-pair barrier.

Conservation and diagnostic support are not the reason for rejection:

- the worst absolute liquid-mass drift is
  \(1.95\times10^{-8}<10^{-7}\);
- the registered 1–5000 μm fixed-bin range contains all diagnosed mass in
  every member and time (out-of-range fraction 0).

## Interpretation

The experiment provides strong evidence of improving numerical agreement as
\(N_\mathrm{SD}\) increases, especially for bulk moments. It does not provide
evidence that the full droplet-size distribution is converged under the
registered all-times/all-bin-count definition.

The increasing L1 error with finer diagnostic bins is meaningful: a finer
histogram exposes more sampling structure. A fixed absolute L1 threshold is
therefore harder to satisfy at 1000 bins than at 250 bins. This must not be
“fixed” by relaxing the rule after seeing the result. A follow-up should
pre-register whether to:

1. extend the resolution ladder above 16,384;
2. extend selected ensembles beyond 20 members where interval width is the
   limiting factor;
3. retain one primary physically motivated binning and treat the others as
   sensitivity diagnostics;
4. use a distribution metric less sensitive to arbitrary bin refinement,
   while keeping the current result as the unchanged baseline.

The correct present conclusion is not “Golovin failed” and not “16,384 is
converged.” It is:

> Bulk-moment agreement is strong at high resolution, distribution error
> decreases systematically, but formal distribution convergence was not
> reached in the initial 512–16,384, 20-member matrix.

## Compute and provenance

| Stage | Levante job | Request | Measured result |
| --- | ---: | --- | --- |
| exact build | 26537974 | 8 CPU, 8 GiB, 30 min | completed in 1 min 40 s |
| 120-member model | 26538151 | 1 CPU, 940 MiB, 1 h | completed in 20 min 57 s |
| final analysis publication | 26538924 | 1 process, 2 GiB, 30 min | completed in 50 s |

The shared partition allocated more CPUs than the model requested because of
Levante's memory/accounting granularity. The model remained serial and used
one thread per member.

- model matrix SHA-256:
  `e867ec0055eefd08627b00b385dcc1680e53643426c691b8f0a61200d6b45dde`;
- model/code build commit:
  `9cb4549787481142e68fe8dc35c5a10abbf377b0`;
- final analysis commit:
  `61c63b26b776019158b215149fadff880cc3c2be`;
- raw Zarr: 8,400,208,880 bytes on Levante SCRATCH;
- compact published package: `analysis_v1/`;
- all package files are covered by `analysis_v1/SHA256SUMS`.

## Artifact guide

- `analysis_v1/resolution/resolution_decision.json`: machine-readable formal
  decision and provenance;
- `analysis_v1/resolution/analytical_agreement.csv`: every resolution/time/
  metric analytical and precision gate;
- `analysis_v1/resolution/adjacent_resolution_equivalence.csv`: every
  pair/time/metric equivalence gate;
- `analysis_v1/resolution/resolution_convergence.png`: final-time overview;
- `analysis_v1/ensemble_summary/`: member-level and ensemble-level compact
  tables;
- `analysis_v1/model_inventory.json`: complete 120-member model audit;
- `analysis_v1/SHA256SUMS`: integrity manifest.

The 7.9 GiB raw model output is intentionally not committed to Git.
