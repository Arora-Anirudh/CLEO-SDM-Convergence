#!/bin/bash
#SBATCH --job-name=cleo_gol_dtscreen
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=02:00:00

# Run the reviewed controlled collision-timestep screen sequentially inside one
# allocation. Completed members can be safely skipped on a retry; incomplete
# paths always stop the workflow.
#
# Required submission form:
#
#   sbatch --account=<project> \
#     --export=ALL,MATRIX_FILE=/path/to/cases.tsv,SCREEN_RECORD_ROOT=/path/to/record \
#     scripts/levante/run_golovin_timestep_screen.sbatch
#
# SPDX-License-Identifier: BSD-3-Clause

set -eo pipefail
source /etc/profile
set -u

if [[ -n "${CLEO_SDM_PROJECT_ROOT:-}" ]]; then
  SCRIPT_DIR="${CLEO_SDM_PROJECT_ROOT}/scripts/levante"
elif [[ -n "${SLURM_SUBMIT_DIR:-}" ]] \
  && [[ -f "${SLURM_SUBMIT_DIR}/scripts/levante/common.sh" ]]; then
  SCRIPT_DIR="${SLURM_SUBMIT_DIR}/scripts/levante"
else
  SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
fi
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

: "${MATRIX_FILE:?Set MATRIX_FILE to the reviewed timestep cases.tsv.}"
: "${SCREEN_RECORD_ROOT:?Set SCREEN_RECORD_ROOT to a persistent HOME record path.}"
EXPECTED_CASE_COUNT="${EXPECTED_CASE_COUNT:-25}"
if [[ ! "${EXPECTED_CASE_COUNT}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: EXPECTED_CASE_COUNT must be a positive integer." >&2
  exit 2
fi

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
cleo_sdm_print_environment
export OMP_NUM_THREADS=1
umask 027

MATRIX_FILE="$(cd "$(dirname "${MATRIX_FILE}")" && pwd)/$(basename "${MATRIX_FILE}")"
if [[ ! -f "${MATRIX_FILE}" ]]; then
  echo "ERROR: matrix file is missing: ${MATRIX_FILE}" >&2
  exit 2
fi
actual_case_count="$(( $(wc -l <"${MATRIX_FILE}") - 1 ))"
if ((actual_case_count != EXPECTED_CASE_COUNT)); then
  echo "ERROR: expected ${EXPECTED_CASE_COUNT} cases, found ${actual_case_count}." >&2
  exit 2
fi
matrix_sha256="$(sha256sum "${MATRIX_FILE}" | awk '{print $1}')"
project_commit="$(git -C "${CLEO_SDM_PROJECT_ROOT}" rev-parse HEAD)"
if ! grep -Fqx \
  "project_commit=${project_commit}" \
  "${CLEO_SDM_BUILD_ROOT}/build_manifest.txt"; then
  echo "ERROR: exact project commit must be built before the screen." >&2
  exit 1
fi

if [[ -e "${SCREEN_RECORD_ROOT}" ]]; then
  if [[ ! -f "${SCREEN_RECORD_ROOT}/cases.tsv" ]]; then
    echo "ERROR: existing screen record has no cases.tsv." >&2
    exit 1
  fi
  existing_matrix_sha256="$(
    sha256sum "${SCREEN_RECORD_ROOT}/cases.tsv" | awk '{print $1}'
  )"
  if [[ "${existing_matrix_sha256}" != "${matrix_sha256}" ]]; then
    echo "ERROR: existing screen record belongs to a different matrix." >&2
    exit 1
  fi
else
  mkdir -p "${SCREEN_RECORD_ROOT}"
  install -m 0440 "${MATRIX_FILE}" "${SCREEN_RECORD_ROOT}/cases.tsv"
fi

screen_failed() {
  local status=$?
  if ((status != 0)); then
    {
      echo "status=failed"
      echo "exit_code=${status}"
      echo "failed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "slurm_job_id=${SLURM_JOB_ID}"
      echo "project_commit=${project_commit}"
      echo "matrix_sha256=${matrix_sha256}"
    } >"${SCREEN_RECORD_ROOT}/screen_failed_job${SLURM_JOB_ID}.txt"
  fi
  exit "${status}"
}
trap screen_failed EXIT

export MATRIX_FILE
export RESUME_COMPLETED=1
for ((case_index = 0; case_index < EXPECTED_CASE_COUNT; case_index++)); do
  echo "TIMESTEP_SCREEN_CASE_BEGIN=${case_index}"
  export MATRIX_CASE_INDEX="${case_index}"
  bash "${SCRIPT_DIR}/run_golovin_matrix.sbatch"
  echo "TIMESTEP_SCREEN_CASE_END=${case_index}"
done

python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
"${python}" - \
  "${MATRIX_FILE}" \
  "${CLEO_SDM_RUN_ROOT}" \
  "${project_commit}" \
  "${matrix_sha256}" \
  "${SCREEN_RECORD_ROOT}/model_inventory.json" <<'PY'
import csv
import hashlib
import json
import sys
from pathlib import Path

matrix_file = Path(sys.argv[1])
run_root = Path(sys.argv[2])
expected_project_commit = sys.argv[3]
expected_matrix_sha256 = sys.argv[4]
output = Path(sys.argv[5])

with matrix_file.open(encoding="utf-8", newline="") as stream:
    cases = list(csv.DictReader(stream, delimiter="\t"))

inventory = []
total_bytes = 0
for case in cases:
    run_directory = run_root / case["run_label"]
    manifest = run_directory / "manifest.txt"
    zarr = run_directory / "output" / "collisions0d_solution.zarr"
    if not manifest.is_file() or not zarr.is_dir():
        raise RuntimeError(f"incomplete screen member: {run_directory}")
    records = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            records[key] = value
    required = {
        "status": "completed",
        "project_commit": expected_project_commit,
        "matrix_sha256": expected_matrix_sha256,
        "initialization_family": "controlled",
        "max_superdroplets": case["max_superdroplets"],
        "collision_timestep_s": case["collision_timestep_s"],
        "collision_seed": case["collision_seed"],
        "member_index": case["member_index"],
    }
    for key, expected in required.items():
        if records.get(key) != expected:
            raise RuntimeError(
                f"{manifest}: {key}={records.get(key)!r}, expected {expected!r}"
            )
    zarr_bytes = sum(path.stat().st_size for path in zarr.rglob("*") if path.is_file())
    total_bytes += zarr_bytes
    inventory.append(
        {
            "run_label": case["run_label"],
            "collision_timestep_s": float(case["collision_timestep_s"]),
            "member_index": int(case["member_index"]),
            "collision_seed": int(case["collision_seed"]),
            "job_wall_seconds": int(records["job_wall_seconds"]),
            "zarr_bytes": zarr_bytes,
            "zarr_tree_sha256": records["zarr_tree_sha256"],
            "bundle_superdroplet_sha256": records["bundle_superdroplet_sha256"],
        }
    )

payload = {
    "status": "completed",
    "schema": "golovin_controlled_timestep_screen_inventory_v1",
    "case_count": len(inventory),
    "matrix_sha256": expected_matrix_sha256,
    "project_commit": expected_project_commit,
    "total_zarr_bytes": total_bytes,
    "members": inventory,
}
output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"completed_cases={len(inventory)}")
print(f"total_zarr_bytes={total_bytes}")
PY

trap - EXIT
echo "GOLOVIN_CONTROLLED_TIMESTEP_SCREEN_PASS=1"
echo "screen_record_root=${SCREEN_RECORD_ROOT}"
echo "matrix_sha256=${matrix_sha256}"
