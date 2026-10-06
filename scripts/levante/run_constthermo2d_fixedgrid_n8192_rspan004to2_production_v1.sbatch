#!/usr/bin/env bash
# One member of a fresh, independent 20-member Ncell=8192 production cohort.
# No gate, smoke, or earlier completed member is pooled into this array.

#SBATCH --job-name=const2d-8192-prod
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=3G
#SBATCH --time=00:25:00
#SBATCH --array=1-20%20
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2/logs/n8192-production-%A_%a.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2/logs/n8192-production-%A_%a.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY="" MPLBACKEND=Agg
set +u; set +e; source /etc/profile; profile_status=$?; set -e
test "$profile_status" -eq 0
module load git/2.43.7-gcc-11.2.0

readonly NCELL=8192
readonly MEMBER="$SLURM_ARRAY_TASK_ID"
readonly SEED=$((2026101500 + MEMBER))
readonly EXPECTED_INITIAL=983040
readonly HOME_ROOT=/home/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2
readonly SCRATCH_ROOT=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2
readonly BASE_HOME=/home/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly SOURCE=/home/m/m301324/SDM/CLEO-v0691-constthermo2d-9224585d
readonly EXPECTED_COMMIT=9224585d784e9371926db9d0a23891a4b0241e24
readonly BUILD=/home/m/m301324/SDM/cleo_builds/CLEO-v0691-constthermo2d-9224585d-threads-gcc-v4
readonly EXECUTABLE="$BUILD/examples/constthermo2d/src/const2d"
readonly PYTHON=/home/m/m301324/SDM/CLEO/.venv/bin/python3
readonly FYAMLLIB=/sw/spack-levante/libfyaml-0.7.12-fvbhgo/lib
readonly GCCLIB=/sw/spack-levante/gcc-11.2.0-bcn7mb/lib64
readonly YACLIB=/home/m/m301324/SDM/cleo_dependencies/yacyaxt/gcc/yac/lib
readonly YAXTLIB=/home/m/m301324/SDM/cleo_dependencies/yacyaxt/gcc/yaxt/lib
readonly CONFIG="$SCRATCH_ROOT/production_v1/prepared_configs/ncell8192_rspan004to2.yaml"
readonly CASE_ROOT="$SCRATCH_ROOT/production_v1/ncell8192/member$(printf '%03d' "$MEMBER")"

test "$MEMBER" -ge 1; test "$MEMBER" -le 20
test -x "$EXECUTABLE"; test -x "$PYTHON"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test -z "$(git -C "$SOURCE" status --porcelain)"
test -r "$CONFIG"
test -r "$HOME_ROOT/package/audit_constthermo2d_case_streaming_v3.py"
test -r "$BASE_HOME/package/run_constthermo2d_seeded_case_v1.py"
test ! -e "$CASE_ROOT"
mkdir -p "$SCRATCH_ROOT/logs"
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export OMP_PROC_BIND=spread OMP_PLACES=threads
export LD_LIBRARY_PATH="$FYAMLLIB:$GCCLIB:$YACLIB:$YAXTLIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$SOURCE${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON" "$BASE_HOME/package/run_constthermo2d_seeded_case_v1.py" \
  --cleo "$SOURCE" --executable "$EXECUTABLE" --source-config "$CONFIG" \
  --case-root "$CASE_ROOT" --seed "$SEED"
"$PYTHON" "$HOME_ROOT/package/audit_constthermo2d_case_streaming_v3.py" \
  --zarr "$CASE_ROOT/bin/const2d_sol.zarr" --output "$CASE_ROOT/trajectory_integrity.json" \
  --expected-initial-supers "$EXPECTED_INITIAL"
test -s "$CASE_ROOT/case_receipt.json"
test -s "$CASE_ROOT/trajectory_integrity.json"
{
  printf 'ncell=%s\nmember=%s\nseed=%s\nexpected_initial=%s\nrspan_m=[4e-9,2e-6]\n' \
    "$NCELL" "$MEMBER" "$SEED" "$EXPECTED_INITIAL"
  sha256sum "$CONFIG" "$CASE_ROOT/case_receipt.json" "$CASE_ROOT/trajectory_integrity.json"
} > "$CASE_ROOT/member_receipt.txt"
printf 'CONSTTHERMO2D_N8192_RSPAN004TO2_PRODUCTION_MEMBER_V1_PASS ncell=%s member=%s seed=%s\n' "$NCELL" "$MEMBER" "$SEED"
