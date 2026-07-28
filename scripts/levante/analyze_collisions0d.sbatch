#!/bin/bash
#SBATCH --job-name=cleo_sdm_diag0d
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=00:10:00
#SBATCH --output=/scratch/b/b383673/SDM/logs/%x_%j.out
#SBATCH --error=/scratch/b/b383673/SDM/logs/%x_%j.err

# Analyze one completed collision-only box-model run.
#
# Required submission form:
#
#   sbatch --account=<project> \
#     --export=ALL,KERNEL=golovin,RUN_LABEL=first_golovin_serial \
#     scripts/levante/analyze_collisions0d.sbatch
#
# SPDX-License-Identifier: BSD-3-Clause

set -eo pipefail
source /etc/profile
set -u

if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
  SCRIPT_DIR="${SLURM_SUBMIT_DIR}/scripts/levante"
else
  SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
fi
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

: "${KERNEL:?Set KERNEL to golovin or long at submission.}"
: "${RUN_LABEL:?Set the completed RUN_LABEL at submission.}"

if [[ "${KERNEL}" != "golovin" && "${KERNEL}" != "long" ]]; then
  echo "ERROR: KERNEL must be golovin or long, got ${KERNEL}" >&2
  exit 2
fi
if [[ ! "${RUN_LABEL}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "ERROR: RUN_LABEL contains unsupported characters: ${RUN_LABEL}" >&2
  exit 2
fi

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
cleo_sdm_print_environment

run_directory="${CLEO_SDM_RUN_ROOT}/${RUN_LABEL}"
cleo_source="${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src"
output_directory="${run_directory}/analysis_v1"
python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"

test -d "${run_directory}"
test -x "${python}"
test -d "${cleo_source}"
if [[ -e "${output_directory}" ]]; then
  echo "ERROR: diagnostic output already exists; refusing to overwrite: ${output_directory}" >&2
  exit 1
fi

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_collisions0d.py" \
  --cleo-source "${cleo_source}" \
  --run-directory "${run_directory}" \
  --kernel "${KERNEL}" \
  --output-directory "${output_directory}" \
  --times 0 1200 2400 3600

test -f "${output_directory}/bulk_diagnostics.csv"
test -f "${output_directory}/${KERNEL}_mass_distribution.png"
test -f "${output_directory}/${KERNEL}_bulk_diagnostics.png"
test -f "${output_directory}/diagnostic_metadata.json"

sha256sum \
  "${output_directory}/bulk_diagnostics.csv" \
  "${output_directory}/${KERNEL}_mass_distribution.png" \
  "${output_directory}/${KERNEL}_bulk_diagnostics.png" \
  "${output_directory}/diagnostic_metadata.json" \
  >"${output_directory}/SHA256SUMS"

echo "DIAGNOSTIC_JOB_PASS=1"
echo "output_directory=${output_directory}"
