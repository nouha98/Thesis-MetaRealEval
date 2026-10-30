#!/bin/bash
# GPU job: serve ONE model with vLLM (through the project's Apptainer image) and
# validate it via the project's own client/pipeline, writing only to
# results_test/<tier>/<model>/.
# Submit through scripts/slurm/launch_vllm_pilot.sh: it prepares the pilot dir and
# config, runs the HOST static preflight, and sets --gres, --time, --mem, the
# constraint and the Slurm log paths.
#
# Order inside the job (each gate stops the job and records a FAIL verdict):
#   1. GPU count: host nvidia-smi == requested --gpus, and the same count is
#      visible inside the container (`--nv`), and --tp <= count
#   2. container-side preflight (vllm_feasibility.py --mode container, run inside
#      the image on the allocated GPUs)
#   3. start `vllm serve` in the container; wait for readiness
#   4. scripts/vllm_probe.py: SERVER_SMOKE + RESPONSE_FORMAT
#   5. --stage pilot only: rq2 generate + evaluate on the pilot config's tasks
#
# The Python client / pipeline run on the HOST (.venv); only the server and the
# container preflight run inside the image. This job never runs a full evaluation.
#
#SBATCH --job-name=vllm_pilot
#SBATCH --account=chair-se2
#SBATCH --partition=gpu
#SBATCH --constraint=gpumem.80gib
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err
# (--constraint/--gres/--mem/--time/--output/--error above are defaults; the launcher overrides them.)

set -uo pipefail     # no -e: gates are checked explicitly so cleanup and reporting always run

TIER="" MODEL="" MODEL_DIR="" GPUS=1 TP="" STAGE="smoke" MAX_LEN=40960 BASE="" PARSER="" EXTRA="" IMAGE=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --tier) TIER="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --model-dir) MODEL_DIR="$2"; shift 2 ;;
        --gpus) GPUS="$2"; shift 2 ;;
        --tp) TP="$2"; shift 2 ;;
        --stage) STAGE="$2"; shift 2 ;;
        --max-model-len) MAX_LEN="$2"; shift 2 ;;
        --base) BASE="$2"; shift 2 ;;
        --image) IMAGE="$2"; shift 2 ;;
        --reasoning-parser) PARSER="$2"; shift 2 ;;
        --vllm-extra) EXTRA="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
: "${TIER:?}" "${MODEL:?}" "${MODEL_DIR:?}" "${BASE:?}" "${IMAGE:?}"
TP="${TP:-${GPUS}}"

# Preflight, HOME/cache redirection and TRITON_CACHE_DIR come from _common.sh.
# It runs from the repo root so its relative paths stay valid.
export MRE_RUNNER_MODULE="meta_real_eval.rq2.runner"
export MRE_CONFIG="${BASE}"
SCRIPT_ROOT="${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}"
source "${SCRIPT_ROOT}/scripts/slurm/_common.sh"
source "${REPO_DIR}/scripts/slurm/_vllm_container.sh"

PILOT_DIR="${REPO_DIR}/results_test/${TIER}/${MODEL}"
[[ -f "${PILOT_DIR}/config.yaml" ]] || { echo "ERROR: ${PILOT_DIR}/config.yaml missing; use launch_vllm_pilot.sh" >&2; exit 2; }
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mkdir -p "${REPO_DIR}/.cache/container_home"
echo "pilot dir:   ${PILOT_DIR}"
echo "image:       ${IMAGE}"
echo "TRITON_CACHE_DIR=${TRITON_CACHE_DIR}"

SERVER_PID=""
cleanup() { [[ -n "${SERVER_PID}" ]] && kill "${SERVER_PID}" 2>/dev/null && wait "${SERVER_PID}" 2>/dev/null; }
trap cleanup EXIT

# Record a failed gate as a verdict (FAIL, not NOT_RUN), write the report, exit.
fail_gate() {   # fail_gate <check-name> <message>
    echo "GATE FAILED: $1: $2" >&2
    "${PY}" -c "import json,sys; json.dump({'checks': {sys.argv[2]: 'FAIL: ' + sys.argv[3]}}, open(sys.argv[1], 'w'))" \
        "${PILOT_DIR}/probe.json" "$1" "$2"
    ( cd "${PILOT_DIR}" && "${PY}" "${REPO_DIR}/scripts/pilot_report.py" "${PILOT_DIR}" >/dev/null 2>&1 ) || true
    exit 1
}

command -v apptainer >/dev/null 2>&1 || fail_gate apptainer "apptainer not found on this node"
[[ -f "${IMAGE}" ]] || fail_gate image "image not found: ${IMAGE}"
[[ -d "${MODEL_DIR}" ]] || fail_gate model_dir "model dir not found: ${MODEL_DIR}"

