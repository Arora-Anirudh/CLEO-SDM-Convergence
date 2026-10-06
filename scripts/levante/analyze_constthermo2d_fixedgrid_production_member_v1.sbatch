#!/usr/bin/env bash
# One-member streamed reduction of an accepted 2-D constthermo2d trajectory.
# It never modifies raw Zarr output and refuses to overwrite an aggregate.

#SBATCH --job-name=const2d-analyse
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/production-analysis-v1-%j.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/production-analysis-v1-%j.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY="" MPLBACKEND=Agg
: "${NCELL:?submit with NCELL}"
: "${MEMBER:?submit with MEMBER}"
: "${ANALYSIS_LABEL:?submit with ANALYSIS_LABEL}"
readonly HOME_ROOT=/home/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly SCRATCH_ROOT=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly PYTHON=/home/m/m301324/SDM/CLEO/.venv/bin/python3
readonly SCRIPT="$HOME_ROOT/package/analyze_constthermo2d_fixedgrid_production_v1.py"
readonly RAW_ROOT="$SCRATCH_ROOT/production_v1"
readonly OUTPUT_ROOT="$SCRATCH_ROOT/analysis_${ANALYSIS_LABEL}"
test -x "$PYTHON"
test -r "$SCRIPT"
test -d "$RAW_ROOT/ncell$(printf '%04d' "$NCELL")/member$(printf '%03d' "$MEMBER")/bin/const2d_sol.zarr"
test ! -e "$OUTPUT_ROOT/ncell$(printf '%04d' "$NCELL")/member$(printf '%03d' "$MEMBER").npz"
"$PYTHON" "$SCRIPT" --raw-root "$RAW_ROOT" --output-root "$OUTPUT_ROOT" --ncell "$NCELL" --member "$MEMBER"
