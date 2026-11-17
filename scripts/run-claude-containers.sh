#!/usr/bin/env bash
# Start coder or reviewer Claude Code containers (interactive).
# Usage: ./scripts/run-claude-containers.sh coder
#        ./scripts/run-claude-containers.sh reviewer
# Run each role in its own terminal. Requires repo-root .env and swarm images
# built from templates, e.g. docker build -t swarm-coder templates/coder
# Each image ships role instructions in ~/.claude/CLAUDE.md (loaded automatically).
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

CLAUDE_VOL="${CLAUDE_CONFIG_VOLUME:-claude-swarm}"
REPO_ROOT="$(pwd)"

docker_run_claude() {
  local image="$1"
  docker run --rm -it \
    --env-file .env \
    -v "${CLAUDE_VOL}:/home/agent/.claude" \
    -v "${REPO_ROOT}/queue/server.js:/opt/swarm/queue.js:ro" \
    -e CLAUDE_CONFIG_DIR=/home/agent/.claude \
    "${image}" \
    bash -lc 'node /opt/swarm/queue.js &
exec claude --dangerously-skip-permissions "/loop 1m /check-for-tasks"'
}

case "${1:-}" in
  coder)
    docker_run_claude swarm-coder
    ;;
  reviewer)
    docker_run_claude swarm-reviewer
    ;;
  *)
    echo "Usage: $0 {coder|reviewer}" >&2
    exit 1
    ;;
esac