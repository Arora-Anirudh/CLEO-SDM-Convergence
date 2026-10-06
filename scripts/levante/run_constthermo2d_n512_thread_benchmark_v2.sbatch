#!/usr/bin/env bash
# Fresh repair of v1's exact-CPU-allocation guard. One model-only Kokkos Threads
# benchmark using the accepted Ncell=512 input; no inputs or plots are written.

#SBATCH --job-name=const2d-threadbench2
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/n512-threadbench-v2-%j.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/n512-threadbench-v2-%j.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY="" MPLBACKEND=Agg
set +u
set +e
source /etc/profile
profile_status=$?
set -e
test "$profile_status" -eq 0
module load git/2.43.7-gcc-11.2.0

: "${THREADS:?submit with --export=ALL,THREADS=<8|16|32|64|128>}"
case "$THREADS" in 8|16|32|64|128) ;; *) echo "unsupported THREADS=$THREADS" >&2; exit 2 ;; esac
test "$SLURM_CPUS_PER_TASK" -ge "$THREADS"
printf 'requested_kokkos_threads=%s\nslurm_cpus_per_task=%s\n' "$THREADS" "$SLURM_CPUS_PER_TASK"

readonly HOME_ROOT=/home/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly SCRATCH_ROOT=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly SOURCE=/home/m/m301324/SDM/CLEO-v0691-constthermo2d-9224585d
readonly EXPECTED_COMMIT=9224585d784e9371926db9d0a23891a4b0241e24
readonly BUILD=/home/m/m301324/SDM/cleo_builds/CLEO-v0691-constthermo2d-9224585d-threads-gcc-v4
readonly EXECUTABLE="$BUILD/examples/constthermo2d/src/const2d"
readonly PYTHON=/home/m/m301324/SDM/CLEO/.venv/bin/python3
readonly FYAMLLIB=/sw/spack-levante/libfyaml-0.7.12-fvbhgo/lib
readonly GCCLIB=/sw/spack-levante/gcc-11.2.0-bcn7mb/lib64
readonly YACLIB=/home/m/m301324/SDM/cleo_dependencies/yacyaxt/gcc/yac/lib
readonly YAXTLIB=/home/m/m301324/SDM/cleo_dependencies/yacyaxt/gcc/yaxt/lib
readonly REFERENCE_CASE="$SCRATCH_ROOT/pilot_v2/ncell0512/member001"
readonly CASE_ROOT="$SCRATCH_ROOT/thread_benchmark_v2/ncell0512/threads${THREADS}"
readonly CONFIG="$CASE_ROOT/tmp/const2d_config.yaml"

test -x "$EXECUTABLE"
test -x "$PYTHON"
test -r "$HOME_ROOT/package/audit_constthermo2d_case_v2.py"
test -r "$REFERENCE_CASE/tmp/const2d_config.yaml"
test -r "$REFERENCE_CASE/share/const2d_dimlessSDsinit.dat"
test -s "$REFERENCE_CASE/trajectory_integrity.json"
test ! -e "$CASE_ROOT"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test -z "$(git -C "$SOURCE" status --porcelain)"
mkdir -p "$SCRATCH_ROOT/logs" "$CASE_ROOT/tmp" "$CASE_ROOT/bin"

export LD_LIBRARY_PATH="$FYAMLLIB:$GCCLIB:$YACLIB:$YAXTLIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$SOURCE${PYTHONPATH:+:$PYTHONPATH}"
cp "$REFERENCE_CASE/tmp/const2d_config.yaml" "$CONFIG"
"$PYTHON" - "$CONFIG" "$CASE_ROOT/bin/const2d_setup.txt" "$CASE_ROOT/bin/const2d_sol.zarr" "$THREADS" <<'PY'
import sys
from pathlib import Path
from cleopy import editconfigfile

config = Path(sys.argv[1])
setup = Path(sys.argv[2])
zarr = Path(sys.argv[3])
threads = int(sys.argv[4])
editconfigfile.edit_config_params(
    config,
    {"setup_filename": str(setup), "zarrbasedir": str(zarr), "num_threads": threads},
)
PY
grep -Eq "num_threads:[[:space:]]*${THREADS}([[:space:]]|$)" "$CONFIG"

start_epoch=$(date +%s)
"$EXECUTABLE" "$CONFIG"
end_epoch=$(date +%s)
"$PYTHON" "$HOME_ROOT/package/audit_constthermo2d_case_v2.py" \
  --zarr "$CASE_ROOT/bin/const2d_sol.zarr" \
  --output "$CASE_ROOT/trajectory_integrity.json" \
  --expected-initial-supers 61440
{
  printf 'status=passed_model_only_thread_benchmark_not_scientific_comparison\n'
  printf 'threads=%s\nwall_seconds=%s\n' "$THREADS" "$((end_epoch - start_epoch))"
  printf 'reference_case=%s\n' "$REFERENCE_CASE"
  printf 'reference_input_sha256='; sha256sum "$REFERENCE_CASE/share/const2d_dimlessSDsinit.dat" | awk '{print $1}'
  printf 'runtime_config_sha256='; sha256sum "$CONFIG" | awk '{print $1}'
  printf 'executable_sha256='; sha256sum "$EXECUTABLE" | awk '{print $1}'
  printf 'trajectory_integrity_sha256='; sha256sum "$CASE_ROOT/trajectory_integrity.json" | awk '{print $1}'
} > "$CASE_ROOT/thread_benchmark_receipt.txt"
echo "CONSTTHERMO2D_N512_THREAD_BENCHMARK_V2_PASS threads=$THREADS"
