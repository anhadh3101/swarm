#!/usr/bin/env bash
# Start coder or reviewer Claude Code containers (interactive).
# Usage: ./scripts/run-claude-containers.sh coder
#        ./scripts/run-claude-containers.sh reviewer
# Run each role in its own terminal. Requires repo-root .env and swarm images
# built from templates, e.g. docker build -t swarm-coder templates/coder
# Each image ships role instructions in ~/.claude/CLAUDE.md (loaded automatically).
# Injects SWARM_CONTAINER_ID per run (e.g. coder-a1b2c3d4); do not set it in .env.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

CLAUDE_VOL="${CLAUDE_CONFIG_VOLUME:-claude-swarm}"
REPO_ROOT="$(pwd)"

docker_run_claude() {
  local image="$1"
  local role="$2"
  local skill="$3"
  local suffix
  suffix="$(uuidgen | tr '[:upper:]' '[:lower:]' | tr -d '-' | cut -c1-8)"
  local container_id="${role}-${suffix}"

  docker run --rm -it \
    --env-file .env \
    -v "${CLAUDE_VOL}:/home/agent/.claude" \
    -v "${REPO_ROOT}/queue/server.js:/opt/swarm/queue.js:ro" \
    -e CLAUDE_CONFIG_DIR=/home/agent/.claude \
    -e "SWARM_CONTAINER_ID=${container_id}" \
    "${image}" \
    bash -lc "node /opt/swarm/queue.js &
exec claude --dangerously-skip-permissions \"/loop 1m /${skill}\""
}

case "${1:-}" in
  coder)
    docker_run_claude swarm-coder coder find-event
    ;;
  reviewer)
    docker_run_claude swarm-reviewer reviewer find-event
    ;;
  *)
    echo "Usage: $0 {coder|reviewer}" >&2
    exit 1
    ;;
esac