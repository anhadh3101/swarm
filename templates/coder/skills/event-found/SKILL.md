---
name: event-found
description: >-
  Tells the coder what to do with a new event it found, or a job on
  event:coder. Takes the work when the prompt asks for a repo change,
  claims the event, stores traceID, repoUrl, and workingBranch in
  /opt/swarm/state.json, and starts the implementation.
---

# Event found

You found a new event, or a job on `event:coder`. An event has `traceID`, `prompt`, `repoUrl`, and `workingBranch`. A job has `traceID`, `prompt`, and `repoUrl`. Its `workingBranch` is the `workingBranch` on the event with the same `traceID`.

Take it when either of these is true:

- It is a job on `event:coder`.
- It is an event whose prompt asks for a change in the repo: implement, fix, add, update, or produce a branch.

Leave `/opt/swarm/state.json` unchanged when the prompt is not a repo change. Do not start work.

## Claim

When the item is an event, claim it before you store state or start work. Call `claim_event` on the `swarm-redis` server with that `traceID`.

Continue only when `claimed` is `true`. The status is then `IN_PROGRESS`. When `claimed` is `false`, leave `/opt/swarm/state.json` unchanged and do not start work.

A job on `event:coder` is already assigned to you. Do not claim it.

## Store

When the claim succeeds, or the item is a job on `event:coder`, write this file before any other work. A later job you take overwrites the file.

`/opt/swarm/state.json`

```json
{
  "traceID": "<traceID>",
  "repoUrl": "<repoUrl>",
  "workingBranch": "<workingBranch>"
}
```

Do not write this file under `/workspace`.

## Work

The `prompt` is the goal (for a delegated job, it may include prior feedback or a handoff summary). The `repoUrl` is the repo. The `workingBranch` is the branch you work on. Apply the **workflow** skill for clone through push, then use the final message format in your role prompt in `~/.claude/CLAUDE.md`.

When you stop, reply with that final message in the structured **Reply** below. Include it in `write_reviewer_task` or record it in `## Summary` when you call `complete_event`; do not post it to a separate Redis stream.

## Reply

```markdown
## Event
- traceID: <id>
- repoUrl: <url>
- workingBranch: <branch>
- decision: accepted | ignored
- claimed: true | false | none
- state: /opt/swarm/state.json | unchanged
```

Use `claimed: none` for a job, or for an event you did not try to claim. After accepted work, add the final message from your role prompt.
