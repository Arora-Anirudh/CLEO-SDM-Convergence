#!/usr/bin/env python3
"""Low-memory integrity audit for a ragged 2-D constthermo2d trajectory.

Unlike the original v2 auditor, this implementation reads one stored time
slice at a time.  It retains the same trajectory-integrity checks without
materialising every ragged superdroplet record simultaneously in memory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import zarr


def scaled_slice(group: zarr.Group, name: str, start: int, stop: int) -> np.ndarray:
    array = group[name]
    return np.asarray(array[start:stop], dtype=float) * float(array.attrs.get("scale_factor", 1.0))


def scaled_full(group: zarr.Group, name: str) -> np.ndarray:
    array = group[name]
    return np.asarray(array[:], dtype=float) * float(array.attrs.get("scale_factor", 1.0))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zarr", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-initial-supers", required=True, type=int)
    args = parser.parse_args()
    store, output = args.zarr.resolve(), args.output.resolve()
    if not store.is_dir():
        raise FileNotFoundError(store)
    if output.exists():
        raise FileExistsError(output)
    if args.expected_initial_supers <= 0:
        raise ValueError("expected initial superdroplet count must be positive")

    group = zarr.open_group(str(store), mode="r")
    required = {"time", "raggedcount", "xi", "sdId", "radius", "msol", "coord3", "coord1", "sdgbxindex", "nsupers"}
    missing = sorted(required.difference(group.array_keys()))
    if missing:
        raise KeyError(f"missing required arrays: {missing}")
    time_s = scaled_full(group, "time")
    required_time = np.arange(0.0, 7200.0 + 120.0, 120.0)
    if time_s.shape != required_time.shape or not np.allclose(time_s, required_time, atol=1e-3, rtol=0.0):
        raise ValueError("expected 0,120,...,7200 s output grid not found")
    counts = np.asarray(group["raggedcount"][:], dtype=np.int64)
    nsupers = np.asarray(group["nsupers"][:], dtype=np.int64)
    if counts.shape != time_s.shape or np.any(counts <= 0):
        raise ValueError("invalid ragged trajectory counts")
    if nsupers.ndim != 2 or nsupers.shape[0] != time_s.size or not np.array_equal(nsupers.sum(axis=1), counts):
        raise ValueError("grid-box and ragged superdroplet counts disagree")
    if counts[0] != args.expected_initial_supers:
        raise ValueError(f"expected {args.expected_initial_supers} initial SDs, found {counts[0]}")
    total_records = int(counts.sum())
    lengths = {name: int(group[name].shape[0]) for name in ("xi", "sdId", "radius", "msol", "coord3", "coord1", "sdgbxindex")}
    if any(length != total_records for length in lengths.values()):
        raise ValueError(f"superdroplet-array lengths inconsistent with ragged counts: {lengths}, total={total_records}")

    offsets = np.r_[0, np.cumsum(counts)]
    outside_records = 0
    radius_min, radius_max = np.inf, -np.inf
    gbx_min, gbx_max = np.iinfo(np.int64).max, np.iinfo(np.int64).min
    sdid_fail_times: list[int] = []
    for tidx, (start, stop) in enumerate(zip(offsets[:-1], offsets[1:], strict=True)):
        xi = np.asarray(group["xi"][start:stop], dtype=np.int64)
        radius_um = scaled_slice(group, "radius", int(start), int(stop))
        msol = scaled_slice(group, "msol", int(start), int(stop))
        sdid = np.asarray(group["sdId"][start:stop], dtype=np.int64)
        coord3_m = scaled_slice(group, "coord3", int(start), int(stop))
        coord1_m = scaled_slice(group, "coord1", int(start), int(stop))
        gbx = np.asarray(group["sdgbxindex"][start:stop], dtype=np.int64)
        n = int(stop - start)
        if not all(item.size == n for item in (xi, radius_um, msol, sdid, coord3_m, coord1_m, gbx)):
            raise ValueError(f"inconsistent sliced superdroplet arrays at stored index {tidx}")
        if np.any(xi <= 0) or np.any(radius_um <= 0) or not np.isfinite(radius_um).all() or not np.isfinite(msol).all():
            raise ValueError(f"invalid multiplicity, radius, or solute mass at stored index {tidx}")
        if np.unique(sdid).size != n:
            sdid_fail_times.append(tidx)
        outside_records += int(np.count_nonzero((coord3_m < 0.0) | (coord3_m > 1500.0) | (coord1_m < 0.0) | (coord1_m > 1500.0)))
        radius_min = min(radius_min, float(np.min(radius_um)))
        radius_max = max(radius_max, float(np.max(radius_um)))
        gbx_min = min(gbx_min, int(gbx.min()))
        gbx_max = max(gbx_max, int(gbx.max()))
    if sdid_fail_times:
        raise ValueError(f"repeated active IDs at stored times {sdid_fail_times}")

    result = {
        "status": "passed_streaming_trajectory_integrity_no_convergence_claim",
        "auditor": "audit_constthermo2d_case_streaming_v3",
        "stored_times": int(time_s.size),
        "initial_active_superdroplets": int(counts[0]),
        "final_active_superdroplets": int(counts[-1]),
        "initial_expected_total": int(args.expected_initial_supers),
        "minimum_active_superdroplets": int(counts.min()),
        "maximum_active_superdroplets": int(counts.max()),
        "total_ragged_records_checked": total_records,
        "radius_um_range": [radius_min, radius_max],
        "records_outside_nominal_xz_domain": outside_records,
        "fraction_records_outside_nominal_xz_domain": outside_records / total_records,
        "unique_gbxindices_min": int(gbx_min),
        "unique_gbxindices_max": int(gbx_max),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CONSTTHERMO2D_STREAMING_TRAJECTORY_INTEGRITY_V3_PASS")


if __name__ == "__main__":
    main()
