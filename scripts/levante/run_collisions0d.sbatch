#!/bin/bash
#SBATCH --job-name=cleo_sdm_colls0d
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=/scratch/b/b383673/SDM/logs/%x_%j.out
#SBATCH --error=/scratch/b/b383673/SDM/logs/%x_%j.err

# Generate one initialization and run one collision-only box.
#
# Required submission form:
#
#   sbatch --account=<project> \
#     --export=ALL,KERNEL=golovin,INITIALIZATION_SEED=12345,RUN_LABEL=first_golovin \
#     scripts/levante/run_collisions0d.sbatch
#
# KERNEL may be "golovin" or "long".
#
# SPDX-License-Identifier: BSD-3-Clause

set -eo pipefail
source /etc/profile
set -u

if [[ -n "${SLURM_SUBMIT_DIR:-}" ]]; then
  SCRIPT_DIR="${SLURM_SUBMIT_DIR}/scripts/levante"
else
  SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
fi
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

: "${KERNEL:?Set KERNEL to golovin or long at submission.}"
: "${INITIALIZATION_SEED:?Set INITIALIZATION_SEED at submission.}"
: "${RUN_LABEL:?Set a unique RUN_LABEL at submission.}"

if [[ "${KERNEL}" != "golovin" && "${KERNEL}" != "long" ]]; then
  echo "ERROR: KERNEL must be golovin or long, got ${KERNEL}" >&2
  exit 2
fi
if [[ ! "${INITIALIZATION_SEED}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: INITIALIZATION_SEED must be a non-negative integer." >&2
  exit 2
fi
if [[ ! "${RUN_LABEL}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "ERROR: RUN_LABEL contains unsupported characters: ${RUN_LABEL}" >&2
  exit 2
fi

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
cleo_sdm_print_environment

project_commit="$(git -C "${CLEO_SDM_PROJECT_ROOT}" rev-parse HEAD)"
run_directory="${CLEO_SDM_RUN_ROOT}/${RUN_LABEL}"
runtime_config="${run_directory}/config.yaml"
executable="${CLEO_SDM_BUILD_ROOT}/src/collisions0d/collisions0d_${KERNEL}"

if [[ -e "${run_directory}" ]]; then
  echo "ERROR: run directory already exists; refusing to overwrite: ${run_directory}" >&2
  exit 1
fi
test -x "${executable}"
test -f "${CLEO_SDM_BUILD_ROOT}/build_manifest.txt"

mkdir -p "${run_directory}"

python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
test -x "${python}"

echo "--- materialize absolute-path runtime configuration ---"
"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/materialize_collisions0d_config.py" \
  --template "${CLEO_SDM_PROJECT_ROOT}/config/collisions0d_reference.yaml" \
  --build-root "${CLEO_SDM_BUILD_ROOT}" \
  --run-directory "${run_directory}" \
  --output "${runtime_config}" \
  --num-threads "${SLURM_CPUS_PER_TASK}"

echo "--- generate the initial grid and superdroplets ---"
cd "${run_directory}"
"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/prepare_collisions0d_inputs.py" \
  --cleo-source "${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src" \
  --config "${runtime_config}" \
  --seed "${INITIALIZATION_SEED}"

echo "--- run CLEO collisions0d (${KERNEL}) ---"
srun \
  --mpi=pmix_v3 \
  --ntasks=1 \
  --cpus-per-task="${SLURM_CPUS_PER_TASK}" \
  "${executable}" \
  "${runtime_config}"

zarr_output="${run_directory}/output/collisions0d_solution.zarr"
setup_output="${run_directory}/output/collisions0d_setup.txt"
test -d "${zarr_output}"
test -f "${setup_output}"

{
  echo "status=completed"
  echo "project_commit=${project_commit}"
  echo "cleo_commit=${CLEO_SDM_PINNED_CLEO_COMMIT}"
  echo "kernel=${KERNEL}"
  echo "initialization_seed=${INITIALIZATION_SEED}"
  echo "run_label=${RUN_LABEL}"
  echo "slurm_job_id=${SLURM_JOB_ID}"
  echo "slurm_account=${SLURM_JOB_ACCOUNT:-unknown}"
  echo "slurm_partition=${SLURM_JOB_PARTITION:-unknown}"
  echo "slurm_cpus_per_task=${SLURM_CPUS_PER_TASK}"
  echo "runtime_config=${runtime_config}"
  echo "zarr_output=${zarr_output}"
  sha256sum \
    "${runtime_config}" \
    "${run_directory}/inputs/grid.dat" \
    "${run_directory}/inputs/superdroplets.dat" \
    "${executable}"
} >"${run_directory}/manifest.txt"

echo "RUN_PASS=1"
echo "run_directory=${run_directory}"
echo "runtime_config=${runtime_config}"
echo "zarr_output=${zarr_output}"
echo "setup_output=${setup_output}"
