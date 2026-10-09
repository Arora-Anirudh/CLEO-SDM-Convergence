# N=32 ICON--YAC--CLEO raw/compact output audit

This is a small, shareable, **read-only output-integrity audit** for the
one-member, 32-superdroplet-per-gridbox ICON--YAC--CLEO bubble run.  It is not
a convergence analysis and does not modify, deduplicate, or otherwise repair
any model output.

The package deliberately contains only the source-backed audit code, the
effective CLEO configuration, compact numerical results, and rendered
figures.  It excludes reports, presentations, videos, and the approximately
429 MB `bubble3d_sol.zarr` particle store.  The audit can be reproduced when
that Zarr store is available on Levante.

## Question tested

CLEO writes two independent output products at every 30 s observation time:

1. **Compact diagnostics.** `MassMomentsObserver` reduces the live
   in-memory superdroplet state in each gridbox to `massmom0`, `massmom1`, and
   `massmom2`; `StateObserver` writes the gridbox thermodynamic and wind
   fields.  These dense variables have dimensions `(time, gbxindex)`.
2. **Ragged particle attributes.** `SuperdropsObserver` copies live particle
   attributes (`sdId`, coordinates, multiplicity `xi`, radius, and `msol`) to
   one concatenated `superdroplets` axis.  `raggedcount(time)` is used to
   recover the individual saved states.  In this executable, `sdgbxindex` was
   not written.

The raw-particle stream is useful for particle snapshots.  Before using it to
derive a bulk diagnostic, this audit checks whether its reconstructed moments
agree with the separately written compact products.

This is intentionally a “domain-total versus domain-total” comparison. The
raw stream has one concatenated `superdroplets` axis and, for this executable,
does not contain a saved `sdgbxindex`. `raggedcount(time)` gives the number of
particle records saved at each time, so its cumulative sum supplies the
start/end offsets needed to select one complete output time. It does not select
or accumulate gridboxes. A cell-by-cell audit is still possible, but it must
first reconstruct a provisional gridbox assignment from `coord1/2/3` and the
saved grid-boundary file, then validate the boundary convention against CLEO's
native mapping; it cannot directly use an output `sdgbxindex` here.

## What the code compares

`code/audit_n32_raw_compact_alltime_v2.py` partitions the ragged stream using
`raggedcount`, with no ID filtering or corrections, then evaluates

`M0_raw = sum(xi)`, `M1_raw = sum(xi*m)`, and `M2_raw = sum(xi*m^2)`.

The drop mass is the exact CLEO expression used in the audit:

`m = 4*pi*rho_water*r^3/3 + msol*(1 - rho_water/rho_solute)`

with `rho_water = 998.203 kg m^-3` and `rho_solute = 2016.5 kg m^-3`.
The raw stored radius is converted from micrometres to metres and `msol` from
grams to kilograms before evaluating the formula.

For assessing whether a discrepancy could be rounding, the output CSV also
contains the signed difference `raw_minus_compact_*` and magnitude
`abs_raw_minus_compact_*` for all three moments in their physical units. The
script prints the initial difference, the largest finite absolute difference,
its time, and the number of non-finite differences when it is run.

## Result

At the initial state, raw/compact `M1 = 0.99999994`, validating the units and
mass reconstruction.  At 59 min, raw/compact `M1 = 1.9007`; the corresponding
water-only/compact ratio is `1.9001` and the effective solute contribution is
only `0.03%` of raw mass.  The later inconsistency is therefore **not** caused
by including aerosol/solute mass in one calculation but not the other.

The audit establishes that the two observer paths need a source-level review
before particle-stream-derived bulk moments are treated as scientific
diagnostics.  It does **not** identify the implementation stage responsible
for the mismatch and it is not evidence about the physical simulation itself.

## Contents

- `code/audit_n32_raw_compact_alltime_v2.py` -- all-time numerical audit.
- `code/plot_n32_observer_dataflow_v1.py` -- source-backed data-flow schematic.
- `config/bubble3d_setup.txt` -- configuration written for the audited run.
- `results/n32_raw_compact_alltime.csv` -- the 241-time-step audit table.
- `results/01_n32_raw_compact_alltime.png` -- moment ratios and raw-record indicators.
- `results/n32_v2_provenance_manifest.csv` -- run provenance manifest.

## Reproduce on Levante

Activate the CLEO Python environment used for the run, then execute:

```bash
python code/audit_n32_raw_compact_alltime_v2.py \
  --dataset /path/to/bubble3d_sol.zarr \
  --outdir /path/to/new_audit_output
python code/plot_n32_observer_dataflow_v1.py
```

The first command intentionally refuses to overwrite an existing output
directory.  Its required Python packages are `xarray`, `zarr`, `numpy`, and
`matplotlib`.
