#!/bin/bash
#SBATCH --job-name=sdm_migrate
#SBATCH --account=mh0731
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=02:00:00
#
# Restartable, non-destructive migration of portable SDM data from b383673 to
# m301324. Submit with explicit --output and --error paths.
#
# SPDX-License-Identifier: BSD-3-Clause

set -euo pipefail
umask 027

readonly SOURCE_HOME_ROOT="/home/b/b383673/SDM"
readonly SOURCE_SCRATCH_ROOT="/scratch/b/b383673/SDM"
readonly DEST_HOME_ROOT="/home/m/m301324/SDM"
readonly DEST_SCRATCH_ROOT="/scratch/m/m301324/SDM"
readonly RECORD_ROOT="${DEST_HOME_ROOT}/account_migration/b383673_to_m301324"
readonly RUN_STAMP="${SLURM_JOB_ID:-manual}"
readonly RUN_RECORD_ROOT="${RECORD_ROOT}/job_${RUN_STAMP}"

readonly -a PORTABLE_HOME_NAMES=(
  "CLEO-SDM-Convergence-records"
  "CLEO_convergence"
  "cleo_configs"
  "cleo_convergence_records"
  "cleo_convergence_scripts"
  "cleo_runs"
  "cleo_scripts"
  "trial_box_model"
)

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

tree_file_count() {
  find "$1" -type f -printf '.' | wc -c
}

tree_file_bytes() {
  find "$1" -type f -printf '%s\n' |
    awk '{ total += $1 } END { printf "%.0f\n", total + 0 }'
}

write_tree_inventory() {
  local root="$1"
  local output_prefix="$2"

  printf 'root=%s\n' "${root}" > "${output_prefix}.summary"
  printf 'regular_files=%s\n' "$(tree_file_count "${root}")" >> "${output_prefix}.summary"
  printf 'regular_file_bytes=%s\n' "$(tree_file_bytes "${root}")" >> "${output_prefix}.summary"
  printf 'directories=%s\n' "$(find "${root}" -type d -printf '.' | wc -c)" >> "${output_prefix}.summary"
  printf 'symlinks=%s\n' "$(find "${root}" -type l -printf '.' | wc -c)" >> "${output_prefix}.summary"

  (
    cd "${root}"
    find . -type f -print0 |
      LC_ALL=C sort -z |
      xargs -0 -r sha256sum
  ) > "${output_prefix}.sha256"

  (
    cd "${root}"
    find . -type l -printf '%p -> %l\n' | LC_ALL=C sort
  ) > "${output_prefix}.symlinks"
}

compare_tree_inventories() {
  local source_prefix="$1"
  local dest_prefix="$2"
  local label="$3"

  diff -u \
    <(grep -v '^root=' "${source_prefix}.summary") \
    <(grep -v '^root=' "${dest_prefix}.summary") \
    > "${RUN_RECORD_ROOT}/${label}.summary.diff"
  diff -u \
    "${source_prefix}.sha256" \
    "${dest_prefix}.sha256" \
    > "${RUN_RECORD_ROOT}/${label}.sha256.diff"
  diff -u \
    "${source_prefix}.symlinks" \
    "${dest_prefix}.symlinks" \
    > "${RUN_RECORD_ROOT}/${label}.symlinks.diff"
}

[[ "$(id -un)" == "m301324" ]] ||
  fail "this migration must run as m301324"
[[ "${SLURM_JOB_ACCOUNT:-}" == "mh0731" ]] ||
  fail "expected Slurm account mh0731, got ${SLURM_JOB_ACCOUNT:-unset}"
[[ -r "${SOURCE_HOME_ROOT}" && -x "${SOURCE_HOME_ROOT}" ]] ||
  fail "old HOME SDM root is not readable"
[[ -r "${SOURCE_SCRATCH_ROOT}" && -x "${SOURCE_SCRATCH_ROOT}" ]] ||
  fail "old SCRATCH SDM root is not readable"

mkdir -p \
  "${DEST_HOME_ROOT}" \
  "${DEST_SCRATCH_ROOT}" \
  "${RUN_RECORD_ROOT}"

echo "migration_job_id=${SLURM_JOB_ID:-none}"
echo "migration_account=${SLURM_JOB_ACCOUNT:-none}"
echo "migration_host=$(hostname)"
echo "source_home=${SOURCE_HOME_ROOT}"
echo "source_scratch=${SOURCE_SCRATCH_ROOT}"
echo "destination_home=${DEST_HOME_ROOT}"
echo "destination_scratch=${DEST_SCRATCH_ROOT}"
echo "record_root=${RUN_RECORD_ROOT}"
echo "rsync=$(command -v rsync)"
echo "sha256sum=$(command -v sha256sum)"

printf '%s\n' "${PORTABLE_HOME_NAMES[@]}" \
  > "${RUN_RECORD_ROOT}/portable_home_names.txt"

for name in "${PORTABLE_HOME_NAMES[@]}"; do
  source_path="${SOURCE_HOME_ROOT}/${name}"
  [[ -e "${source_path}" ]] ||
    fail "expected portable HOME source is missing: ${source_path}"

  echo "HOME_TRANSFER_START=${name}"
  rsync \
    --recursive \
    --links \
    --perms \
    --times \
    --partial \
    --human-readable \
    --stats \
    "${source_path}" \
    "${DEST_HOME_ROOT}/"
  echo "HOME_TRANSFER_FINISH=${name}"
done

echo "SCRATCH_TRANSFER_START=${SOURCE_SCRATCH_ROOT}"
rsync \
  --recursive \
  --links \
  --perms \
  --times \
  --partial \
  --human-readable \
  --stats \
  "${SOURCE_SCRATCH_ROOT}/" \
  "${DEST_SCRATCH_ROOT}/"
echo "SCRATCH_TRANSFER_FINISH=${DEST_SCRATCH_ROOT}"

for name in "${PORTABLE_HOME_NAMES[@]}"; do
  source_prefix="${RUN_RECORD_ROOT}/home_${name}.source"
  dest_prefix="${RUN_RECORD_ROOT}/home_${name}.destination"

  echo "HOME_VERIFY_START=${name}"
  write_tree_inventory "${SOURCE_HOME_ROOT}/${name}" "${source_prefix}"
  write_tree_inventory "${DEST_HOME_ROOT}/${name}" "${dest_prefix}"
  compare_tree_inventories "${source_prefix}" "${dest_prefix}" "home_${name}"
  echo "HOME_VERIFY_PASS=${name}"
done

echo "SCRATCH_VERIFY_START=${SOURCE_SCRATCH_ROOT}"
write_tree_inventory \
  "${SOURCE_SCRATCH_ROOT}" \
  "${RUN_RECORD_ROOT}/scratch.source"
write_tree_inventory \
  "${DEST_SCRATCH_ROOT}" \
  "${RUN_RECORD_ROOT}/scratch.destination"
compare_tree_inventories \
  "${RUN_RECORD_ROOT}/scratch.source" \
  "${RUN_RECORD_ROOT}/scratch.destination" \
  "scratch"
echo "SCRATCH_VERIFY_PASS=${DEST_SCRATCH_ROOT}"

{
  echo "MIGRATION_PASS=1"
  echo "source_identity=b383673"
  echo "destination_identity=m301324"
  echo "slurm_account=mh0731"
  echo "slurm_job_id=${SLURM_JOB_ID:-none}"
  echo "completed_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} | tee "${RUN_RECORD_ROOT}/migration_pass.txt"
