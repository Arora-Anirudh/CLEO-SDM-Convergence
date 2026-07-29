"""Read back and validate one controlled CLEO initial-condition binary.

The controlled initializer first constructs scientific arrays and then asks
CLEO to write them in its native binary format. This gate uses CLEO's own
reader to verify the artifact that a compiled model would actually consume.

SPDX-License-Identifier: BSD-3-Clause
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from ruamel.yaml import YAML


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cleo-source",
        required=True,
        type=Path,
        help="CLEO source directory containing the cleopy package",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="materialized collisions0d YAML configuration",
    )
    parser.add_argument(
        "--audit-file",
        required=True,
        type=Path,
        help="controlled-initialization JSON audit",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="new JSON readback report",
    )
    return parser.parse_args()


def sha256_file(filename: Path) -> str:
    """Return one file's SHA-256 checksum."""
    digest = hashlib.sha256()
    with filename.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def population_sha256(multiplicities: np.ndarray, radii_m: np.ndarray) -> str:
    """Hash the read-back physical population using the project convention."""
    digest = hashlib.sha256()
    digest.update(np.asarray(multiplicities, dtype="<u8").tobytes())
    digest.update(np.asarray(radii_m, dtype="<f8").tobytes())
    return digest.hexdigest()


def radius_moment(
    order: int,
    radii_m: np.ndarray,
    multiplicities: np.ndarray,
    sample_volume_m3: float,
) -> float:
    """Return one represented radius moment in micron**order / m**3."""
    if order == 0:
        return sum(int(value) for value in multiplicities) / sample_volume_m3
    radii_um = np.asarray(radii_m, dtype=np.float64) * 1.0e6
    return float(
        np.sum(np.asarray(multiplicities, dtype=np.float64) * radii_um**order) / sample_volume_m3
    )


def load_yaml(filename: Path) -> dict:
    yaml = YAML(typ="safe")
    with filename.open("r", encoding="utf-8") as stream:
        return yaml.load(stream)


