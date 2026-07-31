#!/bin/bash
#SBATCH --job-name=cleo_step_probe
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=4
#SBATCH --cpus-per-task=1
#SBATCH --hint=nomultithread
#SBATCH --mem=3600M
#SBATCH --time=00:10:00

# Verify that a reviewed number of one-rank member-shaped Slurm steps can start
# concurrently inside one allocation. This intentionally runs no CLEO
# executable and writes no model data; it is a scheduler-layout gate for the
# production runner. Four workers remain the default for backwards
# compatibility; larger probes must opt in explicitly.
#
# SPDX-License-Identifier: BSD-3-Clause

set -eo pipefail
unset LC_ALL
source /etc/profile
set -u

EXPECTED_WORKERS="${PARALLEL_PROBE_EXPECTED_WORKERS:-4}"
PROBE_SLEEP_SECONDS="${PARALLEL_PROBE_SLEEP_SECONDS:-20}"
START_WINDOW_SECONDS="${PARALLEL_PROBE_START_WINDOW_SECONDS:-10}"
ACTIVE_USER="${USER:-$(id -un)}"
DEFAULT_SCRATCH_ROOT="/scratch/${ACTIVE_USER:0:1}/${ACTIVE_USER}/SDM"
PROBE_ROOT="${PARALLEL_PROBE_ROOT:-${DEFAULT_SCRATCH_ROOT}/CLEO-SDM-Convergence/probes}"

if [[ ! "${EXPECTED_WORKERS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: PARALLEL_PROBE_EXPECTED_WORKERS must be a positive integer." >&2
  exit 2
fi
if ((SLURM_NTASKS != EXPECTED_WORKERS)); then
  echo "ERROR: expected ${EXPECTED_WORKERS} Slurm tasks, got ${SLURM_NTASKS}." >&2
  exit 2
fi
if [[ ! "${PROBE_SLEEP_SECONDS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: PARALLEL_PROBE_SLEEP_SECONDS must be a positive integer." >&2
  exit 2
fi
if [[ ! "${START_WINDOW_SECONDS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: PARALLEL_PROBE_START_WINDOW_SECONDS must be a positive integer." >&2
  exit 2
fi

probe_directory="${PROBE_ROOT}/parallel_member_layout_job${SLURM_JOB_ID}"
if [[ -e "${probe_directory}" ]]; then
  echo "ERROR: probe directory already exists: ${probe_directory}" >&2
  exit 1
fi
mkdir -p "${probe_directory}"

echo "probe_directory=${probe_directory}"
echo "expected_workers=${EXPECTED_WORKERS}"
echo "probe_sleep_seconds=${PROBE_SLEEP_SECONDS}"
echo "start_window_seconds=${START_WINDOW_SECONDS}"

declare -a worker_pids=()
for ((worker_index = 0; worker_index < EXPECTED_WORKERS; worker_index++)); do
  (
    export PARALLEL_PROBE_WORKER="${worker_index}"
    export PROBE_SLEEP_SECONDS
    srun \
      --exclusive \
      --mem=0 \
      --mpi=pmix_v3 \
      --nodes=1 \
      --ntasks=1 \
      --cpus-per-task=1 \
      --hint=nomultithread \
      bash -c '
        printf "worker=%s\\n" "${PARALLEL_PROBE_WORKER}"
        printf "hostname=%s\\n" "$(hostname)"
        printf "step_id=%s\\n" "${SLURM_STEP_ID:-unknown}"
        printf "start_ns=%s\\n" "$(date +%s%N)"
        sleep "${PROBE_SLEEP_SECONDS}"
        printf "end_ns=%s\\n" "$(date +%s%N)"
      '
  ) >"${probe_directory}/worker_${worker_index}.out" \
    2>"${probe_directory}/worker_${worker_index}.err" &
  worker_pids+=("$!")
done

worker_failure=0
for worker_pid in "${worker_pids[@]}"; do
  if ! wait "${worker_pid}"; then
    worker_failure=1
  fi
done
if ((worker_failure != 0)); then
  echo "ERROR: at least one probe worker failed; inspect ${probe_directory}." >&2
  exit 1
fi

python3 - "${probe_directory}" "${EXPECTED_WORKERS}" "${START_WINDOW_SECONDS}" <<'PY'
import re
import sys
from pathlib import Path

directory = Path(sys.argv[1])
expected_workers = int(sys.argv[2])
window_ns = int(sys.argv[3]) * 1_000_000_000
starts = []

for worker_index in range(expected_workers):
    output = (directory / f"worker_{worker_index}.out").read_text(encoding="utf-8")
    match = re.search(r"^start_ns=(\d+)$", output, flags=re.MULTILINE)
    if match is None:
        raise SystemExit(f"missing start timestamp for worker {worker_index}")
    starts.append(int(match.group(1)))

start_span_ns = max(starts) - min(starts)
print(f"worker_start_span_seconds={start_span_ns / 1_000_000_000:.6f}")
if start_span_ns > window_ns:
    raise SystemExit(
        "workers did not start within the configured concurrency window; "
        f"span={start_span_ns / 1_000_000_000:.6f}s"
    )
PY

if find "${probe_directory}" -name '*.err' -type f -size +0c | grep -q .; then
  echo "ERROR: probe worker stderr is non-empty." >&2
  exit 1
fi

echo "PARALLEL_MEMBER_LAYOUT_PROBE_PASS=1"
