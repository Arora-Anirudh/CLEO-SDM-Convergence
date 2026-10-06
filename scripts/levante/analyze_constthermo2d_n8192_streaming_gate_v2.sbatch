#!/usr/bin/env bash
# One-member aggregation gate for the 8192-SD extension. It reads the completed
# trajectory without modifying it and writes a compact aggregate elsewhere.

#SBATCH --job-name=const2d-8192-agg
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2/logs/n8192-aggregate-gate-%j.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2/logs/n8192-aggregate-gate-%j.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY="" MPLBACKEND=Agg
set +u; set +e; source /etc/profile; profile_status=$?; set -e
test "$profile_status" -eq 0

readonly HOME_ROOT=/home/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2
readonly SCRATCH_ROOT=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2
readonly PYTHON=/home/m/m301324/SDM/CLEO/.venv/bin/python3
readonly SCRIPT="$HOME_ROOT/package/analyze_constthermo2d_member_streaming_v2.py"
readonly RAW_ROOT="$SCRATCH_ROOT/production_v1"
readonly OUTPUT_ROOT="$SCRATCH_ROOT/analysis_gate_v2"

test -x "$PYTHON"; test -r "$SCRIPT"
test -d "$RAW_ROOT/ncell8192/member001/bin/const2d_sol.zarr"
test -r "$RAW_ROOT/ncell8192/member001/trajectory_integrity.json"
test ! -e "$OUTPUT_ROOT/ncell8192/member001.npz"
"$PYTHON" "$SCRIPT" --raw-root "$RAW_ROOT" --output-root "$OUTPUT_ROOT" --ncell 8192 --member 1
test -s "$OUTPUT_ROOT/ncell8192/member001.npz"
test -s "$OUTPUT_ROOT/ncell8192/member001.json"
printf 'CONSTTHERMO2D_N8192_STREAMING_AGGREGATION_GATE_V2_PASS\n'
