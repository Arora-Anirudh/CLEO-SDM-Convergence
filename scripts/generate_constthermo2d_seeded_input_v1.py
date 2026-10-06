#!/usr/bin/env python3
"""Generate and audit native constthermo2d input files without running CLEO."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
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
    parser.add_argument("--source-config", required=True, type=Path)
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--nsupers-pergbx", required=True, type=int)
    parser.add_argument("--expected-initial-supers", required=True, type=int)
    args = parser.parse_args()

    cleo = args.cleo.resolve()
    source_config = args.source_config.resolve()
    root = args.case_root.resolve()
    expected = args.expected_initial_supers
    if not (cleo.is_dir() and source_config.is_file()):
        raise FileNotFoundError("CLEO source or source configuration is missing")
    if root.exists():
        raise FileExistsError(f"refusing to reuse a case directory: {root}")
    if args.nsupers_pergbx <= 0 or expected <= 0:
        raise ValueError("SD counts must be positive")

    import numpy as np
    from cleopy import editconfigfile
    from cleopy.initsuperdropsbinary_src import read_initsuperdrops as read_supers
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

    np.random.seed(args.seed)
    inputs.main(
        cleo, root, config, thermofiles, gen_gbxs=True, gen_supers=True,
        gen_thermo=True, savefigpath=binpath, save_figures=False,
    )
    attributes = read_supers.read_dimless_superdrops_binary(params["initsupers_filename"], isprint=False)
    xi = np.asarray(attributes.xi, dtype=np.int64)
    gbx = np.asarray(attributes.sdgbxindex, dtype=np.int64)
    if xi.size != expected:
        raise ValueError(f"expected {expected} initial SDs, found {xi.size}")
    if np.any(xi <= 0):
        raise ValueError("non-positive multiplicity in generated initial SDs")
    unique_gbx, per_gbx = np.unique(gbx, return_counts=True)
    if unique_gbx.size != 120 or not np.all(per_gbx == args.nsupers_pergbx):
        raise ValueError(
            "expected 120 populated grid boxes with exactly "
            f"{args.nsupers_pergbx} SDs each; found {unique_gbx.size} boxes and "
            f"counts {np.unique(per_gbx).tolist()}"
        )

    receipt = {
        "status": "passed_native_input_only_no_model_run",
        "seed": args.seed,
        "nsupers_per_populated_grid_box": args.nsupers_pergbx,
        "expected_initial_superdroplets": expected,
        "observed_initial_superdroplets": int(xi.size),
        "populated_grid_boxes": int(unique_gbx.size),
        "sd_count_per_populated_grid_box": int(per_gbx[0]),
        "multiplicity_min": int(xi.min()),
        "multiplicity_max": int(xi.max()),
        "source_config": str(source_config),
        "source_config_sha256": sha256(source_config),
        "runtime_config_sha256": sha256(config),
        "input_superdrops_sha256": sha256(Path(params["initsupers_filename"])),
    }
    (root / "input_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("CONSTTHERMO2D_NATIVE_INPUT_AUDIT_PASS")


if __name__ == "__main__":
    main()
