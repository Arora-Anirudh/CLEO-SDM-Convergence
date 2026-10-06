#!/usr/bin/env bash
# Native-input-only resolution gate. No CLEO executable is called here.

#SBATCH --job-name=const2d-inputgate
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/input-preflight-v1-%j.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/input-preflight-v1-%j.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY="" MPLBACKEND=Agg
set +u
set +e
source /etc/profile
profile_status=$?
set -e
test "$profile_status" -eq 0
module load git/2.43.7-gcc-11.2.0

readonly HOME_ROOT=/home/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly SCRATCH_ROOT=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly SOURCE=/home/m/m301324/SDM/CLEO-v0691-constthermo2d-9224585d
readonly EXPECTED_COMMIT=9224585d784e9371926db9d0a23891a4b0241e24
readonly PYTHON=/home/m/m301324/SDM/CLEO/.venv/bin/python3
readonly BASE_CONFIG="$HOME_ROOT/package/constthermo2d_fixedgrid_baseline_v1.yaml"
readonly MATERIALIZER="$HOME_ROOT/package/materialize_constthermo2d_resolution_config_v1.py"
readonly GENERATOR="$HOME_ROOT/package/generate_constthermo2d_seeded_input_v1.py"
readonly CONFIG_ROOT="$SCRATCH_ROOT/prepared_configs_input_preflight_v1"
readonly CASE_PARENT="$SCRATCH_ROOT/input_preflight_v1"

test -x "$PYTHON"
test -r "$BASE_CONFIG"
test -r "$MATERIALIZER"
test -r "$GENERATOR"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test -z "$(git -C "$SOURCE" status --porcelain)"
mkdir -p "$SCRATCH_ROOT/logs"
export PYTHONPATH="$SOURCE${PYTHONPATH:+:$PYTHONPATH}"

for row in '2 2026092402 240' '4 2026092404 480'; do
  read -r ncell seed expected <<< "$row"
  config="$CONFIG_ROOT/ncell${ncell}.yaml"
  case_root="$CASE_PARENT/ncell$(printf '%04d' "$ncell")_seed${seed}"
  test ! -e "$config"
  test ! -e "$case_root"
  "$PYTHON" "$MATERIALIZER" --source-config "$BASE_CONFIG" --output-config "$config" \
    --nsupers-pergbx "$ncell" --num-threads 1
  "$PYTHON" "$GENERATOR" --cleo "$SOURCE" --source-config "$config" --case-root "$case_root" \
    --seed "$seed" --nsupers-pergbx "$ncell" --expected-initial-supers "$expected"
  test -s "$case_root/input_receipt.json"
done
echo "CONSTTHERMO2D_INPUT_PREFLIGHT_V1_PASS"
