---
name: workflow
description: >-
  Reviews workingBranch with `greptile review --agent` after event-found
  stored state. Checks the branch out, confirms findings, then either
  approves or sends the confirmed findings back on event:coder. Does not
  edit the repo, push, or open a pull request.
---

# Workflow

Run this after `/opt/swarm/state.json` exists and you have accepted a review. Read that file for `traceID`, `repoUrl`, and `workingBranch`. The task `prompt` is the goal and any prior findings. The final message sections are in `~/.claude/CLAUDE.md`.

You are read-only toward the repository. Do not edit tracked files, apply patches, commit, push, force-push, or open a pull request. Do not pass `--include` to Greptile.

These writes are part of the review and are allowed:

- cloning and fetching into `/workspace`
- `git checkout -B` of `workingBranch` inside that clone
- Greptile's own files under the home directory
- the review output under `/tmp`

Do not print `GH_TOKEN` or `GREPTILE_API_KEY`, and do not put either value in the final message or in a handoff prompt.

## Preconditions

Stop before Greptile when any of these fail. Say why under **Findings**, set the approval line to `changes requested`, and do not publish to `event:coder`. A setup failure is not a code defect for the coder to fix.

- `traceID`, `repoUrl`, and `workingBranch` are set in `/opt/swarm/state.json`.
- `GH_TOKEN` is set (clone and fetch).
- `GREPTILE_API_KEY` is set. `greptile whoami` exits 0.

`workingBranch` is the branch under review. The base branch is the target named in the prompt. When the prompt names none, use the remote default: `origin/HEAD`, then `main`, then `master`.

## Checkout

`greptile review` reviews committed changes on the current named branch against a base. Detached HEAD is an error. Uncommitted files are not part of the review.

If `/workspace` is missing, empty, or its `origin` is a different repo, clone so the repository root is `/workspace`. Compare remotes after stripping a trailing `.git` and any `x-access-token` user. Use `GIT_TERMINAL_PROMPT=0`. Replace only `/workspace` contents.

```bash
export GIT_TERMINAL_PROMPT=0
git clone "https://x-access-token:${GH_TOKEN}@github.com/OWNER/REPO.git" /workspace
```

Parse `OWNER/REPO` from `repoUrl`. On `Repository not found` or `403`, stop with that error under **Findings**. Do not guess another URL.

Then:

```bash
cd /workspace
git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/OWNER/REPO.git"
git fetch origin --prune
git checkout -B "$SRC" "origin/$SRC"
git rev-parse --verify "origin/$TARGET"
```

`$SRC` is `workingBranch`. `$TARGET` is the base branch name, without `origin/`.

When the prompt names a commit SHA, `git rev-parse HEAD` must equal it. If it does not, fetch once more. If it still does not, stop under **Findings** and do not review a stale checkout. Do not publish to `event:coder`.

## Review

Confirm the repo is already enabled for Greptile. `greptile init --json` only prints status. Do not enable the repo yourself. If it is not enabled, stop as a setup failure.

Run one review. A second `greptile review` starts a new review. Pass the goal as `--instructions` (one short paragraph: what success means, plus any stack constraints from the prompt).

The command can run for up to 30 minutes. Start it in the background and poll. Do not start another review while this one is running.

```bash
OUT=/tmp/greptile-review-$TRACE
rm -f "$OUT.out" "$OUT.err" "$OUT.exit"
greptile review --agent -b "$TARGET" --no-color --instructions "$GOAL" \
  > "$OUT.out" 2> "$OUT.err"
echo $? > "$OUT.exit"
```

`$TRACE` is `traceID`. `$GOAL` is the goal paragraph.

About once a minute, until `$OUT.exit` exists or 30 minutes pass:

```bash
greptile review status --commit "$(git rev-parse HEAD)"
```

Exit `3` means still running. Exit `0` means a completed review exists for that commit. Then read `$OUT.exit`.

| Exit | What to do |
|------|------------|
| `0` | Read `$OUT.out` and continue to **Confirm**. |
| `1`, and stderr says there are no committed changes against the base | Say that under **Findings**. Set the approval line to `changes requested`. Do not invent findings. |
| `1`, auth, remote, or base branch | Setup failure. Do not publish to `event:coder`. |
| `1` after the 30 minute wait, or `130` | Run `greptile review --resume --agent --no-color` once, the same way, into a new `$OUT`. If that also fails, setup failure. |
| `2` | Setup failure. The invocation was wrong or this is not a git repo. |

On a timeout or a dropped background command, use `--resume`. Do not start a fresh `greptile review`.

## Confirm

`$OUT.out` is the review text for a coding agent. Treat it as input, not the verdict.

For each finding, open the file and line range it names and decide if it is real on this branch. Drop false positives. Keep a one-line reason for each drop. Also check completeness against the goal. Greptile only knows the goal from `--instructions`.

Map what you keep onto the role-prompt groups:

| In the Greptile output | Findings group |
|------------------------|----------------|
| `P0`, or a security finding | **Critical** |
| `P1` | **Major** |
| `P2` | **Minor** or **Nit** |
| A goal or completeness gap you found | The same scale |

Each kept item names the file, the lines, and the behavior.

## Decide

Any confirmed **Critical** or **Major** item means the approval line is `changes requested`. Otherwise it is `approved`.

Do not open a pull request on either path.

### Approved

Call `complete_event` on `swarm-redis` with `trace_id` from state. Do not call `write_coder_task`.

### Changes requested

Publish once with `write_coder_task` on `swarm-redis`:

- `trace_id`: from state
- `repo_url`: the same `repoUrl`
- `from_role`: `reviewer`
- `prompt`: the goal, `$SRC`, `$TARGET`, the reviewed SHA (`git rev-parse HEAD`), and the kept findings. Paste the kept part of `$OUT.out` (file, lines, severity, and the finding text). Ask the coder to fix those items and request review again. Do not paste dropped findings or the raw stream of every Greptile comment.

If this prompt is already a re-review and the same **Critical** or **Major** items are still present, do not publish again. Leave them in the final message.

A review that did not run (setup failure, stale SHA, repo not enabled) does not get a `write_coder_task`.

## Final message

Use the sections from `~/.claude/CLAUDE.md`, in order. Under **Findings**, list kept items by severity and name anything you dropped, with the reason. Under **What was delivered**, include the branch, the reviewed SHA, and the base. The approval line is only `approved` or `changes requested`.
