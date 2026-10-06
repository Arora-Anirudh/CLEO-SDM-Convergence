#!/usr/bin/env bash
# Run exactly one fresh constthermo2d pilot member.  The calling Slurm script
# owns allocation and module setup; this helper owns only per-member products.

set -eo pipefail

: "${PROJECT_HOME:?PROJECT_HOME is required}"
: "${SOURCE:?SOURCE is required}"
: "${EXECUTABLE:?EXECUTABLE is required}"
: "${PYTHON:?PYTHON is required}"
: "${CASE_ROOT:?CASE_ROOT is required}"
: "${CONFIG_ROOT:?CONFIG_ROOT is required}"
: "${NCELL:?NCELL is required}"
: "${MEMBER:?MEMBER is required}"
: "${SEED:?SEED is required}"
: "${EXPECTED_INITIAL:?EXPECTED_INITIAL is required}"

readonly BASE_CONFIG="$PROJECT_HOME/config/constthermo2d_fixedgrid_baseline_v1.yaml"
readonly MATERIALIZER="$PROJECT_HOME/scripts/materialize_constthermo2d_resolution_config_v1.py"
readonly RUNNER="$PROJECT_HOME/scripts/run_constthermo2d_seeded_case_v1.py"
readonly AUDITOR="$PROJECT_HOME/scripts/audit_constthermo2d_case_v2.py"
readonly CASE_CONFIG="$CONFIG_ROOT/ncell${NCELL}.yaml"

test -x "$PYTHON"
test -x "$EXECUTABLE"
test -r "$BASE_CONFIG"
test -r "$MATERIALIZER"
test -r "$RUNNER"
test -r "$AUDITOR"
test ! -e "$CASE_ROOT"
mkdir -p "$CONFIG_ROOT"

if test ! -e "$CASE_CONFIG"; then
  "$PYTHON" "$MATERIALIZER" \
    --source-config "$BASE_CONFIG" --output-config "$CASE_CONFIG" \
    --nsupers-pergbx "$NCELL" --num-threads "$SLURM_CPUS_PER_TASK"
fi
test -r "$CASE_CONFIG"

"$PYTHON" "$RUNNER" \
  --cleo "$SOURCE" --executable "$EXECUTABLE" --source-config "$CASE_CONFIG" \
  --case-root "$CASE_ROOT" --seed "$SEED"
"$PYTHON" "$AUDITOR" --zarr "$CASE_ROOT/bin/const2d_sol.zarr" \
  --output "$CASE_ROOT/trajectory_integrity.json" \
  --expected-initial-supers "$EXPECTED_INITIAL"
test -s "$CASE_ROOT/case_receipt.json"
test -s "$CASE_ROOT/trajectory_integrity.json"
{
  printf 'ncell=%s\nmember=%s\nseed=%s\nexpected_initial=%s\n' \
    "$NCELL" "$MEMBER" "$SEED" "$EXPECTED_INITIAL"
  sha256sum "$CASE_CONFIG" "$CASE_ROOT/case_receipt.json" "$CASE_ROOT/trajectory_integrity.json"
} > "$CASE_ROOT/member_receipt.txt"
printf 'CONSTTHERMO2D_PILOT_MEMBER_PASS ncell=%s member=%s\n' "$NCELL" "$MEMBER"
