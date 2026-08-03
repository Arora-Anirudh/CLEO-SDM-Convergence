#!/bin/bash
#SBATCH --job-name=cleo_gol_unf_smoke
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --hint=nomultithread
#SBATCH --mem=4G
#SBATCH --time=03:00:00

# Run exactly two production-shaped operational-initialization Golovin members:
# the 4,096- and 1,048,576-SD endpoints.  This is the mandatory smoke gate for
# the full 450-member experiment, not a miniature convergence experiment.
#
# The job creates two genuine, reusable members.  It verifies that fresh input
# binaries, the highest planned resolution, MPI launch, output writing and
# Stage-0 diagnostics work together before broader resources are requested.
#
# SPDX-License-Identifier: BSD-3-Clause

set -eo pipefail
unset LC_ALL
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

: "${MATRIX_FILE:?Set MATRIX_FILE to the committed operational cases.tsv.}"
: "${RESOLUTION_RECORD_ROOT:?Set RESOLUTION_RECORD_ROOT to a fresh HOME record path.}"

EXPECTED_CASE_COUNT="${EXPECTED_CASE_COUNT:-450}"
SMOKE_CASE_LOW="${SMOKE_CASE_LOW:-0}"
SMOKE_CASE_HIGH="${SMOKE_CASE_HIGH:-400}"

if ((SLURM_NTASKS != 1)); then
  echo "ERROR: smoke must allocate exactly one Slurm task." >&2
  exit 2
fi
# On the shared partition, Slurm can raise SLURM_CPUS_PER_TASK above the
# submitted value in order to satisfy a node-level --mem request. The actual
# model step below still requests one exclusive physical core, and the smoke
# explicitly fixes OMP_NUM_THREADS=1. Do not mistake memory-accounting CPUs
# for model threads.
if ((SLURM_CPUS_PER_TASK < 1)); then
  echo "ERROR: smoke allocation provides no CPU for its one model task." >&2
  exit 2
fi
if [[ ! "${SMOKE_CASE_LOW}" =~ ^[0-9]+$ || ! "${SMOKE_CASE_HIGH}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: smoke case indices must be non-negative integers." >&2
  exit 2
fi
if [[ "${SMOKE_CASE_LOW}" == "${SMOKE_CASE_HIGH}" ]]; then
  echo "ERROR: smoke case indices must differ." >&2
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
  echo "ERROR: matrix is missing: ${MATRIX_FILE}" >&2
  exit 2
fi
if (( $(wc -l <"${MATRIX_FILE}") - 1 != EXPECTED_CASE_COUNT )); then
  echo "ERROR: smoke matrix does not contain ${EXPECTED_CASE_COUNT} cases." >&2
  exit 2
fi

if [[ -e "${RESOLUTION_RECORD_ROOT}/smoke_gate.json" ]]; then
  echo "ERROR: smoke gate already exists; refusing to overwrite it." >&2
  exit 1
fi

for case_index in "${SMOKE_CASE_LOW}" "${SMOKE_CASE_HIGH}"; do
  export MATRIX_FILE
  export MATRIX_CASE_INDEX="${case_index}"
  export RESUME_COMPLETED=1
  bash "${SCRIPT_DIR}/run_golovin_matrix.sbatch"

  run_label="$(sed -n "$((case_index + 2))p" "${MATRIX_FILE}" | cut -f2)"
  run_directory="${CLEO_SDM_RUN_ROOT}/${run_label}"
  smoke_analysis="${run_directory}/analysis_smoke_v1"
  if [[ ! -d "${smoke_analysis}" ]]; then
    smoke_staging="${run_directory}/.analysis_smoke_v1_job${SLURM_JOB_ID}.tmp"
    if [[ -e "${smoke_staging}" ]]; then
      echo "ERROR: smoke diagnostic staging path exists: ${smoke_staging}" >&2
      exit 1
    fi
    "${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python" \
      "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_collisions0d.py" \
      --cleo-source "${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src" \
      --run-directory "${run_directory}" \
      --kernel golovin \
      --output-directory "${smoke_staging}" \
      --skip-figures \
      --times 0 600 1200 1800 2400 3000 3600
    mv "${smoke_staging}" "${smoke_analysis}"
  fi
  test -f "${smoke_analysis}/diagnostic_metadata.json"
  grep -Fq '"status": "completed"' "${smoke_analysis}/diagnostic_metadata.json"
done

"${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python" \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/validate_golovin_unfrozen_smoke.py" \
  --matrix-file "${MATRIX_FILE}" \
  --run-root "${CLEO_SDM_RUN_ROOT}" \
  --case-indices "${SMOKE_CASE_LOW}" "${SMOKE_CASE_HIGH}" \
  --output "${RESOLUTION_RECORD_ROOT}/smoke_gate.json"

echo "GOLOVIN_UNFROZEN_SMOKE_PASS=1"
echo "smoke_gate=${RESOLUTION_RECORD_ROOT}/smoke_gate.json"
