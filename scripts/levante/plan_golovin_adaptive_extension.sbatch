#!/bin/bash
#SBATCH --job-name=cleo_gol_plan
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=00:20:00
#SBATCH --output=/scratch/b/b383673/SDM/logs/%x_%j.out
#SBATCH --error=/scratch/b/b383673/SDM/logs/%x_%j.err

# Use the completed 100-member Golovin matrix as a variance-and-cost pilot for
# a non-overwriting adaptive-extension plan. This runs no CLEO executable and
# creates no simulation member or Zarr output.
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

: "${MATRIX_FILE:?Set MATRIX_FILE to the reviewed high-resolution cases.tsv.}"
: "${RESOLUTION_CONFIG:?Set RESOLUTION_CONFIG to the reviewed high-resolution YAML.}"
: "${CURRENT_ANALYSIS_ROOT:?Set CURRENT_ANALYSIS_ROOT to checksum-published analysis_v4.}"
: "${PRACTICAL_ANALYSIS_ROOT:?Set PRACTICAL_ANALYSIS_ROOT to checksum-published practical_v2.}"
: "${ADAPTIVE_RECORD_ROOT:?Set ADAPTIVE_RECORD_ROOT to the persistent HOME record root.}"
ADAPTIVE_LABEL="${ADAPTIVE_LABEL:-adaptive_plan_v1}"
if [[ ! "${ADAPTIVE_LABEL}" =~ ^adaptive_plan_v[0-9]+$ ]]; then
  echo "ERROR: ADAPTIVE_LABEL must match adaptive_plan_v<integer>." >&2
  exit 2
fi

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
export OMP_NUM_THREADS=1
umask 027

python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
output_directory="${ADAPTIVE_RECORD_ROOT}/${ADAPTIVE_LABEL}"
staging_directory="${ADAPTIVE_RECORD_ROOT}/.${ADAPTIVE_LABEL}_job${SLURM_JOB_ID}.tmp"
failed_directory="${ADAPTIVE_RECORD_ROOT}/${ADAPTIVE_LABEL}_failed_job${SLURM_JOB_ID}"
for path in "${output_directory}" "${staging_directory}" "${failed_directory}"; do
  if [[ -e "${path}" ]]; then
    echo "ERROR: output/staging/failure path already exists: ${path}" >&2
    exit 1
  fi
done

test -x "${python}"
test -f "${MATRIX_FILE}"
test -f "${RESOLUTION_CONFIG}"
test -f "${CURRENT_ANALYSIS_ROOT}/SHA256SUMS"
test -f "${PRACTICAL_ANALYSIS_ROOT}/SHA256SUMS"
test -f \
  "${CURRENT_ANALYSIS_ROOT}/ensemble_summary/all_member_time_diagnostics.csv"
test -f "${CURRENT_ANALYSIS_ROOT}/model_inventory.json"
test -f \
  "${PRACTICAL_ANALYSIS_ROOT}/products/diminishing_returns_by_prefix.csv"
(
  cd "${CURRENT_ANALYSIS_ROOT}"
  sha256sum -c SHA256SUMS
)
(
  cd "${PRACTICAL_ANALYSIS_ROOT}"
  sha256sum -c SHA256SUMS
)

mkdir -p "${staging_directory}"
analysis_failed() {
  local status=$?
  if ((status != 0)) && [[ -d "${staging_directory}" ]]; then
    mv "${staging_directory}" "${failed_directory}"
    echo "Preserved failed adaptive planning analysis: ${failed_directory}" >&2
  fi
  exit "${status}"
}
trap analysis_failed EXIT

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/plan_golovin_adaptive_extension.py" \
  --combined-member-time \
  "${CURRENT_ANALYSIS_ROOT}/ensemble_summary/all_member_time_diagnostics.csv" \
  --run-root "${CLEO_SDM_RUN_ROOT}" \
  --matrix-file "${MATRIX_FILE}" \
  --config "${RESOLUTION_CONFIG}" \
  --model-inventory "${CURRENT_ANALYSIS_ROOT}/model_inventory.json" \
  --practical-change-table \
  "${PRACTICAL_ANALYSIS_ROOT}/products/diminishing_returns_by_prefix.csv" \
  --output-directory "${staging_directory}/products"

for source in \
  plan_golovin_adaptive_extension.py \
  analyze_golovin_practical_convergence.py \
  analyze_golovin_resolution_convergence.py \
  golovin_stage0.py; do
  install -m 0440 \
    "${CLEO_SDM_PROJECT_ROOT}/scripts/${source}" \
    "${staging_directory}/${source}"
done
install -m 0440 "${MATRIX_FILE}" "${staging_directory}/cases.tsv"
install -m 0440 "${RESOLUTION_CONFIG}" "${staging_directory}/source_config.yaml"
git -C "${CLEO_SDM_PROJECT_ROOT}" rev-parse HEAD \
  >"${staging_directory}/analysis_project_commit.txt"

(
  cd "${staging_directory}"
  find . -type f ! -name SHA256SUMS -print0 \
    | LC_ALL=C sort -z \
    | xargs -0 sha256sum \
    >SHA256SUMS
  sha256sum -c SHA256SUMS
)
mv "${staging_directory}" "${output_directory}"
(
  cd "${output_directory}"
  sha256sum -c SHA256SUMS
)
trap - EXIT

echo "GOLOVIN_ADAPTIVE_EXTENSION_PLAN_PASS=1"
echo "output_directory=${output_directory}"
echo "plan=${output_directory}/products/adaptive_extension_plan.json"
