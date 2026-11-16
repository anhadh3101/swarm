---
name: event-found
description: >-
  Tells the reviewer what to do with a new event it found, or a job on
  event:reviewer. Takes the work when the prompt asks for a review of
  existing work, stores traceID, repoUrl, and workingBranch in
  /opt/swarm/state.json, and starts the review.
---

# Event found

You found a new event, or a job on `event:reviewer`. An event has `traceID`, `prompt`, `repoUrl`, and `workingBranch`. A job has `traceID`, `prompt`, and `repoUrl`. Its `workingBranch` is the `workingBranch` on the event with the same `traceID`.

Take it when either of these is true:

- It is a job on `event:reviewer`.
- It is an event whose prompt asks for a review of work that already exists.

Leave `/opt/swarm/state.json` unchanged when the prompt is not a review. Do not start work.

## Store

When you take it, write this file before any other work. This is the one write outside the review. Do not write it under `/workspace`. A later job you take overwrites the file.

`/opt/swarm/state.json`

```json
{
  "traceID": "<traceID>",
  "repoUrl": "<repoUrl>",
  "workingBranch": "<workingBranch>"
}
```

## Work

The `prompt` is what you review (for a coder handoff it should include the implementation summary and verification notes). The `repoUrl` is the repo. The `workingBranch` is the branch under review.

Carry out the review and the final message in your role prompt in `~/.claude/CLAUDE.md`. Do not edit the repo.

When you stop, reply with that final message in the structured **Reply** below. If you request rework, include your findings in the `prompt` when you publish back to `event:coder`.

## Reply

```markdown
## Event
- traceID: <id>
- repoUrl: <url>
- workingBranch: <branch>
- decision: accepted | ignored
- state: /opt/swarm/state.json | unchanged
```

After accepted work, add the final message from your role prompt.
