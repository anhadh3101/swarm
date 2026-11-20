---
name: workflow
description: >-
  Clones repoUrl into /workspace with GH_TOKEN, explores the repo, implements
  the task prompt on workingBranch from /opt/swarm/state.json, runs checks,
  commits, and pushes to origin, then either marks the trace complete or
  publishes event:reviewer. Use after find-event wrote state.json and before
  the role-prompt final message.
---

# Workflow

Run this after `/opt/swarm/state.json` exists and you are carrying out an accepted coder job. Read that file for `repoUrl`, `workingBranch`, `traceID`, and `prompt`. The `prompt` in that file is the goal. For definition of done, verification, and final message sections, follow `~/.claude/CLAUDE.md`.

Do not print `GH_TOKEN` or embed it in logs, commits, or delegation prompts.

## Preconditions

- `repoUrl` and `workingBranch` are set in `/opt/swarm/state.json`.
- `GH_TOKEN` is available in the environment for GitHub HTTPS clone and push.
- Work only under `/workspace`. Do not store swarm state there.

If `repoUrl` or `workingBranch` is missing, stop and report under `## Blocked` in the role-prompt final message format.

## Prepare /workspace

1. If `/workspace` is a git checkout whose `origin` URL does not match `repoUrl` (normalize both: strip trailing `.git`, ignore `x-access-token` user in URLs), remove checkout contents safely: only delete when `/workspace` is empty or is a clone you are replacing for this job—use `rm -rf /workspace/* /workspace/.[!.]*` when appropriate, not the host paths outside `/workspace`.
2. If `/workspace` is empty or not a git repo, clone into `/workspace` so the repository root is `/workspace` (not `/workspace/repo-name` unless you move files up).

## Clone and auth

Use `GIT_TERMINAL_PROMPT=0`. Prefer HTTPS with the token:

```bash
export GIT_TERMINAL_PROMPT=0
# Build clone URL from repoUrl: host/path from repoUrl, inject token for github.com
git clone "https://x-access-token:${GH_TOKEN}@github.com/OWNER/REPO.git" /workspace
```

Rules:

- Parse `repoUrl` from state (HTTPS or `git@github.com:OWNER/REPO.git`). For `git@` remotes, either convert to HTTPS with token or use `gh repo clone` with `GH_TOKEN` set.
- On `Repository not found` or `403`, report the exact `git`/`gh` error under `## Blocked`. Do not retry with guessed URLs.

Alternatively, when `gh` is available:

```bash
export GH_TOKEN
gh repo clone OWNER/REPO /workspace
```

## Default branch and working branch

From `/workspace`:

```bash
cd /workspace
git fetch origin
DEFAULT="$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')"
# If unset: try main, then master
test -n "$DEFAULT" || DEFAULT=main
git show-ref --verify --quiet "refs/remotes/origin/$DEFAULT" || DEFAULT=master
git checkout -B "$WORKING_BRANCH" "origin/$DEFAULT"
```

Set `WORKING_BRANCH` from `workingBranch` in state. Do not commit on the default branch. Do not push the default branch.

## Understand the codebase

Before editing:

- List top-level layout and read README, package manifests, Makefile, and CI config the repo already uses.
- Find how tests and lint are run (package scripts, `make test`, etc.). Use those commands later; do not invent a new toolchain.
- Use targeted search (`rg`, file reads) to locate code related to the goal in the task `prompt`.

## Implement

- Make the smallest change that satisfies the `prompt`, including any prior feedback embedded in a delegated `prompt`.
- Respect reviewer rework in the prompt when `attempt` > 1 or the prompt includes prior feedback.
- Stay in scope. If the goal is impossible without a guess, stop with `## Blocked` and what you need.

## Verify, commit, push

Match `~/.claude/CLAUDE.md`: run the repo's checks, review the diff, commit on `workingBranch`, push to `origin`.

Configure push auth the same way as clone (token in remote URL or credential helper). Example:

```bash
git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/OWNER/REPO.git"
git push -u origin "$WORKING_BRANCH"
```

Replace `OWNER/REPO` from the same repo you cloned. Never commit `.env`, tokens, or debug-only code.

If push fails, capture command, exit code, and stderr under `## Blocked`.

## Change size (for your decision)

After a successful push, classify the change against the default branch you branched from. From `/workspace`:

```bash
git diff --stat "origin/$DEFAULT...HEAD"
git diff --numstat "origin/$DEFAULT...HEAD"
```

Count **files touched** and **lines changed** (insertions + deletions from `--numstat`). Treat any generated lockfile-only churn as part of the diff unless the goal was explicitly to update that lockfile only.

| Size | Typical signal |
|------|----------------|
| **minor** | At most 2 files and at most 50 lines changed; or docs/copy/style only with no behavior, auth, or API change |
| **medium** | 3–15 files, or 51–500 lines; or any auth, payments, persistence, security, or public API surface |
| **huge** | More than 15 files, or more than 500 lines; or a cross-cutting refactor or new subsystem |

When two tiers conflict, use the **larger** tier (e.g. 2 files but 200 lines → medium). Use this label in your reasoning; it does not force the outcome by itself.

## Finish: complete or request review

Run this only when the role prompt **Done** criteria are met: the goal is achieved, the branch is pushed, required checks passed, and `## Blocked` will be `None`. If work is incomplete, blocked, or the goal is not met, skip this section—do not call `complete_event` or `write_reviewer_task`.

Build your **final message** first (see below) so you can reuse it in `write_reviewer_task` or your closing reply.

You must choose exactly one path:

### Mark complete (`complete_event`)

Choose this when you are confident the task is **finished** for the swarm: the prompt goal is met, verification passed, and **review would not add meaningful value** (typical for **minor** changes, or when the prompt never implied a review step and risk is low).

Call `complete_event` on the `swarm-redis` server with `trace_id` from state. Continue only when `completed` is `true`. If `completed` is `false`, record the returned `status` in `## Summary` and still post your final message—do not publish to `event:reviewer` unless you then deliberately switch to the review path below.

Do **not** call `write_reviewer_task` on this path.

### Request review (`write_reviewer_task`)

Choose this when the goal is met and the branch is ready, but **another agent should verify** the change before the run closes—typical for **medium** or **huge** diffs, behavioral or security-sensitive edits, or whenever you are unsure and review is cheaper than a bad merge.

Call `write_reviewer_task` on the `swarm-redis` server:

- `trace_id`: from state
- `repo_url`: same `repoUrl` from state
- `from_role`: `coder`
- `prompt`: a short review request with the original goal, branch name, change size (`minor`, `medium`, or `huge`), why you want review, and paste the final message sections the reviewer needs (at least `## Summary`, `## Branch`, `## Files changed`, `## Verification`)

Do **not** call `complete_event` on this path. The reviewer or a later step closes the trace.

### Decision guide

| You believe | Typical action |
|-------------|----------------|
| Goal done; change is minor or clearly safe; no review requested in the prompt | `complete_event` |
| Goal done; medium/huge, risky, or you want a second pair of eyes | `write_reviewer_task` |
| Goal not done, or blocked, or push/checks failed | Neither call |

When unsure between complete and review, prefer `write_reviewer_task` unless the change is clearly **minor** and verification is strong.

## Hand back to the role prompt

Produce the **final message** sections from `~/.claude/CLAUDE.md` (`## Summary`, `## Branch`, `## Files changed`, `## Verification`, `## Blocked`). In `## Summary`, state your finish choice: `complete_event` (and whether it succeeded), `event:reviewer` published, or neither (incomplete/blocked).