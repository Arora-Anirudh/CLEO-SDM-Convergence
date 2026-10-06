#!/usr/bin/env bash
# Audit-only repair for the completed Ncell=8192 v2 gate trajectory.
# It reads the existing Zarr result in bounded time slices and creates only the
# absent trajectory-integrity receipt; it never reruns initialization or CLEO.

#SBATCH --job-name=const2d-8192-audit
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:30:00
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2/logs/n8192-v2audit-%j.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2/logs/n8192-v2audit-%j.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY="" MPLBACKEND=Agg
set +u
set +e
source /etc/profile
profile_status=$?
set -e
test "$profile_status" -eq 0

readonly HOME_ROOT=/home/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2
readonly SCRATCH_ROOT=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2
readonly PYTHON=/home/m/m301324/SDM/CLEO/.venv/bin/python3
readonly CASE_ROOT="$SCRATCH_ROOT/gate/ncell8192/member001"
readonly OUTPUT="$CASE_ROOT/trajectory_integrity.json"

test -x "$PYTHON"
test -r "$HOME_ROOT/package/audit_constthermo2d_case_streaming_v3.py"
test -d "$CASE_ROOT/bin/const2d_sol.zarr"
test -r "$CASE_ROOT/case_receipt.json"
test ! -e "$OUTPUT"
mkdir -p "$SCRATCH_ROOT/logs"

"$PYTHON" "$HOME_ROOT/package/audit_constthermo2d_case_streaming_v3.py" \
  --zarr "$CASE_ROOT/bin/const2d_sol.zarr" --output "$OUTPUT" \
  --expected-initial-supers 983040
test -s "$OUTPUT"
{
  sha256sum "$HOME_ROOT/package/audit_constthermo2d_case_streaming_v3.py" \
    "$CASE_ROOT/case_receipt.json" "$OUTPUT"
} > "$CASE_ROOT/audit_v3_receipt.txt"
printf 'CONSTTHERMO2D_N8192_RSPAN004TO2_AUDIT_V3_PASS\n'
