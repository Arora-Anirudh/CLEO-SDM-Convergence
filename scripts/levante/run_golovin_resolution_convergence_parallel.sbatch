#!/bin/bash
#SBATCH --job-name=cleo_gol_hires
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=1
#SBATCH --hint=nomultithread
#SBATCH --mem=3600M
#SBATCH --time=02:15:00
#SBATCH --output=/scratch/b/b383673/SDM/logs/%x_%j.out
#SBATCH --error=/scratch/b/b383673/SDM/logs/%x_%j.err

# Run a reviewed Golovin matrix with a bounded number of independent serial
# CLEO members inside one Slurm allocation. This avoids one scheduler job per
# member while preserving one rank and one thread per member.
#
# Each worker owns a disjoint strided subset of matrix rows. Completed rows
# are checksum-audited and skipped on restart; incomplete or mismatched paths
# stop the allocation for inspection.
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

: "${MATRIX_FILE:?Set MATRIX_FILE to the reviewed resolution cases.tsv.}"
: "${RESOLUTION_RECORD_ROOT:?Set RESOLUTION_RECORD_ROOT to a persistent HOME record path.}"
EXPECTED_CASE_COUNT="${EXPECTED_CASE_COUNT:-400}"
WORKER_COUNT="${WORKER_COUNT:-4}"
RESUME_COMPLETED="${RESUME_COMPLETED:-1}"

for integer_name in EXPECTED_CASE_COUNT WORKER_COUNT; do
  integer_value="${!integer_name}"
  if [[ ! "${integer_value}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: ${integer_name} must be a positive integer." >&2
    exit 2
  fi
done
if [[ "${RESUME_COMPLETED}" != "1" ]]; then
  echo "ERROR: this restartable runner requires RESUME_COMPLETED=1." >&2
  exit 2
fi
if ((WORKER_COUNT > SLURM_NTASKS)); then
  echo "ERROR: WORKER_COUNT exceeds allocated Slurm tasks." >&2
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
  echo "ERROR: exact project commit must be built before the experiment." >&2
  exit 1
fi

if [[ -e "${RESOLUTION_RECORD_ROOT}" ]]; then
  if [[ ! -f "${RESOLUTION_RECORD_ROOT}/cases.tsv" ]]; then
    echo "ERROR: existing resolution record has no cases.tsv." >&2
    exit 1
  fi
  existing_matrix_sha256="$(
    sha256sum "${RESOLUTION_RECORD_ROOT}/cases.tsv" | awk '{print $1}'
  )"
  if [[ "${existing_matrix_sha256}" != "${matrix_sha256}" ]]; then
    echo "ERROR: existing resolution record belongs to a different matrix." >&2
    exit 1
  fi
else
  mkdir -p "${RESOLUTION_RECORD_ROOT}"
  install -m 0440 "${MATRIX_FILE}" "${RESOLUTION_RECORD_ROOT}/cases.tsv"
fi

worker_log_directory="${RESOLUTION_RECORD_ROOT}/worker_logs_job${SLURM_JOB_ID}"
if [[ -e "${worker_log_directory}" ]]; then
  echo "ERROR: worker-log directory already exists: ${worker_log_directory}" >&2
  exit 1
fi
mkdir "${worker_log_directory}"

run_started_epoch="$(date +%s)"
runner_failed() {
  local status=$?
  if ((status != 0)); then
    {
      echo "status=failed"
      echo "exit_code=${status}"
      echo "failed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "slurm_job_id=${SLURM_JOB_ID}"
      echo "project_commit=${project_commit}"
      echo "matrix_sha256=${matrix_sha256}"
      echo "worker_count=${WORKER_COUNT}"
    } >"${RESOLUTION_RECORD_ROOT}/runner_failed_job${SLURM_JOB_ID}.txt"
  fi
  exit "${status}"
}
trap runner_failed EXIT

export MATRIX_FILE
export RESUME_COMPLETED
declare -a worker_pids=()
for ((worker_index = 0; worker_index < WORKER_COUNT; worker_index++)); do
  (
    for ((case_index = worker_index;
      case_index < EXPECTED_CASE_COUNT;
      case_index += WORKER_COUNT)); do
      echo "RESOLUTION_CASE_BEGIN=${case_index}"
      export MATRIX_CASE_INDEX="${case_index}"
      bash "${SCRIPT_DIR}/run_golovin_matrix.sbatch"
      echo "RESOLUTION_CASE_END=${case_index}"
    done
  ) >"${worker_log_directory}/worker_${worker_index}.out" \
    2>"${worker_log_directory}/worker_${worker_index}.err" &
  worker_pids+=("$!")
done

worker_failure=0
for worker_pid in "${worker_pids[@]}"; do
  if ! wait "${worker_pid}"; then
    worker_failure=1
  fi
done
if ((worker_failure != 0)); then
  echo "ERROR: at least one matrix worker failed; inspect ${worker_log_directory}." >&2
  exit 1
fi

python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
inventory_staging="${RESOLUTION_RECORD_ROOT}/.model_inventory_job${SLURM_JOB_ID}.json"
if [[ -e "${inventory_staging}" ]]; then
  echo "ERROR: inventory staging path already exists: ${inventory_staging}" >&2
  exit 1
fi
"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/audit_golovin_matrix.py" \
  --matrix-file "${MATRIX_FILE}" \
  --run-root "${CLEO_SDM_RUN_ROOT}" \
  --output "${inventory_staging}"

inventory="${RESOLUTION_RECORD_ROOT}/model_inventory.json"
if [[ -e "${inventory}" ]]; then
  if ! cmp --silent "${inventory}" "${inventory_staging}"; then
    echo "ERROR: existing model inventory differs from the new audit." >&2
    exit 1
  fi
  rm "${inventory_staging}"
else
  mv "${inventory_staging}" "${inventory}"
fi

run_finished_epoch="$(date +%s)"
{
  echo "status=completed"
  echo "completed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "slurm_job_id=${SLURM_JOB_ID}"
  echo "slurm_account=${SLURM_JOB_ACCOUNT:-unknown}"
  echo "slurm_partition=${SLURM_JOB_PARTITION:-unknown}"
  echo "slurm_ntasks=${SLURM_NTASKS}"
  echo "slurm_cpus_per_task=${SLURM_CPUS_PER_TASK}"
  echo "slurm_mem_per_node=${SLURM_MEM_PER_NODE:-unknown}"
  echo "slurm_time_limit=${SLURM_TIMELIMIT:-unknown}"
  echo "worker_count=${WORKER_COUNT}"
  echo "runner_wall_seconds=$((run_finished_epoch - run_started_epoch))"
  echo "project_commit=${project_commit}"
  echo "matrix_sha256=${matrix_sha256}"
  echo "completed_cases=${EXPECTED_CASE_COUNT}"
  echo "model_inventory_sha256=$(sha256sum "${inventory}" | awk '{print $1}')"
} >"${RESOLUTION_RECORD_ROOT}/runner_completed_job${SLURM_JOB_ID}.txt"

trap - EXIT
echo "GOLOVIN_CONTROLLED_PARALLEL_RESOLUTION_RUN_PASS=1"
echo "completed_cases=${EXPECTED_CASE_COUNT}"
echo "worker_count=${WORKER_COUNT}"
echo "resolution_record_root=${RESOLUTION_RECORD_ROOT}"
echo "model_inventory=${inventory}"
echo "matrix_sha256=${matrix_sha256}"
