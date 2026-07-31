#!/bin/bash
# CPU-bound single job (no array). Used for cross-task aggregation steps.
#
# Usage:
#   sbatch scripts/slurm/submit_cpu_single.sh rq4 analyze
#
#SBATCH --cpus-per-task=2
#SBATCH --time=01:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

set -euo pipefail

STAGE=${1:?Usage: submit_cpu_single.sh <stage> <phase>}
PHASE=${2:?Usage: submit_cpu_single.sh <stage> <phase>}

echo "Job ${SLURM_JOB_ID}: ${STAGE} --phase ${PHASE} (CPU single job)"

source .venv/bin/activate

python -m meta_real_eval.${STAGE}.runner \
    --config config/default.yaml \
    --phase "${PHASE}"
