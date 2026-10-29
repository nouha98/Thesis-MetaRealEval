#!/bin/bash
# GPU job: serve ONE self-hosted model of a serving-group config
# (config/tier2_runs/<label>_vllm-<model>.yaml) with vLLM through the project's
# Apptainer image, then run RQ1 and/or RQ2 generate for it. One model per group,
# so one job never needs another model's server and parallel GPU jobs never
# share a results dir. The gateway group runs through submit_llm.sh instead;
# merge_generation_runs.py joins the groups before any evaluation.
#
# Submit through scripts/slurm/launch_vllm_generate.sh (login node). Check the
# model first with the existing smoke test (launch_vllm_pilot.sh --stage smoke).
#
# Gates (each stops the job with a recorded reason in <out_dir>/jobs/<jobid>/):
#   1. the config lists exactly this model
#   2. GPU count, host == requested == container; tp <= GPUs
#   3. host + container preflight (vllm_feasibility.py)
#   4. vllm serve ... ready (/health and /v1/models)
# then write_serving_info.py records what served the model (serving_<model>.json).
#
# Runs from the repo root (configs use repo-relative paths). Generation stops
# MARGIN seconds before the time limit (exit 124); resubmit the same command and
# the response cache + per-task done markers resume where it stopped. Chunks of
# one group may run as parallel jobs with disjoint --task-range values.
#
#SBATCH --job-name=vllm_generate
#SBATCH --account=chair-se2
#SBATCH --partition=gpu
#SBATCH --constraint=gpumem.80gib
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=24:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err
# (--constraint/--gres/--mem/--time/--output/--error above are defaults; the launcher overrides them.)

set -uo pipefail     # no -e: gates are checked explicitly so cleanup and reporting always run

CONFIG="" MODEL="" MODEL_DIR="" GPUS=1 TP="" MAX_LEN=40960 PARSER="" EXTRA="" IMAGE=""
TASK_RANGE="" PHASES="rq1,rq2" MARGIN=900
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
        --image) IMAGE="$2"; shift 2 ;;
        --task-range) TASK_RANGE="$2"; shift 2 ;;
        --phases) PHASES="$2"; shift 2 ;;
        --margin) MARGIN="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
: "${CONFIG:?}" "${MODEL:?}" "${MODEL_DIR:?}" "${IMAGE:?}"
TP="${TP:-${GPUS}}"

export MRE_RUNNER_MODULE="meta_real_eval.rq2.runner"
export MRE_CONFIG="${CONFIG}"
SCRIPT_ROOT="${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}"
source "${SCRIPT_ROOT}/scripts/slurm/_common.sh"          # cds to the repo root, sets PY
source "${REPO_DIR}/scripts/slurm/_vllm_container.sh"

OUT_DIR="$("${PY}" -c "import sys; from meta_real_eval.core.config import Config; print(Config.from_yaml(sys.argv[1]).project.output_dir.resolve())" "${CONFIG}")"
JOB_DIR="${OUT_DIR}/jobs/${SLURM_JOB_ID:-local}"
mkdir -p "${JOB_DIR}" "${REPO_DIR}/.cache/container_home"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "config: ${CONFIG}  model: ${MODEL}  out: ${OUT_DIR}  job dir: ${JOB_DIR}"

SERVER_PID=""
cleanup() { [[ -n "${SERVER_PID}" ]] && kill "${SERVER_PID}" 2>/dev/null && wait "${SERVER_PID}" 2>/dev/null; }
trap cleanup EXIT

fail_gate() {   # fail_gate <check-name> <message>
    echo "GATE FAILED: $1: $2" >&2
    "${PY}" -c "import json,sys; json.dump({'gate': sys.argv[2], 'reason': sys.argv[3]}, open(sys.argv[1], 'w'), indent=2)" \
        "${JOB_DIR}/gate_failed.json" "$1" "$2"
    exit 1
}

# --- Gate 1: the config is this model's own serving group ---------------------
"${PY}" - "${CONFIG}" "${MODEL}" <<'PYEOF' || fail_gate config "the config must list exactly this model (one GPU job = one model = one group)"
import sys
from meta_real_eval.core.config import Config
cfg = Config.from_yaml(sys.argv[1])
print(f"config models={cfg.model_ids()}")
sys.exit(0 if cfg.model_ids() == [sys.argv[2]] else 1)
PYEOF

command -v apptainer >/dev/null 2>&1 || fail_gate apptainer "apptainer not found on this node"
[[ -f "${IMAGE}" ]] || fail_gate image "image not found: ${IMAGE}"
[[ -d "${MODEL_DIR}" ]] || fail_gate model_dir "model dir not found: ${MODEL_DIR}"

mre_apptainer_args "${IMAGE}" "${MODEL_DIR}" "${REPO_DIR}" "${JOB_DIR}"

# --- Gate 2: GPUs, measured on the host and inside the container -------------
HOST_GPUS="$(mre_count_gpus)"
CONT_GPUS="$(mre_count_gpus apptainer exec --nv "${IMAGE}" nvidia-smi)"
nvidia-smi -L | tee "${JOB_DIR}/gpus_host.txt"
[[ "${HOST_GPUS}" == "${GPUS}" ]] || fail_gate gpu_count "allocated GPUs (${HOST_GPUS}) != requested --gpus (${GPUS})"
[[ "${CONT_GPUS}" == "${HOST_GPUS}" ]] || fail_gate gpu_in_container "container sees ${CONT_GPUS} GPU(s), host has ${HOST_GPUS}"
(( TP <= HOST_GPUS )) || fail_gate tensor_parallel "tp=${TP} > allocated GPUs ${HOST_GPUS}"

