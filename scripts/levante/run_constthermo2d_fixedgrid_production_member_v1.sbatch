#!/usr/bin/env bash
# One independently seeded member of the fixed-grid 2-D constthermo2d
# convergence cohort. Submission supplies NCELL, WALLTIME and array member.
# The package wrapper provides materialisation, native input generation,
# simulation, and a per-case trajectory-integrity audit.

#SBATCH --job-name=const2d-prod
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=2G
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/production-v1-%A_%a.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/production-v1-%A_%a.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY="" MPLBACKEND=Agg
set +u
set +e
source /etc/profile
profile_status=$?
set -e
test "$profile_status" -eq 0
module load git/2.43.7-gcc-11.2.0

: "${NCELL:?submit with --export=ALL,NCELL=<resolution>}"
: "${EXPECTED_INITIAL:?submit with --export=ALL,EXPECTED_INITIAL=<120*ncell>}"
readonly MEMBER="$SLURM_ARRAY_TASK_ID"
test "$MEMBER" -ge 1
test "$MEMBER" -le 20

# 12 resolution blocks, 20 deterministic but independent input seeds each.
case "$NCELL" in
  2) resolution_index=1 ;; 4) resolution_index=2 ;; 8) resolution_index=3 ;;
  16) resolution_index=4 ;; 32) resolution_index=5 ;; 64) resolution_index=6 ;;
  128) resolution_index=7 ;; 256) resolution_index=8 ;; 512) resolution_index=9 ;;
  1024) resolution_index=10 ;; 2048) resolution_index=11 ;; 4096) resolution_index=12 ;;
  *) echo "unsupported NCELL=$NCELL" >&2; exit 2 ;;
esac
readonly SEED=$((2026100000 + resolution_index * 100 + MEMBER))

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
export PACKAGE_ROOT="$HOME_ROOT/package" SOURCE EXECUTABLE PYTHON NCELL MEMBER SEED EXPECTED_INITIAL
export CONFIG_ROOT="$SCRATCH_ROOT/prepared_configs_production_v1"
export CASE_ROOT="$SCRATCH_ROOT/production_v1/ncell$(printf '%04d' "$NCELL")/member$(printf '%03d' "$MEMBER")"

# Production configurations are materialised once by the separate preflight
# job.  Requiring their presence here prevents an array-wide create-if-absent
# race, while the underlying case wrapper preserves its immutable-case guard.
test -r "$CONFIG_ROOT/ncell${NCELL}.yaml"
bash "$HOME_ROOT/package/run_constthermo2d_pilot_member_v2.sh"
printf 'CONSTTHERMO2D_PRODUCTION_MEMBER_V1_PASS ncell=%s member=%s seed=%s\n' "$NCELL" "$MEMBER" "$SEED"
