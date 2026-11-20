---
name: find-event
description: >-
  Polls this container's queue, then event:coder, then events. Stores the
  first task that belongs to this coder and carries it out. Use when /loop fires.
---

# Find event

Take one task per turn. Check the three sources in order. On the first task you take, continue to **Claim** when it came from `events`. Otherwise continue to **Store**.

## 1. Queue

```bash
curl -sS -w "\n%{http_code}" http://127.0.0.1:8080/next
```

The last line is the status code. The body above it is the task.

- `200`: this task is yours. It has `traceID`, `repoUrl`, `workingBranch`, `prompt`, and `from`. `from` is the reviewer container. Use it as `sender`. Continue to **Store**.
- `204`: the queue is empty. Continue below.
- Any other status: report the status and stop.

`GET /next` already removed this job. Handle it in this turn.

## 2. Coder stream

Call `read_coder_tasks` on `swarm-redis`.

Each entry has `traceID`, `prompt`, `repoUrl`, and `from`. `from` is a role name. There is no `sender`. `workingBranch` is the `workingBranch` on the `events` entry with the same `traceID`.

If the list is empty, continue to the event stream.

Otherwise take the first entry and continue to **Store**.

## 3. Event stream

Call `read_events` on `swarm-redis`.

Walk the entries in order. Decide for each one:

- **Yours:** `status` is `AVAILABLE`, and the prompt asks for a change in the repo: implement, fix, add, update, or produce a branch.
- **Not yours:** `status` is `IN_PROGRESS` or `COMPLETE`, or the prompt asks for a review of work that already exists.

When an entry is not yours, look at the next entry.

When an entry is yours, continue to **Claim**.

When no remaining entry is yours, stop. Do nothing else.

## Claim

Call `claim_event` on `swarm-redis` with that `traceID` before you store state or start work.

Continue to **Store** only when `claimed` is `true`. When `claimed` is `false`, leave `/opt/swarm/state.json` unchanged and stop.

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

### Queue job

`sender` is set. Read the line under `## Approval status` in `prompt`.

**Changes requested.** Follow the **workflow** skill to check out `workingBranch`, make the fixes, run the checks, commit, and push. Fix the **Critical** and **Major** findings in `prompt`. Skip that skill's **Finish** section. Then ask the reviewer to review again:

```bash
curl -sS -X POST "http://<sender>:8080/chat" \
  -H "Content-Type: application/json" \
  -d '{"traceID":"<traceID>","repoUrl":"<repoUrl>","workingBranch":"<workingBranch>","prompt":"<re-review request>"}'
```

The re-review request names the branch and the new commit SHA, lists each finding you fixed with the file you changed, and includes your final message.

**Approved.** Open a pull request from `workingBranch` into the default branch:

```bash
gh pr create --head "<workingBranch>" --base "<default branch>" \
  --title "<short summary>" --body "<what changed, plus any Minor or Nit findings from prompt>"
```

Do not make further code changes. Put the PR URL in `## Summary`.

If the approval line is neither `approved` nor `changes requested`, stop and name that under `## Blocked`.

### Event or event:coder job

`sender` is not set. The `prompt` is the goal. The `repoUrl` is the repo. The `workingBranch` is the branch you work on. Apply the **workflow** skill for clone through push, then use the final message format in your role prompt in `~/.claude/CLAUDE.md`.

Include that final message in `write_reviewer_task` or record it in `## Summary` when you call `complete_event`.

## Reply

```markdown
## Event
- traceID: <id>
- repoUrl: <url>
- workingBranch: <branch>
- claimed: true | none
- state: /opt/swarm/state.json
```

Use `claimed: none` for a queue job or an `event:coder` job. Use `claimed: true` after `claim_event` succeeds. After that, add the final message from your role prompt.
