#!/usr/bin/env bash
# Fresh internally consistent small 2-D resolution pilot. Each array task uses
# one MPI rank and 16 Kokkos Threads, running three members serially. The
# earlier 8-thread Ncell=32/512 trajectories remain execution gates only and
# are deliberately excluded from this cohort.

#SBATCH --job-name=const2d-pilot
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --array=0-3%4
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/pilot-remaining-v1-%A_%a.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/pilot-remaining-v1-%A_%a.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY="" MPLBACKEND=Agg
set +u
set +e
source /etc/profile
profile_status=$?
set -e
test "$profile_status" -eq 0
module load git/2.43.7-gcc-11.2.0

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

test -x "$EXECUTABLE"
test -x "$PYTHON"
test -r "$HOME_ROOT/package/run_constthermo2d_pilot_member_v2.sh"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test -z "$(git -C "$SOURCE" status --porcelain)"
mkdir -p "$SCRATCH_ROOT/logs"
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export OMP_PROC_BIND=spread OMP_PLACES=threads
export LD_LIBRARY_PATH="$FYAMLLIB:$GCCLIB:$YACLIB:$YAXTLIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$SOURCE${PYTHONPATH:+:$PYTHONPATH}"
export PACKAGE_ROOT="$HOME_ROOT/package" SOURCE EXECUTABLE PYTHON
export CONFIG_ROOT="$SCRATCH_ROOT/prepared_configs_pilot_v3_16threads"

case "$SLURM_ARRAY_TASK_ID" in
  0) members=('8 1 2026092501 960' '8 2 2026092502 960' '8 3 2026092503 960') ;;
  1) members=('32 1 2026092601 3840' '32 2 2026092602 3840' '32 3 2026092603 3840') ;;
  2) members=('128 1 2026092701 15360' '128 2 2026092702 15360' '128 3 2026092703 15360') ;;
  3) members=('512 1 2026092801 61440' '512 2 2026092802 61440' '512 3 2026092803 61440') ;;
  *) echo "invalid array task: $SLURM_ARRAY_TASK_ID" >&2; exit 2 ;;
esac

for row in "${members[@]}"; do
  read -r NCELL MEMBER SEED EXPECTED_INITIAL <<< "$row"
  export NCELL MEMBER SEED EXPECTED_INITIAL
  export CASE_ROOT="$SCRATCH_ROOT/pilot_v3_16threads/ncell$(printf '%04d' "$NCELL")/member$(printf '%03d' "$MEMBER")"
  bash "$HOME_ROOT/package/run_constthermo2d_pilot_member_v2.sh"
done
printf 'CONSTTHERMO2D_PILOT_REMAINING_V1_PASS array_task=%s\n' "$SLURM_ARRAY_TASK_ID"
