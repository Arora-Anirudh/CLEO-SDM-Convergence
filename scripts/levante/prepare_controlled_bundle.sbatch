#!/bin/bash
#SBATCH --job-name=cleo_sdm_bundle0d
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=00:10:00

# Create one non-overwriting, read-only CLEO-native controlled bundle.
#
# Required submission form:
#
#   sbatch --account=<project> \
#     --export=ALL,MAX_SUPERDROPLETS=4096,BUNDLE_LABEL=golovin_controlled_N004096_v1 \
#     scripts/levante/prepare_controlled_bundle.sbatch
#
# This job writes and reads inputs only. It runs no collision executable.
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

: "${MAX_SUPERDROPLETS:?Set MAX_SUPERDROPLETS at submission.}"
: "${BUNDLE_LABEL:?Set a unique BUNDLE_LABEL at submission.}"
if [[ ! "${MAX_SUPERDROPLETS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: MAX_SUPERDROPLETS must be a positive integer." >&2
  exit 2
fi
if [[ ! "${BUNDLE_LABEL}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "ERROR: BUNDLE_LABEL contains unsupported characters." >&2
  exit 2
fi

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
cleo_sdm_print_environment
export OMP_NUM_THREADS=1
umask 027

project_commit="$(git -C "${CLEO_SDM_PROJECT_ROOT}" rev-parse HEAD)"
tracked_status="$(
  git -C "${CLEO_SDM_PROJECT_ROOT}" status --porcelain --untracked-files=no
)"
if [[ -n "${tracked_status}" ]]; then
  echo "ERROR: tracked project files are dirty; commit or restore them first." >&2
  echo "${tracked_status}" >&2
  exit 1
fi
cleo_source="${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src"
actual_cleo_commit="$(git -C "${cleo_source}" rev-parse HEAD)"
if [[ "${actual_cleo_commit}" != "${CLEO_SDM_PINNED_CLEO_COMMIT}" ]]; then
  echo "ERROR: build-local CLEO source does not match the project pin." >&2
  exit 1
fi

bundle_directory="${CLEO_SDM_BUNDLE_ROOT}/${BUNDLE_LABEL}"
runtime_config="${bundle_directory}/config.yaml"
audit_file="${bundle_directory}/controlled_initialization_audit.json"
readback_file="${bundle_directory}/native_readback.json"
python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"

if [[ -e "${bundle_directory}" ]]; then
  echo "ERROR: bundle path already exists; refusing to overwrite: ${bundle_directory}" >&2
  exit 1
fi
test -x "${python}"
mkdir -p "${bundle_directory}/provenance"

bundle_failed() {
  local status=$?
  if ((status != 0)) && [[ -d "${bundle_directory}" ]]; then
    {
      echo "status=failed"
      echo "exit_code=${status}"
      echo "failed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "slurm_job_id=${SLURM_JOB_ID}"
    } >"${bundle_directory}/bundle_failed.txt"
  fi
  exit "${status}"
}
trap bundle_failed EXIT

install -m 0640 \
  "${CLEO_SDM_PROJECT_ROOT}/config/collisions0d_reference.yaml" \
  "${bundle_directory}/source_reference_config.yaml"
install -m 0640 \
  "${CLEO_SDM_PROJECT_ROOT}/config/golovin_stage0_development.yaml" \
  "${bundle_directory}/source_controlled_config.yaml"
install -m 0640 \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/controlled_initialization.py" \
  "${bundle_directory}/provenance/controlled_initialization.py"
install -m 0640 \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/prepare_collisions0d_inputs.py" \
  "${bundle_directory}/provenance/prepare_collisions0d_inputs.py"
install -m 0640 \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/validate_controlled_initialization_binary.py" \
  "${bundle_directory}/provenance/validate_controlled_initialization_binary.py"

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/materialize_collisions0d_config.py" \
  --template "${bundle_directory}/source_reference_config.yaml" \
  --build-root "${CLEO_SDM_BUILD_ROOT}" \
  --run-directory "${bundle_directory}" \
  --output "${runtime_config}" \
  --num-threads 1 \
  --max-superdroplets "${MAX_SUPERDROPLETS}"

(
  cd "${bundle_directory}"
  "${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/prepare_collisions0d_inputs.py" \
    --cleo-source "${cleo_source}" \
    --config "${runtime_config}" \
    --initialization-family controlled \
    --controlled-config "${bundle_directory}/source_controlled_config.yaml" \
    --audit-file "${audit_file}"
)

"${python}" \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/validate_controlled_initialization_binary.py" \
  --cleo-source "${cleo_source}" \
  --config "${runtime_config}" \
  --audit-file "${audit_file}" \
  --output "${readback_file}"

if [[ -e "${bundle_directory}/output/collisions0d_solution.zarr" ]]; then
  echo "ERROR: bundle preparation unexpectedly created model output." >&2
  exit 1
fi

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/controlled_bundle.py" finalize \
  --bundle-directory "${bundle_directory}" \
  --project-commit "${project_commit}" \
  --cleo-commit "${actual_cleo_commit}" \
  --expected-superdroplets "${MAX_SUPERDROPLETS}"

trap - EXIT
echo "CONTROLLED_BUNDLE_PREPARATION_PASS=1"
echo "bundle_directory=${bundle_directory}"
echo "bundle_manifest=${bundle_directory}/bundle_manifest.json"
