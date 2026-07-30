#!/bin/bash
#SBATCH --job-name=cleo_sdm_colls0d
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=00:10:00
#SBATCH --output=/scratch/b/b383673/SDM/logs/%x_%j.out
#SBATCH --error=/scratch/b/b383673/SDM/logs/%x_%j.err

# Generate or reuse one initialization and run one collision-only box.
#
# Required submission form:
#
#   sbatch --account=<project> \
#     --export=ALL,KERNEL=golovin,INITIALIZATION_SEED=12345,COLLISION_SEED=67890,RUN_LABEL=first_golovin \
#     scripts/levante/run_collisions0d.sbatch
#
# KERNEL may be "golovin" or "long".
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

: "${KERNEL:?Set KERNEL to golovin or long at submission.}"
: "${COLLISION_SEED:?Set COLLISION_SEED at submission.}"
: "${RUN_LABEL:?Set a unique RUN_LABEL at submission.}"
MODEL_THREADS="${MODEL_THREADS:-1}"
MAX_SUPERDROPLETS="${MAX_SUPERDROPLETS:-4096}"
COLLISION_TIMESTEP_S="${COLLISION_TIMESTEP_S:-1}"
OBSERVATION_TIMESTEP_S="${OBSERVATION_TIMESTEP_S:-300}"
END_TIME_S="${END_TIME_S:-3600}"
MATRIX_STAGE="${MATRIX_STAGE:-single_run}"
INITIALIZATION_FAMILY="${INITIALIZATION_FAMILY:-operational_stochastic}"
INITIALIZATION_SEED="${INITIALIZATION_SEED:-not_applicable}"
CONTROLLED_BUNDLE="${CONTROLLED_BUNDLE:-}"
MATRIX_CASE_INDEX="${MATRIX_CASE_INDEX:--1}"
MEMBER_INDEX="${MEMBER_INDEX:--1}"

if [[ "${KERNEL}" != "golovin" && "${KERNEL}" != "long" ]]; then
  echo "ERROR: KERNEL must be golovin or long, got ${KERNEL}" >&2
  exit 2
fi
if [[ ! "${COLLISION_SEED}" =~ ^[0-9]+$ ]]; then
  echo "ERROR: COLLISION_SEED must be an integer in [0, 2^64 - 1]." >&2
  exit 2
