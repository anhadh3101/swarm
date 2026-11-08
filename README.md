# Agent Swarm

Prototype: **orchestrator** + **architect / coder / reviewer** workers over **Redis Streams**, agents run **Codex CLI** in Docker.

## Prerequisites

- Docker Compose v2
- Codex auth (device login or `OPENAI_API_KEY` in `.env`)

## Quick start

```bash
docker pull ghcr.io/icoretech/codex-docker:latest
docker compose build
docker compose up -d

# One-time login (shared codex-home volume across workers):
docker compose run --rm --entrypoint codex architect login --device-auth

# Alternative: `scripts/docker-workers.sh` uses separate Codex volumes per role
# (`swarm-codex-architect`, `swarm-codex-coder`, `swarm-codex-reviewer`) so configs do not
# overwrite each other. Log in once per volume you need, e.g. for coder:
# docker run --rm -it --network swarm -v swarm-codex-coder:/codex-home -e CODEX_HOME=/codex-home \
#   --entrypoint codex coder login --device-auth

# Start a pipeline (architect → coder → reviewer via orchestrator):
docker compose exec redis redis-cli XADD tasks:architect '*' \
  run_id demo-1 job_id job-1 \
  payload '{"goal":"Add a short README section for this project"}'

docker compose logs -f orchestrator architect coder reviewer
```

Architect and reviewer mount the **repo root** at `/workspace` (read-only). When using `scripts/docker-workers.sh`, the **coder** uses a Docker volume (`swarm-coder-workspace` by default) for `/workspace` so builds are **not** written to your host checkout. Copy sources into that volume first if needed, e.g. `docker run --rm -v swarm-coder-workspace:/out -v "$PWD":/src alpine cp -a /src/. /out/`.

## Streams

| Stream | Purpose |
|--------|---------|
| `tasks:architect` | Architect jobs |
| `tasks:coder` | Coder jobs |
| `tasks:reviewer` | Reviewer jobs |
| `events:orchestrator` | Worker completions; orchestrator enqueues next stage |

## Stop

```bash
docker compose down
```
