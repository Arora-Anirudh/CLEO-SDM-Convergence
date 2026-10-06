# DSD size-class visualisation

All products use the audited 2-D fixed-20 cache; no CLEO trajectory was rerun.

Size categories use wet diameter D=2r:

- cloud: D < 0.1 mm, equivalently r < 50 micrometres;
- drizzle-sized: 0.1 <= D < 0.5 mm, equivalently 50 <= r < 250 micrometres;
- rain-sized: D >= 0.5 mm, equivalently r >= 250 micrometres.

The rain-sized label is a size class only. The constthermo2d executable uses
NullBoundaryConditions, therefore these figures do not diagnose surface
rainfall, rain-out, or rainfall onset.

The spatial field is natively 20 by 20 cells over 1500 m by 1500 m. Each cell
is 75 m by 75 m. Its blocky appearance is the physical grid resolution, not
an image-resolution problem.
