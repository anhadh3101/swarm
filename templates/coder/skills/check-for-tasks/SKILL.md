---
name: check-for-tasks
description: >-
  Checks this container's task queue and handles one task from the reviewer.
  Fixes requested changes and asks for re-review, or opens a pull request when
  the reviewer approved. Use when /loop fires.
---

# Check for tasks

## Poll

```bash
curl -sS -w "\n%{http_code}" http://127.0.0.1:8080/next
```

The last line is the status code. The body above it is the task.

- `204`: the queue is empty. Stop this turn and do nothing else.
- `200`: handle the task below.

The task has `traceID`, `repoUrl`, `workingBranch`, `prompt`, and `from`. `prompt` is the reviewer's final message. `from` is the sender's Docker container name (use it to reach that peer's queue). Write `/opt/swarm/state.json` with `traceID`, `repoUrl`, `workingBranch`, and `from` before any other work.

Read the line under `## Approval status` in `prompt`.

## Changes requested

1. Follow the **workflow** skill to check out `workingBranch`, make the fixes, run the checks, commit, and push. Fix the **Critical** and **Major** findings in `prompt`. Skip that skill's **Finish** section.
2. Ask the reviewer to review again:

```bash
curl -sS -X POST "http://<from>:8080/chat" \
  -H "Content-Type: application/json" \
  -d '{"traceID":"<traceID>","repoUrl":"<repoUrl>","workingBranch":"<workingBranch>","prompt":"<re-review request>"}'
```

Use `from` from state (the reviewer container that sent this task).

The re-review request names the branch and the new commit SHA, lists each finding you fixed with the file you changed, and includes your final message.

## Approved

Open a pull request from `workingBranch` into the default branch:

```bash
gh pr create --head "<workingBranch>" --base "<default branch>" \
  --title "<short summary>" --body "<what changed, plus any Minor or Nit findings from prompt>"
```

Do not make further code changes. Put the PR URL in `## Summary`.

## Finish

Reply with the final message from `~/.claude/CLAUDE.md`.