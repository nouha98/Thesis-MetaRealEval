#!/bin/bash
# Login-node launcher for the vLLM generation job of one self-hosted model.
#
#   1. checks the config (exactly this model), the model dir and image
#   2. runs the HOST static preflight (scripts/vllm_feasibility.py --mode host);
#      PREFLIGHT_BLOCKED stops here -- a blocker is a decision, not retried
#   3. submits scripts/slurm/submit_vllm_generate.sh, Slurm logs in <out_dir>/jobs/
#
# Usage (configs from scripts/make_run_configs.py):
#   scripts/slurm/launch_vllm_generate.sh --config config/tier2_runs/pilot_vllm-qwen36.yaml \
#       --model qwen36-35b --model-dir /shared/karouin/models/Qwen3.6-35B-A3B-FP8 --gpus 1 \
#       --reasoning-parser qwen3 --vllm-extra "--language-model-only"
#   scripts/slurm/launch_vllm_generate.sh --config config/tier2_runs/full_vllm-qwen38.yaml \
#       --model qwen38-27b --model-dir /shared/karouin/models/Qwen3.8-27B --gpus 2 \
#       --reasoning-parser qwen3 [--task-range 0-99] [--phases rq1,rq2] [--time 24:00:00]
#
# --max-model-len defaults to 40960: the 32768-token output ceiling plus the
# prompt. For a ceiling trial (make_run_configs.py --max-tokens N) pass
# --max-model-len >= longest prompt + N (e.g. 65536 for N=49152): vLLM rejects a
# request whose prompt + max_tokens exceed it (HTTP 400, recorded as
# context_overflow). Do not pass --generation-config: vLLM's default reads the checkpoint's
# generation_config.json, i.e. the model's own recommended defaults for anything
# the request does not set.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_DIR}"

CONFIG="" MODEL="" MODEL_DIR="" GPUS=1 TP="" MAX_LEN=40960 PARSER="" EXTRA=""
TASK_RANGE="" PHASES="rq1,rq2" TIME="24:00:00"
IMAGE="/shared/karouin/containers/vllm-v0.17.0.sif" CONSTRAINT="gpumem.80gib" MEM="64G"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config) CONFIG="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --model-dir) MODEL_DIR="$2"; shift 2 ;;
        --gpus) GPUS="$2"; shift 2 ;;
        --tp) TP="$2"; shift 2 ;;
        --max-model-len) MAX_LEN="$2"; shift 2 ;;
        --reasoning-parser) PARSER="$2"; shift 2 ;;
        --vllm-extra) EXTRA="$2"; shift 2 ;;
        --task-range) TASK_RANGE="$2"; shift 2 ;;
        --phases) PHASES="$2"; shift 2 ;;
        --time) TIME="$2"; shift 2 ;;
        --image) IMAGE="$2"; shift 2 ;;
        --constraint) CONSTRAINT="$2"; shift 2 ;;
        --mem) MEM="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
[[ -f "${CONFIG}" ]] || { echo "config not found: ${CONFIG}" >&2; exit 2; }
[[ -n "${MODEL}" && -n "${MODEL_DIR}" ]] || { echo "--model and --model-dir are required" >&2; exit 2; }
[[ -d "${MODEL_DIR}" ]] || { echo "model dir not found: ${MODEL_DIR} (nothing is downloaded automatically)" >&2; exit 2; }
[[ -f "${IMAGE}" ]] || { echo "container image not found: ${IMAGE}" >&2; exit 2; }
TP="${TP:-${GPUS}}"

PY="${REPO_DIR}/.venv/bin/python"
[[ -x "${PY}" ]] || { echo "no interpreter at ${PY}" >&2; exit 2; }
export PYTHONPATH="${REPO_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

OUT_DIR="$("${PY}" - "${CONFIG}" "${MODEL}" <<'PYEOF'
import sys
from meta_real_eval.core.config import Config
cfg = Config.from_yaml(sys.argv[1])
if cfg.model_ids() != [sys.argv[2]]:
    sys.exit(f"ERROR: {sys.argv[1]} must list exactly {sys.argv[2]!r} "
             f"(it lists {cfg.model_ids()}); use the model's own group config")
print(cfg.project.output_dir.resolve())
PYEOF
)"
LOG_DIR="${OUT_DIR}/jobs"
mkdir -p "${LOG_DIR}"

echo "== HOST static preflight =="
if ! "${PY}" scripts/vllm_feasibility.py "${MODEL_DIR}" --mode host --gpus "${GPUS}" --tp "${TP}" \
        --max-model-len "${MAX_LEN}" --no-hash --out "${LOG_DIR}/launch_feasibility.json" \
        > "${LOG_DIR}/launch_feasibility.stdout" 2>&1; then
    echo "PREFLIGHT_BLOCKED -- not submitting. See ${LOG_DIR}/launch_feasibility.json" >&2
    exit 3
fi

echo "== submit =="
sbatch --parsable \
    --job-name="generate_${MODEL}" \
    --gres="gpu:${GPUS}" \
    --constraint="${CONSTRAINT}" \
    --mem="${MEM}" \
    --time="${TIME}" \
    --output="${LOG_DIR}/slurm-%j.out" \
    --error="${LOG_DIR}/slurm-%j.err" \
    scripts/slurm/submit_vllm_generate.sh \
    --config "${CONFIG}" --model "${MODEL}" --model-dir "${MODEL_DIR}" --gpus "${GPUS}" --tp "${TP}" \
    --max-model-len "${MAX_LEN}" --image "${IMAGE}" \
    --reasoning-parser "${PARSER}" --vllm-extra "${EXTRA}" \
    --task-range "${TASK_RANGE}" --phases "${PHASES}"
echo "logs: ${LOG_DIR}"
