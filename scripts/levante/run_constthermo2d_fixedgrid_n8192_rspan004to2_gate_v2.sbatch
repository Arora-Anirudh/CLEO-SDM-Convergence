#!/usr/bin/env bash
# Isolated one-member Ncell=8192 gate with physically negligible rspan trimming.
# The failed v1 case is retained under a different root and is never overwritten.

#SBATCH --job-name=const2d-8192-v2gate
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=3G
#SBATCH --time=00:30:00
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2/logs/n8192-v2gate-%j.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2/logs/n8192-v2gate-%j.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY="" MPLBACKEND=Agg
set +u
set +e
source /etc/profile
profile_status=$?
set -e
test "$profile_status" -eq 0
module load git/2.43.7-gcc-11.2.0

readonly NCELL=8192 MEMBER=1 SEED=2026101401 EXPECTED_INITIAL=983040
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
readonly CONFIG="$SCRATCH_ROOT/prepared_configs/ncell8192_rspan004to2.yaml"
readonly CASE_ROOT="$SCRATCH_ROOT/gate/ncell8192/member001"

test -x "$EXECUTABLE"
test -x "$PYTHON"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test -z "$(git -C "$SOURCE" status --porcelain)"
test -r "$BASE_HOME/package/constthermo2d_fixedgrid_baseline_v1.yaml"
test -r "$BASE_HOME/package/run_constthermo2d_seeded_case_v1.py"
test -r "$BASE_HOME/package/audit_constthermo2d_case_v2.py"
test -r "$HOME_ROOT/package/materialize_constthermo2d_resolution_rspan_v2.py"
test ! -e "$CONFIG"
test ! -e "$CASE_ROOT"
mkdir -p "$SCRATCH_ROOT/logs" "$SCRATCH_ROOT/prepared_configs"
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export OMP_PROC_BIND=spread OMP_PLACES=threads
export LD_LIBRARY_PATH="$FYAMLLIB:$GCCLIB:$YACLIB:$YAXTLIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$SOURCE${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON" "$HOME_ROOT/package/materialize_constthermo2d_resolution_rspan_v2.py" \
  --source-config "$BASE_HOME/package/constthermo2d_fixedgrid_baseline_v1.yaml" \
  --output-config "$CONFIG" --nsupers-pergbx "$NCELL" --num-threads "$SLURM_CPUS_PER_TASK" \
  --rspan-min-m 4e-9 --rspan-max-m 2e-6
"$PYTHON" "$BASE_HOME/package/run_constthermo2d_seeded_case_v1.py" \
  --cleo "$SOURCE" --executable "$EXECUTABLE" --source-config "$CONFIG" \
  --case-root "$CASE_ROOT" --seed "$SEED"
"$PYTHON" "$BASE_HOME/package/audit_constthermo2d_case_v2.py" \
  --zarr "$CASE_ROOT/bin/const2d_sol.zarr" --output "$CASE_ROOT/trajectory_integrity.json" \
  --expected-initial-supers "$EXPECTED_INITIAL"
{
  printf 'ncell=%s\nmember=%s\nseed=%s\nexpected_initial=%s\nrspan_m=[4e-9,2e-6]\n' \
    "$NCELL" "$MEMBER" "$SEED" "$EXPECTED_INITIAL"
  sha256sum "$CONFIG" "$CASE_ROOT/case_receipt.json" "$CASE_ROOT/trajectory_integrity.json"
} > "$CASE_ROOT/member_receipt.txt"
printf 'CONSTTHERMO2D_N8192_RSPAN004TO2_GATE_V2_PASS ncell=%s member=%s seed=%s\n' "$NCELL" "$MEMBER" "$SEED"
