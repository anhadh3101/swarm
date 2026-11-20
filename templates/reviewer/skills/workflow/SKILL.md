---
name: workflow
description: >-
  Reviews workingBranch against the target branch with Claude Code's built-in
  review. Checks the branch out, confirms findings, then asks the coder either
  to fix confirmed Critical or Major findings or to open a pull request. Does
  not edit the repo, push, or open a pull request.
---

# Workflow

Read `/opt/swarm/state.json` for `traceID`, `repoUrl`, `workingBranch`, `prompt`, and `sender`. Use `sender` when it is set. The request may also give `targetBranch`. The `prompt` is the goal and the coder's implementation summary. The final message sections are in `~/.claude/CLAUDE.md`.

You are read-only toward the repository. Do not edit tracked files, apply patches, commit, push, force-push, or open a pull request.

These writes are part of the review and are allowed:

- cloning and fetching into `/workspace`
- `git checkout -B` of `workingBranch` inside that clone
- review output under `/tmp`

Do not print `GH_TOKEN`, and do not put it in the final message or in a message to the coder.

## Branches

`$SRC` is `workingBranch`. `$TARGET` is `targetBranch`. When the request has no `targetBranch`, use the remote default: `origin/HEAD`, then `main`, then `master`. `$TRACE` is `traceID`.

## Checkout

Parse `OWNER/REPO` from `repoUrl`. Use `GIT_TERMINAL_PROMPT=0`.

If `/workspace` already holds this repo (its `origin` matches `repoUrl` after stripping a trailing `.git` and any `x-access-token` user), update it:

```bash
cd /workspace
git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/OWNER/REPO.git"
git fetch origin --prune
git checkout -B "$SRC" "origin/$SRC"
```

Otherwise, replace the contents of `/workspace` with a fresh clone, then check out the branch:

```bash
git clone "https://x-access-token:${GH_TOKEN}@github.com/OWNER/REPO.git" /workspace
cd /workspace
git checkout -B "$SRC" "origin/$SRC"
```

Then check:

- `git status --porcelain` is empty.
- `git rev-parse --verify "origin/$TARGET"` succeeds.
- When the prompt names a commit SHA, `git rev-parse HEAD` equals it. If it does not, fetch once more.

If a check fails, or the clone returns `Repository not found` or `403`, stop. This is a setup failure, not a code defect. Say what failed under **Findings**, set the approval line to `changes requested`, and do not send anything to the coder.

## Review

Run the built-in review once, in the foreground:

```bash
cd /workspace
claude -p "/review high --max-findings all origin/$TARGET...$SRC" > /tmp/review-$TRACE.md
```

Use `/review`, not `/code-review`. Do not pass `--fix` or `--comment`.

If the review reports that there are no changes against the target, say that under **Findings**, set the approval line to `changes requested`, and do not send anything to the coder.

## Confirm

`/tmp/review-$TRACE.md` is input, not the verdict. For each finding, open the file and lines it names and decide if it is real on this branch. Drop false positives, with a one-line reason for each. Also check the change against the goal in `prompt`. The review does not know the goal.

Group what you keep:

- **Critical**: a security issue, data loss, or a crash on a main path.
- **Major**: a correctness bug, broken behavior, or part of the goal left undone.
- **Minor**: a real gap that does not break the goal, such as a missing edge case or weak error message.
- **Nit**: style, naming, or cleanup.

Each kept item names the file, the lines, and the behavior.

## Decide

Any confirmed **Critical** or **Major** item means the approval line is `changes requested`. Otherwise it is `approved`.

Both outcomes go to the coder. Only the message differs.

- `changes requested`: ask the coder to fix the **Critical** and **Major** items and request review again.
- `approved`: ask the coder to open a pull request from `$SRC` into `$TARGET`. Include any **Minor** and **Nit** items as notes, not required fixes.

The message includes the goal, `$SRC`, `$TARGET`, the reviewed SHA (`git rev-parse HEAD`), the kept findings, and the `## Approval status` section exactly as written in the final message. Do not include dropped findings.

### Send to the coder

When `sender` is set, post to that coder:

```bash
curl -sS -X POST "http://<sender>:8080/chat" \
  -H "Content-Type: application/json" \
  -d '{"traceID":"<traceID>","repoUrl":"<repoUrl>","workingBranch":"<workingBranch>","prompt":"<message>"}'
```

When `sender` is not set, call `write_coder_task` on `swarm-redis`:

- `trace_id`: `traceID`
- `repo_url`: `repoUrl`
- `from_role`: `reviewer`
- `prompt`: the message

Send once. Do not call `complete_event`. Do not open a pull request.

## Final message

Use the sections from `~/.claude/CLAUDE.md`, in order. Under **What was delivered**, include `$SRC`, the reviewed SHA, and `$TARGET`. Under **Findings**, list kept items by severity and name anything you dropped, with the reason. The approval line is only `approved` or `changes requested`.