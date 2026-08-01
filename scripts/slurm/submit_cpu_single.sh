set -euo pipefail

STAGE=${1:?Usage: submit_cpu_single.sh <stage> <phase>}
PHASE=${2:?Usage: submit_cpu_single.sh <stage> <phase>}

cd "${SLURM_SUBMIT_DIR}"

# /home/ is not mounted on compute nodes on this cluster, but HuggingFace
# `datasets` defaults its cache to $HOME/.cache. Point it at /shared instead.
export HF_HOME="${SLURM_SUBMIT_DIR}/.cache/huggingface"
mkdir -p "${HF_HOME}"

source .venv/bin/activate

echo "Job ${SLURM_JOB_ID}: ${STAGE} --phase ${PHASE} (CPU single job)"

srun python -m meta_real_eval.${STAGE}.runner \
    --config config/default.yaml \
    --phase "${PHASE}"
