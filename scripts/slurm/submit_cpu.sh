#!/bin/bash
# CPU-bound job array: one task per SLURM_ARRAY_TASK_ID
#
# Usage: sbatch scripts/slurm/submit_cpu.sh <stage> <phase>
# Example: sbatch --array=0-163 scripts/slurm/submit_cpu.sh rq2 evaluate
#
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --output=logs/slurm_%A_%a.out
#SBATCH --error=logs/slurm_%A_%a.err

set -euo pipefail

STAGE=${1:?Usage: submit_cpu.sh <stage> <phase>}
PHASE=${2:?Usage: submit_cpu.sh <stage> <phase>}

#SBATCH --job-name=mre-${STAGE}-${PHASE}

echo "Job ${SLURM_JOB_ID} array-task ${SLURM_ARRAY_TASK_ID}: ${STAGE} --phase ${PHASE}"

source .venv/bin/activate

python -m meta_real_eval.${STAGE}.runner \
    --config config/default.yaml \
    --phase "${PHASE}" \
    --task-index "${SLURM_ARRAY_TASK_ID}"
