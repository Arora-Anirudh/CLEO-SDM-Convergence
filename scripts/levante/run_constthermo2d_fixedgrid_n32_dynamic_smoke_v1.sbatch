#!/usr/bin/env bash
# First dynamic-resolution full-physics gate: one Ncell=32 member only.

#SBATCH --job-name=const2d-n32-gate
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/n32-dynamic-gate-v1-%j.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/n32-dynamic-gate-v1-%j.err

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
test -r "$HOME_ROOT/package/run_constthermo2d_pilot_member_v1.sh"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test -z "$(git -C "$SOURCE" status --porcelain)"
mkdir -p "$SCRATCH_ROOT/logs"
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export OMP_PROC_BIND=spread OMP_PLACES=threads
export LD_LIBRARY_PATH="$FYAMLLIB:$GCCLIB:$YACLIB:$YAXTLIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$SOURCE${PYTHONPATH:+:$PYTHONPATH}"
export PROJECT_HOME="$HOME_ROOT/package" SOURCE EXECUTABLE PYTHON
export CONFIG_ROOT="$SCRATCH_ROOT/prepared_configs_pilot_v1"
export CASE_ROOT="$SCRATCH_ROOT/pilot_v1/ncell0032/member001"
export NCELL=32 MEMBER=1 SEED=2026092601 EXPECTED_INITIAL=3840
bash "$HOME_ROOT/package/run_constthermo2d_pilot_member_v1.sh"
echo "CONSTTHERMO2D_N32_DYNAMIC_GATE_V1_PASS"
