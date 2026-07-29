#!/bin/bash
#SBATCH --job-name=cleo_gol_resdiag
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=00:45:00
#SBATCH --output=/scratch/b/b383673/SDM/logs/%x_%j.out
#SBATCH --error=/scratch/b/b383673/SDM/logs/%x_%j.err

# Analyze all members of the controlled Golovin resolution experiment and
# apply the registered analytical-agreement, precision, adjacent-equivalence,
# conservation, range-coverage and N/2N/4N confirmation gates.
#
# This is analysis only. It never launches the CLEO model.
#
# SPDX-License-Identifier: BSD-3-Clause

set -eo pipefail
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

: "${MATRIX_FILE:?Set MATRIX_FILE to the reviewed resolution cases.tsv.}"
: "${RESOLUTION_CONFIG:?Set RESOLUTION_CONFIG to the reviewed resolution YAML.}"
: "${RESOLUTION_RECORD_ROOT:?Set RESOLUTION_RECORD_ROOT to the persistent HOME record path.}"
EXPECTED_CASE_COUNT="${EXPECTED_CASE_COUNT:-120}"

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
cleo_sdm_print_environment
export OMP_NUM_THREADS=1
umask 027

python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
cleo_source="${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src"
test -x "${python}"
test -d "${cleo_source}"
test -f "${MATRIX_FILE}"
test -f "${RESOLUTION_CONFIG}"

actual_case_count="$(( $(wc -l <"${MATRIX_FILE}") - 1 ))"
if ((actual_case_count != EXPECTED_CASE_COUNT)); then
  echo "ERROR: expected ${EXPECTED_CASE_COUNT} cases, found ${actual_case_count}." >&2
  exit 2
fi

analysis_directory="${RESOLUTION_RECORD_ROOT}/analysis_v1"
staging_directory="${RESOLUTION_RECORD_ROOT}/.analysis_v1_job${SLURM_JOB_ID}.tmp"
failed_directory="${RESOLUTION_RECORD_ROOT}/analysis_failed_job${SLURM_JOB_ID}"
if [[ -e "${analysis_directory}" || -e "${staging_directory}" || -e "${failed_directory}" ]]; then
  echo "ERROR: analysis output/staging path already exists." >&2
  exit 1
fi
mkdir -p "${staging_directory}"

analysis_failed() {
  local status=$?
  if ((status != 0)) && [[ -d "${staging_directory}" ]]; then
    mv "${staging_directory}" "${failed_directory}"
    echo "Preserved failed resolution analysis: ${failed_directory}" >&2
  fi
  exit "${status}"
}
trap analysis_failed EXIT

tail -n +2 "${MATRIX_FILE}" |
  while IFS=$'\t' read -r \
    case_index \
    run_label \
    matrix_stage \
    initialization_family \
    kernel \
    max_superdroplets \
    collision_timestep_s \
    observation_timestep_s \
    end_time_s \
    model_threads \
    member_index \
    initialization_seed \
    collision_seed \
    controlled_bundle_label; do
    run_directory="${CLEO_SDM_RUN_ROOT}/${run_label}"
    member_analysis="${run_directory}/analysis_stage0_v2"
    if [[ -e "${member_analysis}" ]]; then
      if [[ -f "${member_analysis}/diagnostic_metadata.json" ]] \
        && grep -Fq '"status": "completed"' \
          "${member_analysis}/diagnostic_metadata.json"; then
        echo "MEMBER_ANALYSIS_ALREADY_COMPLETED=${run_label}"
        continue
      fi
      echo "ERROR: existing member analysis is incomplete: ${member_analysis}" >&2
      exit 1
    fi

    member_staging="${run_directory}/.analysis_stage0_v2_job${SLURM_JOB_ID}.tmp"
    if [[ -e "${member_staging}" ]]; then
      echo "ERROR: member staging path already exists: ${member_staging}" >&2
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
      sha256sum \
        member_time_diagnostics.csv \
        member_summary.csv \
        fixed_bin_distributions.npz \
        diagnostic_metadata.json \
        >SHA256SUMS
      sha256sum -c SHA256SUMS
    )
    mv "${member_staging}" "${member_analysis}"
    echo "MEMBER_ANALYSIS_COMPLETED=${run_label}"
  done

summary_directory="${staging_directory}/ensemble_summary"
"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/audit_golovin_matrix.py" \
  --matrix-file "${MATRIX_FILE}" \
  --run-root "${CLEO_SDM_RUN_ROOT}" \
  --output "${staging_directory}/model_inventory.json"

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/summarize_golovin_ensemble.py" \
  --run-root "${CLEO_SDM_RUN_ROOT}" \
  --output-directory "${summary_directory}" \
  --matrix-file "${MATRIX_FILE}" \
  --confidence-level 0.95 \
  --bootstrap-resamples 10000 \
  --bootstrap-seed 20260729

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_golovin_resolution_convergence.py" \
  --combined-member-time "${summary_directory}/all_member_time_diagnostics.csv" \
  --run-root "${CLEO_SDM_RUN_ROOT}" \
  --matrix-file "${MATRIX_FILE}" \
  --config "${RESOLUTION_CONFIG}" \
  --output-directory "${staging_directory}/resolution"

install -m 0440 "${MATRIX_FILE}" "${staging_directory}/cases.tsv"
install -m 0440 "${RESOLUTION_CONFIG}" "${staging_directory}/source_config.yaml"
install -m 0440 \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/analyze_golovin_resolution_convergence.py" \
  "${staging_directory}/analyze_golovin_resolution_convergence.py"
install -m 0440 \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/golovin_stage0.py" \
  "${staging_directory}/golovin_stage0.py"
install -m 0440 \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/audit_golovin_matrix.py" \
  "${staging_directory}/audit_golovin_matrix.py"
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

mv "${staging_directory}" "${analysis_directory}"
(
  cd "${analysis_directory}"
  sha256sum -c SHA256SUMS
)
trap - EXIT

echo "GOLOVIN_RESOLUTION_DIAGNOSTIC_PASS=1"
echo "analysis_directory=${analysis_directory}"
echo "decision=${analysis_directory}/resolution/resolution_decision.json"