fi
if [[ "${INITIALIZATION_FAMILY}" == "operational_stochastic" ]]; then
  if [[ ! "${INITIALIZATION_SEED}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: operational_stochastic requires a non-negative INITIALIZATION_SEED." >&2
    exit 2
  fi
  if [[ -n "${CONTROLLED_BUNDLE}" ]]; then
    echo "ERROR: CONTROLLED_BUNDLE is valid only for controlled initialization." >&2
    exit 2
  fi
elif [[ "${INITIALIZATION_FAMILY}" == "controlled" ]]; then
  if [[ "${KERNEL}" != "golovin" ]]; then
    echo "ERROR: the current controlled bundle contract is Golovin-only." >&2
    exit 2
  fi
  if [[ "${INITIALIZATION_SEED}" != "not_applicable" ]]; then
    echo "ERROR: controlled initialization does not accept INITIALIZATION_SEED." >&2
    exit 2
  fi
  if [[ -z "${CONTROLLED_BUNDLE}" ]]; then
    echo "ERROR: controlled initialization requires CONTROLLED_BUNDLE." >&2
    exit 2
  fi
else
  echo "ERROR: unsupported INITIALIZATION_FAMILY=${INITIALIZATION_FAMILY}." >&2
  exit 2
fi
if [[ ! "${RUN_LABEL}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "ERROR: RUN_LABEL contains unsupported characters: ${RUN_LABEL}" >&2
  exit 2
fi
if [[ ! "${MODEL_THREADS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: MODEL_THREADS must be a positive integer." >&2
  exit 2
fi
if [[ ! "${MAX_SUPERDROPLETS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: MAX_SUPERDROPLETS must be a positive integer." >&2
  exit 2
fi
for positive_value in \
  "${COLLISION_TIMESTEP_S}" \
  "${OBSERVATION_TIMESTEP_S}" \
  "${END_TIME_S}"; do
  if ! awk -v value="${positive_value}" 'BEGIN { exit !(value + 0 > 0) }'; then
    echo "ERROR: all timestep values must be positive numbers." >&2
    exit 2
  fi
done
if ! awk \
  -v end_time="${END_TIME_S}" \
  -v observation_step="${OBSERVATION_TIMESTEP_S}" \
  'BEGIN { exit !(end_time + 0 >= observation_step + 0) }'; then
  echo "ERROR: END_TIME_S must be at least OBSERVATION_TIMESTEP_S." >&2
  exit 2
fi
if ((MODEL_THREADS > SLURM_CPUS_PER_TASK)); then
  echo "ERROR: MODEL_THREADS=${MODEL_THREADS} exceeds allocated task CPUs." >&2
  exit 2
fi

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
cleo_sdm_print_environment
export OMP_NUM_THREADS="${MODEL_THREADS}"
echo "model_threads=${MODEL_THREADS}"
echo "max_superdroplets=${MAX_SUPERDROPLETS}"
echo "collision_timestep_s=${COLLISION_TIMESTEP_S}"
echo "observation_timestep_s=${OBSERVATION_TIMESTEP_S}"
echo "end_time_s=${END_TIME_S}"

project_commit="$(git -C "${CLEO_SDM_PROJECT_ROOT}" rev-parse HEAD)"
tracked_status="$(
  git -C "${CLEO_SDM_PROJECT_ROOT}" status --porcelain --untracked-files=no
)"
if [[ -n "${tracked_status}" ]]; then
  echo "ERROR: tracked project files are dirty; commit or restore them before a run:" >&2
  echo "${tracked_status}" >&2
  exit 1
fi
run_directory="${CLEO_SDM_RUN_ROOT}/${RUN_LABEL}"
runtime_config="${run_directory}/config.yaml"
executable="${CLEO_SDM_BUILD_ROOT}/src/collisions0d/collisions0d_${KERNEL}"

if [[ -e "${run_directory}" ]]; then
  echo "ERROR: run directory already exists; refusing to overwrite: ${run_directory}" >&2
  exit 1
fi
test -x "${executable}"
test -f "${CLEO_SDM_BUILD_ROOT}/build_manifest.txt"
if ! grep -Fqx \
  "project_commit=${project_commit}" \
  "${CLEO_SDM_BUILD_ROOT}/build_manifest.txt"; then
  echo "ERROR: build manifest does not match project commit ${project_commit}." >&2
  echo "Rebuild this exact commit before running a member." >&2
  exit 1
fi

mkdir -p "${run_directory}"
run_started_epoch="$(date +%s)"
inprogress_manifest="${run_directory}/manifest.inprogress.txt"
{
  echo "status=running"
  echo "run_started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "run_label=${RUN_LABEL}"
  echo "matrix_stage=${MATRIX_STAGE}"
  echo "matrix_case_index=${MATRIX_CASE_INDEX}"
  echo "member_index=${MEMBER_INDEX}"
  echo "initialization_family=${INITIALIZATION_FAMILY}"
  echo "kernel=${KERNEL}"
  echo "initialization_seed=${INITIALIZATION_SEED}"
  echo "collision_seed=${COLLISION_SEED}"
} >"${inprogress_manifest}"

preserve_failed_manifest() {
  local status=$?
  if ((status != 0)) && [[ -f "${inprogress_manifest}" ]]; then
    {
      echo "status=failed"
      tail -n +2 "${inprogress_manifest}"
      echo "exit_code=${status}"
      echo "failed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } >"${inprogress_manifest}.tmp"
    mv "${inprogress_manifest}.tmp" "${inprogress_manifest}"
  fi
  exit "${status}"
}
trap preserve_failed_manifest EXIT

python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
test -x "${python}"

bundle_manifest_sha256="none"
bundle_grid_sha256="none"
bundle_superdroplet_sha256="none"
if [[ "${INITIALIZATION_FAMILY}" == "controlled" ]]; then
  CONTROLLED_BUNDLE="$(cd "${CONTROLLED_BUNDLE}" && pwd)"
  "${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/controlled_bundle.py" verify \
    --bundle-directory "${CONTROLLED_BUNDLE}" \
    --expected-superdroplets "${MAX_SUPERDROPLETS}" \
    --expected-cleo-commit "${CLEO_SDM_PINNED_CLEO_COMMIT}" \
    --reference-config "${CLEO_SDM_PROJECT_ROOT}/config/collisions0d_reference.yaml" \
    --controlled-config "${CLEO_SDM_PROJECT_ROOT}/config/golovin_stage0_development.yaml"
  bundle_manifest_sha256="$(
    sha256sum "${CONTROLLED_BUNDLE}/bundle_manifest.json" | awk '{print $1}'
  )"
  bundle_grid_sha256="$(
    sha256sum "${CONTROLLED_BUNDLE}/inputs/grid.dat" | awk '{print $1}'
  )"
  bundle_superdroplet_sha256="$(
    sha256sum "${CONTROLLED_BUNDLE}/inputs/superdroplets.dat" | awk '{print $1}'
  )"
fi

echo "--- materialize absolute-path runtime configuration ---"
materialize_arguments=(
  --template "${CLEO_SDM_PROJECT_ROOT}/config/collisions0d_reference.yaml"
  --build-root "${CLEO_SDM_BUILD_ROOT}"
  --run-directory "${run_directory}"
  --output "${runtime_config}"
  --num-threads "${MODEL_THREADS}"
  --max-superdroplets "${MAX_SUPERDROPLETS}"
  --collision-timestep-s "${COLLISION_TIMESTEP_S}"
  --observation-timestep-s "${OBSERVATION_TIMESTEP_S}"
  --end-time-s "${END_TIME_S}"
)
if [[ "${INITIALIZATION_FAMILY}" == "controlled" ]]; then
  materialize_arguments+=(
    --grid-file "${CONTROLLED_BUNDLE}/inputs/grid.dat"
    --superdroplet-file "${CONTROLLED_BUNDLE}/inputs/superdroplets.dat"
  )
fi
"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/materialize_collisions0d_config.py" \
  "${materialize_arguments[@]}"

if [[ "${INITIALIZATION_FAMILY}" == "operational_stochastic" ]]; then
  echo "--- generate the operational stochastic grid and superdroplets ---"
  cd "${run_directory}"
  "${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/prepare_collisions0d_inputs.py" \
    --cleo-source "${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src" \
    --config "${runtime_config}" \
    --seed "${INITIALIZATION_SEED}"
else
  echo "--- reuse verified controlled initialization bundle ---"
  echo "controlled_bundle=${CONTROLLED_BUNDLE}"
  echo "bundle_manifest_sha256=${bundle_manifest_sha256}"
  echo "bundle_grid_sha256=${bundle_grid_sha256}"
  echo "bundle_superdroplet_sha256=${bundle_superdroplet_sha256}"
fi

echo "--- run CLEO collisions0d (${KERNEL}) ---"
cd "${run_directory}"
# Keep the one-rank step CPU-exclusive without reserving the full job-memory
# allocation for every concurrent member step.
srun \
  --exclusive \
  --mem=0 \
  --mpi=pmix_v3 \
  --ntasks=1 \
  --cpus-per-task="${MODEL_THREADS}" \
  --hint=nomultithread \
  "${executable}" \
  "${runtime_config}" \
  "${COLLISION_SEED}"

if [[ "${INITIALIZATION_FAMILY}" == "controlled" ]]; then
  "${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/controlled_bundle.py" verify \
    --bundle-directory "${CONTROLLED_BUNDLE}" \
    --expected-superdroplets "${MAX_SUPERDROPLETS}" \
    --expected-cleo-commit "${CLEO_SDM_PINNED_CLEO_COMMIT}" \
    --reference-config "${CLEO_SDM_PROJECT_ROOT}/config/collisions0d_reference.yaml" \
    --controlled-config "${CLEO_SDM_PROJECT_ROOT}/config/golovin_stage0_development.yaml"
fi

zarr_output="${run_directory}/output/collisions0d_solution.zarr"
setup_output="${run_directory}/output/collisions0d_setup.txt"
test -d "${zarr_output}"
test -f "${setup_output}"

sha256_directory() {
  local directory="$1"
  (
    cd "${directory}"
    find . -type f -print0 \
      | LC_ALL=C sort -z \
      | xargs -0 sha256sum \
      | sha256sum \
      | awk '{print $1}'
  )
}

run_finished_epoch="$(date +%s)"
zarr_sha256="$(sha256_directory "${zarr_output}")"
module_list="$(module -t list 2>&1 | paste -sd, -)"
{
  echo "status=completed"
  echo "run_started_epoch=${run_started_epoch}"
  echo "run_finished_epoch=${run_finished_epoch}"
  echo "job_wall_seconds=$((run_finished_epoch - run_started_epoch))"
  echo "project_commit=${project_commit}"
  echo "cleo_commit=${CLEO_SDM_PINNED_CLEO_COMMIT}"
  echo "kernel=${KERNEL}"
  echo "initialization_seed=${INITIALIZATION_SEED}"
  echo "collision_seed=${COLLISION_SEED}"
  echo "run_label=${RUN_LABEL}"
  echo "matrix_stage=${MATRIX_STAGE}"
  echo "matrix_case_index=${MATRIX_CASE_INDEX}"
  echo "member_index=${MEMBER_INDEX}"
  echo "initialization_family=${INITIALIZATION_FAMILY}"
  echo "controlled_bundle=${CONTROLLED_BUNDLE:-none}"
  echo "bundle_manifest_sha256=${bundle_manifest_sha256}"
  echo "bundle_grid_sha256=${bundle_grid_sha256}"
  echo "bundle_superdroplet_sha256=${bundle_superdroplet_sha256}"
  echo "matrix_file=${MATRIX_FILE:-none}"
  echo "matrix_sha256=${MATRIX_SHA256:-none}"
  echo "slurm_job_id=${SLURM_JOB_ID}"
  echo "slurm_account=${SLURM_JOB_ACCOUNT:-unknown}"
  echo "slurm_partition=${SLURM_JOB_PARTITION:-unknown}"
  echo "slurm_nodes=${SLURM_JOB_NUM_NODES:-unknown}"
  echo "slurm_ntasks=${SLURM_NTASKS:-unknown}"
  echo "slurm_cpus_per_task=${SLURM_CPUS_PER_TASK}"
  echo "slurm_mem_per_node=${SLURM_MEM_PER_NODE:-unknown}"
  echo "slurm_time_limit=${SLURM_TIMELIMIT:-unknown}"
  echo "model_threads=${MODEL_THREADS}"
  echo "max_superdroplets=${MAX_SUPERDROPLETS}"
  echo "collision_timestep_s=${COLLISION_TIMESTEP_S}"
  echo "observation_timestep_s=${OBSERVATION_TIMESTEP_S}"
  echo "end_time_s=${END_TIME_S}"
  echo "module_list=${module_list}"
  echo "runtime_config=${runtime_config}"
  echo "zarr_output=${zarr_output}"
  echo "zarr_tree_sha256=${zarr_sha256}"
  sha256sum \
    "${runtime_config}" \
    "${setup_output}" \
    "${executable}" \
    "${CLEO_SDM_BUILD_ROOT}/build_manifest.txt"
  if [[ "${INITIALIZATION_FAMILY}" == "operational_stochastic" ]]; then
    sha256sum \
      "${run_directory}/inputs/grid.dat" \
      "${run_directory}/inputs/superdroplets.dat"
  else
    sha256sum \
      "${CONTROLLED_BUNDLE}/bundle_manifest.json" \
      "${CONTROLLED_BUNDLE}/inputs/grid.dat" \
      "${CONTROLLED_BUNDLE}/inputs/superdroplets.dat"
  fi
} >"${run_directory}/manifest.txt"
rm "${inprogress_manifest}"
trap - EXIT

echo "RUN_PASS=1"
echo "run_directory=${run_directory}"
echo "runtime_config=${runtime_config}"
echo "zarr_output=${zarr_output}"
echo "setup_output=${setup_output}"
