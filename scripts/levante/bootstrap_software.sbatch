#!/bin/bash
#SBATCH --job-name=cleo_bootstrap
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#
# Recreate the account-local CLEO Python tools, YAXT/YAC dependencies and the
# earlier trial-box environment. Supply --account, --output and --error at
# submission.
#
# SPDX-License-Identifier: BSD-3-Clause

set -eo pipefail
source /etc/profile
set -u
umask 027

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

readonly MAMBA="/sw/spack-levante/jupyterhub/jupyterhub/bin/mamba"
readonly TOOLS_ENV="${HOME}/.conda/envs/cleo_tools"
readonly TRIAL_ENV="${HOME}/.conda/envs/sdm_work"
readonly UPSTREAM_CLEO="${CLEO_SDM_HOME_ROOT}/CLEO"
readonly LEGACY_CLEO_LOCK="${CLEO_SDM_HOME_ROOT}/account_migration/b383673_to_m301324/legacy_environment_locks/CLEO_uv.lock"
readonly YACYAXT_PARENT="${CLEO_SDM_HOME_ROOT}/cleo_dependencies/yacyaxt"
readonly YACYAXT_FINAL="${YACYAXT_PARENT}/gcc"
readonly YAXT_URL="https://gitlab.dkrz.de/dkrz-sw/yaxt/-/archive/release-0.11.4/yaxt-0.11.4.tar.gz"
readonly YAC_URL="https://gitlab.dkrz.de/dkrz-sw/yac/-/archive/v3.9.2/yac_v3.9.2.tar.gz"
readonly YAC_SHA256="4e0b14c1bac1f18e6c428344d91a40f8dd377d5ed09b452315091f9737c3e010"
readonly NETCDF_ROOT="/sw/spack-levante/netcdf-c-4.8.1-6qheqr"
readonly FYAML_ROOT="/sw/spack-levante/libfyaml-0.7.12-fvbhgo"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

download_archive() {
  local url="$1"
  local output="$2"
  local attempt
  local partial="${output}.partial"

  for attempt in $(seq 1 8); do
    if curl \
      --fail \
      --location \
      --silent \
      --show-error \
      --output "${partial}" \
      "${url}"; then
      mv "${partial}" "${output}"
      return 0
    fi

    rm -f -- "${partial}"
    echo "download attempt ${attempt}/8 failed: ${url}" >&2
    sleep "$((attempt * 5))"
  done

  fail "archive download failed after 8 attempts: ${url}"
}

[[ "$(id -un)" == "${CLEO_SDM_USER}" ]] ||
  fail "USER and effective identity differ"
[[ -x "${MAMBA}" ]] || fail "mamba is missing: ${MAMBA}"
[[ -d "${CLEO_SDM_PROJECT_ROOT}/.git" ]] ||
  fail "canonical project checkout is missing: ${CLEO_SDM_PROJECT_ROOT}"

cleo_sdm_load_modules

echo "--- create or validate cleo_tools ---"
if [[ ! -d "${TOOLS_ENV}" ]]; then
  "${MAMBA}" create \
    --yes \
    --prefix "${TOOLS_ENV}" \
    --channel conda-forge \
    "doxygen>=1.10.0" \
    uv
fi
readonly UV="${TOOLS_ENV}/bin/uv"
[[ -x "${UV}" ]] || fail "uv is missing from ${TOOLS_ENV}"
[[ -x "${TOOLS_ENV}/bin/doxygen" ]] ||
  fail "doxygen is missing from ${TOOLS_ENV}"
"${UV}" --version
"${TOOLS_ENV}/bin/doxygen" --version

echo "--- clone or validate pinned upstream CLEO ---"
if [[ ! -e "${UPSTREAM_CLEO}" ]]; then
  git clone https://github.com/yoctoyotta1024/CLEO.git "${UPSTREAM_CLEO}"
  git -C "${UPSTREAM_CLEO}" checkout --detach "${CLEO_SDM_PINNED_CLEO_COMMIT}"
fi
actual_cleo_commit="$(git -C "${UPSTREAM_CLEO}" rev-parse HEAD)"
[[ "${actual_cleo_commit}" == "${CLEO_SDM_PINNED_CLEO_COMMIT}" ]] ||
  fail "upstream CLEO checkout is ${actual_cleo_commit}, expected the project pin"
if [[ ! -e "${UPSTREAM_CLEO}/uv.lock" ]]; then
  [[ -f "${LEGACY_CLEO_LOCK}" ]] ||
    fail "the preserved CLEO uv.lock is missing: ${LEGACY_CLEO_LOCK}"
  cp "${LEGACY_CLEO_LOCK}" "${UPSTREAM_CLEO}/uv.lock"
fi

