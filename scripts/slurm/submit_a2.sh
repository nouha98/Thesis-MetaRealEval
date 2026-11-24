#!/bin/bash
# CPU (array) job: Stage 4 A2 hidden tests -- build, admit, control (plan rev. 9.3). No model is called.
#
# Usage (login node, repo root):
#   development pilot (after G2 passed), one job per cover_k to tune (then also held-out detection):
#     sbatch --array=0-0 scripts/slurm/submit_a2.sh --tasks dev --cover-k 3 \
#         --witness results_tier2_ext/witness/dev_pilot_freia --out results_tier2_ext/a2/dev_pilot_k3
#   evaluation tasks (after the full witness run and its --summarise):
#     sbatch --array=0-7 scripts/slurm/submit_a2.sh --tasks eval --cover-k <FROZEN_K> \
#         --witness results_tier2_ext/witness/full --out results_tier2_ext/a2/full
#     sbatch --dependency=afterok:<ARRAY_JOB_ID> scripts/slurm/submit_a2.sh --out results_tier2_ext/a2/full --summarise
#
#SBATCH --job-name=a2
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=08:00:00
#SBATCH --output=logs/slurm_%A_%a.out
#SBATCH --error=logs/slurm_%A_%a.err

set -euo pipefail

CONFIG="config/tier2_extensions.yaml"
OUT=""
WITNESS=""
TASKS="dev"
SUMMARISE=0
COVER_K=1
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config) CONFIG="${2:?}"; shift 2 ;;
        --cover-k) COVER_K="${2:?}"; shift 2 ;;
        --out) OUT="${2:?}"; shift 2 ;;
        --witness) WITNESS="${2:?}"; shift 2 ;;
        --tasks) TASKS="${2:?}"; shift 2 ;;
        --summarise) SUMMARISE=1; shift ;;
        *) echo "unknown argument $1" >&2; exit 2 ;;
    esac
done
[[ -n "${OUT}" ]] || { echo "ERROR: --out is required" >&2; exit 2; }

export MRE_RUNNER_MODULE="meta_real_eval.stage0.runner"
export MRE_CONFIG="${CONFIG}"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

if [[ "${SUMMARISE}" == 1 ]]; then
    srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/build_a2.py --config "${CONFIG}" --out "${OUT}" --summarise
    exit 0
fi
[[ -n "${WITNESS}" ]] || { echo "ERROR: --witness <Stage 2 results> is required" >&2; exit 2; }
SHARD="${SLURM_ARRAY_TASK_ID:-0}"
SHARDS="${SLURM_ARRAY_TASK_COUNT:-1}"
echo "Job ${SLURM_JOB_ID:-local} shard ${SHARD}/${SHARDS}: A2 ${TASKS} -> ${OUT}"
"${PY}" -c "import hypothesis; assert hypothesis.__version__ == '6.170.15', hypothesis.__version__"
srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/build_a2.py --config "${CONFIG}" --tasks ${TASKS} \
    --witness "${WITNESS}" --out "${OUT}" --shard "${SHARD}" --shards "${SHARDS}" --cover-k "${COVER_K}"
if [[ "${TASKS}" == "dev" ]]; then      # tuning input on development tasks only (plan D5)
    srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/eval_heldout.py --config "${CONFIG}" \
        --witness "${WITNESS}" --hidden "${OUT}" --out "${OUT}/heldout.json" --workers "${SLURM_CPUS_PER_TASK:-4}"
fi
