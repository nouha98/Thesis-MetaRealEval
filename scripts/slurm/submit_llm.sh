#!/bin/bash
# LLM-bound single job: processes all tasks in one async process.
# Rate limiting (requests_per_minute in config) controls Innkube load.
#
# Usage: sbatch scripts/slurm/submit_llm.sh <stage> <phase>
# Example: sbatch scripts/slurm/submit_llm.sh rq2 generate
#
#SBATCH --cpus-per-task=2
#SBATCH --time=24:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

set -euo pipefail

STAGE=${1:?Usage: submit_llm.sh <stage> <phase>}
PHASE=${2:?Usage: submit_llm.sh <stage> <phase>}

#SBATCH --job-name=mre-${STAGE}-${PHASE}

echo "Job ${SLURM_JOB_ID}: ${STAGE} --phase ${PHASE} (LLM-bound, all tasks)"

source .venv/bin/activate

python -m meta_real_eval.${STAGE}.runner \
    --config config/default.yaml \
    --phase "${PHASE}"