echo "--- synchronize CLEO's Python environment ---"
cd "${UPSTREAM_CLEO}"
"${UV}" python install 3.13
"${UV}" sync \
  --frozen \
  --all-extras \
  --group dev \
  --inexact \
  --python 3.13
readonly CLEO_PYTHON="${UPSTREAM_CLEO}/.venv/bin/python3"
[[ -x "${CLEO_PYTHON}" ]] || fail "CLEO Python was not created"

echo "--- rebuild mpi4py against Levante OpenMPI ---"
readonly MPICC="$(command -v mpicc)"
readonly OPENMPI_ROOT="$(cd -- "$(dirname -- "${MPICC}")/.." && pwd)"
mpi4py_extension="$(
  find \
    "${UPSTREAM_CLEO}/.venv/lib/python3.13/site-packages/mpi4py" \
    -maxdepth 1 \
    -type f \
    -name 'MPI*.so' \
    -print \
    -quit 2>/dev/null || true
)"
if [[ -n "${mpi4py_extension}" ]] \
  && ldd "${mpi4py_extension}" | grep -Fq "${OPENMPI_ROOT}/lib/libmpi"; then
  echo "existing mpi4py is linked to Levante OpenMPI"
else
  "${UV}" pip uninstall \
    --python "${CLEO_PYTHON}" \
    mpi4py || true
  MPI4PY_BUILD_MPICC="${MPICC}" \
  MPI4PY_BUILD_MPILD="${OPENMPI_ROOT}/lib" \
    "${UV}" pip install \
      --python "${CLEO_PYTHON}" \
      --no-cache-dir \
      --no-binary=mpi4py \
      "mpi4py==4.1.2"
fi

echo "--- build and install plotcleo ---"
if "${CLEO_PYTHON}" -c 'import plotcleo' 2>/dev/null; then
  echo "existing plotcleo import passes"
else
  "${UV}" build "${UPSTREAM_CLEO}/examples/exampleplotting/plotcleo"
  plotcleo_archive="$(
    find "${UPSTREAM_CLEO}/examples/exampleplotting/plotcleo/dist" \
      -maxdepth 1 \
      -type f \
      -name 'plotcleo-*.tar.gz' \
      -print |
      LC_ALL=C sort |
      tail -n 1
  )"
  [[ -n "${plotcleo_archive}" ]] || fail "plotcleo source archive was not built"
  "${UV}" pip install \
    --python "${CLEO_PYTHON}" \
    "${plotcleo_archive}"
fi

echo "--- create or validate the earlier trial-box environment ---"
if [[ ! -d "${TRIAL_ENV}" ]]; then
  "${MAMBA}" env create \
    --yes \
    --prefix "${TRIAL_ENV}" \
    --file "${CLEO_SDM_HOME_ROOT}/trial_box_model/environment.yml"
fi
"${TRIAL_ENV}/bin/python" -c \
  'import matplotlib, netCDF4, numpy, pandas, pytest, scipy, xarray'

