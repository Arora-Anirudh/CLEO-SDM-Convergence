#!/usr/bin/env bash
# Compile-only repair v4. The maintained CLEO build helper appends to optional
# unset variables (for example CLEO_CXX_FLAGS), so nounset intentionally stays
# disabled for the helper, following CLEO's own Levante example pattern.

#SBATCH --job-name=const2d-v0691-b4
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=00:40:00
#SBATCH --output=/home/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/build-v4-%j.out
#SBATCH --error=/home/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/build-v4-%j.err

set -eo pipefail
export LC_ALL=C ZSH_VERSION="" HISTCONTROL="" DISPLAY=""
set +u
set +e
source /etc/profile
profile_status=$?
set -e
test "$profile_status" -eq 0
module load git/2.43.7-gcc-11.2.0

readonly ROOT=/home/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1
readonly SOURCE=/home/m/m301324/SDM/CLEO-v0691-constthermo2d-9224585d
readonly EXPECTED_COMMIT=9224585d784e9371926db9d0a23891a4b0241e24
readonly BUILD=/home/m/m301324/SDM/cleo_builds/CLEO-v0691-constthermo2d-9224585d-threads-gcc-v4
readonly YACYAXTROOT=/home/m/m301324/SDM/cleo_dependencies/yacyaxt/gcc

test -d "$SOURCE"
test -r "$YACYAXTROOT/yac/lib/libyac.a"
test -r "$YACYAXTROOT/yaxt/lib/libyaxt.a"
test ! -e "$BUILD" || { echo "refusing to reuse build directory" >&2; exit 2; }
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test -z "$(git -C "$SOURCE" status --porcelain)"

mkdir -p "$ROOT/logs" "$BUILD"
export CLEO_BUILDTYPE=threads
export CLEO_COMPILERNAME=gcc
export CLEO_ENABLEDEBUG=false
export CLEO_PATH2CLEO="$SOURCE"
export CLEO_PATH2BUILD="$BUILD"
export CLEO_YACYAXTROOT="$YACYAXTROOT"
export CLEO_BUILD_FLAGS="-DCLEO_COUPLED_DYNAMICS=fromfile -DCLEO_DOMAIN=cartesian -DCLEO_NO_ROUGHPAPER=ON -DCLEO_NO_PYBINDINGS=ON"
source "$SOURCE/scripts/levante/bash/build_cleo.sh"
cmake --build "$BUILD" --target const2d --parallel "$SLURM_CPUS_PER_TASK"

readonly EXECUTABLE="$BUILD/examples/constthermo2d/src/const2d"
test -x "$EXECUTABLE"
{
  printf 'source_commit=%s\n' "$EXPECTED_COMMIT"
  printf 'build_type=threads\ncompile_cpus=%s\n' "$SLURM_CPUS_PER_TASK"
  printf 'site_profile_gate=HISTCONTROL_and_DISPLAY_defined_nounset_off_for_build_helper\n'
  printf 'v1_failure=site_profile_HISTCONTROL_nounset_before_CMake\n'
  printf 'v2_failure=site_profile_DISPLAY_nounset_before_CMake\n'
  printf 'v3_failure=build_helper_CLEO_CXX_FLAGS_nounset_before_CMake\n'
  sha256sum "$EXECUTABLE"
} | tee "$ROOT/build-v4-receipt-${SLURM_JOB_ID}.txt"
echo "CONSTTHERMO2D_COMPILE_ONLY_SUCCESS"
