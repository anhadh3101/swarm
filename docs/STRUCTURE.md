# Stream structure

Three Redis streams. `traceID` joins an event to any delegated task. Redis does not link the streams. The first `XADD` creates each one. Every field is a string.

The id Redis returns from `XADD` is the entry id. It is not stored again inside the entry.

| Stream | Who writes | Who reads |
|---|---|---|
| `events` | Orchestrator | Every agent |
| `event:coder` | Any agent | Coders |
| `event:reviewer` | Any agent | Reviewers |

## `events`

One entry is one task. Each agent keeps its own last-seen id and reads every new entry. A shared consumer group would hand the entry to only one agent.

| Field | Value |
|---|---|
| `traceID` | UUID generated when the event is written, copied onto every later entry |
| `startTime` | ISO-8601 time when the event is written |
| `prompt` | The task text from the orchestrator |
| `repoUrl` | Git remote |
| `workingBranch` | Branch the work is done on |

Live status is a Redis hash, `event:<traceID>`, with one field `status`. A new event sets that field to `AVAILABLE`. `claim_event` sets it to `IN_PROGRESS` only while it is `AVAILABLE`. The other value is `COMPLETE`. `read_events` returns this hash value as `status`. The stream entry does not store it.

An agent reads `prompt`, `repoUrl`, and `workingBranch`. If the work matches what that agent does, it takes the task and copies `traceID`, `repoUrl`, and `workingBranch` into `/opt/swarm/state.json`. If it does not, it advances its cursor and leaves the entry untouched.

## `event:coder` and `event:reviewer`

An agent writes one of these only when it is handing work to that role. The entry carries the same `traceID` so the coder or reviewer can find the event. The delegator's `prompt` carries handoff context (for example the prior agent's final message).

| Field | Value |
|---|---|
| `traceID` | The event this delegation belongs to |
| `prompt` | What that role should do |
| `repoUrl` | Same remote as the event |
| `from` | Role that delegated it |

Coders read only `event:coder`. Reviewers read only `event:reviewer`. Use one consumer group per task stream so one worker claims each delegated task.

## How a run moves

1. The orchestrator appends one entry to `events`.
2. Every agent sees it. An agent that can do the work starts on that `traceID`.
3. When that work needs the other role, the agent appends one entry to `event:coder` or `event:reviewer` with the same `traceID` and a `prompt` that includes what the next role needs.
4. The chosen role claims that task, does it, and may delegate back or mark the trace complete.