# --- bind/args: every container call below uses the same bindings ------------
mre_apptainer_args "${IMAGE}" "${MODEL_DIR}" "${REPO_DIR}" "${PILOT_DIR}"
echo "apptainer ${APPTAINER_ARGS[*]}"

# --- Gate 1: GPU count, measured, host and container -------------------------
HOST_GPUS="$(mre_count_gpus)"
CONT_GPUS="$(mre_count_gpus apptainer exec --nv "${IMAGE}" nvidia-smi)"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}  host GPUs=${HOST_GPUS}  container GPUs=${CONT_GPUS}  requested=${GPUS}  tp=${TP}"
nvidia-smi -L | tee "${PILOT_DIR}/gpus_host.txt"
[[ "${HOST_GPUS}" == "${GPUS}" ]] || fail_gate gpu_count "allocated GPUs (${HOST_GPUS}) != requested --gpus (${GPUS}); not guessing, resubmit with the right --gpus"
[[ "${CONT_GPUS}" == "${HOST_GPUS}" ]] || fail_gate gpu_in_container "container sees ${CONT_GPUS} GPU(s), host has ${HOST_GPUS} (is --nv working?)"
(( TP <= HOST_GPUS )) || fail_gate tensor_parallel "tp=${TP} > allocated GPUs ${HOST_GPUS}"

# --- Gate 2: container-side preflight (what this image's vLLM says) ----------
CPF_ARGS=("${MRE_CONTAINER_MODEL_PATH}" --mode container --gpus "${HOST_GPUS}" --tp "${TP}"
          --max-model-len "${MAX_LEN}" --no-hash --out "${PILOT_DIR}/feasibility_container.json")
[[ -n "${PARSER}" ]] && CPF_ARGS+=(--reasoning-parser "${PARSER}")
apptainer "${APPTAINER_ARGS[@]}" python3 "${MRE_CONTAINER_SCRIPTS_PATH}/vllm_feasibility.py" "${CPF_ARGS[@]}" \
    > "${PILOT_DIR}/feasibility_container.stdout" 2> "${PILOT_DIR}/feasibility_container.stderr"
CPF_RC=$?
if [[ "${CPF_RC}" != "0" ]]; then
    echo "container preflight: PREFLIGHT_BLOCKED (rc=${CPF_RC})"
    "${PY}" -c "import json,sys; d=json.load(open(sys.argv[1])); [print('  -', b) for b in d['blockers']]" \
        "${PILOT_DIR}/feasibility_container.json" 2>/dev/null || tail -20 "${PILOT_DIR}/feasibility_container.stderr"
    fail_gate container_preflight "see ${PILOT_DIR}/feasibility_container.json (a decision is needed; not retrying or substituting)"
fi
echo "container preflight: PREFLIGHT_PASSED (static + registry only; runtime is decided by the smoke test)"

# --- isolation baseline ------------------------------------------------------
snapshot() {   # production paths only: file count + newest mtime
    for d in cache/llm_responses results_tier1 results_tier2 logs; do
        printf '%s files=%s newest=%s\n' "$d" \
            "$(find "${REPO_DIR}/$d" -type f 2>/dev/null | wc -l)" \
            "$(find "${REPO_DIR}/$d" -type f -printf '%T@\n' 2>/dev/null | sort -n | tail -1)"
    done
}
echo "== isolation: jobs of mine currently running =="
squeue -u "${USER}" -h -o '%i %j %T' | tee "${PILOT_DIR}/isolation_squeue.txt"
OTHER_JOBS=$(grep -vc "^${SLURM_JOB_ID} " "${PILOT_DIR}/isolation_squeue.txt" || true)
[[ "${OTHER_JOBS}" != "0" ]] && echo "WARNING: ${OTHER_JOBS} other job(s) running; a production-path change below may not be ours."
snapshot > "${PILOT_DIR}/isolation_before.txt"
TRITON_BEFORE=$(find "${TRITON_CACHE_DIR}" -type f 2>/dev/null | wc -l)

# --- Gate 3: server ----------------------------------------------------------
PORT=$("${PY}" -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1])")
mre_server_args "${MODEL}" "${PORT}" "${TP}" "${MAX_LEN}" "${PARSER}" "${EXTRA}"
echo "server: apptainer ${APPTAINER_ARGS[*]} ${SERVER_ARGS[*]}"
apptainer "${APPTAINER_ARGS[@]}" "${SERVER_ARGS[@]}" > "${PILOT_DIR}/server.log" 2>&1 &
SERVER_PID=$!

