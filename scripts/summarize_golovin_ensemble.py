"""Summarize Stage-0 diagnostics across independent Golovin ensemble members.

The script discovers completed per-member analyses, preserves every member
value in a combined table, and writes long-form uncertainty summaries.  It
never modifies a run or an existing analysis directory.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.stats import t as student_t

TIME_GROUP_COLUMNS = (
    "matrix_stage",
    "initialization_family",
    "kernel",
    "max_superdroplets",
    "collision_timestep_s",
    "observation_timestep_s",
    "end_time_s",
    "time_s",
)
MEMBER_GROUP_COLUMNS = TIME_GROUP_COLUMNS[:-1]

TIME_METRICS = (
    "golovin_fixed_bin_l1_relative",
    "radius_moment_0_m3",
    "radius_moment_3_um3_m3",
    "radius_moment_6_um6_m3",
    "golovin_relative_error_radius_moment_0_m3",
    "golovin_relative_error_radius_moment_3_um3_m3",
    "golovin_relative_error_radius_moment_6_um6_m3",
    "liquid_water_gm3",
    "relative_liquid_mass_drift",
    "mass_fraction_r_ge_cloud_threshold",
    "mass_fraction_r_ge_large_threshold",
    "mass_fraction_r_ge_onset_threshold",
    "mass_weighted_radius_q99_um",
    "fixed_bin_mass_below_range_fraction",
    "fixed_bin_mass_above_range_fraction",
)
MEMBER_METRICS = (
    "tail_onset_first_recorded_crossing_s",
    "maximum_absolute_liquid_mass_drift",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-root",
        required=True,
        type=Path,
        help="root containing member run directories and analysis_stage0_v2",
    )
    parser.add_argument(
        "--output-directory",
        required=True,
        type=Path,
        help="fresh directory for combined tables and metadata",
    )
    parser.add_argument(
        "--matrix-file",
        required=True,
        type=Path,
        help="reviewed cases.tsv used to validate complete member coverage",
    )
    parser.add_argument("--confidence-level", default=0.95, type=float)
    parser.add_argument("--bootstrap-resamples", default=10000, type=int)
    parser.add_argument("--bootstrap-seed", default=20260728, type=int)
    return parser.parse_args()


def sha256_file(filename: Path) -> str:
    digest = hashlib.sha256()
    with filename.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv_rows(filename: Path, *, delimiter: str = ",") -> list[dict[str, str]]:
    with filename.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def write_csv_rows(filename: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty table: {filename}")
    with filename.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def discover_member_tables(run_root: Path) -> tuple[list[Path], list[Path]]:
    time_tables = sorted(run_root.glob("*/analysis_stage0_v2/member_time_diagnostics.csv"))
    member_tables = sorted(run_root.glob("*/analysis_stage0_v2/member_summary.csv"))
    if not time_tables:
        raise FileNotFoundError(f"no member_time_diagnostics.csv files found below {run_root}")
    if len(time_tables) != len(member_tables):
        raise RuntimeError(
            "each time-diagnostic table must have one corresponding member summary: "
            f"{len(time_tables)} time tables versus {len(member_tables)} summaries"
        )
    time_run_directories = {path.parents[1] for path in time_tables}
    member_run_directories = {path.parents[1] for path in member_tables}
    if time_run_directories != member_run_directories:
        raise RuntimeError("time and member tables do not describe the same run directories")
    return time_tables, member_tables


def _bootstrap_seed(base_seed: int, group_key: tuple[str, ...], metric: str) -> int:
    payload = "|".join((str(base_seed), *group_key, metric)).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def summarize_values(
    values: Iterable[float],
    *,
    confidence_level: float,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> dict[str, float | int]:
    """Return sample and uncertainty statistics for finite values."""
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence level must lie strictly between zero and one")
    if bootstrap_resamples < 1:
        raise ValueError("bootstrap_resamples must be at least one")

    raw = np.asarray(list(values), dtype=float)
    finite = raw[np.isfinite(raw)]
    n_valid = int(finite.size)
    n_total = int(raw.size)
    if n_valid == 0:
        return {
            "n_total": n_total,
            "n_valid": 0,
            "mean": float("nan"),
            "sample_standard_deviation": float("nan"),
            "standard_error": float("nan"),
            "student_ci_low": float("nan"),
            "student_ci_high": float("nan"),
            "bootstrap_ci_low": float("nan"),
            "bootstrap_ci_high": float("nan"),
            "coefficient_of_variation": float("nan"),
        }

    mean = float(np.mean(finite))
    if n_valid == 1:
        standard_deviation = float("nan")
        standard_error = float("nan")
        student_low = float("nan")
        student_high = float("nan")
    else:
        standard_deviation = float(np.std(finite, ddof=1))
        standard_error = standard_deviation / np.sqrt(n_valid)
        alpha = 1.0 - confidence_level
        multiplier = float(student_t.ppf(1.0 - alpha / 2.0, df=n_valid - 1))
        student_low = mean - multiplier * standard_error
        student_high = mean + multiplier * standard_error

    generator = np.random.default_rng(bootstrap_seed)
    bootstrap_means = np.mean(
        generator.choice(finite, size=(bootstrap_resamples, n_valid), replace=True),
        axis=1,
    )
    alpha = 1.0 - confidence_level
    bootstrap_low, bootstrap_high = np.quantile(
        bootstrap_means,
        [alpha / 2.0, 1.0 - alpha / 2.0],
    )
    coefficient_of_variation = (
        standard_deviation / abs(mean)
        if np.isfinite(standard_deviation) and mean != 0.0
        else float("nan")
    )
    return {
        "n_total": n_total,
        "n_valid": n_valid,
        "mean": mean,
        "sample_standard_deviation": standard_deviation,
        "standard_error": standard_error,
        "student_ci_low": float(student_low),
        "student_ci_high": float(student_high),
        "bootstrap_ci_low": float(bootstrap_low),
        "bootstrap_ci_high": float(bootstrap_high),
        "coefficient_of_variation": float(coefficient_of_variation),
    }


def group_metric_summaries(
    rows: list[dict[str, str]],
    *,
    group_columns: tuple[str, ...],
    metrics: tuple[str, ...],
    confidence_level: float,
    bootstrap_resamples: int,
    bootstrap_seed: int,
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        missing = [column for column in (*group_columns, *metrics) if column not in row]
        if missing:
            raise KeyError(f"input row is missing required columns: {missing}")
        grouped[tuple(row[column] for column in group_columns)].append(row)

    summaries: list[dict[str, object]] = []
    for group_key in sorted(grouped):
        group = grouped[group_key]
        identifiers = dict(zip(group_columns, group_key, strict=True))
        for metric in metrics:
            values = [float(row[metric]) for row in group]
            statistics = summarize_values(
                values,
                confidence_level=confidence_level,
                bootstrap_resamples=bootstrap_resamples,
                bootstrap_seed=_bootstrap_seed(bootstrap_seed, group_key, metric),
            )
            summaries.append({**identifiers, "metric": metric, **statistics})
    return summaries


def validate_unique_members(rows: list[dict[str, str]]) -> None:
    seen: set[tuple[str, str]] = set()
    for row in rows:
        identity = (row["run_label"], row["time_s"])
        if identity in seen:
            raise RuntimeError(f"duplicate member/time row: {identity}")
        seen.add(identity)


def validate_matrix_coverage(
    time_rows: list[dict[str, str]],
    member_rows: list[dict[str, str]],
    matrix_rows: list[dict[str, str]],
) -> None:
    """Require exactly one analyzed member for every reviewed matrix row."""
    expected = {row["run_label"]: row for row in matrix_rows}
    if len(expected) != len(matrix_rows):
        raise RuntimeError("matrix contains duplicate run labels")
    actual_member = {row["run_label"]: row for row in member_rows}
    if len(actual_member) != len(member_rows):
        raise RuntimeError("member summaries contain duplicate run labels")
    actual_time_labels = {row["run_label"] for row in time_rows}
    if set(expected) != set(actual_member) or set(expected) != actual_time_labels:
        missing = sorted(set(expected) - set(actual_member))
        unexpected = sorted(set(actual_member) - set(expected))
        missing_time = sorted(set(expected) - actual_time_labels)
        raise RuntimeError(
            "analyzed members do not exactly cover the reviewed matrix; "
            f"missing summaries={missing}, unexpected summaries={unexpected}, "
            f"missing time tables={missing_time}"
        )

    comparison_columns = (
        "matrix_stage",
        "initialization_family",
        "kernel",
        "max_superdroplets",
        "collision_timestep_s",
        "observation_timestep_s",
        "end_time_s",
        "member_index",
        "initialization_seed",
        "collision_seed",
    )
    for run_label, matrix_row in expected.items():
        member_row = actual_member[run_label]
        for column in comparison_columns:
            if member_row[column] != matrix_row[column]:
                raise RuntimeError(
                    f"member {run_label} disagrees with matrix column {column}: "
                    f"{member_row[column]!r} != {matrix_row[column]!r}"
                )


def main() -> None:
    args = parse_args()
    run_root = args.run_root.resolve()
    output_directory = args.output_directory.resolve()
    matrix_file = args.matrix_file.resolve()
    if output_directory.exists():
        raise FileExistsError(f"refusing to overwrite existing ensemble output: {output_directory}")
    time_tables, member_tables = discover_member_tables(run_root)

    time_rows = [row for table in time_tables for row in read_csv_rows(table)]
    member_rows = [row for table in member_tables for row in read_csv_rows(table)]
    matrix_rows = read_csv_rows(matrix_file, delimiter="\t")
    validate_unique_members(time_rows)
    validate_matrix_coverage(time_rows, member_rows, matrix_rows)

    output_directory.mkdir(parents=True)
    combined_time = output_directory / "all_member_time_diagnostics.csv"
    combined_member = output_directory / "all_member_summaries.csv"
    write_csv_rows(combined_time, time_rows)
    write_csv_rows(combined_member, member_rows)

    time_summaries = group_metric_summaries(
        time_rows,
        group_columns=TIME_GROUP_COLUMNS,
        metrics=TIME_METRICS,
        confidence_level=args.confidence_level,
        bootstrap_resamples=args.bootstrap_resamples,
        bootstrap_seed=args.bootstrap_seed,
    )
    member_summaries = group_metric_summaries(
        member_rows,
        group_columns=MEMBER_GROUP_COLUMNS,
        metrics=MEMBER_METRICS,
        confidence_level=args.confidence_level,
        bootstrap_resamples=args.bootstrap_resamples,
        bootstrap_seed=args.bootstrap_seed,
    )
    write_csv_rows(output_directory / "ensemble_time_summary.csv", time_summaries)
    write_csv_rows(output_directory / "ensemble_member_summary.csv", member_summaries)

    onset_status_counts: dict[str, int] = defaultdict(int)
    for row in member_rows:
        onset_status_counts[row["tail_onset_status"]] += 1

    source_records = [
        {"path": str(path), "sha256": sha256_file(path)} for path in (*time_tables, *member_tables)
    ]
    metadata = {
        "status": "completed",
        "run_root": str(run_root),
        "member_count": len(member_tables),
        "member_time_row_count": len(time_rows),
        "confidence_level": args.confidence_level,
        "bootstrap_resamples": args.bootstrap_resamples,
        "bootstrap_seed": args.bootstrap_seed,
        "matrix_file": str(matrix_file),
        "matrix_sha256": sha256_file(matrix_file),
        "onset_status_counts": dict(sorted(onset_status_counts.items())),
        "sources": source_records,
        "notes": [
            "Student intervals describe the ensemble mean under the usual "
            "independent-member assumption.",
            "Bootstrap intervals are percentile intervals from deterministic resampling.",
            "Tail-growth timing remains interval-censored by the configured output interval.",
            "The tail-growth time is not rain onset or surface precipitation.",
            "This summary does not by itself establish convergence or equivalence.",
        ],
    }
    (output_directory / "ensemble_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    print("ENSEMBLE_SUMMARY_PASS=1")
    print(f"member_count={len(member_tables)}")
    print(f"output_directory={output_directory}")


if __name__ == "__main__":
    main()
