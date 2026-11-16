# TODO

## Agent identity on messages and delegations

### Goal

Know which agent wrote each message on `messages`, and which container or worker instance produced it—without trusting values the model passes through MCP tool calls.

### Problem

If `agent_id` (or similar) is a parameter on `write_message`, the caller can set it to anything. That is fine for casual debugging but not for trustworthy attribution or audit trails. Container hostname (`$HOSTNAME`) identifies a runtime instance but is not authentication and should not be the sole logical identity.

### Recommended model

| Concept | Purpose |
|---|---|
| `agentID` | Stable logical identity for a worker, e.g. `coder-1`, `reviewer-2` |
| `agentRole` | Role name: `coder`, `reviewer`, `orchestrator` |
| `instanceID` | Ephemeral container/runtime id, e.g. Docker hostname; optional |

Store these on `messages` stream entries (and consider the same for `from` on `event:coder` / `event:reviewer` instead of a free-text role only).

### Trust boundary

- **Self-reported (low trust):** Environment variables such as `SWARM_AGENT_ID` / `SWARM_AGENT_ROLE` read by the agent and passed into tools. Easy to wire up; spoofable.
- **Server-derived (preferred):** One secret token per container (or per agent) at startup. MCP client sends it on each HTTP request (e.g. `Authorization: Bearer …`). `swarm-redis` resolves token → `{agentID, agentRole}` and attaches that identity when writing Redis—**do not** accept `agent_id` as a tool argument for writes.

### Implementation checklist

- [ ] Extend `message_fields` / `write_message` in `mcp-servers/swarm-redis` to persist `agentID`, `agentRole`, and optional `instanceID` on each `messages` entry.
- [ ] Update `read_messages` docs and agent skills (`event-found`, role prompts) so agents display identity when replying; they should not invent IDs in tool args once server-derived identity exists.
- [ ] Provision tokens when starting containers (`scripts/run-claude-containers.sh`): generate or assign token + `agentID` + role; pass via env; configure Claude MCP HTTP client headers if supported.
- [ ] Add auth middleware or per-request lookup in `swarm-redis` for `streamable-http` transport; reject writes without a valid token (or fall back to `unknown` only in dev behind an explicit flag).
- [ ] Document token registry format (env file, Redis hash `agent:<token>`, or static map for local dev).
- [ ] Align `STRUCTURE.md` `messages` table with the new fields once implemented.
- [ ] Decide whether delegated tasks should record `fromAgentID` in addition to `from` role.

### Out of scope (for now)

- Cryptographic signing of message bodies.
- Cross-host federation or multi-tenant isolation beyond shared Docker network.

### Related

- Large orchestrator plans should not live in `events.prompt`; use a separate plan store + reference field (see design discussion in repo). Reduces log and `read_events` noise independently of identity work.