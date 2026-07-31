#!/bin/bash
#SBATCH --job-name=cleo_smt_bench
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --cpus-per-task=1
#SBATCH --mem=14400M
#SBATCH --time=00:45:00

# Benchmark the resource cost of two Slurm placements for the same 16
# controlled Golovin members. The source matrix supplies the immutable
# initialization bundle and collision seeds; the generated case matrix changes
# only run labels and stage names so it cannot overwrite scientific results.
#
# Submit one job with CPU_LAYOUT=physical_cores and --hint=nomultithread; then
# submit a dependent job with CPU_LAYOUT=smt_threads and --ntasks-per-core=2.
# EXPECTED_ALLOCATED_LOGICAL_CPUS makes a layout failure stop before CLEO runs.
#
# SPDX-License-Identifier: BSD-3-Clause

set -eo pipefail
unset LC_ALL
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
source "$SCRIPT_DIR/common.sh"

: "${CPU_LAYOUT:?Set CPU_LAYOUT to physical_cores or smt_threads.}"
: "${EXPECTED_ALLOCATED_LOGICAL_CPUS:?Set EXPECTED_ALLOCATED_LOGICAL_CPUS.}"
: "${BENCHMARK_RECORD_ROOT:?Set BENCHMARK_RECORD_ROOT to a new HOME record path.}"
: "${BENCHMARK_RUN_ROOT:?Set BENCHMARK_RUN_ROOT to a new SCRATCH output path.}"

if [[ "$CPU_LAYOUT" != "physical_cores" && "$CPU_LAYOUT" != "smt_threads" ]]; then
  echo "ERROR: CPU_LAYOUT must be physical_cores or smt_threads." >&2
  exit 2
fi
if [[ ! "$EXPECTED_ALLOCATED_LOGICAL_CPUS" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: EXPECTED_ALLOCATED_LOGICAL_CPUS must be a positive integer." >&2
  exit 2
fi
if ((SLURM_NTASKS != 16 || SLURM_CPUS_PER_TASK != 1)); then
  echo "ERROR: this benchmark requires exactly 16 one-thread worker tasks." >&2
  exit 2
fi

actual_allocated_cpus="$(
  scontrol show job "$SLURM_JOB_ID" \
    | sed -n 's/.*AllocTRES=.*cpu=\([0-9][0-9]*\).*/\1/p'
)"
if [[ "$actual_allocated_cpus" != "$EXPECTED_ALLOCATED_LOGICAL_CPUS" ]]; then
  echo "ERROR: layout allocation mismatch: expected $EXPECTED_ALLOCATED_LOGICAL_CPUS logical CPUs, got ${actual_allocated_cpus:-none}." >&2
  exit 3
fi

cleo_sdm_load_modules
cleo_sdm_set_runtime
cleo_sdm_validate_paths
cleo_sdm_print_environment
export OMP_NUM_THREADS=1
export CLEO_SDM_CPU_LAYOUT="$CPU_LAYOUT"
umask 027

source_matrix="$CLEO_SDM_PROJECT_ROOT/experiments/golovin_fixed50_extended_resolution_convergence_v1/cases.tsv"
case_matrix="$BENCHMARK_RECORD_ROOT/cases.tsv"
if [[ -e "$BENCHMARK_RECORD_ROOT" || -e "$BENCHMARK_RUN_ROOT" ]]; then
  echo "ERROR: benchmark record or run root already exists; refusing overwrite." >&2
  exit 1
fi
mkdir -p "$BENCHMARK_RECORD_ROOT"

awk -F $'\t' -v layout="$CPU_LAYOUT" '
  BEGIN { OFS = FS; count = 0 }
  NR == 1 { print; next }
  $6 == 262144 && $11 < 16 {
    $1 = count
    $2 = sprintf("golovin_smt_efficiency_v1_%s_N262144_m%03d", layout, $11)
    $3 = sprintf("golovin_smt_efficiency_v1_%s", layout)
    print
    count++
  }
  END {
    if (count != 16) {
      printf("ERROR: expected 16 N=262144 source rows, found %d\n", count) > "/dev/stderr"
      exit 1
    }
  }
' "$source_matrix" >"$case_matrix"
chmod 0440 "$case_matrix"

matrix_sha256="$(sha256sum "$case_matrix" | awk '{print $1}')"
{
  echo "status=running"
  echo "benchmark_version=1"
  echo "cpu_layout=$CPU_LAYOUT"
  echo "expected_allocated_logical_cpus=$EXPECTED_ALLOCATED_LOGICAL_CPUS"
  echo "actual_allocated_logical_cpus=$actual_allocated_cpus"
  echo "source_matrix=$source_matrix"
  echo "source_matrix_sha256=$(sha256sum "$source_matrix" | awk '{print $1}')"
  echo "case_matrix_sha256=$matrix_sha256"
  echo "members=16"
  echo "max_superdroplets=262144"
  echo "collision_timestep_s=0.1"
  echo "end_time_s=3600"
  echo "slurm_job_id=$SLURM_JOB_ID"
} >"$BENCHMARK_RECORD_ROOT/benchmark_manifest.inprogress.txt"

export MATRIX_FILE="$case_matrix"
export RESOLUTION_RECORD_ROOT="$BENCHMARK_RECORD_ROOT/model_record"
export EXPECTED_CASE_COUNT=16
export WORKER_COUNT=16
export RESUME_COMPLETED=1
export CLEO_SDM_RUN_ROOT="$BENCHMARK_RUN_ROOT"

bash "$SCRIPT_DIR/run_golovin_resolution_convergence_parallel.sbatch"

mv \
  "$BENCHMARK_RECORD_ROOT/benchmark_manifest.inprogress.txt" \
  "$BENCHMARK_RECORD_ROOT/benchmark_manifest.txt"
echo "SMT_EFFICIENCY_BENCHMARK_PASS=1"
