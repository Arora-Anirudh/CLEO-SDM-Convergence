#!/bin/bash
#SBATCH --job-name=cleo_sdm_bundlereplay
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=00:10:00

# Independently regenerate one controlled bundle on the same Levante stack and
# require exact native grid/superdroplet byte identity with the canonical
# persistent bundle. This script runs no collision executable.
#
# Required submission form:
#
#   sbatch --account=<project> \
#     --export=ALL,MAX_SUPERDROPLETS=4096,REPLAY_LABEL=golovin_controlled_N004096_replay_v1,CANONICAL_BUNDLE=/path/to/canonical \
#     scripts/levante/validate_controlled_bundle_replay.sbatch
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
: "${REPLAY_LABEL:?Set a unique REPLAY_LABEL at submission.}"
: "${CANONICAL_BUNDLE:?Set CANONICAL_BUNDLE at submission.}"
if [[ ! "${MAX_SUPERDROPLETS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: MAX_SUPERDROPLETS must be a positive integer." >&2
  exit 2
fi
if [[ ! "${REPLAY_LABEL}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  echo "ERROR: REPLAY_LABEL contains unsupported characters." >&2
  exit 2
fi

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
cleo_sdm_print_environment
export OMP_NUM_THREADS=1
umask 027

python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
test -x "${python}"
CANONICAL_BUNDLE="$(cd "${CANONICAL_BUNDLE}" && pwd)"
"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/controlled_bundle.py" verify \
  --bundle-directory "${CANONICAL_BUNDLE}" \
  --expected-superdroplets "${MAX_SUPERDROPLETS}" \
  --expected-cleo-commit "${CLEO_SDM_PINNED_CLEO_COMMIT}" \
  --reference-config "${CLEO_SDM_PROJECT_ROOT}/config/collisions0d_reference.yaml" \
  --controlled-config "${CLEO_SDM_PROJECT_ROOT}/config/golovin_stage0_development.yaml"

replay_root="${CLEO_SDM_RUN_ROOT}/controlled_bundle_replay/${REPLAY_LABEL}"
replay_bundle_root="${replay_root}/bundles"
replay_bundle="${replay_bundle_root}/${REPLAY_LABEL}"
report="${replay_root}/replay_report.txt"
if [[ -e "${replay_root}" ]]; then
  echo "ERROR: replay path already exists; refusing to overwrite: ${replay_root}" >&2
  exit 1
fi
mkdir -p "${replay_root}"

replay_failed() {
  local status=$?
  if ((status != 0)); then
    {
      echo "status=failed"
      echo "exit_code=${status}"
      echo "failed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "slurm_job_id=${SLURM_JOB_ID}"
    } >"${replay_root}/replay_failed.txt"
  fi
  exit "${status}"
}
trap replay_failed EXIT

(
  export CLEO_SDM_BUNDLE_ROOT="${replay_bundle_root}"
  export BUNDLE_LABEL="${REPLAY_LABEL}"
  export MAX_SUPERDROPLETS
  bash "${SCRIPT_DIR}/prepare_controlled_bundle.sbatch"
)

"${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/controlled_bundle.py" verify \
  --bundle-directory "${replay_bundle}" \
  --expected-superdroplets "${MAX_SUPERDROPLETS}" \
  --expected-cleo-commit "${CLEO_SDM_PINNED_CLEO_COMMIT}" \
  --reference-config "${CLEO_SDM_PROJECT_ROOT}/config/collisions0d_reference.yaml" \
  --controlled-config "${CLEO_SDM_PROJECT_ROOT}/config/golovin_stage0_development.yaml"

canonical_grid="${CANONICAL_BUNDLE}/inputs/grid.dat"
canonical_supers="${CANONICAL_BUNDLE}/inputs/superdroplets.dat"
replay_grid="${replay_bundle}/inputs/grid.dat"
replay_supers="${replay_bundle}/inputs/superdroplets.dat"

cmp --silent "${canonical_grid}" "${replay_grid}"
cmp --silent "${canonical_supers}" "${replay_supers}"

canonical_grid_sha256="$(sha256sum "${canonical_grid}" | awk '{print $1}')"
replay_grid_sha256="$(sha256sum "${replay_grid}" | awk '{print $1}')"
canonical_supers_sha256="$(sha256sum "${canonical_supers}" | awk '{print $1}')"
replay_supers_sha256="$(sha256sum "${replay_supers}" | awk '{print $1}')"
canonical_manifest_sha256="$(
  sha256sum "${CANONICAL_BUNDLE}/bundle_manifest.json" | awk '{print $1}'
)"
replay_manifest_sha256="$(
  sha256sum "${replay_bundle}/bundle_manifest.json" | awk '{print $1}'
)"

{
  echo "status=completed"
  echo "schema=controlled_bundle_same_stack_replay_v1"
  echo "slurm_job_id=${SLURM_JOB_ID}"
  echo "project_commit=$(git -C "${CLEO_SDM_PROJECT_ROOT}" rev-parse HEAD)"
  echo "cleo_commit=${CLEO_SDM_PINNED_CLEO_COMMIT}"
  echo "number_of_superdroplets=${MAX_SUPERDROPLETS}"
  echo "canonical_bundle=${CANONICAL_BUNDLE}"
  echo "replay_bundle=${replay_bundle}"
  echo "canonical_grid_sha256=${canonical_grid_sha256}"
  echo "replay_grid_sha256=${replay_grid_sha256}"
  echo "grid_byte_identical=true"
  echo "canonical_superdroplet_sha256=${canonical_supers_sha256}"
  echo "replay_superdroplet_sha256=${replay_supers_sha256}"
  echo "superdroplet_byte_identical=true"
  echo "canonical_manifest_sha256=${canonical_manifest_sha256}"
  echo "replay_manifest_sha256=${replay_manifest_sha256}"
  echo "collision_model_ran=false"
  echo "zarr_output_created=false"
} >"${report}"

if find "${replay_root}" -type d -name "*.zarr" -print -quit | grep -q .; then
  echo "ERROR: replay unexpectedly created Zarr output." >&2
  exit 1
fi

trap - EXIT
echo "CONTROLLED_BUNDLE_SAME_STACK_REPLAY_PASS=1"
echo "replay_report=${report}"
echo "canonical_superdroplet_sha256=${canonical_supers_sha256}"
echo "replay_superdroplet_sha256=${replay_supers_sha256}"