def validate_binary(
    *,
    cleo_source: Path,
    config_filename: Path,
    audit_filename: Path,
) -> dict:
    """Read one native binary and return a passing validation record."""
    if not (cleo_source / "cleopy" / "__init__.py").is_file():
        raise FileNotFoundError(f"CLEO cleopy package not found under {cleo_source}")
    config = load_yaml(config_filename)
    audit = json.loads(audit_filename.read_text(encoding="utf-8"))
    if audit.get("schema") != "controlled_initialization_audit_v1":
        raise ValueError("unexpected controlled-initialization audit schema")
    if audit.get("status") != "passed":
        raise ValueError("controlled-initialization audit did not pass")

    constants_filename = Path(config["inputfiles"]["constants_filename"]).resolve()
    grid_filename = Path(config["inputfiles"]["grid_filename"]).resolve()
    superdroplet_filename = Path(config["initsupers"]["initsupers_filename"]).resolve()
    for filename in (constants_filename, grid_filename, superdroplet_filename):
        if not filename.is_file():
            raise FileNotFoundError(f"required native input is missing: {filename}")

    expected_binary_sha256 = audit["artifacts"]["superdroplet_file"]["sha256"]
    actual_binary_sha256 = sha256_file(superdroplet_filename)
    if actual_binary_sha256 != expected_binary_sha256:
        raise ValueError("native superdroplet binary differs from its audit checksum")

    sys.path.insert(0, str(cleo_source))
    from cleopy.initsuperdropsbinary_src import read_initsuperdrops  # noqa: PLC0415

    attrs = read_initsuperdrops.get_superdroplet_attributes(
        config_filename,
        constants_filename,
        superdroplet_filename,
    )
    arrays = {
        "sdgbxindex": np.asarray(attrs.sdgbxindex).reshape(-1),
        "multiplicity": np.asarray(attrs.xi).reshape(-1),
        "radius_m": np.asarray(attrs.radius, dtype=np.float64).reshape(-1),
        "solute_mass_kg": np.asarray(attrs.msol, dtype=np.float64).reshape(-1),
        "coord3_m": np.asarray(attrs.coord3, dtype=np.float64).reshape(-1),
        "coord1_m": np.asarray(attrs.coord1, dtype=np.float64).reshape(-1),
        "coord2_m": np.asarray(attrs.coord2, dtype=np.float64).reshape(-1),
    }
    lengths = {name: int(values.size) for name, values in arrays.items()}
    if len(set(lengths.values())) != 1:
        raise ValueError(f"native attribute lengths differ: {lengths}")

    expected_nsd = int(audit["population"]["number_of_superdroplets"])
    if lengths["multiplicity"] != expected_nsd:
        raise ValueError(
            f"read-back N_SD={lengths['multiplicity']} differs from audit N_SD={expected_nsd}"
        )
    if np.any(arrays["sdgbxindex"] != 0):
        raise ValueError("controlled collisions0d binary contains a nonzero grid-box index")
    for name, values in arrays.items():
        if name not in {"sdgbxindex", "multiplicity"} and np.any(~np.isfinite(values)):
            raise ValueError(f"native attribute contains non-finite values: {name}")
    if np.any(arrays["multiplicity"] < 1):
        raise ValueError("native binary contains a non-positive multiplicity")
    if np.any(arrays["radius_m"] <= 0):
        raise ValueError("native binary contains a non-positive radius")
    if np.any(arrays["solute_mass_kg"] < 0):
        raise ValueError("native binary contains a negative solute mass")

    grid = config["python_initconds"]["grid"]
    for coordinate_name, axis in (
        ("coord3_m", "zgrid"),
        ("coord1_m", "xgrid"),
        ("coord2_m", "ygrid"),
    ):
        lower, upper = map(float, grid[axis])
        values = arrays[coordinate_name]
        if np.any(values < lower) or np.any(values > upper):
            raise ValueError(f"{coordinate_name} lies outside configured {axis} bounds")

    sample_volume_m3 = float(
        np.prod(
            [float(grid[axis][1]) - float(grid[axis][0]) for axis in ("zgrid", "xgrid", "ygrid")]
        )
    )
    represented_total = sum(int(value) for value in arrays["multiplicity"])
    expected_total = int(audit["population"]["represented_real_droplets"])
    if represented_total != expected_total:
        raise ValueError(
            f"read-back physical-droplet total {represented_total} "
            f"differs from audit total {expected_total}"
        )

    moments = {
        order: radius_moment(
            order,
            arrays["radius_m"],
            arrays["multiplicity"],
            sample_volume_m3,
        )
        for order in (0, 3, 6)
    }
    moment_checks = {}
    for order, value in moments.items():
        expected = float(audit["moments"][f"M{order}_represented"])
        relative_difference = (value - expected) / expected
        if not np.isclose(value, expected, rtol=5.0e-13, atol=0.0):
            raise ValueError(
                f"native read-back M{order} differs from the initializer audit: "
                f"relative_difference={relative_difference:.17g}"
            )
        moment_checks[f"M{order}"] = {
            "readback": value,
            "audit_represented": expected,
            "relative_difference": relative_difference,
        }

    readback_population_sha256 = population_sha256(
        arrays["multiplicity"],
        arrays["radius_m"],
    )
    source_population_sha256 = audit["population"]["population_sha256"]
    return {
        "schema": "controlled_initialization_native_readback_v1",
        "status": "passed",
        "reader": "CLEO cleopy.initsuperdropsbinary_src.read_initsuperdrops",
        "artifacts": {
            "config": {
                "path": str(config_filename),
                "sha256": sha256_file(config_filename),
            },
            "audit": {
                "path": str(audit_filename),
                "sha256": sha256_file(audit_filename),
            },
            "grid_binary": {
                "path": str(grid_filename),
                "sha256": sha256_file(grid_filename),
            },
            "superdroplet_binary": {
                "path": str(superdroplet_filename),
                "sha256": actual_binary_sha256,
            },
        },
        "population": {
            "number_of_superdroplets": expected_nsd,
            "represented_real_droplets": represented_total,
            "minimum_multiplicity": int(np.min(arrays["multiplicity"])),
            "maximum_multiplicity": int(np.max(arrays["multiplicity"])),
            "minimum_radius_um": float(np.min(arrays["radius_m"]) * 1.0e6),
            "maximum_radius_um": float(np.max(arrays["radius_m"]) * 1.0e6),
            "source_population_sha256": source_population_sha256,
            "readback_population_sha256": readback_population_sha256,
            "population_sha256_exact_match": (
                readback_population_sha256 == source_population_sha256
            ),
        },
        "moments": moment_checks,
        "coordinates": {
            name: {
                "minimum_m": float(np.min(arrays[name])),
                "maximum_m": float(np.max(arrays[name])),
            }
            for name in ("coord3_m", "coord1_m", "coord2_m")
        },
        "checks": {
            "binary_sha256_matches_audit": True,
            "attribute_lengths_equal": True,
            "one_grid_box_only": True,
            "finite_dimensional_attributes": True,
            "coordinates_inside_configured_bounds": True,
            "exact_integer_physical_droplet_total": True,
            "represented_moments_match_audit": True,
        },
    }


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite readback report: {output}")
    record = validate_binary(
        cleo_source=args.cleo_source.resolve(),
        config_filename=args.config.resolve(),
        audit_filename=args.audit_file.resolve(),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CONTROLLED_INITIALIZATION_NATIVE_READBACK_PASS=1")
    print(f"readback_report={output}")
    print(f"population_sha256_exact_match={record['population']['population_sha256_exact_match']}")


if __name__ == "__main__":
    main()