READY_TIMEOUT="${READY_TIMEOUT:-1800}"
echo "waiting up to ${READY_TIMEOUT}s for /health and /v1/models on port ${PORT}"
ready=0
for ((t = 0; t < READY_TIMEOUT; t += 5)); do
    if ! kill -0 "${SERVER_PID}" 2>/dev/null; then echo "vLLM exited during startup" >&2; break; fi
    if "${PY}" - "${PORT}" <<'PYEOF'
import sys, urllib.request
base = f"http://127.0.0.1:{sys.argv[1]}"
try:
    urllib.request.urlopen(base + "/health", timeout=3).read()
    urllib.request.urlopen(base + "/v1/models", timeout=3).read()
except Exception:
    sys.exit(1)
PYEOF
    then ready=1; break; fi
    sleep 5
done
if [[ "${ready}" != "1" ]]; then
    tail -40 "${PILOT_DIR}/server.log" >&2
    fail_gate server_start "vLLM not ready (timeout or crash); see ${PILOT_DIR}/server.log"
fi
echo "server ready after ~${t}s"

export INNKUBE_BASE_URL="http://127.0.0.1:${PORT}"     # the client appends /v1
export INNKUBE_API_KEY="dummy"

# --- run from the pilot dir so relative logs/ stays inside it ----------------
cd "${PILOT_DIR}"
PIPE_CMDS="${PY} -m meta_real_eval.rq2.runner --config ${PILOT_DIR}/config.yaml --phase generate; ... --phase evaluate"
"${PY}" "${REPO_DIR}/scripts/write_run_info.py" --pilot-dir "${PILOT_DIR}" --tier "${TIER}" --stage "${STAGE}" \
    --base-config "${BASE}" --model-dir "${MODEL_DIR}" --gpus "${GPUS}" --tp "${TP}" --max-model-len "${MAX_LEN}" \
    --reasoning-parser "${PARSER}" --vllm-extra="${EXTRA}" --port "${PORT}" \
    --server-cmd "apptainer ${APPTAINER_ARGS[*]} ${SERVER_ARGS[*]}" --pipeline-cmds "${PIPE_CMDS}" \
    --image "${IMAGE}" --gpus-detected "${HOST_GPUS}" --apptainer-extra="${MRE_APPTAINER_EXTRA:-}" \
    --started-at "${STARTED_AT}"

echo "== Stage A/5: server smoke + raw-response probe =="
"${PY}" "${REPO_DIR}/scripts/vllm_probe.py" --config "${PILOT_DIR}/config.yaml" --out "${PILOT_DIR}/probe.json" \
    --server-log "${PILOT_DIR}/server.log" --triton-count-before "${TRITON_BEFORE}"
SMOKE_RC=$?

if [[ "${STAGE}" == "pilot" ]]; then
    if [[ "${SMOKE_RC}" != "0" ]]; then
        echo "SERVER_SMOKE failed: NOT running the pipeline pilot (gate)."
    else
        echo "== Stage B: rq2 generate (real settings) =="
        "${PY}" -m meta_real_eval.rq2.runner --config "${PILOT_DIR}/config.yaml" --phase generate
        echo "generate rc=$?"
        echo "== Stage D: rq2 evaluate =="
        "${PY}" -m meta_real_eval.rq2.runner --config "${PILOT_DIR}/config.yaml" --phase evaluate
        echo "evaluate rc=$?"
    fi
fi

# --- isolation check (simple) ------------------------------------------------
snapshot > "${PILOT_DIR}/isolation_after.txt"
if diff -q "${PILOT_DIR}/isolation_before.txt" "${PILOT_DIR}/isolation_after.txt" >/dev/null; then
    echo "ISOLATION: production paths unchanged (cache/llm_responses, results_tier1, results_tier2, logs)"
else
    echo "ISOLATION: CHANGE DETECTED in production paths (other jobs running: ${OTHER_JOBS}):"
    diff "${PILOT_DIR}/isolation_before.txt" "${PILOT_DIR}/isolation_after.txt"
fi
PILOT_CACHE_DIR="$("${PY}" -c "import sys; from meta_real_eval.core.config import Config; print(Config.from_yaml(sys.argv[1]).llm.cache_dir)" "${PILOT_DIR}/config.yaml")"
echo "pilot cache (${PILOT_CACHE_DIR}): $(find "${PILOT_CACHE_DIR}" -type f 2>/dev/null | wc -l) entries"

echo "== report =="
"${PY}" "${REPO_DIR}/scripts/pilot_report.py" "${PILOT_DIR}" || echo "pilot_report failed"
"${PY}" "${REPO_DIR}/scripts/write_run_info.py" --pilot-dir "${PILOT_DIR}" --finalize
exit "${SMOKE_RC}"
