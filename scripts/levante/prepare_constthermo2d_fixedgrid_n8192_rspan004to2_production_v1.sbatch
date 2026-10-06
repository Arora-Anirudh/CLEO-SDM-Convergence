#!/usr/bin/env bash
# Materialise the single immutable configuration required by the fresh
# Ncell=8192 v2-support production cohort before its 20-member array begins.

#SBATCH --job-name=const2d-8192-prep
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2/logs/n8192-production-prep-%j.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2/logs/n8192-production-prep-%j.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY="" MPLBACKEND=Agg
set +u; set +e; source /etc/profile; profile_status=$?; set -e
test "$profile_status" -eq 0

readonly HOME_ROOT=/home/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2
readonly SCRATCH_ROOT=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_highres_v2
readonly BASE_HOME=/home/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly PYTHON=/home/m/m301324/SDM/CLEO/.venv/bin/python3
readonly CONFIG="$SCRATCH_ROOT/production_v1/prepared_configs/ncell8192_rspan004to2.yaml"

test -x "$PYTHON"
test -r "$HOME_ROOT/package/materialize_constthermo2d_resolution_rspan_v2.py"
test -r "$BASE_HOME/package/constthermo2d_fixedgrid_baseline_v1.yaml"
test ! -e "$CONFIG"
mkdir -p "$SCRATCH_ROOT/logs" "$SCRATCH_ROOT/production_v1/prepared_configs"
"$PYTHON" "$HOME_ROOT/package/materialize_constthermo2d_resolution_rspan_v2.py" \
  --source-config "$BASE_HOME/package/constthermo2d_fixedgrid_baseline_v1.yaml" \
  --output-config "$CONFIG" --nsupers-pergbx 8192 --num-threads 16 \
  --rspan-min-m 4e-9 --rspan-max-m 2e-6
sha256sum "$CONFIG" > "$SCRATCH_ROOT/production_v1/prepared_configs/ncell8192_rspan004to2.sha256"
printf 'CONSTTHERMO2D_N8192_RSPAN004TO2_PRODUCTION_CONFIG_PREFLIGHT_V1_PASS\n'
