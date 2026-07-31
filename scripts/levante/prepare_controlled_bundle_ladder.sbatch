#!/bin/bash
#SBATCH --job-name=cleo_sdm_bundleladder
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=940M
#SBATCH --time=00:10:00

# Create immutable controlled-initialization bundles required by a registered
# Golovin resolution ladder. By default the historical N=4096 canonical
# bundle is verified and reused. Set REUSE_CANONICAL_N4096=0 for a completely
# fresh ladder that creates every requested resolution under new labels.
#
# Required submission form:
#
#   sbatch --account=<project> \
#     --export=ALL,CANONICAL_N4096_BUNDLE=/path/to/golovin_controlled_N004096_v1 \
#     scripts/levante/prepare_controlled_bundle_ladder.sbatch
#
# This job writes and reads CLEO-native inputs only. It runs no collision
# executable, creates no Zarr output, and uses no accelerator.
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

BUNDLE_RESOLUTIONS="${BUNDLE_RESOLUTIONS:-512 1024 2048 8192 16384}"
REUSE_CANONICAL_N4096="${REUSE_CANONICAL_N4096:-1}"
BUNDLE_LABEL_STEM="${BUNDLE_LABEL_STEM:-golovin_controlled}"
BUNDLE_LABEL_VERSION="${BUNDLE_LABEL_VERSION:-v1}"
BUNDLE_LADDER_RECORD_LABEL="${BUNDLE_LADDER_RECORD_LABEL:-golovin_controlled_ladder_v1_record}"

if [[ "${REUSE_CANONICAL_N4096}" != "0" \
  && "${REUSE_CANONICAL_N4096}" != "1" ]]; then
  echo "ERROR: REUSE_CANONICAL_N4096 must be 0 or 1." >&2
  exit 2