echo "--- build YAXT and YAC in a same-filesystem staging directory ---"
if [[ ! -d "${YACYAXT_FINAL}/yaxt" || ! -d "${YACYAXT_FINAL}/yac" ]]; then
  [[ ! -e "${YACYAXT_FINAL}" ]] ||
    fail "partial final YAXT/YAC prefix exists: ${YACYAXT_FINAL}"

  readonly STAGE_ROOT="${YACYAXT_PARENT}/.gcc.bootstrap_${SLURM_JOB_ID}"
  [[ ! -e "${STAGE_ROOT}" ]] ||
    fail "staging path already exists: ${STAGE_ROOT}"
  mkdir -p \
    "${STAGE_ROOT}/archives" \
    "${STAGE_ROOT}/source" \
    "${STAGE_ROOT}/install"

  download_archive \
    "${YAXT_URL}" \
    "${STAGE_ROOT}/archives/yaxt-0.11.4.tar.gz"
  download_archive \
    "${YAC_URL}" \
    "${STAGE_ROOT}/archives/yac-v3.9.2.tar.gz"

  echo "${YAC_SHA256}  ${STAGE_ROOT}/archives/yac-v3.9.2.tar.gz" |
    sha256sum --check -
  tar -tzf "${STAGE_ROOT}/archives/yaxt-0.11.4.tar.gz" >/dev/null
  tar -tzf "${STAGE_ROOT}/archives/yac-v3.9.2.tar.gz" >/dev/null

  mkdir "${STAGE_ROOT}/source/yaxt"
  tar \
    -xzf "${STAGE_ROOT}/archives/yaxt-0.11.4.tar.gz" \
    -C "${STAGE_ROOT}/source/yaxt" \
    --strip-components=1
  mkdir "${STAGE_ROOT}/source/yaxt/build"
  cd "${STAGE_ROOT}/source/yaxt/build"
  ../configure \
    CC="$(command -v mpicc)" \
    FC="$(command -v mpifort)" \
    CFLAGS="-O0 -g -Wall" \
    FCFLAGS="-O0 -g -Wall -cpp -fimplicit-none" \
    --without-regard-for-quality \
    --without-example-programs \
    --without-perf-programs \
    --with-pic \
    --prefix="${STAGE_ROOT}/install/yaxt"
  make --jobs "${SLURM_CPUS_PER_TASK}"
  make install

  mkdir "${STAGE_ROOT}/source/yac"
  tar \
    -xzf "${STAGE_ROOT}/archives/yac-v3.9.2.tar.gz" \
    -C "${STAGE_ROOT}/source/yac" \
    --strip-components=1
  mkdir "${STAGE_ROOT}/source/yac/build"
  cd "${STAGE_ROOT}/source/yac/build"
  ../configure \
    CC="$(command -v mpicc)" \
    FC="$(command -v mpifort)" \
    CFLAGS="-O0 -g -Wall" \
    FCFLAGS="-O0 -g -Wall -cpp -fimplicit-none" \
    LDFLAGS="-lm" \
    PYTHON="${CLEO_PYTHON}" \
    --disable-mpi-checks \
    --with-yaxt-root="${STAGE_ROOT}/install/yaxt" \
    --with-netcdf-root="${NETCDF_ROOT}" \
    --with-fyaml-root="${FYAML_ROOT}" \
    --enable-python-bindings \
    --enable-rpaths \
    --with-pic \
    --prefix="${STAGE_ROOT}/install/yac"
  make --jobs "${SLURM_CPUS_PER_TASK}"
  make install
  mv "${STAGE_ROOT}/source/yac/build/python" "${STAGE_ROOT}/install/yac/"

  {
    echo "bootstrap_job_id=${SLURM_JOB_ID}"
    echo "completed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "yaxt_url=${YAXT_URL}"
    echo "yac_url=${YAC_URL}"
    echo "yac_expected_sha256=${YAC_SHA256}"
    sha256sum "${STAGE_ROOT}/archives/"*.tar.gz
  } > "${STAGE_ROOT}/install/bootstrap_manifest.txt"

  mv "${STAGE_ROOT}/install" "${YACYAXT_FINAL}"
fi

echo "--- validate shared-library resolution and MPI/YAC Python imports ---"
export PYTHONPATH="${YACYAXT_FINAL}/yac/python${PYTHONPATH:+:${PYTHONPATH}}"
export LD_LIBRARY_PATH="${YACYAXT_FINAL}/yac/lib:${YACYAXT_FINAL}/yaxt/lib:${FYAML_ROOT}/lib:${CLEO_SDM_GCC_LIB}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

link_failure=0
while IFS= read -r shared_object; do
  missing="$(ldd "${shared_object}" | grep 'not found' || true)"
  if [[ -n "${missing}" ]]; then
    echo "FAIL: ${shared_object}"
    echo "${missing}"
    link_failure=1
  fi
done < <(
  find \
    "${YACYAXT_FINAL}/yaxt/lib" \
    "${YACYAXT_FINAL}/yac/lib" \
    "${YACYAXT_FINAL}/yac/python" \
    -type f \
    -name '*.so*' \
    -print
)
[[ "${link_failure}" -eq 0 ]] || fail "one or more shared libraries are missing"

srun \
  --mpi=pmix_v3 \
  --ntasks=1 \
  --cpus-per-task=1 \
  "${CLEO_PYTHON}" -c \
  'from mpi4py import MPI
import mpi4py
import plotcleo
import yac
print("mpi4py_version=", mpi4py.__version__)
print("rank_size=", MPI.COMM_WORLD.Get_rank(), MPI.COMM_WORLD.Get_size())
print("mpi_library=", MPI.Get_library_version())
print("plotcleo=", plotcleo.__file__)
print("yac=", yac.__file__)'

{
  echo "SOFTWARE_BOOTSTRAP_PASS=1"
  echo "bootstrap_job_id=${SLURM_JOB_ID}"
  echo "cleo_commit=${actual_cleo_commit}"
  echo "cleo_python=$("${CLEO_PYTHON}" --version 2>&1)"
  echo "uv=$("${UV}" --version)"
  echo "doxygen=$("${TOOLS_ENV}/bin/doxygen" --version)"
  echo "trial_python=$("${TRIAL_ENV}/bin/python" --version 2>&1)"
  echo "mpicc=${MPICC}"
} | tee "${CLEO_SDM_HOME_ROOT}/software_bootstrap_manifest.txt"
