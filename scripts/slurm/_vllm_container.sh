# Helpers for running vLLM through the project's Apptainer image.
#
# Sourced (not executed) by submit_vllm_pilot.sh. These functions only BUILD
# argument arrays and count GPUs; none of them starts a container, so they can be
# unit-tested (tests/test_scripts/test_pilot_tooling.py).
#
# Pattern taken from the working run_qwen36.slurm: `apptainer exec --nv`, the
# model directory bound read-only, `vllm serve <path inside container>`. What that
# script proves is limited to "this one model served once"; it is NOT evidence
# that any given model, parser or flag is supported, so nothing here defaults a
# reasoning parser, tool-call flag, max-model-len or batching flag from it.
#
# Inside the container the model is always /model, and the project's scripts are
# at /opt/mre_scripts (read-only), so the container-side preflight can run there.

MRE_CONTAINER_MODEL_PATH="/model"
MRE_CONTAINER_SCRIPTS_PATH="/opt/mre_scripts"

# mre_apptainer_args IMAGE MODEL_DIR REPO_DIR [RW_DIR]
# Fills APPTAINER_ARGS (everything after `apptainer`, up to and including IMAGE).
#
# Binds: the model dir (ro), the scripts dir (ro), and <repo>/.cache (rw) at the
# SAME path (plus RW_DIR, if given, for container-side reports), because TRITON_CACHE_DIR / XDG_CACHE_HOME / HF_HOME exported by
# _common.sh point into it and must resolve identically inside the container.
# /home is not mounted on the compute nodes, so the container gets its own home
# under <repo>/.cache instead of Apptainer's default $HOME bind.
# Extra flags can be supplied without editing this file via MRE_APPTAINER_EXTRA
# (word-split on purpose, e.g. "--cleanenv"); they are recorded in RUN_INFO.
mre_apptainer_args() {
    local image="$1" model_dir="$2" repo_dir="$3" rw_dir="${4:-}"
    local cache_dir="${repo_dir}/.cache"
    local ct_home="${cache_dir}/container_home"
    APPTAINER_ARGS=(
        exec --nv
        --home "${ct_home}:${ct_home}"
        --bind "${model_dir}:${MRE_CONTAINER_MODEL_PATH}:ro"
        --bind "${repo_dir}/scripts:${MRE_CONTAINER_SCRIPTS_PATH}:ro"
        --bind "${cache_dir}:${cache_dir}"
        --env "TRITON_CACHE_DIR=${TRITON_CACHE_DIR:-${cache_dir}/triton}"
        --env "XDG_CACHE_HOME=${XDG_CACHE_HOME:-${cache_dir}/xdg}"
        --env "HF_HOME=${HF_HOME:-${cache_dir}/huggingface}"
        --env "HF_HUB_OFFLINE=1"
    )
    [[ -n "${rw_dir}" ]] && APPTAINER_ARGS+=(--bind "${rw_dir}:${rw_dir}")
    # shellcheck disable=SC2206
    [[ -n "${MRE_APPTAINER_EXTRA:-}" ]] && APPTAINER_ARGS+=(${MRE_APPTAINER_EXTRA})
    APPTAINER_ARGS+=("${image}")
}

# mre_server_args SERVED_NAME PORT TP MAX_LEN PARSER EXTRA
# Fills SERVER_ARGS: the command run INSIDE the container. PARSER and EXTRA may be
# empty; EXTRA is word-split (e.g. "--dtype auto --enable-chunked-prefill").
mre_server_args() {
    local name="$1" port="$2" tp="$3" max_len="$4" parser="${5:-}" extra="${6:-}"
    SERVER_ARGS=(
        vllm serve "${MRE_CONTAINER_MODEL_PATH}"
        --host 127.0.0.1 --port "${port}"
        --served-model-name "${name}"
        --tensor-parallel-size "${tp}"
        --max-model-len "${max_len}"
    )
    [[ -n "${parser}" ]] && SERVER_ARGS+=(--reasoning-parser "${parser}")
    # shellcheck disable=SC2206
    [[ -n "${extra}" ]] && SERVER_ARGS+=(${extra})
    return 0
}

# mre_count_gpus [nvidia-smi-command...]  -> number of GPUs it lists.
# Used both on the host and (with `apptainer exec --nv IMAGE nvidia-smi`) inside
# the container, so a binding problem shows up as a count mismatch.
mre_count_gpus() {
    "${@:-nvidia-smi}" -L 2>/dev/null | grep -c '^GPU' || true
}
