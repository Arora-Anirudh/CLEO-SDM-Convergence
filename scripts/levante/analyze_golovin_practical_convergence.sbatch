#!/bin/bash
#SBATCH --job-name=cleo_gol_practical
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=00:20:00

# Apply the non-overwriting practical diminishing-returns analysis to the
# existing controlled Golovin members. This launches no CLEO model and creates
# no new ensemble member.
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
: "${PRACTICAL_RECORD_ROOT:?Set PRACTICAL_RECORD_ROOT to the persistent HOME record root.}"
PRACTICAL_LABEL="${PRACTICAL_LABEL:-practical_v1}"
if [[ ! "${PRACTICAL_LABEL}" =~ ^practical_v[0-9]+$ ]]; then
  echo "ERROR: PRACTICAL_LABEL must match practical_v<integer>." >&2
  exit 2
fi

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
export OMP_NUM_THREADS=1
umask 027

python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
output_directory="${PRACTICAL_RECORD_ROOT}/${PRACTICAL_LABEL}"
staging_directory="${PRACTICAL_RECORD_ROOT}/.${PRACTICAL_LABEL}_job${SLURM_JOB_ID}.tmp"
failed_directory="${PRACTICAL_RECORD_ROOT}/${PRACTICAL_LABEL}_failed_job${SLURM_JOB_ID}"
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
test -f \
  "${CURRENT_ANALYSIS_ROOT}/ensemble_summary/all_member_time_diagnostics.csv"
(
  cd "${CURRENT_ANALYSIS_ROOT}"
  sha256sum -c SHA256SUMS
)

mkdir -p "${staging_directory}"
analysis_failed() {
  local status=$?
  if ((status != 0)) && [[ -d "${staging_directory}" ]]; then
    mv "${staging_directory}" "${failed_directory}"
    echo "Preserved failed practical analysis: ${failed_directory}" >&2
  fi
  exit "${status}"
}
trap analysis_failed EXIT

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_golovin_practical_convergence.py" \
  --combined-member-time \
  "${CURRENT_ANALYSIS_ROOT}/ensemble_summary/all_member_time_diagnostics.csv" \
  --run-root "${CLEO_SDM_RUN_ROOT}" \
  --matrix-file "${MATRIX_FILE}" \
  --config "${RESOLUTION_CONFIG}" \
  --output-directory "${staging_directory}/products"

install -m 0440 \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_golovin_practical_convergence.py" \
  "${staging_directory}/analyze_golovin_practical_convergence.py"
install -m 0440 \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_golovin_resolution_convergence.py" \
  "${staging_directory}/analyze_golovin_resolution_convergence.py"
install -m 0440 \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/golovin_stage0.py" \
  "${staging_directory}/golovin_stage0.py"
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

echo "GOLOVIN_PRACTICAL_ANALYSIS_JOB_PASS=1"
echo "output_directory=${output_directory}"
echo "decision=${output_directory}/products/practical_convergence_decision.json"
