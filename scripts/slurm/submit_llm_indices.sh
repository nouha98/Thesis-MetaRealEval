#!/bin/bash
# LLM-bound rerun for a specific list of task indices -- e.g. redoing just the
# tasks recorded in generation_failed.json after a fix, without resubmitting
# the whole corpus. Indices run sequentially inside one job so the async
# client's rate limiter/semaphore stays shared across all of them, unlike a
# SLURM array (--array=...) which would give each index its own independent
# client and could burst past requests_per_minute.
#
# Usage: sbatch scripts/slurm/submit_llm_indices.sh <stage> <phase> [--config path] <idx1> [idx2 ...]
# Example: sbatch scripts/slurm/submit_llm_indices.sh rq1 generate 3 69 75 87 89 92 94 99 111 113 119 150
#
#SBATCH --job-name=submit_llm_indices
#SBATCH --cpus-per-task=2
#SBATCH --time=02:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

set -euo pipefail

USAGE="Usage: submit_llm_indices.sh <stage> <phase> [--config path] <idx1> [idx2 ...]"
STAGE=${1:?${USAGE}}
PHASE=${2:?${USAGE}}
shift 2

CONFIG="config/default.yaml"
if [[ "${1:-}" == "--config" ]]; then
    CONFIG="${2:?--config needs a path}"
    shift 2
fi
INDICES=("$@")
[[ ${#INDICES[@]} -gt 0 ]] || { echo "${USAGE}" >&2; exit 1; }

export MRE_RUNNER_MODULE="meta_real_eval.${STAGE}.runner"
export MRE_CONFIG="${CONFIG}"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

echo "Job ${SLURM_JOB_ID}: ${STAGE} --phase ${PHASE} --force, task indices: ${INDICES[*]}"

for idx in "${INDICES[@]}"; do
    echo "--- task-index ${idx} ---"
    srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" -m meta_real_eval.${STAGE}.runner \
        --config "${CONFIG}" \
        --phase "${PHASE}" \
        --task-index "${idx}" \
        --force
done
