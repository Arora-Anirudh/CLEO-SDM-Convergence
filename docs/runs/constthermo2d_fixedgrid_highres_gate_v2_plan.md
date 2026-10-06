# 2-D `constthermo2d` higher-resolution gate, v2 — proposed only

## Proposed purpose

This would be one fresh \(N_{\rm cell}=4096\) trajectory, or 491,520 initial
domain SDs. It is the next factor-of-two execution/performance gate after the
accepted \(N_{\rm cell}=2048\) case. It would establish whether runtime,
memory and output integrity remain healthy before a fixed-20 ladder is
committed. It would still not be an ensemble, internal reference, or
convergence result.

## Estimate from measured data

The two accepted 16-thread measurements are 83 s at \(N_{\rm cell}=512\) and
333 s at \(N_{\rm cell}=2048\). Their local scaling exponent is

\[
p=\frac{\ln(333/83)}{\ln(2048/512)}=1.0022.
\]

Extrapolating only one factor of two gives 667 s, or **11.1 min**, at
\(N_{\rm cell}=4096\). At 16 CPUs this is **2.96 allocated CPU-hours**.

The proposed request would be one rank, 16 Kokkos Threads, 8 GiB and 25 min,
with a hard scheduler maximum of **6.67 CPU-hours**. The 8-GiB memory request
remains conservative: the completed 2048 gate used only about 545 MiB batch
RSS, but memory must be remeasured at 4096 rather than assumed to scale
perfectly.

## Submission record

The researcher approved the estimate above. After absent-target, clean-source,
executable and remote/local wrapper-hash checks, the gate was submitted as
Levante job `27670405` on 24 September 2026. The local/remote wrapper SHA-256
is `6574ef8be102de794876147a1c07fdb5056bce4aa55f4f0b49700b27a1d17d6e`.

At the immediate check it was `RUNNING` on `l40002`. No performance or
scientific conclusion is available until the 61-output integrity audit and
accounting record have completed.
