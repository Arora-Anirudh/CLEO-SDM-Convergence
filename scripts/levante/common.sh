#!/bin/bash
#
# Shared Levante settings for CLEO-SDM-Convergence.
#
# This file is sourced by the Slurm scripts. It does not submit work.
#
# SPDX-License-Identifier: BSD-3-Clause

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "ERROR: source scripts/levante/common.sh; do not execute it directly." >&2
  exit 2
fi

export CLEO_SDM_PROJECT_ROOT="${CLEO_SDM_PROJECT_ROOT:-/home/b/b383673/SDM/CLEO-SDM-Convergence}"
export CLEO_SDM_BUILD_ROOT="${CLEO_SDM_BUILD_ROOT:-/home/b/b383673/SDM/cleo_builds/CLEO-SDM-Convergence/openmp}"
export CLEO_SDM_RUN_ROOT="${CLEO_SDM_RUN_ROOT:-/scratch/b/b383673/SDM/CLEO-SDM-Convergence/runs}"
export CLEO_SDM_BUNDLE_ROOT="${CLEO_SDM_BUNDLE_ROOT:-/home/b/b383673/SDM/CLEO-SDM-Convergence-records/controlled_bundles}"

export CLEO_SDM_YACYAXT_ROOT="${CLEO_SDM_YACYAXT_ROOT:-/home/b/b383673/SDM/cleo_dependencies/yacyaxt/gcc}"
export CLEO_SDM_UV="${CLEO_SDM_UV:-/home/b/b383673/.conda/envs/cleo_tools/bin/uv}"
export CLEO_SDM_BOOTSTRAP_PYTHON="${CLEO_SDM_BOOTSTRAP_PYTHON:-/home/b/b383673/SDM/CLEO/.venv/bin/python3}"

export CLEO_SDM_GCC_MODULE="${CLEO_SDM_GCC_MODULE:-gcc/11.2.0-gcc-11.2.0}"
export CLEO_SDM_OPENMPI_MODULE="${CLEO_SDM_OPENMPI_MODULE:-openmpi/4.1.2-gcc-11.2.0}"
export CLEO_SDM_NETCDF_MODULE="${CLEO_SDM_NETCDF_MODULE:-netcdf-c/4.8.1-openmpi-4.1.2-gcc-11.2.0}"
export CLEO_SDM_GIT_MODULE="${CLEO_SDM_GIT_MODULE:-git/2.43.7-gcc-11.2.0}"

export CLEO_SDM_GCC_LIB="${CLEO_SDM_GCC_LIB:-/sw/spack-levante/gcc-11.2.0-bcn7mb/lib64}"
export CLEO_SDM_FYAML_ROOT="${CLEO_SDM_FYAML_ROOT:-/sw/spack-levante/libfyaml-0.7.12-fvbhgo}"
export CLEO_SDM_OPENBLAS_ROOT="${CLEO_SDM_OPENBLAS_ROOT:-/sw/spack-levante/openblas-0.3.18-tpmfvw}"

readonly CLEO_SDM_PINNED_CLEO_COMMIT="83318c23223546d10759d202d70f4fa2f7fe4688"

cleo_sdm_load_modules() {
  module purge

  module load \
    "${CLEO_SDM_GIT_MODULE}" \
    "${CLEO_SDM_GCC_MODULE}" \
    "${CLEO_SDM_OPENMPI_MODULE}" \
    "${CLEO_SDM_NETCDF_MODULE}"
}

cleo_sdm_set_runtime() {
  local yaclib="${CLEO_SDM_YACYAXT_ROOT}/yac/lib"
  local yaxtlib="${CLEO_SDM_YACYAXT_ROOT}/yaxt/lib"
  local fyamllib="${CLEO_SDM_FYAML_ROOT}/lib"
  local openblaslib="${CLEO_SDM_OPENBLAS_ROOT}/lib"

  export LD_LIBRARY_PATH="${yaclib}:${yaxtlib}:${fyamllib}:${openblaslib}:${CLEO_SDM_GCC_LIB}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
  export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-1}"
  export OMP_PROC_BIND=spread
  export OMP_PLACES=threads
  export OPENBLAS_NUM_THREADS=1
  export MKL_NUM_THREADS=1

  export OMPI_MCA_osc=ucx
  export OMPI_MCA_pml=ucx
  export OMPI_MCA_btl=self
  export OMPI_MCA_io=romio321
  export UCX_HANDLE_ERRORS=bt
  export UCX_TLS=shm,rc_mlx5,rc_x,self

  ulimit -s 204800
  ulimit -c 0
}

cleo_sdm_validate_paths() {
  local required_paths=(
    "${CLEO_SDM_PROJECT_ROOT}/CMakeLists.txt"
    "${CLEO_SDM_PROJECT_ROOT}/config/collisions0d_reference.yaml"
    "${CLEO_SDM_YACYAXT_ROOT}/yac"
    "${CLEO_SDM_YACYAXT_ROOT}/yaxt"
    "${CLEO_SDM_OPENBLAS_ROOT}/lib/libopenblas.so"
    "${CLEO_SDM_UV}"
    "${CLEO_SDM_BOOTSTRAP_PYTHON}"
  )

  local path
  for path in "${required_paths[@]}"; do
    if [[ ! -e "${path}" ]]; then
      echo "ERROR: required path is missing: ${path}" >&2
      return 1
    fi
  done
}

cleo_sdm_print_environment() {
  echo "project_root=${CLEO_SDM_PROJECT_ROOT}"
  echo "build_root=${CLEO_SDM_BUILD_ROOT}"
  echo "run_root=${CLEO_SDM_RUN_ROOT}"
  echo "bundle_root=${CLEO_SDM_BUNDLE_ROOT}"
  echo "yacyaxt_root=${CLEO_SDM_YACYAXT_ROOT}"
  echo "pinned_cleo_commit=${CLEO_SDM_PINNED_CLEO_COMMIT}"
  echo "slurm_job_id=${SLURM_JOB_ID:-none}"
  echo "slurm_cpus_per_task=${SLURM_CPUS_PER_TASK:-none}"
  echo "c_compiler=$(command -v mpicc)"
  echo "cxx_compiler=$(command -v mpic++)"
  echo "cmake=$(command -v cmake)"
  echo "git=$(command -v git)"
}
