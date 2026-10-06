#!/usr/bin/env bash
# Materialise the twelve shared production configurations before any member
# array begins. This serial preparation step eliminates the create-if-absent
# race that concurrent member tasks would otherwise have on a common YAML.

#SBATCH --job-name=const2d-configs
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/production-configs-v1-%j.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/production-configs-v1-%j.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY=""
set +u
set +e
source /etc/profile
profile_status=$?
set -e
test "$profile_status" -eq 0

readonly HOME_ROOT=/home/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly SCRATCH_ROOT=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly PYTHON=/home/m/m301324/SDM/CLEO/.venv/bin/python3
readonly PACKAGE_ROOT="$HOME_ROOT/package"
readonly BASE_CONFIG="$PACKAGE_ROOT/constthermo2d_fixedgrid_baseline_v1.yaml"
readonly MATERIALIZER="$PACKAGE_ROOT/materialize_constthermo2d_resolution_config_v1.py"
readonly CONFIG_ROOT="$SCRATCH_ROOT/prepared_configs_production_v1"

test -x "$PYTHON"
test -r "$BASE_CONFIG"
test -r "$MATERIALIZER"
mkdir -p "$CONFIG_ROOT"
for ncell in 2 4 8 16 32 64 128 256 512 1024 2048 4096; do
  config="$CONFIG_ROOT/ncell${ncell}.yaml"
  if test ! -e "$config"; then
    "$PYTHON" "$MATERIALIZER" --source-config "$BASE_CONFIG" \
      --output-config "$config" --nsupers-pergbx "$ncell" --num-threads 16
  fi
  test -s "$config"
  sha256sum "$config"
done > "$CONFIG_ROOT/production_v1_config_sha256s.txt"
printf 'CONSTTHERMO2D_PRODUCTION_CONFIG_PREFLIGHT_V1_PASS\n'
