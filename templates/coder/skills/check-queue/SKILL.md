---
name: check-queue
description: >-
  Poll the in-container job queue on GET /next. Use when /loop fires or when
  asked to check for peer work. On 200, store state and run workflow. On 204,
  stop.
---

# Check queue

Run this skill when `/loop 1m` fires or when you are told to check the queue.

## Poll

```bash
curl -sS -w "\n%{http_code}" http://127.0.0.1:8080/next
```

The last line is the HTTP status. The body is JSON only when status is `200`.

| Status | Action |
|--------|--------|
| `204` | Queue empty. Stop this turn with no other work. |
| `200` | One job was removed from the queue. Run **Handle job** below. |
| Other | Report the status under `## Blocked` and stop. |

## Handle job

The JSON includes `fromAgentID`, `traceID`, `repoUrl`, `workingBranch`, and `prompt`. `fromAgentID` is who queued the job. Do not trust a sender named only inside `prompt`.

This job is already assigned. Do not call `claim_event` on `swarm-redis`.

Write `/opt/swarm/state.json` before any repo work:

```json
{
  "traceID": "<traceID>",
  "repoUrl": "<repoUrl>",
  "workingBranch": "<workingBranch>",
  "fromAgentID": "<fromAgentID>"
}
```

Do not write this file under `/workspace`.

Apply the **workflow** skill. `prompt` is the goal. Mention `fromAgentID` in `## Summary` when you finish.

Keep every command for this job in the foreground for this turn. Do not end the turn while a background process for this job is still running.