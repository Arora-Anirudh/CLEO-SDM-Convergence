#!/bin/bash
#SBATCH --job-name=cleo_sdm_build
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=/scratch/b/b383673/SDM/logs/%x_%j.out
#SBATCH --error=/scratch/b/b383673/SDM/logs/%x_%j.err

# Configure the project, fetch the pinned CLEO source, and build the two
# collision-only executables. Supply the active project account at submission:
#
#   sbatch --account=<project> scripts/levante/build.sbatch
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

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
cleo_sdm_print_environment

mkdir -p "${CLEO_SDM_BUILD_ROOT}"
cd "${CLEO_SDM_PROJECT_ROOT}"

echo "--- synchronize the locked Python environment ---"
"${CLEO_SDM_UV}" sync \
  --frozen \
  --group dev \
  --python "${CLEO_SDM_BOOTSTRAP_PYTHON}"

echo "--- configure CMake ---"
cmake \
  -S "${CLEO_SDM_PROJECT_ROOT}" \
  -B "${CLEO_SDM_BUILD_ROOT}" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER="$(command -v mpicc)" \
  -DCMAKE_CXX_COMPILER="$(command -v mpic++)" \
  -DCMAKE_CXX_FLAGS="-Wall -Wextra -Wno-unused-parameter -pedantic -O3 -mfma" \
  -DKokkos_ARCH_NATIVE=ON \
  -DKokkos_ENABLE_SERIAL=ON \
  -DKokkos_ENABLE_OPENMP=ON \
  -DCLEO_COUPLED_DYNAMICS=null \
  -DCLEO_DOMAIN=cartesian \
  -DCLEO_NO_PYBINDINGS=ON \
  -DBLAS_openblas_LIBRARY="${CLEO_SDM_OPENBLAS_ROOT}/lib/libopenblas.so" \
  -DCLEO_FYAMLLIB="${CLEO_SDM_FYAML_ROOT}/lib" \
  -DCLEO_YAXT_ROOT="${CLEO_SDM_YACYAXT_ROOT}/yaxt" \
  -DCLEO_YAC_ROOT="${CLEO_SDM_YACYAXT_ROOT}/yac" \
  -DCLEO_YAC_MODULE_PATH="${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src/libs/coupldyn_yac/cmake"

actual_cleo_commit="$(
  git -C "${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src" rev-parse HEAD
)"
if [[ "${actual_cleo_commit}" != "${CLEO_SDM_PINNED_CLEO_COMMIT}" ]]; then
  echo "ERROR: fetched CLEO commit ${actual_cleo_commit} does not match the pin." >&2
  exit 1
fi
patched_files="$(
  git -C "${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src" diff --name-only
)"
if [[ "${patched_files}" != "libs/superdrops/collisions/collisions.hpp" ]]; then
  echo "ERROR: expected only the collision-seed header patch, got: ${patched_files}" >&2
  exit 1
fi
grep -Fq \
  "DoCollisions(const double DELT, Probability p, EnactCollision x, const uint64_t seed)" \
  "${CLEO_SDM_BUILD_ROOT}/_deps/cleo-src/libs/superdrops/collisions/collisions.hpp"

echo "--- compile collision-box targets ---"
cmake \
  --build "${CLEO_SDM_BUILD_ROOT}" \
  --parallel "${SLURM_CPUS_PER_TASK}" \
  --target collisions0d_golovin collisions0d_long

golovin_executable="${CLEO_SDM_BUILD_ROOT}/src/collisions0d/collisions0d_golovin"
long_executable="${CLEO_SDM_BUILD_ROOT}/src/collisions0d/collisions0d_long"
test -x "${golovin_executable}"
test -x "${long_executable}"

{
  echo "project_commit=$(git -C "${CLEO_SDM_PROJECT_ROOT}" rev-parse HEAD)"
  echo "cleo_commit=${actual_cleo_commit}"
  echo "build_job_id=${SLURM_JOB_ID}"
  echo "build_cpus=${SLURM_CPUS_PER_TASK}"
  echo "mpicc=$(command -v mpicc)"
  echo "mpicxx=$(command -v mpic++)"
  echo "build_local_cleo_patch=${patched_files}"
  sha256sum \
    "${CLEO_SDM_PROJECT_ROOT}/patches/cleo/0001-add-explicit-collision-rng-seed.patch"
  sha256sum "${golovin_executable}" "${long_executable}"
} >"${CLEO_SDM_BUILD_ROOT}/build_manifest.txt"

echo "BUILD_PASS=1"
echo "build_manifest=${CLEO_SDM_BUILD_ROOT}/build_manifest.txt"
echo "golovin_executable=${golovin_executable}"
echo "long_executable=${long_executable}"
