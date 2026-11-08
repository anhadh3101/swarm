#!/usr/bin/env bash
# Build worker images and start containers.
#
# Each role uses its OWN Codex home volume so entrypoint.sh does not overwrite config.toml
# across architect / coder / reviewer (which caused coder to read reviewer's read-only config).
# Volumes: swarm-codex-architect, swarm-codex-coder, swarm-codex-reviewer, swarm-coder-workspace
#
# If repo-root .env exists, it is passed to each container (e.g. OPENAI_API_KEY for Codex).
# Codex login: run once per role (each volume needs auth), e.g.:
#   docker run --rm -it --network swarm -v swarm-codex-coder:/codex-home -e CODEX_HOME=/codex-home \
#     --entrypoint codex coder login --device-auth
#
# Coder gets CODEX_FLAGS to bypass Codex's Linux sandbox (bubblewrap) inside Docker. Architect &
# reviewer stay sandboxed (read-only workspace mounts).
#
# Coder /workspace: Docker volume (default swarm-coder-workspace), NOT the host repo — builds
# stay inside Docker. Architect & reviewer still mount the repo read-only for context.
# Override: SWARM_CODER_WORKSPACE_VOLUME=my-vol env var before running this script.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

CODER_WS_VOL="${SWARM_CODER_WORKSPACE_VOLUME:-swarm-coder-workspace}"

# Default sandbox bypass for coder. Beware: ${var:---flag} is wrong in bash (one leading
# dash is eaten as :-). Use explicit empty check or quotes.
if [[ -z "${CODEX_FLAGS_CODER:-}" ]]; then
  CODER_CODEX_FLAGS="--dangerously-bypass-approvals-and-sandbox"
else
  CODER_CODEX_FLAGS="$CODEX_FLAGS_CODER"
fi

codex_volume_for() {
  case "$1" in
    architect) echo "swarm-codex-architect" ;;
    coder) echo "swarm-codex-coder" ;;
    reviewer) echo "swarm-codex-reviewer" ;;
    *) echo "swarm-codex-${1}" ;;
  esac
}

docker_run_worker() {
  local name="$1"
  local image="$2"
  local ws_mode="$3" # ro | rw
  local vol
  vol="$(codex_volume_for "$name")"

  if [[ "$name" == "coder" ]]; then
    if [[ -f .env ]]; then
      docker run -d --name "$name" --network swarm \
        --env-file .env \
        --restart unless-stopped \
        -e REDIS_URL=redis://redis:6379/0 \
        -e CODEX_HOME=/codex-home \
        -e "CODEX_FLAGS=${CODER_CODEX_FLAGS}" \
        -v "${vol}:/codex-home" \
        -v "${CODER_WS_VOL}:/workspace" \
        "$image"
    else
      docker run -d --name "$name" --network swarm \
        --restart unless-stopped \
        -e REDIS_URL=redis://redis:6379/0 \
        -e CODEX_HOME=/codex-home \
        -e "CODEX_FLAGS=${CODER_CODEX_FLAGS}" \
        -v "${vol}:/codex-home" \
        -v "${CODER_WS_VOL}:/workspace" \
        "$image"
    fi
  else
    if [[ -f .env ]]; then
      docker run -d --name "$name" --network swarm \
        --env-file .env \
        --restart unless-stopped \
        -e REDIS_URL=redis://redis:6379/0 \
        -e CODEX_HOME=/codex-home \
        -v "${vol}:/codex-home" \
        -v "$PWD:/workspace:${ws_mode}" \
        "$image"
    else
      docker run -d --name "$name" --network swarm \
        --restart unless-stopped \
        -e REDIS_URL=redis://redis:6379/0 \
        -e CODEX_HOME=/codex-home \
        -v "${vol}:/codex-home" \
        -v "$PWD:/workspace:${ws_mode}" \
        "$image"
    fi
  fi
}

docker build -t architect templates/architect
docker build -t coder templates/coder
docker build -t reviewer templates/reviewer

docker_run_worker architect architect ro
docker_run_worker coder coder rw
docker_run_worker reviewer reviewer ro
