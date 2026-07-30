#!/bin/bash
#SBATCH --job-name=cleo_sdm_init0d
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=00:10:00

# Generate and read back one 4096-SD controlled CLEO native input bundle.
#
# This is an input-format validation only. It does not start a collision
# executable, create model output, or run an ensemble.
#
# Required submission form:
#
#   sbatch --account=<project> \
#     --export=ALL,VALIDATION_LABEL=controlled_init_n4096_v1 \
#     scripts/levante/validate_controlled_initialization.sbatch
#
# SPDX-License-Identifier: BSD-3-Clause

set -eo pipefail
source /etc/profile
set -u

if [[ -n "${CLEO_SDM_PROJECT_ROOT:-}" ]]; then
  SCRIPT_DIR="${CLEO_SDM_PROJECT_ROOT}/scripts/levante"
elif [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
  SCRIPT_DIR="${SLURM_SUBMIT_DIR}/scripts/levante"
else
  SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
fi
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

: "${VALIDATION_LABEL:?Set a unique VALIDATION_LABEL at submission.}"
if [[ ! "${VALIDATION_LABEL}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "ERROR: VALIDATION_LABEL contains unsupported characters." >&2
  exit 2
fi

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
cleo_sdm_print_environment
export OMP_NUM_THREADS=1

validation_root="${CLEO_SDM_RUN_ROOT}/controlled_initialization_validation/${VALIDATION_LABEL}"
case_directory="${validation_root}/case"
runtime_config="${case_directory}/config.yaml"
audit_file="${validation_root}/controlled_initialization_audit.json"
readback_file="${validation_root}/native_readback.json"
manifest_file="${validation_root}/validation_manifest.txt"
python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
cleo_source="${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src"

if [[ -e "${validation_root}" ]]; then
  echo "ERROR: validation path already exists; refusing to overwrite: ${validation_root}" >&2
  exit 1
fi
test -x "${python}"
test -f "${cleo_source}/cleopy/__init__.py"
mkdir -p "${case_directory}"

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/materialize_collisions0d_config.py" \
  --template "${CLEO_SDM_PROJECT_ROOT}/config/collisions0d_reference.yaml" \
  --build-root "${CLEO_SDM_BUILD_ROOT}" \
  --run-directory "${case_directory}" \
  --output "${runtime_config}" \
  --num-threads 1 \
  --max-superdroplets 4096

(
  cd "${case_directory}"
  "${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/prepare_collisions0d_inputs.py" \
    --cleo-source "${cleo_source}" \
    --config "${runtime_config}" \
    --initialization-family controlled \
    --controlled-config "${CLEO_SDM_PROJECT_ROOT}/config/golovin_stage0_development.yaml" \
    --audit-file "${audit_file}"
)

"${python}" \
  "${CLEO_SDM_PROJECT_ROOT}/scripts/validate_controlled_initialization_binary.py" \
  --cleo-source "${cleo_source}" \
  --config "${runtime_config}" \
  --audit-file "${audit_file}" \
  --output "${readback_file}"

if [[ -e "${case_directory}/output/collisions0d_solution.zarr" ]]; then
  echo "ERROR: input-only gate unexpectedly created model output." >&2
  exit 1
fi

{
  echo "status=passed"
  echo "scope=one_4096_superdroplet_native_input_bundle_no_model"
  echo "project_commit=$(git -C "${CLEO_SDM_PROJECT_ROOT}" rev-parse HEAD)"
  echo "cleo_commit=${CLEO_SDM_PINNED_CLEO_COMMIT}"
  echo "initialization_family=controlled"
  echo "initialization_seed=not_applicable"
  echo "number_of_superdroplets=4096"
  echo "slurm_job_id=${SLURM_JOB_ID}"
  echo "slurm_account=${SLURM_JOB_ACCOUNT:-unknown}"
  echo "slurm_partition=${SLURM_JOB_PARTITION:-unknown}"
  echo "slurm_cpus_per_task=${SLURM_CPUS_PER_TASK}"
  sha256sum \
    "${runtime_config}" \
    "${case_directory}/inputs/grid.dat" \
    "${case_directory}/inputs/superdroplets.dat" \
    "${audit_file}" \
    "${readback_file}"
} >"${manifest_file}"

echo "CONTROLLED_INITIALIZATION_NATIVE_GATE_PASS=1"
echo "validation_root=${validation_root}"
echo "audit_file=${audit_file}"
echo "readback_file=${readback_file}"
echo "manifest_file=${manifest_file}"
