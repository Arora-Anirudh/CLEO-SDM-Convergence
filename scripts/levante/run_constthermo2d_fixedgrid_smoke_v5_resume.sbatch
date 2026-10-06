#!/usr/bin/env bash
# Resume only the model/plot/audit stages of the v4 smoke's successfully
# materialized immutable inputs. V4 never loaded the executable, so no Zarr,
# setup file, plot, audit, or case receipt may pre-exist.

#SBATCH --job-name=const2d-n8-smk5
#SBATCH --partition=shared
#SBATCH --account=mh0731
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/smoke-v5-%j.out
#SBATCH --error=/scratch/m/m301324/SDM/constthermo2d_fixedgrid_baseline_v1/logs/smoke-v5-%j.err

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
readonly BUILD=/home/m/m301324/SDM/cleo_builds/CLEO-v0691-constthermo2d-9224585d-threads-gcc-v4
readonly EXECUTABLE="$BUILD/examples/constthermo2d/src/const2d"
readonly PYTHON=/home/m/m301324/SDM/CLEO/.venv/bin/python3
readonly CASE="$SCRATCH_ROOT/smoke_ncell8_seed2026092401"
readonly FYAMLLIB=/sw/spack-levante/libfyaml-0.7.12-fvbhgo/lib
readonly GCCLIB=/sw/spack-levante/gcc-11.2.0-bcn7mb/lib64
readonly YACLIB=/home/m/m301324/SDM/cleo_dependencies/yacyaxt/gcc/yac/lib
readonly YAXTLIB=/home/m/m301324/SDM/cleo_dependencies/yacyaxt/gcc/yaxt/lib

test -x "$EXECUTABLE"
test -x "$PYTHON"
test -r "$HOME_ROOT/package/audit_constthermo2d_case_v1.py"
test -r "$CASE/tmp/const2d_config.yaml"
test -r "$CASE/share/const2d_dimlessGBxboundaries.dat"
test -r "$CASE/share/const2d_dimlessSDsinit.dat"
test ! -e "$CASE/bin/const2d_sol.zarr"
test ! -e "$CASE/bin/const2d_setup.txt"
test ! -e "$CASE/trajectory_integrity.json"
test ! -e "$CASE/case_receipt.json"
test "$(git -C "$SOURCE" rev-parse HEAD)" = "$EXPECTED_COMMIT"
test -z "$(git -C "$SOURCE" status --porcelain)"
test -r "$FYAMLLIB/libfyaml.so.0"

mkdir -p "$SCRATCH_ROOT/logs"
export OMP_NUM_THREADS="$SLURM_CPUS_PER_TASK"
export OMP_PROC_BIND=spread OMP_PLACES=threads
export LD_LIBRARY_PATH="$FYAMLLIB:$GCCLIB:$YACLIB:$YAXTLIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$SOURCE${PYTHONPATH:+:$PYTHONPATH}"
{
  printf 'repair_scope=model_plot_audit_only\n'
  printf 'seed=2026092401\nsource_commit=%s\n' "$EXPECTED_COMMIT"
  printf 'input_superdrops_sha256='; sha256sum "$CASE/share/const2d_dimlessSDsinit.dat" | awk '{print $1}'
  printf 'runtime_config_sha256='; sha256sum "$CASE/tmp/const2d_config.yaml" | awk '{print $1}'
  printf 'executable_sha256='; sha256sum "$EXECUTABLE" | awk '{print $1}'
  printf 'runtime_libfyaml=%s\n' "$FYAMLLIB/libfyaml.so.0"
} | tee "$CASE/resume_input_receipt.txt"

"$EXECUTABLE" "$CASE/tmp/const2d_config.yaml"
"$PYTHON" "$SOURCE/examples/constthermo2d/constthermo2d_plotting.py" \
  --path2CLEO="$SOURCE" --savefigpath="$CASE/bin" \
  --grid_filename="$CASE/share/const2d_dimlessGBxboundaries.dat" \
  --setupfile="$CASE/bin/const2d_setup.txt" --dataset="$CASE/bin/const2d_sol.zarr"
"$PYTHON" "$HOME_ROOT/package/audit_constthermo2d_case_v1.py" \
  --zarr "$CASE/bin/const2d_sol.zarr" --output "$CASE/trajectory_integrity.json"
test -s "$CASE/bin/const2d_domainmassmoms.png"
test -s "$CASE/bin/const2d_motion2d.png"
test -s "$CASE/trajectory_integrity.json"
{
  cat "$CASE/resume_input_receipt.txt"
  sha256sum "$CASE/trajectory_integrity.json" "$CASE/bin/const2d_domainmassmoms.png" "$CASE/bin/const2d_motion2d.png"
} | tee "$CASE/resume_model_receipt.txt"
echo "CONSTTHERMO2D_N8_SMOKE_RESUME_SUCCESS"
