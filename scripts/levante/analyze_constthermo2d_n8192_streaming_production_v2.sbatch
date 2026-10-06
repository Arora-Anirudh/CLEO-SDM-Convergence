#!/usr/bin/env bash
# Stream compact diagnostics for all 20 accepted Ncell=8192 production members.
# It reads raw Zarr stores only and refuses to overwrite any compact output.

#SBATCH --job-name=const2d-8192-agg
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --array=1-20%20
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2/logs/n8192-aggregate-production-%A_%a.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2/logs/n8192-aggregate-production-%A_%a.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY="" MPLBACKEND=Agg
set +u; set +e; source /etc/profile; profile_status=$?; set -e
test "$profile_status" -eq 0

readonly MEMBER="$SLURM_ARRAY_TASK_ID"
readonly HOME_ROOT=/home/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2
readonly SCRATCH_ROOT=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2
readonly PYTHON=/home/m/m301324/SDM/CLEO/.venv/bin/python3
readonly SCRIPT="$HOME_ROOT/package/analyze_constthermo2d_member_streaming_v2.py"
readonly RAW_ROOT="$SCRATCH_ROOT/production_v1"
readonly OUTPUT_ROOT="$SCRATCH_ROOT/analysis_production_v2"

test "$MEMBER" -ge 1; test "$MEMBER" -le 20
test -x "$PYTHON"; test -r "$SCRIPT"
test -d "$RAW_ROOT/ncell8192/member$(printf '%03d' "$MEMBER")/bin/const2d_sol.zarr"
test -r "$RAW_ROOT/ncell8192/member$(printf '%03d' "$MEMBER")/trajectory_integrity.json"
test ! -e "$OUTPUT_ROOT/ncell8192/member$(printf '%03d' "$MEMBER").npz"
"$PYTHON" "$SCRIPT" --raw-root "$RAW_ROOT" --output-root "$OUTPUT_ROOT" --ncell 8192 --member "$MEMBER"
test -s "$OUTPUT_ROOT/ncell8192/member$(printf '%03d' "$MEMBER").npz"
test -s "$OUTPUT_ROOT/ncell8192/member$(printf '%03d' "$MEMBER").json"
printf 'CONSTTHERMO2D_N8192_STREAMING_PRODUCTION_AGGREGATION_V2_PASS member=%s\n' "$MEMBER"
