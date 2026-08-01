#!/bin/bash
#SBATCH --job-name=cleo_gol_extdiag
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --hint=nomultithread
#SBATCH --mem=940M
#SBATCH --time=02:00:00

# Assemble a read-only analysis view and evaluate the targeted high-resolution
# Golovin precision follow-up. This job launches no CLEO model member.
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

: "${BASE_MATRIX_FILE:?Set BASE_MATRIX_FILE to the completed fixed-50 cases.tsv.}"
: "${BASE_RUN_ROOT:?Set BASE_RUN_ROOT to the completed fixed-50 raw run root.}"
: "${BASE_INVENTORY:?Set BASE_INVENTORY to the completed fixed-50 model inventory.}"
: "${EXTENSION_MATRIX_FILE:?Set EXTENSION_MATRIX_FILE to the completed extension cases.tsv.}"
: "${EXTENSION_RUN_ROOT:?Set EXTENSION_RUN_ROOT to the completed extension raw run root.}"
: "${EXTENSION_INVENTORY:?Set EXTENSION_INVENTORY to the completed extension inventory.}"
: "${COMBINED_ANALYSIS_CONFIG:?Set COMBINED_ANALYSIS_CONFIG to the analysis-only YAML.}"
: "${COMBINED_VIEW_ROOT:?Set COMBINED_VIEW_ROOT to a fresh persistent view path.}"
: "${ANALYSIS_RECORD_ROOT:?Set ANALYSIS_RECORD_ROOT to a fresh persistent result path.}"

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
export OMP_NUM_THREADS=1
umask 027

python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
for path in \
  "${BASE_MATRIX_FILE}" "${BASE_INVENTORY}" "${EXTENSION_MATRIX_FILE}" \
  "${EXTENSION_INVENTORY}" "${COMBINED_ANALYSIS_CONFIG}"; do
  test -f "${path}"
done
for path in "${BASE_RUN_ROOT}" "${EXTENSION_RUN_ROOT}"; do
  test -d "${path}"
done
for path in "${COMBINED_VIEW_ROOT}" "${ANALYSIS_RECORD_ROOT}"; do
  if [[ -e "${path}" ]]; then
    echo "ERROR: output path already exists: ${path}" >&2
    exit 1
  fi
done

staging_directory="${ANALYSIS_RECORD_ROOT}.job${SLURM_JOB_ID}.tmp"
if [[ -e "${staging_directory}" ]]; then
  echo "ERROR: analysis staging path already exists: ${staging_directory}" >&2
  exit 1
fi
mkdir -p "${staging_directory}"
analysis_failed() {
  local status=$?
  if ((status != 0)) && [[ -d "${staging_directory}" ]]; then
    mv "${staging_directory}" "${ANALYSIS_RECORD_ROOT}.failed_job${SLURM_JOB_ID}"
    echo "Preserved failed targeted analysis staging tree." >&2
  fi
  exit "${status}"
}
trap analysis_failed EXIT

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/assemble_golovin_analysis_view.py" \
  --base-matrix "${BASE_MATRIX_FILE}" \
  --base-run-root "${BASE_RUN_ROOT}" \
  --base-inventory "${BASE_INVENTORY}" \
  --extension-matrix "${EXTENSION_MATRIX_FILE}" \
  --extension-run-root "${EXTENSION_RUN_ROOT}" \
  --extension-inventory "${EXTENSION_INVENTORY}" \
  --output-directory "${COMBINED_VIEW_ROOT}"

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/summarize_golovin_ensemble.py" \
  --run-root "${COMBINED_VIEW_ROOT}/runs" \
  --output-directory "${staging_directory}/ensemble_summary" \
  --matrix-file "${COMBINED_VIEW_ROOT}/cases.tsv" \
  --confidence-level 0.95 \
  --bootstrap-resamples 10000 \
  --bootstrap-seed 2026080104

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_golovin_resolution_convergence.py" \
  --combined-member-time "${staging_directory}/ensemble_summary/all_member_time_diagnostics.csv" \
  --run-root "${COMBINED_VIEW_ROOT}/runs" \
  --matrix-file "${COMBINED_VIEW_ROOT}/cases.tsv" \
  --config "${COMBINED_ANALYSIS_CONFIG}" \
  --output-directory "${staging_directory}/resolution"

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_golovin_targeted_precision_extension.py" \
  --combined-member-time "${staging_directory}/ensemble_summary/all_member_time_diagnostics.csv" \
  --run-root "${COMBINED_VIEW_ROOT}/runs" \
  --matrix-file "${COMBINED_VIEW_ROOT}/cases.tsv" \
  --config "${COMBINED_ANALYSIS_CONFIG}" \
  --output-directory "${staging_directory}/targeted_practical"

install -m 0440 "${COMBINED_ANALYSIS_CONFIG}" "${staging_directory}/source_config.yaml"
for script in \
  assemble_golovin_analysis_view.py \
  summarize_golovin_ensemble.py \
  analyze_golovin_resolution_convergence.py \
  analyze_golovin_practical_convergence.py \
  analyze_golovin_targeted_precision_extension.py; do
  install -m 0440 "${CLEO_SDM_PROJECT_ROOT}/scripts/${script}" "${staging_directory}/${script}"
done
git -C "${CLEO_SDM_PROJECT_ROOT}" rev-parse HEAD >"${staging_directory}/analysis_project_commit.txt"
(
  cd "${staging_directory}"
  find . -type f ! -name SHA256SUMS -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS
  sha256sum -c SHA256SUMS
)
mv "${staging_directory}" "${ANALYSIS_RECORD_ROOT}"
(
  cd "${ANALYSIS_RECORD_ROOT}"
  sha256sum -c SHA256SUMS
)
trap - EXIT
echo "GOLOVIN_TARGETED_PRECISION_EXTENSION_ANALYSIS_PASS=1"
echo "combined_view_root=${COMBINED_VIEW_ROOT}"
echo "analysis_record_root=${ANALYSIS_RECORD_ROOT}"
echo "decision=${ANALYSIS_RECORD_ROOT}/targeted_practical/targeted_precision_decision.json"
