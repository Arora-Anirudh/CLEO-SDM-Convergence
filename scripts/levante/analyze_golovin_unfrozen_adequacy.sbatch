#!/bin/bash
#SBATCH --job-name=cleo_gol_unf_n
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --hint=nomultithread
#SBATCH --mem=4G
#SBATCH --time=02:00:00

# Reconstruct the parent-pool-conditional ensemble-size adequacy curve after
# the complete operational 50-member resolution analysis. This is analysis
# only and derives its target from the full-50 operational decision.
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

: "${ADEQUACY_CONFIG:?Set ADEQUACY_CONFIG.}"
: "${OPERATIONAL_CASES:?Set OPERATIONAL_CASES.}"
: "${OPERATIONAL_MEMBER_TIME:?Set OPERATIONAL_MEMBER_TIME.}"
: "${OPERATIONAL_RUN_ROOT:?Set OPERATIONAL_RUN_ROOT.}"
: "${OPERATIONAL_RESOLUTION_DECISION:?Set OPERATIONAL_RESOLUTION_DECISION.}"
: "${ADEQUACY_OUTPUT_DIRECTORY:?Set ADEQUACY_OUTPUT_DIRECTORY.}"

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
export OMP_NUM_THREADS=1
umask 027

if [[ -e "${ADEQUACY_OUTPUT_DIRECTORY}" ]]; then
  echo "ERROR: adequacy output already exists: ${ADEQUACY_OUTPUT_DIRECTORY}" >&2
  exit 1
fi

"${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python" \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_golovin_ensemble_size_adequacy.py" \
  --config "${ADEQUACY_CONFIG}" \
  --cases "${OPERATIONAL_CASES}" \
  --member-time "${OPERATIONAL_MEMBER_TIME}" \
  --stage0-root "${OPERATIONAL_RUN_ROOT}" \
  --resolution-decision "${OPERATIONAL_RESOLUTION_DECISION}" \
  --output "${ADEQUACY_OUTPUT_DIRECTORY}"

echo "GOLOVIN_UNFROZEN_ADEQUACY_PASS=1"
echo "adequacy_output=${ADEQUACY_OUTPUT_DIRECTORY}"
