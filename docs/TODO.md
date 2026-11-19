# TODO

## Redis MCP (swarm-redis)

### Goal

Keep the `swarm-redis` MCP server aligned with how coder and reviewer workers use Redis streams and delegation tools.

### Checklist

- [ ] Audit tools in `mcp-servers/swarm-redis/app/server.py` against coder/reviewer skills (`event-found`, `workflow`) and `skills/swarm/SKILL.md`; add or adjust tools/fields where agents still guess or pass untrusted identity.
- [ ] Document how workers reach the server (stdio vs `streamable-http`), ports, and `REDIS_URL` for local Docker.
- [ ] Package/run instructions: image build, compose or `docker run`, and how Claude Code registers the MCP server in container.
- [ ] Reconcile with **Agent identity** below (auth middleware, server-derived `agentID` / `agentRole` on delegations).

## Reviewer + Greptile

### Goal

Use Greptile CLI in the reviewer container for structured code review, authenticated via `GREPTILE_API_KEY` (no host Keychain copy).

### Checklist

- [ ] Add `GREPTILE_API_KEY` to `.env.example` and reviewer Dockerfile header comments (with `ANTHROPIC_API_KEY`, `GH_TOKEN`).
- [ ] Define when the reviewer runs `greptile review` (e.g. after cloning/checkout on `workingBranch`) in a reviewer skill or `prompt.md` / `CLAUDE.md` workflow.
- [ ] Document container run: `templates/reviewer/Dockerfile`, image tag, `--env-file .env`, and that Greptile org/repo must already be onboarded in the dashboard.
- [ ] Smoke-test: `greptile whoami` and `greptile review` inside the reviewer image against a real repo.

## Agent identity and delegations

### Goal

Give each container a stable logical identity (`agentID`, `agentRole`) and attach that identity to swarm writes—without trusting values the model passes through MCP tool calls.

Tracked in Linear: [ANH-9 — Give each container a stable agent ID](https://linear.app/anhadhs-personal-workspace/issue/ANH-9/give-each-container-a-stable-agent-id).

### Problem

If identity fields are tool arguments the model sets, callers can spoof them. That is fine for casual debugging but not for trustworthy attribution or audit trails. Container hostname (`$HOSTNAME`) identifies a runtime instance but is not authentication and should not be the sole logical identity.

### Recommended model

| Concept | Purpose |
|---|---|
| `agentID` | Stable logical identity for a worker, e.g. `coder-1`, `reviewer-2` |
| `agentRole` | Role name: `coder`, `reviewer`, `orchestrator` |
| `instanceID` | Ephemeral container/runtime id, e.g. Docker hostname; optional |

Store these on delegated tasks and other swarm writes (for example `from` on `event:coder` / `event:reviewer` should become `fromAgentID` / `fromAgentRole`, not free-text role only).

### Trust boundary

- **Self-reported (low trust):** Environment variables such as `SWARM_AGENT_ID` / `SWARM_AGENT_ROLE` read by the agent and passed into tools. Easy to wire up; spoofable.
- **Server-derived (preferred):** One secret token per container (or per agent) at startup. MCP client sends it on each HTTP request (e.g. `Authorization: Bearer …`). `swarm-redis` resolves token → `{agentID, agentRole}` and attaches that identity when writing Redis—**do not** accept `agent_id` as a tool argument for writes.

### Implementation checklist

- [x] Provision stable `agentID` + `agentRole` per container when starting workers (`scripts/run-claude-containers.sh`): pass via env; document recreate semantics. *(Done: `SWARM_CONTAINER_ID` injected per run in `run-claude-containers.sh`; new ID each start with `--rm`.)*
- [ ] Provision tokens when starting containers: generate or assign token tied to that `agentID`; configure Claude MCP HTTP client headers if supported.
- [ ] Add auth middleware or per-request lookup in `swarm-redis` for `streamable-http` transport; reject writes without a valid token (or fall back to `unknown` only in dev behind an explicit flag).
- [ ] Extend delegation `task_fields` / `write_*_task` to persist server-derived `agentID`, `agentRole`, and optional `instanceID`; do not accept identity as tool arguments.
- [ ] Document token registry format (env file, Redis hash `agent:<token>`, or static map for local dev).
- [ ] Align `STRUCTURE.md` delegation tables with the new fields once implemented.
- [ ] Decide whether delegated tasks should record `fromAgentID` in addition to `from` role.

### Out of scope (for now)

- Cryptographic signing of handoff payloads.
- Cross-host federation or multi-tenant isolation beyond shared Docker network.

### Related

- Large orchestrator plans should not live in `events.prompt`; use a separate plan store + reference field (see design discussion in repo). Reduces log and `read_events` noise independently of identity work.