#!/bin/bash
#SBATCH --job-name=cleo_gol_follow
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=00:10:00

# Produce planning-only sample-size projections and the lower-resolution
# companion figure from checksum-published compact Golovin results.
#
# This job launches no CLEO model and reads no raw Zarr output.
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

: "${EARLIER_ANALYSIS_ROOT:?Set the retained 20-member analysis root.}"
: "${CURRENT_ANALYSIS_ROOT:?Set the canonical 100-member analysis root.}"
: "${FOLLOWUP_RECORD_ROOT:?Set the persistent follow-up record root.}"
FOLLOWUP_LABEL="${FOLLOWUP_LABEL:-followup_v1}"
if [[ ! "${FOLLOWUP_LABEL}" =~ ^followup_v[0-9]+$ ]]; then
  echo "ERROR: FOLLOWUP_LABEL must match followup_v<integer>." >&2
  exit 2
fi

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
export OMP_NUM_THREADS=1
umask 027

python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
output_directory="${FOLLOWUP_RECORD_ROOT}/${FOLLOWUP_LABEL}"
staging_directory="${FOLLOWUP_RECORD_ROOT}/.${FOLLOWUP_LABEL}_job${SLURM_JOB_ID}.tmp"
failed_directory="${FOLLOWUP_RECORD_ROOT}/${FOLLOWUP_LABEL}_failed_job${SLURM_JOB_ID}"
for path in "${output_directory}" "${staging_directory}" "${failed_directory}"; do
  if [[ -e "${path}" ]]; then
    echo "ERROR: output/staging/failure path already exists: ${path}" >&2
    exit 1
  fi
done

for root in "${EARLIER_ANALYSIS_ROOT}" "${CURRENT_ANALYSIS_ROOT}"; do
  test -f "${root}/SHA256SUMS"
  (
    cd "${root}"
    sha256sum -c SHA256SUMS
  )
done

mkdir -p "${staging_directory}"
analysis_failed() {
  local status=$?
  if ((status != 0)) && [[ -d "${staging_directory}" ]]; then
    mv "${staging_directory}" "${failed_directory}"
    echo "Preserved failed follow-up analysis: ${failed_directory}" >&2
  fi
  exit "${status}"
}
trap analysis_failed EXIT

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_golovin_followup.py" \
  --current-adjacent \
  "${CURRENT_ANALYSIS_ROOT}/resolution/adjacent_resolution_equivalence.csv" \
  --earlier-analytical \
  "${EARLIER_ANALYSIS_ROOT}/resolution/analytical_agreement.csv" \
  --current-analytical \
  "${CURRENT_ANALYSIS_ROOT}/resolution/analytical_agreement.csv" \
  --output-directory "${staging_directory}/products"

install -m 0440 \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_golovin_followup.py" \
  "${staging_directory}/analyze_golovin_followup.py"
install -m 0440 \
  "${EARLIER_ANALYSIS_ROOT}/resolution/analytical_agreement.csv" \
  "${staging_directory}/earlier_analytical_agreement.csv"
install -m 0440 \
  "${CURRENT_ANALYSIS_ROOT}/resolution/analytical_agreement.csv" \
  "${staging_directory}/current_analytical_agreement.csv"
install -m 0440 \
  "${CURRENT_ANALYSIS_ROOT}/resolution/adjacent_resolution_equivalence.csv" \
  "${staging_directory}/current_adjacent_resolution_equivalence.csv"

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

echo "GOLOVIN_FOLLOWUP_JOB_PASS=1"
echo "output_directory=${output_directory}"
