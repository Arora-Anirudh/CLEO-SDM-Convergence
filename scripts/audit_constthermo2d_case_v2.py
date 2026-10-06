#!/usr/bin/env python3
"""Integrity audit for one 2-D constthermo2d trajectory; not convergence analysis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import zarr


def scaled(group, name: str) -> np.ndarray:
    array = group[name]
    return np.asarray(array[:], dtype=float) * float(array.attrs.get("scale_factor", 1.0))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zarr", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-initial-supers", required=True, type=int)
    args = parser.parse_args()
    store, output = args.zarr.resolve(), args.output.resolve()
    expected_initial = args.expected_initial_supers
    if not store.is_dir():
        raise FileNotFoundError(store)
    if output.exists():
        raise FileExistsError(output)
    if expected_initial <= 0:
        raise ValueError("expected initial superdroplet count must be positive")

    group = zarr.open_group(str(store), mode="r")
    required = {"time", "raggedcount", "xi", "sdId", "radius", "msol", "coord3", "coord1", "sdgbxindex", "nsupers"}
    missing = sorted(required.difference(group.array_keys()))
    if missing:
        raise KeyError(f"missing required arrays: {missing}")
    time_s = scaled(group, "time")
    required_time = np.arange(0.0, 7200.0 + 120.0, 120.0)
    if time_s.shape != required_time.shape or not np.allclose(time_s, required_time, atol=1e-3, rtol=0.0):
        raise ValueError("expected 0,120,...,7200 s output grid not found")

    counts = np.asarray(group["raggedcount"][:], dtype=np.int64)
    xi = np.asarray(group["xi"][:], dtype=np.int64)
    sdid = np.asarray(group["sdId"][:], dtype=np.int64)
    radius_um = scaled(group, "radius")
    coord3_m, coord1_m = scaled(group, "coord3"), scaled(group, "coord1")
    gbxindex = np.asarray(group["sdgbxindex"][:], dtype=np.int64)
    if counts.shape != time_s.shape or np.any(counts <= 0) or counts.sum() != xi.size:
        raise ValueError("inconsistent ragged trajectory record")
    if not all(values.size == xi.size for values in (sdid, radius_um, coord3_m, coord1_m, gbxindex)):
        raise ValueError("superdroplet arrays have inconsistent total length")
    if np.any(xi <= 0) or np.any(radius_um <= 0) or not np.isfinite(radius_um).all():
        raise ValueError("invalid multiplicity or radius")
    offsets = np.r_[0, np.cumsum(counts)]
    repeated = [int(i) for i, (left, right) in enumerate(zip(offsets[:-1], offsets[1:], strict=True)) if np.unique(sdid[left:right]).size != right - left]
    if repeated:
        raise ValueError(f"repeated active IDs at stored times {repeated}")
    nsupers = np.asarray(group["nsupers"][:], dtype=np.int64)
    if nsupers.ndim != 2 or nsupers.shape[0] != time_s.size or not np.array_equal(nsupers.sum(axis=1), counts):
        raise ValueError("grid-box and ragged superdroplet counts disagree")
    if counts[0] != expected_initial:
        raise ValueError(f"expected {expected_initial} initial SDs, found {counts[0]}")

    outside = (coord3_m < 0.0) | (coord3_m > 1500.0) | (coord1_m < 0.0) | (coord1_m > 1500.0)
    result = {
        "status": "passed_trajectory_integrity_no_convergence_claim",
        "stored_times": int(time_s.size),
        "initial_active_superdroplets": int(counts[0]),
        "final_active_superdroplets": int(counts[-1]),
        "initial_expected_total": expected_initial,
        "minimum_active_superdroplets": int(counts.min()),
        "maximum_active_superdroplets": int(counts.max()),
        "radius_um_range": [float(radius_um.min()), float(radius_um.max())],
        "coord3_m_range": [float(coord3_m.min()), float(coord3_m.max())],
        "coord1_m_range": [float(coord1_m.min()), float(coord1_m.max())],
        "records_outside_nominal_xz_domain": int(outside.sum()),
        "fraction_records_outside_nominal_xz_domain": float(outside.mean()),
        "unique_gbxindices_min": int(gbxindex.min()),
        "unique_gbxindices_max": int(gbxindex.max()),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CONSTTHERMO2D_TRAJECTORY_INTEGRITY_PASS")


if __name__ == "__main__":
    main()
