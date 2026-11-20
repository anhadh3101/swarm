---
name: find-event
description: >-
  Polls this container's queue, then event:reviewer, then events. Stores the
  first task that belongs to this reviewer and reviews it. Use when /loop fires.
---

# Find event

Take one task per turn. Check the three sources in order. On the first task you take, continue to **Store**.

## 1. Queue

```bash
curl -sS -w "\n%{http_code}" http://127.0.0.1:8080/next
```

The last line is the status code. The body above it is the task.

- `200`: this task is yours. It has `traceID`, `repoUrl`, `workingBranch`, `prompt`, and `from`. `from` is the coder container. Use it as `sender`. Continue to **Store**.
- `204`: the queue is empty. Continue below.
- Any other status: report the status and stop.

`GET /next` already removed this job. Handle it in this turn.

## 2. Reviewer stream

Call `read_reviewer_tasks` on `swarm-redis`.

Each entry has `traceID`, `prompt`, `repoUrl`, and `from`. `from` is a role name. There is no `sender`. `workingBranch` is the `workingBranch` on the `events` entry with the same `traceID`.

If the list is empty, continue to the event stream.

Otherwise take the first entry and continue to **Store**.

## 3. Event stream

Call `read_events` on `swarm-redis`.

Walk the entries in order. Decide for each one:

- **Yours:** `status` is `AVAILABLE`, and the prompt asks for a review of work that already exists.
- **Not yours:** `status` is `IN_PROGRESS` or `COMPLETE`, or the prompt asks for a repo change (implement, fix, add, update, or produce a branch).

When an entry is not yours, look at the next entry.

When an entry is yours, continue to **Store**.

When no remaining entry is yours, stop. Do nothing else.

## Store

Write this file before any other work. Do not write it under `/workspace`. A later job you take overwrites the file.

`/opt/swarm/state.json`

```json
{
  "traceID": "<traceID>",
  "repoUrl": "<repoUrl>",
  "workingBranch": "<workingBranch>",
  "prompt": "<prompt>",
  "sender": "<from>"
}
```

`prompt` is the request you took. `sender` is the queue field `from`. Leave `sender` out when the task came from a stream. Read this file for the rest of the turn.

## Work

The `prompt` is what you review. The `repoUrl` is the repo. The `workingBranch` is the branch under review.

Follow the **workflow** skill. When `sender` is set, it posts the result to that coder's queue. When `sender` is not set, workflow calls `write_coder_task`.

Do not edit the repo.

## Reply

```markdown
## Event
- traceID: <id>
- repoUrl: <url>
- workingBranch: <branch>
- state: /opt/swarm/state.json
```

After that, add the final message from your role prompt.