# --- Gate 3: preflights (host: artifact facts incl. revision; container: vLLM) -
"${PY}" scripts/vllm_feasibility.py "${MODEL_DIR}" --mode host --gpus "${HOST_GPUS}" --tp "${TP}" \
    --max-model-len "${MAX_LEN}" --no-hash --out "${JOB_DIR}/feasibility.json" > "${JOB_DIR}/feasibility.stdout" 2>&1 \
    || fail_gate host_preflight "see ${JOB_DIR}/feasibility.json"
CPF_ARGS=("${MRE_CONTAINER_MODEL_PATH}" --mode container --gpus "${HOST_GPUS}" --tp "${TP}"
          --max-model-len "${MAX_LEN}" --no-hash --out "${JOB_DIR}/feasibility_container.json")
[[ -n "${PARSER}" ]] && CPF_ARGS+=(--reasoning-parser "${PARSER}")
apptainer "${APPTAINER_ARGS[@]}" python3 "${MRE_CONTAINER_SCRIPTS_PATH}/vllm_feasibility.py" "${CPF_ARGS[@]}" \
    > "${JOB_DIR}/feasibility_container.stdout" 2> "${JOB_DIR}/feasibility_container.stderr" \
    || fail_gate container_preflight "see ${JOB_DIR}/feasibility_container.json"

# --- Gate 4: server -----------------------------------------------------------
PORT=$("${PY}" -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1])")
mre_server_args "${MODEL}" "${PORT}" "${TP}" "${MAX_LEN}" "${PARSER}" "${EXTRA}"
SERVER_CMD="apptainer ${APPTAINER_ARGS[*]} ${SERVER_ARGS[*]}"
echo "server: ${SERVER_CMD}"
apptainer "${APPTAINER_ARGS[@]}" "${SERVER_ARGS[@]}" > "${JOB_DIR}/server.log" 2>&1 &
SERVER_PID=$!

READY_TIMEOUT="${READY_TIMEOUT:-1800}"
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
[[ "${ready}" == "1" ]] || { tail -40 "${JOB_DIR}/server.log" >&2; fail_gate server_start "vLLM not ready; see ${JOB_DIR}/server.log"; }
echo "server ready after ~${t}s"

export INNKUBE_BASE_URL="http://127.0.0.1:${PORT}"     # the client appends /v1
export INNKUBE_API_KEY="dummy"

# --- record what serves the model ------------------------------------------------
"${PY}" scripts/write_serving_info.py --config "${CONFIG}" --model "${MODEL}" --model-dir "${MODEL_DIR}" \
    --job-dir "${JOB_DIR}" --out-dir "${OUT_DIR}" --image "${IMAGE}" --server-cmd "${SERVER_CMD}" \
    --max-model-len "${MAX_LEN}" --tp "${TP}" --reasoning-parser "${PARSER}" --vllm-extra "${EXTRA}" \
    --job-id "${SLURM_JOB_ID:-local}" --started-at "${STARTED_AT}" \
    || fail_gate serving_info "could not record serving info"

# --- seeded-sampling probe (evidence only; never stops the job) -------------------
# A HANG (exit 3, or timeout's 124) is fatal: an engine that stopped producing
# tokens would stall the generation the same way, for hours.
timeout 900 "${PY}" scripts/probe_seeds.py --config "${CONFIG}" --model "${MODEL}" \
    --out "${JOB_DIR}/probe_seeds.json" > "${JOB_DIR}/probe_seeds.stdout" 2>&1
probe_rc=$?
if [[ "${probe_rc}" == "3" || "${probe_rc}" == "124" ]]; then
    cat "${JOB_DIR}/probe_seeds.stdout" >&2
    fail_gate probe_hang "vLLM stopped answering on the seeded probe (rc=${probe_rc}); see ${JOB_DIR}/probe_seeds.stdout and server.log"
elif [[ "${probe_rc}" != "0" ]]; then
    echo "probe_seeds failed rc=${probe_rc} (non-fatal); see ${JOB_DIR}/probe_seeds.stdout"
fi

# --- generate -----------------------------------------------------------------
RANGE_ARGS=()
[[ -n "${TASK_RANGE}" ]] && RANGE_ARGS=(--task-range "${TASK_RANGE}")
FINAL_RC=0
IFS=, read -r -a PHASE_LIST <<< "${PHASES}"
for phase in "${PHASE_LIST[@]}"; do
    LEFT=$(mre_seconds_left "$(squeue -h -j "${SLURM_JOB_ID:-0}" -o %L 2>/dev/null)")
    TIMEOUT_ARGS=()
    if (( LEFT > 0 )); then
        BUDGET=$(( LEFT - MARGIN ))
        (( BUDGET > 60 )) || { echo "only ${LEFT}s left; not starting ${phase}"; FINAL_RC=124; break; }
        TIMEOUT_ARGS=(timeout --signal=TERM "${BUDGET}")
    fi
    echo "== ${phase} generate (${TASK_RANGE:-all tasks}; budget ${BUDGET:-unlimited}s) =="
    ${TIMEOUT_ARGS[@]+"${TIMEOUT_ARGS[@]}"} "${PY}" -m "meta_real_eval.${phase}.runner" --config "${CONFIG}" \
        --phase generate ${RANGE_ARGS[@]+"${RANGE_ARGS[@]}"}
    rc=$?
    echo "${phase} generate rc=${rc}"
    if [[ "${rc}" == "124" ]]; then
        echo "time limit reached: resubmit the same command; cache + done markers resume the run"
        FINAL_RC=124; break
    fi
    [[ "${rc}" != "0" ]] && FINAL_RC="${rc}"
done
echo "finished generate rc=${FINAL_RC}; outputs in ${OUT_DIR}"
exit "${FINAL_RC}"
