#!/usr/bin/env python3
"""Generate, run and plot one sealed CLEO constthermo2d case.

This wrapper leaves upstream source unchanged.  It makes the otherwise implicit
NumPy initialization stream explicit, and it writes every mutable product below
one initially absent case directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cleo", required=True, type=Path)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--source-config", required=True, type=Path)
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--plot", action="store_true")
    args = parser.parse_args()

    cleo = args.cleo.resolve()
    executable = args.executable.resolve()
    source_config = args.source_config.resolve()
    root = args.case_root.resolve()
    if not (cleo.is_dir() and executable.is_file() and source_config.is_file()):
        raise FileNotFoundError("CLEO source, executable, or source configuration is missing")
    if root.exists():
        raise FileExistsError(f"refusing to reuse a case directory: {root}")

    import numpy as np
    from cleopy import editconfigfile
    from examples.constthermo2d import constthermo2d_inputfiles as inputs

    tmp = root / "tmp"
    share = root / "share"
    binpath = root / "bin"
    for directory in (tmp, share, binpath):
        directory.mkdir(parents=True, exist_ok=False)
    config = tmp / "const2d_config.yaml"
    shutil.copy2(source_config, config)
    thermofiles = share / "const2d_dimlessthermo.dat"
    params = {
        "constants_filename": str(cleo / "libs" / "cleoconstants.hpp"),
        "grid_filename": str(share / "const2d_dimlessGBxboundaries.dat"),
        "initsupers_filename": str(share / "const2d_dimlessSDsinit.dat"),
        "setup_filename": str(binpath / "const2d_setup.txt"),
        "zarrbasedir": str(binpath / "const2d_sol.zarr"),
    }
    for variable in ("press", "temp", "qvap", "qcond", "wvel", "uvel"):
        params[variable] = str(share / f"const2d_dimlessthermo_{variable}.dat")
    editconfigfile.edit_config_params(config, params)

    # The upstream generators use NumPy's module-level RNG.  Seeding it here
    # controls radii and both sampled coordinates without a source modification.
    np.random.seed(args.seed)
    inputs.main(
        cleo,
        root,
        config,
        thermofiles,
        gen_gbxs=True,
        gen_supers=True,
        gen_thermo=True,
        savefigpath=binpath,
        save_figures=False,
    )
    subprocess.run([str(executable), str(config)], check=True)

    if args.plot:
        plotting = cleo / "examples" / "constthermo2d" / "constthermo2d_plotting.py"
        subprocess.run(
            [
                sys.executable, str(plotting), f"--path2CLEO={cleo}",
                f"--savefigpath={binpath}",
                f"--grid_filename={params['grid_filename']}",
                f"--setupfile={params['setup_filename']}",
                f"--dataset={params['zarrbasedir']}",
            ],
            check=True,
        )

    receipt = {
        "status": "completed_no_convergence_claim",
        "seed": args.seed,
        "cleo_source": str(cleo),
        "source_config": str(source_config),
        "source_config_sha256": sha256(source_config),
        "runtime_config": str(config),
        "runtime_config_sha256": sha256(config),
        "input_superdrops_sha256": sha256(Path(params["initsupers_filename"])),
        "executable": str(executable),
        "executable_sha256": sha256(executable),
        "plot_requested": bool(args.plot),
    }
    (root / "case_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("CONSTTHERMO2D_SEEDED_CASE_SUCCESS")


if __name__ == "__main__":
    main()
