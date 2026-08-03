#!/bin/bash
#SBATCH --job-name=cleo_gol_unf_cmp
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --hint=nomultithread
#SBATCH --mem=4G
#SBATCH --time=01:30:00

# Compare completed frozen and operational Golovin fixed-50 protocols.  This is
# analysis only: it launches no CLEO model and writes only compact HOME records.
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

: "${UNFROZEN_CONFIG:?Set UNFROZEN_CONFIG.}"
: "${FROZEN_CASES:?Set FROZEN_CASES.}"
: "${OPERATIONAL_CASES:?Set OPERATIONAL_CASES.}"
: "${FROZEN_MEMBER_TIME:?Set FROZEN_MEMBER_TIME.}"
: "${OPERATIONAL_MEMBER_TIME:?Set OPERATIONAL_MEMBER_TIME.}"
: "${FROZEN_RESOLUTION_DIRECTORY:?Set FROZEN_RESOLUTION_DIRECTORY.}"
: "${OPERATIONAL_RESOLUTION_DIRECTORY:?Set OPERATIONAL_RESOLUTION_DIRECTORY.}"
: "${COMPARISON_OUTPUT_DIRECTORY:?Set COMPARISON_OUTPUT_DIRECTORY.}"

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
export OMP_NUM_THREADS=1
umask 027

if [[ -e "${COMPARISON_OUTPUT_DIRECTORY}" ]]; then
  echo "ERROR: comparison output already exists: ${COMPARISON_OUTPUT_DIRECTORY}" >&2
  exit 1
fi

"${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python" \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/compare_golovin_initialization_protocols.py" \
  --config "${UNFROZEN_CONFIG}" \
  --frozen-cases "${FROZEN_CASES}" \
  --operational-cases "${OPERATIONAL_CASES}" \
  --frozen-member-time "${FROZEN_MEMBER_TIME}" \
  --operational-member-time "${OPERATIONAL_MEMBER_TIME}" \
  --frozen-resolution-directory "${FROZEN_RESOLUTION_DIRECTORY}" \
  --operational-resolution-directory "${OPERATIONAL_RESOLUTION_DIRECTORY}" \
  --output-directory "${COMPARISON_OUTPUT_DIRECTORY}"

echo "GOLOVIN_UNFROZEN_COMPARISON_PASS=1"
echo "comparison_output=${COMPARISON_OUTPUT_DIRECTORY}"
