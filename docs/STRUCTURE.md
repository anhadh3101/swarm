# Stream structure

Four Redis streams. `traceID` joins an event to its message board and to any delegated task. Redis does not link the streams. The first `XADD` creates each one. Every field is a string.

The id Redis returns from `XADD` is the entry id. For a message, that id is the `messageID`. It is not stored again inside the entry.

| Stream | Who writes | Who reads |
|---|---|---|
| `events` | Orchestrator | Every agent |
| `messages` | Any agent | Every agent, filtered to one `traceID` |
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

## `messages`

One flat log. A trace's message board is every entry in `messages` with that `traceID`.

| Field | Value |
|---|---|
| `traceID` | The event this note belongs to |
| `messageNum` | `1`, `2`, `3`, … inside that trace |
| `body` | What the agent has completed so far |

`messageNum` is per trace. Before posting, read that trace's board and add one to the highest `messageNum`. The Redis entry id orders the whole stream, so it is not a per-board sequence.

Read a board by scanning `messages` and keeping one `traceID`, then sort those entries by `messageNum`.

## `event:coder` and `event:reviewer`

An agent writes one of these only when it is handing work to that role. The entry carries the same `traceID` so the coder or reviewer can find the event and the message board.

| Field | Value |
|---|---|
| `traceID` | The event this delegation belongs to |
| `prompt` | What that role should do |
| `repoUrl` | Same remote as the event |
| `from` | Role that delegated it |

Coders read only `event:coder`. Reviewers read only `event:reviewer`. Use one consumer group per task stream so one worker claims each delegated task.

## How a run moves

1. The orchestrator appends one entry to `events`.
2. Every agent sees it. An agent that can do the work starts, and appends progress to `messages` under that `traceID`.
3. When that work needs the other role, the agent appends one entry to `event:coder` or `event:reviewer` with the same `traceID`.
4. The chosen role claims that task, does it, and appends its own progress to `messages`.
