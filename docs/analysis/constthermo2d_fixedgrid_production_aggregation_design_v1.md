# 2-D `constthermo2d` production aggregation design, v1

## Purpose

The completed normal-sampling cohort has 240 accepted trajectories: 20 members
at each `N_cell=2,4,...,4096`. Raw trajectory data remain authoritative on
Levante. This stage performs a non-destructive streamed reduction of each
accepted member into compact, analysis-ready diagnostics. It does not select a
convergence resolution.

## Per-member reconstruction

For every stored time, the extractor reads the active SD radius \(r_i\),
multiplicity \(\xi_i\), solute mass, and position. It reconstructs

\[
\lambda_p(t)=\frac{1}{V}\sum_i\xi_i\left[\frac{r_i(t)}{1\;\mu\mathrm m}\right]^p,
\qquad p=0,1,2,3,6,
\]

and checks \(\lambda_0\) against CLEO's native `massmom0` observer. Exact
droplet mass uses CLEO's liquid-plus-solute definition and is checked against
native `massmom1`. The extracted physical diagnostics are mass-weighted
terminal speed under the same Rogers--Gunn--Kinzer relation used by CLEO,
mass-weighted radius quantiles, and the in-domain lower-150-m mass fraction.
The latter remains a proximity/transport proxy, not surface precipitation,
because this example has `NullBoundaryConditions`.

Number and total-droplet-mass DSDs are retained at 250, 500 and 1000 fixed
log-radius bins (0.002--1000 micrometres), at all 61 output times. This
prevents bin choice from being confused with SD-resolution convergence.

## Staged execution

First run one \(N_{\rm cell}=4096\), member-1 aggregation gate. It measures
memory and wall time on the largest raw trajectory and verifies native-observer
agreement before any cohort-wide array is submitted. Only after it passes will
the full 240-member aggregation be costed and submitted.

## Largest-member gate result and full-array envelope

The gate (`27682327`) completed `0:0` in 23 seconds. The 4096-member compact
aggregate is 1.2 MiB. Reconstructed \(\lambda_0\) agrees exactly with the
native observer; exact mass agrees with native `massmom1` to at worst
\(2.11\times10^{-6}\) relative difference. Peak RSS was 1.56 GiB and stderr
was empty.

The shared partition charged 10 CPUs for the gate's 8-GiB request. The full
array therefore reduces memory to 3 GiB, which retains nearly a twofold margin
above the measured peak while avoiding that unnecessary allocation shape. It
requests one task and one CPU, but shared-partition placement may allocate four
CPUs for a 3-GiB request. The 240-task array has a cap of 20 concurrent
members and five minutes per member. A conservative allocation ceiling is
therefore \(240\times4\times5/60=80\) CPU-hours. Scaling the 23-second
largest-member wall time plus fixed per-member startup gives an expected
allocation of approximately 3--5 CPU-hours, to be remeasured from Slurm after
completion.
