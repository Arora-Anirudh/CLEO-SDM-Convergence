#!/usr/bin/env bash
# Exact source-default N_cell=8 smoke. One seeded trajectory; not an ensemble.

#SBATCH --job-name=const2d-n8-smoke
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/smoke-%j.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/smoke-%j.err

set -euo pipefail
export LC_ALL=C ZSH_VERSION="" MPLBACKEND=Agg
source /etc/profile
module load git/2.43.7-gcc-11.2.0

readonly HOME_ROOT=/home/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly SCRATCH_ROOT=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly SOURCE=/home/m/m301324/SDM/CLEO-v0691-constthermo2d-9224585d
readonly EXPECTED_COMMIT=9224585d784e9371926db9d0a23891a4b0241e24
readonly BUILD=/home/m/m301324/SDM/cleo_builds/CLEO-v0691-constthermo2d-9224585d-threads-gcc-v1
readonly EXECUTABLE="$BUILD/examples/constthermo2d/src/const2d"
# The fresh immutable source checkout intentionally contains no environment.
# Reuse only the pre-existing Python environment; PYTHONPATH below resolves
# cleopy/plotcleo from the pinned fresh source, not the old source checkout.
readonly PYTHON=/home/m/m301324/SDM/CLEO/.venv/bin/python3
readonly CASE="$SCRATCH_ROOT/smoke_ncell8_seed2026092401"

test -x "$EXECUTABLE"
test -x "$PYTHON"
test -r "$HOME_ROOT/package/run_constthermo2d_seeded_case_v1.py"
test -r "$HOME_ROOT/package/audit_constthermo2d_case_v1.py"
test -r "$HOME_ROOT/config/constthermo2d_fixedgrid_baseline_v1.yaml"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test -z "$(git -C "$SOURCE" status --porcelain)"
test ! -e "$CASE" || { echo "refusing to reuse smoke case" >&2; exit 2; }

mkdir -p "$SCRATCH_ROOT/logs"
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export PYTHONPATH="$SOURCE${PYTHONPATH:+:$PYTHONPATH}"
"$PYTHON" "$HOME_ROOT/package/run_constthermo2d_seeded_case_v1.py" \
  --cleo "$SOURCE" --executable "$EXECUTABLE" \
  --source-config "$HOME_ROOT/config/constthermo2d_fixedgrid_baseline_v1.yaml" \
  --case-root "$CASE" --seed 2026092401 --plot
"$PYTHON" "$HOME_ROOT/package/audit_constthermo2d_case_v1.py" \
  --zarr "$CASE/bin/const2d_sol.zarr" --output "$CASE/trajectory_integrity.json"
test -s "$CASE/bin/const2d_domainmassmoms.png"
test -s "$CASE/bin/const2d_motion2d.png"
test -s "$CASE/trajectory_integrity.json"
sha256sum "$CASE/case_receipt.json" "$CASE/trajectory_integrity.json" \
  | tee "$CASE/final_sha256s.txt"
echo "CONSTTHERMO2D_N8_SMOKE_SUCCESS"
