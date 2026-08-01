#!/bin/bash
# CPU-bound job array: one HumanEval task per SLURM_ARRAY_TASK_ID.
#
# Usage:
#   sbatch --array=0-163 scripts/slurm/submit_cpu.sh stage0
#   sbatch --array=0-163 scripts/slurm/submit_cpu.sh rq2 evaluate
#
#SBATCH --job-name=submit_cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=logs/slurm_%A_%a.out
#SBATCH --error=logs/slurm_%A_%a.err

set -euo pipefail

STAGE=${1:?Usage: submit_cpu.sh <stage> [phase]}
PHASE=${2:-}

export MRE_RUNNER_MODULE="meta_real_eval.${STAGE}.runner"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

TASK_INDEX="${SLURM_ARRAY_TASK_ID:-0}"

if [[ "${STAGE}" == "stage0" ]]; then
    echo "Job ${SLURM_JOB_ID} array-task ${TASK_INDEX}: stage0"
    srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" -m meta_real_eval.stage0.runner \
        --config config/default.yaml \
        --task-index "${TASK_INDEX}"
elif [[ -n "${PHASE}" ]]; then
    echo "Job ${SLURM_JOB_ID} array-task ${TASK_INDEX}: ${STAGE} --phase ${PHASE}"
    srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" -m meta_real_eval.${STAGE}.runner \
        --config config/default.yaml \
        --phase "${PHASE}" \
        --task-index "${TASK_INDEX}"
else
    echo "ERROR: phase required for stage '${STAGE}'" >&2
    exit 1
fi
