#!/bin/bash
# LLM-bound rerun for a specific list of task indices -- e.g. redoing just the
# tasks recorded in generation_failed.json after a fix, without resubmitting
# the whole corpus. Indices run sequentially inside one job so the async
# client's rate limiter/semaphore stays shared across all of them, unlike a
# SLURM array (--array=...) which would give each index its own independent
# client and could burst past requests_per_minute.
#
# Usage: sbatch scripts/slurm/submit_llm_indices.sh <stage> <phase> <idx1> [idx2 ...]
# Example: sbatch scripts/slurm/submit_llm_indices.sh rq1 generate 3 69 75 87 89 92 94 99 111 113 119 150
#
#SBATCH --job-name=submit_llm_indices
#SBATCH --cpus-per-task=2
#SBATCH --time=02:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

set -euo pipefail

STAGE=${1:?Usage: submit_llm_indices.sh <stage> <phase> <idx1> [idx2 ...]}
PHASE=${2:?Usage: submit_llm_indices.sh <stage> <phase> <idx1> [idx2 ...]}
shift 2
INDICES=("$@")
[[ ${#INDICES[@]} -gt 0 ]] || { echo "Usage: submit_llm_indices.sh <stage> <phase> <idx1> [idx2 ...]" >&2; exit 1; }

export MRE_RUNNER_MODULE="meta_real_eval.${STAGE}.runner"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

echo "Job ${SLURM_JOB_ID}: ${STAGE} --phase ${PHASE} --force, task indices: ${INDICES[*]}"

for idx in "${INDICES[@]}"; do
    echo "--- task-index ${idx} ---"
    srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" -m meta_real_eval.${STAGE}.runner \
        --config config/default.yaml \
        --phase "${PHASE}" \
        --task-index "${idx}" \
        --force
done
