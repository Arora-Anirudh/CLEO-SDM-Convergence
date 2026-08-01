#!/bin/bash
#SBATCH --job-name=cleo_gol_stage0
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --hint=nomultithread
#SBATCH --mem=940M
#SBATCH --time=02:00:00

# Produce only per-member Stage-0 diagnostics for a completed Golovin matrix.
# It is intentionally separate from resolution selection because an extension
# matrix can contain only a subset of the final analysis resolutions.
#
# SPDX-License-Identifier: BSD-3-Clause

set -eo pipefail
source /etc/profile
set -u

if [[ -n "${CLEO_SDM_PROJECT_ROOT:-}" ]]; then
  SCRIPT_DIR="${CLEO_SDM_PROJECT_ROOT}/scripts/levante"
else
  SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
fi
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

: "${MATRIX_FILE:?Set MATRIX_FILE to the reviewed completed cases.tsv.}"
: "${STAGE0_RECORD_ROOT:?Set STAGE0_RECORD_ROOT to a fresh persistent record path.}"
EXPECTED_CASE_COUNT="${EXPECTED_CASE_COUNT:?Set EXPECTED_CASE_COUNT.}"

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
export OMP_NUM_THREADS=1
umask 027

python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
cleo_source="${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src"
test -x "${python}"
test -d "${cleo_source}"
test -f "${MATRIX_FILE}"
if [[ -e "${STAGE0_RECORD_ROOT}" ]]; then
  echo "ERROR: stage0 record path already exists: ${STAGE0_RECORD_ROOT}" >&2
  exit 1
fi
actual_case_count="$(( $(wc -l <"${MATRIX_FILE}") - 1 ))"
if ((actual_case_count != EXPECTED_CASE_COUNT)); then
  echo "ERROR: expected ${EXPECTED_CASE_COUNT} cases, found ${actual_case_count}." >&2
  exit 2
fi

mkdir -p "${STAGE0_RECORD_ROOT}"
install -m 0440 "${MATRIX_FILE}" "${STAGE0_RECORD_ROOT}/cases.tsv"

tail -n +2 "${MATRIX_FILE}" |
  while IFS=$'\t' read -r \
    case_index run_label matrix_stage initialization_family kernel \
    max_superdroplets collision_timestep_s observation_timestep_s end_time_s \
    model_threads member_index initialization_seed collision_seed controlled_bundle_label; do
    run_directory="${CLEO_SDM_RUN_ROOT}/${run_label}"
    member_analysis="${run_directory}/analysis_stage0_v2"
    if [[ -e "${member_analysis}" ]]; then
      echo "ERROR: stage0 analysis already exists; preserve it and use a new matrix/run root: ${member_analysis}" >&2
      exit 1
    fi
    member_staging="${run_directory}/.analysis_stage0_v2_job${SLURM_JOB_ID}.tmp"
    if [[ -e "${member_staging}" ]]; then
      echo "ERROR: member staging exists: ${member_staging}" >&2
      exit 1
    fi
    "${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_collisions0d.py" \
      --cleo-source "${cleo_source}" \
      --run-directory "${run_directory}" \
      --kernel golovin \
      --output-directory "${member_staging}" \
      --skip-figures \
      --times 0 600 1200 1800 2400 3000 3600
    (
      cd "${member_staging}"
      sha256sum member_time_diagnostics.csv member_summary.csv \
        fixed_bin_distributions.npz diagnostic_metadata.json >SHA256SUMS
      sha256sum -c SHA256SUMS
    )
    mv "${member_staging}" "${member_analysis}"
    echo "STAGE0_MEMBER_COMPLETED=${run_label}"
  done

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/audit_golovin_matrix.py" \
  --matrix-file "${MATRIX_FILE}" \
  --run-root "${CLEO_SDM_RUN_ROOT}" \
  --output "${STAGE0_RECORD_ROOT}/model_inventory.json"
install -m 0440 "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_collisions0d.py" \
  "${STAGE0_RECORD_ROOT}/analyze_collisions0d.py"
git -C "${CLEO_SDM_PROJECT_ROOT}" rev-parse HEAD >"${STAGE0_RECORD_ROOT}/analysis_project_commit.txt"
(
  cd "${STAGE0_RECORD_ROOT}"
  find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  sha256sum -c SHA256SUMS
)
echo "GOLOVIN_STAGE0_MATRIX_ANALYSIS_PASS=1"
echo "stage0_record_root=${STAGE0_RECORD_ROOT}"