fi
for label_component in \
  "${BUNDLE_LABEL_STEM}" \
  "${BUNDLE_LABEL_VERSION}" \
  "${BUNDLE_LADDER_RECORD_LABEL}"; do
  if [[ ! "${label_component}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    echo "ERROR: bundle label component contains unsupported characters." >&2
    exit 2
  fi
done

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
cleo_sdm_print_environment
export OMP_NUM_THREADS=1
umask 027

python="${CLEO_SDM_PROJECT_ROOT}/.venv/bin/python"
test -x "${python}"
if [[ "${REUSE_CANONICAL_N4096}" == "1" ]]; then
  : "${CANONICAL_N4096_BUNDLE:?Set CANONICAL_N4096_BUNDLE at submission.}"
  CANONICAL_N4096_BUNDLE="$(
    cd "${CANONICAL_N4096_BUNDLE}" && pwd
  )"
  "${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/controlled_bundle.py" verify \
    --bundle-directory "${CANONICAL_N4096_BUNDLE}" \
    --expected-superdroplets 4096 \
    --expected-cleo-commit "${CLEO_SDM_PINNED_CLEO_COMMIT}" \
    --reference-config "${CLEO_SDM_PROJECT_ROOT}/config/collisions0d_reference.yaml" \
    --controlled-config "${CLEO_SDM_PROJECT_ROOT}/config/golovin_stage0_development.yaml"
else
  CANONICAL_N4096_BUNDLE="not_used"
fi

declare -a resolutions=()
declare -a labels=()
for resolution in ${BUNDLE_RESOLUTIONS}; do
  if [[ ! "${resolution}" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: invalid bundle resolution: ${resolution}" >&2
    exit 2
  fi
  if ((resolution == 4096)) && [[ "${REUSE_CANONICAL_N4096}" == "1" ]]; then
    echo "ERROR: omit 4096 from BUNDLE_RESOLUTIONS; the canonical bundle is reused." >&2
    exit 2
  fi
  label="$(
    printf '%s_N%06d_%s' \
      "${BUNDLE_LABEL_STEM}" \
      "${resolution}" \
      "${BUNDLE_LABEL_VERSION}"
  )"
  target="${CLEO_SDM_BUNDLE_ROOT}/${label}"
  if [[ -e "${target}" ]]; then
    echo "ERROR: bundle target already exists; refusing partial overwrite: ${target}" >&2
    exit 1
  fi
  resolutions+=("${resolution}")
  labels+=("${label}")
done
if ((${#resolutions[@]} == 0)); then
  echo "ERROR: BUNDLE_RESOLUTIONS contains no work." >&2
  exit 2
fi
if ((${#resolutions[@]} != ${#labels[@]})); then
  echo "ERROR: internal bundle-ladder length mismatch." >&2
  exit 1
fi

project_commit="$(git -C "${CLEO_SDM_PROJECT_ROOT}" rev-parse HEAD)"
record_directory="${CLEO_SDM_BUNDLE_ROOT}/${BUNDLE_LADDER_RECORD_LABEL}"
if [[ -e "${record_directory}" ]]; then
  echo "ERROR: ladder record already exists; refusing overwrite: ${record_directory}" >&2
  exit 1
fi
mkdir -p "${record_directory}"

ladder_failed() {
  local status=$?
  if ((status != 0)); then
    {
      echo "status=failed"
      echo "exit_code=${status}"
      echo "failed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "slurm_job_id=${SLURM_JOB_ID}"
      echo "project_commit=${project_commit}"
    } >"${record_directory}/ladder_failed.txt"
  fi
  exit "${status}"
}
trap ladder_failed EXIT

{
  echo "schema=controlled_bundle_ladder_v1"
  echo "status=preparing"
  echo "project_commit=${project_commit}"
  echo "cleo_commit=${CLEO_SDM_PINNED_CLEO_COMMIT}"
  echo "slurm_job_id=${SLURM_JOB_ID}"
  echo "reuse_canonical_n4096=${REUSE_CANONICAL_N4096}"
  echo "canonical_n4096_bundle=${CANONICAL_N4096_BUNDLE}"
  echo "bundle_label_stem=${BUNDLE_LABEL_STEM}"
  echo "bundle_label_version=${BUNDLE_LABEL_VERSION}"
} >"${record_directory}/ladder_report.txt"

for index in "${!resolutions[@]}"; do
  resolution="${resolutions[${index}]}"
  label="${labels[${index}]}"
  echo "BUNDLE_LADDER_CASE_BEGIN N=${resolution} label=${label}"
  (
    export MAX_SUPERDROPLETS="${resolution}"
    export BUNDLE_LABEL="${label}"
    bash "${SCRIPT_DIR}/prepare_controlled_bundle.sbatch"
  )
  "${python}" "${CLEO_SDM_PROJECT_ROOT}/scripts/controlled_bundle.py" verify \
    --bundle-directory "${CLEO_SDM_BUNDLE_ROOT}/${label}" \
    --expected-superdroplets "${resolution}" \
    --expected-cleo-commit "${CLEO_SDM_PINNED_CLEO_COMMIT}" \
    --reference-config "${CLEO_SDM_PROJECT_ROOT}/config/collisions0d_reference.yaml" \
    --controlled-config "${CLEO_SDM_PROJECT_ROOT}/config/golovin_stage0_development.yaml"
  {
    echo "bundle_N${resolution}=${CLEO_SDM_BUNDLE_ROOT}/${label}"
    echo "manifest_sha256_N${resolution}=$(
      sha256sum "${CLEO_SDM_BUNDLE_ROOT}/${label}/bundle_manifest.json" | awk '{print $1}'
    )"
  } >>"${record_directory}/ladder_report.txt"
  echo "BUNDLE_LADDER_CASE_END N=${resolution} label=${label}"
done

{
  echo "status=completed"
  echo "completed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "generated_bundle_count=${#resolutions[@]}"
  echo "collision_model_ran=false"
  echo "zarr_output_created=false"
} >>"${record_directory}/ladder_report.txt"

if find "${CLEO_SDM_BUNDLE_ROOT}" \
  -maxdepth 2 -type d -name "*.zarr" -print -quit | grep -q .; then
  echo "ERROR: bundle ladder unexpectedly contains Zarr output." >&2
  exit 1
fi

trap - EXIT
echo "CONTROLLED_BUNDLE_LADDER_PASS=1"
echo "generated_bundle_count=${#resolutions[@]}"
echo "ladder_report=${record_directory}/ladder_report.txt"
