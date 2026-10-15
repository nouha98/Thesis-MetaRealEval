#!/bin/bash
# Login-node launcher for one vLLM pilot (one tier x one model).
#
# It does the checks that need no GPU, and only then submits the GPU job:
#   1. creates results_test/<tier>/<model>/ (the isolated pilot directory)
#   2. writes the pilot config there (scripts/make_pilot_config.py, which asserts
#      model id, task bounds, absolute paths and isolation)
#   3. runs the HOST static preflight (scripts/vllm_feasibility.py --mode host):
#      artifact facts, estimates, tensor-parallel necessary conditions. It does
#      NOT check what vLLM supports -- vLLM exists only inside the container, so
#      that is checked later, inside the GPU job, on the allocated GPUs.
#      PREFLIGHT_BLOCKED  -> prints the blockers and STOPS. There is no override:
#                            a blocker is a decision for the thesis author.
#   4. submits scripts/slurm/submit_vllm_pilot.sh with its Slurm stdout/stderr
#      inside the pilot directory (a #SBATCH line cannot name a per-run path).
#
# Run it from anywhere; it changes to the repo root first.
#
# Usage:
#   scripts/slurm/launch_vllm_pilot.sh --tier tier1 --model qwen36-35b \
#       --model-dir /shared/karouin/models/Qwen3.6-35B --gpus 2 \
#       [--stage smoke|pilot] [--tasks 0-2] [--max-model-len 16384] \
#       [--reasoning-parser NAME] [--vllm-extra "--dtype bfloat16"] \
#       [--repo-id ORG/NAME] [--base config/x.yaml] [--time HH:MM:SS] [--no-hash] \
#       [--image /path/to.sif] [--constraint gpumem.80gib] [--mem 32G]
#
# --gpus is the number of GPUs the job will be allocated; the job measures the real
# count (on the host and inside the container) and aborts on a mismatch rather than
# adjusting tensor parallelism on its own. --tp defaults to --gpus.
#
# --stage smoke (default) runs only the server smoke test + raw-response probe.
# --stage pilot runs the smoke test and, only if it passes, the 3-task pipeline.
# Nothing here submits a full evaluation.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_DIR}"

TIER="" MODEL="" MODEL_DIR="" GPUS=1 TP="" STAGE="smoke" TASKS="0-2"
MAX_LEN=16384 PARSER="" EXTRA="" REPO_ID="" BASE="" TIME="04:00:00" NO_HASH=""
IMAGE="/shared/karouin/containers/vllm-v0.17.0.sif" CONSTRAINT="gpumem.80gib" MEM="32G"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tier) TIER="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --model-dir) MODEL_DIR="$2"; shift 2 ;;
        --gpus) GPUS="$2"; shift 2 ;;
        --tp) TP="$2"; shift 2 ;;
        --stage) STAGE="$2"; shift 2 ;;
        --tasks) TASKS="$2"; shift 2 ;;
        --max-model-len) MAX_LEN="$2"; shift 2 ;;
        --reasoning-parser) PARSER="$2"; shift 2 ;;
        --vllm-extra) EXTRA="$2"; shift 2 ;;
        --repo-id) REPO_ID="$2"; shift 2 ;;
        --base) BASE="$2"; shift 2 ;;
        --time) TIME="$2"; shift 2 ;;
        --no-hash) NO_HASH="--no-hash"; shift ;;
        --image) IMAGE="$2"; shift 2 ;;
        --constraint) CONSTRAINT="$2"; shift 2 ;;
        --mem) MEM="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
[[ "${TIER}" == "tier1" || "${TIER}" == "tier2" ]] || { echo "--tier must be tier1 or tier2" >&2; exit 2; }
[[ -n "${MODEL}" && -n "${MODEL_DIR}" ]] || { echo "--model and --model-dir are required" >&2; exit 2; }
[[ "${STAGE}" == "smoke" || "${STAGE}" == "pilot" ]] || { echo "--stage must be smoke or pilot" >&2; exit 2; }
[[ -d "${MODEL_DIR}" ]] || { echo "model dir not found: ${MODEL_DIR} (nothing is downloaded automatically)" >&2; exit 2; }
[[ -f "${IMAGE}" ]] || { echo "container image not found: ${IMAGE}" >&2; exit 2; }
TP="${TP:-${GPUS}}"
if [[ -z "${BASE}" ]]; then
    if [[ "${TIER}" == "tier1" ]]; then BASE="config/default.yaml"; else BASE="config/tier2_realclasseval.yaml"; fi
fi

PY="${REPO_DIR}/.venv/bin/python"
[[ -x "${PY}" ]] || { echo "no interpreter at ${PY}" >&2; exit 2; }

PILOT_DIR="${REPO_DIR}/results_test/${TIER}/${MODEL}"
mkdir -p "${PILOT_DIR}"
export PYTHONPATH="${REPO_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

echo "== 1/3 pilot config =="
"${PY}" scripts/make_pilot_config.py --base "${BASE}" --tier "${TIER}" --model "${MODEL}" --tasks "${TASKS}"

echo "== 2/3 HOST static preflight (no GPU, no vLLM, nothing downloaded) =="
FEAS_ARGS=("${MODEL_DIR}" --mode host --gpus "${GPUS}" --tp "${TP}" --max-model-len "${MAX_LEN}" --out "${PILOT_DIR}/feasibility.json")
[[ -n "${REPO_ID}" ]] && FEAS_ARGS+=(--repo-id "${REPO_ID}")
[[ -n "${NO_HASH}" ]] && FEAS_ARGS+=("${NO_HASH}")
if ! "${PY}" scripts/vllm_feasibility.py "${FEAS_ARGS[@]}" > "${PILOT_DIR}/feasibility.stdout" 2>&1; then
    echo "PREFLIGHT_BLOCKED -- not submitting. Blockers:" >&2
    "${PY}" -c "import json,sys; [print('  -', b) for b in json.load(open(sys.argv[1]))['blockers']]" "${PILOT_DIR}/feasibility.json" >&2 \
        || tail -20 "${PILOT_DIR}/feasibility.stdout" >&2
    echo "Full report: ${PILOT_DIR}/feasibility.json. This needs a decision; there is no override flag." >&2
    exit 3
fi
echo "PREFLIGHT_PASSED (host, static only). vLLM support and GPU facts are checked inside the container in the job; loading is decided by the smoke test."

echo "== 3/3 submit =="
sbatch --parsable \
    --job-name="pilot_${TIER}_${MODEL}" \
    --gres="gpu:${GPUS}" \
    --constraint="${CONSTRAINT}" \
    --mem="${MEM}" \
    --time="${TIME}" \
    --output="${PILOT_DIR}/slurm-%j.out" \
    --error="${PILOT_DIR}/slurm-%j.err" \
    scripts/slurm/submit_vllm_pilot.sh \
    --tier "${TIER}" --model "${MODEL}" --model-dir "${MODEL_DIR}" --gpus "${GPUS}" --tp "${TP}" \
    --stage "${STAGE}" --max-model-len "${MAX_LEN}" --base "${BASE}" --image "${IMAGE}" \
    --reasoning-parser "${PARSER}" --vllm-extra "${EXTRA}"
echo "Pilot dir: ${PILOT_DIR}"
