---
name: check-for-tasks
description: >-
  Checks this container's task queue and handles one review request from the
  coder. Reviews the branch and sends the result back to the coder. Use when
  /loop fires.
---

# Check for tasks

## Poll

```bash
curl -sS -w "\n%{http_code}" http://127.0.0.1:8080/next
```

The last line is the status code. The body above it is the task.

- `204`: the queue is empty. Stop this turn and do nothing else.
- `200`: handle the task below.

The task has `traceID`, `repoUrl`, `workingBranch`, `prompt`, and `from`. `prompt` is the coder's review request. `from` is the sender's Docker container name (use it to reach that peer's queue). Write `/opt/swarm/state.json` with `traceID`, `repoUrl`, `workingBranch`, and `from` before any other work.

## Review

Follow the **workflow** skill through **Confirm**, and set the approval line as that skill describes. Skip its **Decide** section: do not call `complete_event` or `write_coder_task`.

Stay in this turn until Greptile finishes. Do not leave a review running in the background.

## Send the result to the coder

Send your final message back whether the result is `approved` or `changes requested`:

```bash
curl -sS -X POST "http://<from>:8080/chat" \
  -H "Content-Type: application/json" \
  -d '{"traceID":"<traceID>","repoUrl":"<repoUrl>","workingBranch":"<workingBranch>","prompt":"<your final message>"}'
```

Use `from` from state (the coder container that sent this task).

`prompt` must include the `## Approval status` section exactly as written. The coder reads that line to decide whether to fix or open a pull request.

## Finish

Reply with the final message from `~/.claude/CLAUDE.md`.