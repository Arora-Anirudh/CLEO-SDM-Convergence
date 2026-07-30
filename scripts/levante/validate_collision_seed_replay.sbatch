#!/bin/bash
#SBATCH --job-name=cleo_sdm_seed0d
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=00:10:00

# Validate explicit collision-stream control using one frozen initialization.
#
# Three sequential, one-thread simulations are run:
#   replay_a: initialization seed I, collision seed C
#   replay_b: initialization seed I, collision seed C
#   different: initialization seed I, collision seed D
#
# The gate passes only when replay_a and replay_b have byte-identical Zarr
# stores and the different-seed Zarr store differs.
#
# Required submission form:
#
#   sbatch --account=<project> \
#     --export=ALL,KERNEL=golovin,INITIALIZATION_SEED=12345,REPLAY_COLLISION_SEED=67890,DIFFERENT_COLLISION_SEED=98765,VALIDATION_LABEL=golovin_seed_replay_v1 \
#     scripts/levante/validate_collision_seed_replay.sbatch
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
: "${REPLAY_COLLISION_SEED:?Set REPLAY_COLLISION_SEED at submission.}"
: "${DIFFERENT_COLLISION_SEED:?Set DIFFERENT_COLLISION_SEED at submission.}"
: "${VALIDATION_LABEL:?Set a unique VALIDATION_LABEL at submission.}"

if [[ "${KERNEL}" != "golovin" && "${KERNEL}" != "long" ]]; then
  echo "ERROR: KERNEL must be golovin or long, got ${KERNEL}" >&2
  exit 2
fi
for seed_name in \
  INITIALIZATION_SEED \
  REPLAY_COLLISION_SEED \
  DIFFERENT_COLLISION_SEED
do
  seed_value="${!seed_name}"
  if [[ ! "${seed_value}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: ${seed_name} must be a non-negative integer." >&2
    exit 2
  fi
done
if [[ "${REPLAY_COLLISION_SEED}" == "${DIFFERENT_COLLISION_SEED}" ]]; then
  echo "ERROR: replay and different collision seeds must not be equal." >&2
  exit 2
fi
if [[ ! "${VALIDATION_LABEL}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "ERROR: VALIDATION_LABEL contains unsupported characters." >&2
  exit 2
fi

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
cleo_sdm_print_environment
export OMP_NUM_THREADS=1

validation_root="${CLEO_SDM_RUN_ROOT}/seed_validation/${VALIDATION_LABEL}"
executable="${CLEO_SDM_BUILD_ROOT}/src/collisions0d/collisions0d_${KERNEL}"
python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"

if [[ -e "${validation_root}" ]]; then
  echo "ERROR: validation path already exists; refusing to overwrite: ${validation_root}" >&2
  exit 1
fi
test -x "${executable}"
test -x "${python}"
mkdir -p "${validation_root}"

run_case() {
  local case_name=$1
  local collision_seed=$2
  local case_directory="${validation_root}/${case_name}"
  local runtime_config="${case_directory}/config.yaml"

  mkdir -p "${case_directory}"
  "${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/materialize_collisions0d_config.py" \
    --template "${CLEO_SDM_PROJECT_ROOT}/config/collisions0d_reference.yaml" \
    --build-root "${CLEO_SDM_BUILD_ROOT}" \
    --run-directory "${case_directory}" \
    --output "${runtime_config}" \
    --num-threads 1

  (
    cd "${case_directory}"
    "${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/prepare_collisions0d_inputs.py" \
      --cleo-source "${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src" \
      --config "${runtime_config}" \
      --seed "${INITIALIZATION_SEED}"
  )

  echo "RUN case=${case_name} collision_seed=${collision_seed}"
  srun \
    --mpi=pmix_v3 \
    --ntasks=1 \
    --cpus-per-task=1 \
    "${executable}" \
    "${runtime_config}" \
    "${collision_seed}"

  test -d "${case_directory}/output/collisions0d_solution.zarr"
  (
    cd "${case_directory}/output/collisions0d_solution.zarr"
    find . -type f -print0 |
      LC_ALL=C sort -z |
      xargs -0 sha256sum
  ) >"${case_directory}/zarr_sha256.txt"

  {
    echo "case=${case_name}"
    echo "kernel=${KERNEL}"
    echo "initialization_seed=${INITIALIZATION_SEED}"
    echo "collision_seed=${collision_seed}"
    sha256sum \
      "${runtime_config}" \
      "${case_directory}/inputs/grid.dat" \
      "${case_directory}/inputs/superdroplets.dat" \
      "${executable}"
  } >"${case_directory}/manifest.txt"
}

run_case replay_a "${REPLAY_COLLISION_SEED}"
run_case replay_b "${REPLAY_COLLISION_SEED}"
run_case different_seed "${DIFFERENT_COLLISION_SEED}"

replay_a="${validation_root}/replay_a"
replay_b="${validation_root}/replay_b"
different_seed="${validation_root}/different_seed"

input_hash_a="$(
  sha256sum "${replay_a}/inputs/superdroplets.dat" | awk '{print $1}'
)"
input_hash_b="$(
  sha256sum "${replay_b}/inputs/superdroplets.dat" | awk '{print $1}'
)"
input_hash_different="$(
  sha256sum "${different_seed}/inputs/superdroplets.dat" | awk '{print $1}'
)"
if [[ "${input_hash_a}" != "${input_hash_b}" ||
      "${input_hash_a}" != "${input_hash_different}" ]]; then
  echo "ERROR: the supposedly frozen initializations are not identical." >&2
  exit 1
fi

if ! cmp -s "${replay_a}/zarr_sha256.txt" "${replay_b}/zarr_sha256.txt"; then
  echo "ERROR: equal collision seeds did not produce identical one-thread Zarr stores." >&2
  diff -u "${replay_a}/zarr_sha256.txt" "${replay_b}/zarr_sha256.txt" || true
  exit 1
fi

if cmp -s "${replay_a}/zarr_sha256.txt" "${different_seed}/zarr_sha256.txt"; then
  echo "ERROR: different collision seeds produced identical Zarr stores." >&2
  exit 1
fi

{
  echo "status=passed"
  echo "project_commit=$(git -C "${CLEO_SDM_PROJECT_ROOT}" rev-parse HEAD)"
  echo "cleo_commit=${CLEO_SDM_PINNED_CLEO_COMMIT}"
  echo "kernel=${KERNEL}"
  echo "initialization_seed=${INITIALIZATION_SEED}"
  echo "replay_collision_seed=${REPLAY_COLLISION_SEED}"
  echo "different_collision_seed=${DIFFERENT_COLLISION_SEED}"
  echo "frozen_input_sha256=${input_hash_a}"
  echo "slurm_job_id=${SLURM_JOB_ID}"
  echo "slurm_account=${SLURM_JOB_ACCOUNT:-unknown}"
  echo "slurm_partition=${SLURM_JOB_PARTITION:-unknown}"
  echo "slurm_cpus_per_task=${SLURM_CPUS_PER_TASK}"
} >"${validation_root}/validation_manifest.txt"

echo "COLLISION_SEED_REPLAY_PASS=1"
echo "frozen_initialization_sha256=${input_hash_a}"
echo "validation_root=${validation_root}"
