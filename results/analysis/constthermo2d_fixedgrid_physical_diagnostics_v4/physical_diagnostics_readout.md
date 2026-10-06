# 2-D constthermo2d full physical-diagnostics readout

## Scope

All figures use the compact, audited fixed-20 normal-sampling cache for every completed resolution from 2 through 8,192 SDs per initially populated grid box. The diagnostic reconstruction uses the stored radius, multiplicity-weighted DSDs, moments, terminal-speed relation, and selected spatial mass fields. No new CLEO trajectory was run.

## Physical definitions

- Surface-area density: \(A=4\pi\lambda_2\), after converting micrometre-squared radii to square metres. It is geometric area per air volume, not a radiative-transfer extinction coefficient.
- Liquid-equivalent water content: \(L=\rho_w(4\pi/3)\lambda_3\). It is a radius-derived liquid quantity and is shown alongside CLEO's total-droplet mass diagnostic.
- Rayleigh reflectivity-factor proxy: \(Z=64\lambda_6^{(r,\mathrm{mm})}\), displayed as dBZ. It is not a radar forward simulation.
- Terminal-speed transport proxy: \(\mathcal P=V^{-1}\sum_i\xi_i m_i v_t(r_i)\). It has flux units but, with null boundaries, is not surface precipitation.

## Fast-drop threshold check

A 4 m/s fast-drop threshold is not usable in this 2-D configuration: the 8,192-SD ensemble has essentially zero liquid mass at speeds at or above 2 or 4 m/s by 120 min. The figures therefore show the realized 0.25, 0.5, and 1 m/s classes. The descriptive development time is the first 120-s output where 1% of liquid mass has terminal speed at least 1 m/s.

## Physical corroboration of the 1,024-SD operational selection

For 1,024 versus 8,192, the largest 95% bootstrap-bound/tolerance ratio over physical area, liquid-equivalent water, reflectivity proxy, terminal speed, and terminal-speed flux is 0.707, limited by terminal-speed mass-flux proxy. A ratio at or below one passes its 5% core or 10% tail margin. Thus the physical diagnostics corroborate rather than overturn the existing 1,024-SD operational selection.

The binned flux reconstruction differs from total-mass times mass-weighted speed by at most 0.005% in the 8,192 ensemble mean, documenting the fixed-bin approximation used for the flux figures.

## Interpretation boundary

These figures demonstrate cloud-scale size-distribution development, in-domain redistribution, and the emergence of faster-falling liquid mass. They do not diagnose surface rainfall or accumulation because the 2-D setup has null boundaries and no sedimenting exit.
