#!/bin/bash
#
# Submit one CLEO-SDM-Convergence Slurm script with account- and user-correct
# logging. Usage:
#
#   scripts/levante/submit.sh SCRIPT [SBATCH_OPTIONS...]
#
# Example:
#
#   scripts/levante/submit.sh scripts/levante/run_collisions0d.sbatch \
#     --export=ALL,KERNEL=golovin,RUN_LABEL=example
#
# SPDX-License-Identifier: BSD-3-Clause

set -euo pipefail

if [[ "$#" -lt 1 ]]; then
  echo "Usage: $0 SCRIPT [SBATCH_OPTIONS...]" >&2
  exit 2
fi

readonly SCRIPT="$1"
shift

[[ -f "${SCRIPT}" ]] || {
  echo "ERROR: Slurm script does not exist: ${SCRIPT}" >&2
  exit 1
}

readonly ACTIVE_USER="${USER:-$(id -un)}"
readonly SLURM_ACCOUNT="${CLEO_SDM_SLURM_ACCOUNT:-mh0731}"
readonly SCRATCH_ROOT="${CLEO_SDM_SCRATCH_ROOT:-/scratch/${ACTIVE_USER:0:1}/${ACTIVE_USER}/SDM}"
readonly LOG_ROOT="${CLEO_SDM_LOG_ROOT:-${SCRATCH_ROOT}/logs}"

mkdir -p "${LOG_ROOT}"

echo "submission_user=${ACTIVE_USER}"
echo "submission_account=${SLURM_ACCOUNT}"
echo "submission_script=${SCRIPT}"
echo "submission_log_root=${LOG_ROOT}"

sbatch \
  --account="${SLURM_ACCOUNT}" \
  --output="${LOG_ROOT}/%x_%j.out" \
  --error="${LOG_ROOT}/%x_%j.err" \
  "$@" \
  "${SCRIPT}"
