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

# Start a pipeline (architect → coder → reviewer via orchestrator):
docker compose exec redis redis-cli XADD tasks:architect '*' \
  run_id demo-1 job_id job-1 \
  payload '{"goal":"Add a short README section for this project"}'

docker compose logs -f orchestrator architect coder reviewer
```

The repo root is mounted at `/workspace` in each agent container.

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
