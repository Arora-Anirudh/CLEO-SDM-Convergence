#!/bin/bash
#SBATCH --job-name=cleo_gol_unf_shard
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=8
#SBATCH --cpus-per-task=1
#SBATCH --hint=nomultithread
#SBATCH --mem=12G
#SBATCH --time=08:00:00

# Run one contiguous reviewed operational Golovin matrix group. The calling
# submission must set CASE_INDEX_START, CASE_INDEX_END and (when it differs
# from 50) EXPECTED_GROUP_CASES. It deliberately does not run a whole-matrix
# audit: that happens once, after every group has completed, in the dependent
# analysis job.
#
# Eight one-rank, one-thread members run concurrently on eight physical cores.
# This is an allocation-level parallelism strategy; the 0-D CLEO member itself
# remains serial and is not MPI-decomposed.
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

: "${MATRIX_FILE:?Set MATRIX_FILE to the committed operational cases.tsv.}"
: "${RESOLUTION_RECORD_ROOT:?Set RESOLUTION_RECORD_ROOT to the persistent HOME record path.}"
: "${CASE_INDEX_START:?Set CASE_INDEX_START for this resolution shard.}"
: "${CASE_INDEX_END:?Set CASE_INDEX_END for this resolution shard.}"

export EXPECTED_CASE_COUNT="${EXPECTED_CASE_COUNT:-450}"
export WORKER_COUNT="${WORKER_COUNT:-8}"
export RESUME_COMPLETED=1
export REQUIRE_COMPLETE_MATRIX=0
EXPECTED_GROUP_CASES="${EXPECTED_GROUP_CASES:-50}"

if ((WORKER_COUNT != 8 || SLURM_NTASKS != 8 || SLURM_CPUS_PER_TASK != 1)); then
  echo "ERROR: the reviewed shard layout is eight one-core members." >&2
  exit 2
fi
if [[ ! "${EXPECTED_GROUP_CASES}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: EXPECTED_GROUP_CASES must be a positive integer." >&2
  exit 2
fi
if ((CASE_INDEX_END - CASE_INDEX_START + 1 != EXPECTED_GROUP_CASES)); then
  echo "ERROR: selected matrix range does not match EXPECTED_GROUP_CASES." >&2
  exit 2
fi

exec bash "${SCRIPT_DIR}/run_golovin_resolution_convergence_parallel.sbatch"
