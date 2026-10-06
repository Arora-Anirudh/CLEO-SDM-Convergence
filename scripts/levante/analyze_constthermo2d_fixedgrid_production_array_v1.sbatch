#!/usr/bin/env bash
# One task per accepted member in the 240-member fixed-grid production cohort.
# The array cap, rather than intra-member threading, controls concurrency.

#SBATCH --job-name=const2d-aggregate
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:05:00
#SBATCH --array=1-240%20
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/production-aggregate-v1-%A_%a.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/production-aggregate-v1-%A_%a.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY="" MPLBACKEND=Agg
readonly HOME_ROOT=/home/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly SCRATCH_ROOT=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly PYTHON=/home/m/m301324/SDM/CLEO/.venv/bin/python3
readonly PACKAGE_ROOT="$HOME_ROOT/package"
readonly MANIFEST="$PACKAGE_ROOT/constthermo2d_fixedgrid_production_v1.csv"
readonly SCRIPT="$PACKAGE_ROOT/analyze_constthermo2d_fixedgrid_production_v1.py"
readonly RAW_ROOT="$SCRATCH_ROOT/production_v1"
readonly OUTPUT_ROOT="$SCRATCH_ROOT/analysis_production_v1"

test -x "$PYTHON"
test -r "$MANIFEST"
test -r "$SCRIPT"
row=$(awk -F, -v record_no="$SLURM_ARRAY_TASK_ID" 'NR == record_no + 1 {print $1 "," $2 "," $4}' "$MANIFEST")
test -n "$row"
IFS=, read -r NCELL MEMBER EXPECTED_INITIAL <<< "$row"
test "$EXPECTED_INITIAL" -eq $((120 * NCELL))
test -d "$RAW_ROOT/ncell$(printf '%04d' "$NCELL")/member$(printf '%03d' "$MEMBER")/bin/const2d_sol.zarr"
test ! -e "$OUTPUT_ROOT/ncell$(printf '%04d' "$NCELL")/member$(printf '%03d' "$MEMBER").npz"
"$PYTHON" "$SCRIPT" --raw-root "$RAW_ROOT" --output-root "$OUTPUT_ROOT" --ncell "$NCELL" --member "$MEMBER"
printf 'CONSTTHERMO2D_PRODUCTION_AGGREGATE_V1_PASS ncell=%s member=%s\n' "$NCELL" "$MEMBER"
