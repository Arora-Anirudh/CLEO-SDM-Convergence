#!/bin/bash
#SBATCH --job-name=cleo_gol_matrix
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=00:10:00
#SBATCH --output=/scratch/b/b383673/SDM/logs/%x_%A_%a.out
#SBATCH --error=/scratch/b/b383673/SDM/logs/%x_%A_%a.err

# Execute exactly one row of a prepared Stage-0 Golovin matrix.
#
# MATRIX_FILE must name the immutable tab-separated cases.tsv file.
# Submit the array bounds explicitly after inspecting matrix_manifest.json.
# Existing completed cases are skipped only with RESUME_COMPLETED=1. Existing
# incomplete paths always fail because CLEO has no safe partial-output resume.
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

: "${MATRIX_FILE:?Set MATRIX_FILE to an immutable cases.tsv file.}"
: "${SLURM_ARRAY_TASK_ID:?Submit this script as a bounded Slurm array.}"
RESUME_COMPLETED="${RESUME_COMPLETED:-0}"

if [[ "${RESUME_COMPLETED}" != "0" && "${RESUME_COMPLETED}" != "1" ]]; then
  echo "ERROR: RESUME_COMPLETED must be 0 or 1." >&2
  exit 2
fi
if [[ ! -f "${MATRIX_FILE}" ]]; then
  echo "ERROR: matrix file is missing: ${MATRIX_FILE}" >&2
  exit 2
fi
if [[ ! "${SLURM_ARRAY_TASK_ID}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: SLURM_ARRAY_TASK_ID must be a non-negative integer." >&2
  exit 2
fi

expected_header=$'case_index\trun_label\tmatrix_stage\tinitialization_family\tkernel\tmax_superdroplets\tcollision_timestep_s\tobservation_timestep_s\tend_time_s\tmodel_threads\tmember_index\tinitialization_seed\tcollision_seed\tcontrolled_bundle_label'
actual_header="$(head -n 1 "${MATRIX_FILE}")"
if [[ "${actual_header}" != "${expected_header}" ]]; then
  echo "ERROR: matrix header is not the registered Stage-0 schema." >&2
  exit 2
fi

line_number=$((SLURM_ARRAY_TASK_ID + 2))
case_line="$(sed -n "${line_number}p" "${MATRIX_FILE}")"
if [[ -z "${case_line}" ]]; then
  echo "ERROR: array index ${SLURM_ARRAY_TASK_ID} is outside the matrix." >&2
  exit 2
fi

IFS=$'\t' read -r \
  case_index \
  run_label \
  matrix_stage \
  initialization_family \
  kernel \
  max_superdroplets \
  collision_timestep_s \
  observation_timestep_s \
  end_time_s \
  model_threads \
  member_index \
  initialization_seed \
  collision_seed \
  controlled_bundle_label <<<"${case_line}"

if [[ "${case_index}" != "${SLURM_ARRAY_TASK_ID}" ]]; then
  echo "ERROR: row case_index=${case_index} does not match array index." >&2
  exit 2
fi
if [[ "${kernel}" != "golovin" ]]; then
  echo "ERROR: this wrapper accepts only Golovin rows." >&2
  exit 2
fi

run_directory="${CLEO_SDM_RUN_ROOT}/${run_label}"
if [[ -e "${run_directory}" ]]; then
  if [[ "${RESUME_COMPLETED}" == "1" ]] \
    && [[ -f "${run_directory}/manifest.txt" ]] \
    && grep -qx "status=completed" "${run_directory}/manifest.txt"; then
    echo "CASE_ALREADY_COMPLETED=1"
    echo "run_directory=${run_directory}"
    exit 0
  fi
  echo "ERROR: case path exists and is not eligible for completed-case skip:" >&2
  echo "${run_directory}" >&2
  exit 1
fi

export KERNEL="${kernel}"
export INITIALIZATION_SEED="${initialization_seed}"
export COLLISION_SEED="${collision_seed}"
export RUN_LABEL="${run_label}"
export MODEL_THREADS="${model_threads}"
export MAX_SUPERDROPLETS="${max_superdroplets}"
export COLLISION_TIMESTEP_S="${collision_timestep_s}"
export OBSERVATION_TIMESTEP_S="${observation_timestep_s}"
export END_TIME_S="${end_time_s}"
export MATRIX_STAGE="${matrix_stage}"
export INITIALIZATION_FAMILY="${initialization_family}"
if [[ "${initialization_family}" == "controlled" ]]; then
  if [[ "${controlled_bundle_label}" == "not_applicable" ]]; then
    echo "ERROR: controlled row has no bundle label." >&2
    exit 2
  fi
  export CONTROLLED_BUNDLE="${CLEO_SDM_BUNDLE_ROOT}/${controlled_bundle_label}"
elif [[ "${controlled_bundle_label}" != "not_applicable" ]]; then
  echo "ERROR: operational row unexpectedly contains a controlled bundle label." >&2
  exit 2
fi
export MATRIX_CASE_INDEX="${case_index}"
export MEMBER_INDEX="${member_index}"
export MATRIX_FILE
export MATRIX_SHA256
MATRIX_SHA256="$(sha256sum "${MATRIX_FILE}" | awk '{print $1}')"

echo "matrix_file=${MATRIX_FILE}"
echo "matrix_sha256=${MATRIX_SHA256}"
echo "case_index=${case_index}"
echo "run_label=${run_label}"

bash "${SCRIPT_DIR}/run_collisions0d.sbatch"
