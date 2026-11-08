---
name: swarm
description: >-
  Runs a user task through the agent swarm when the user invokes /swarm.
  The orchestrator judges complexity and publishes one job to the Redis task
  stream for the single architect, coder, or reviewer. Later agents publish
  the next job themselves until the run is done. Use when the message starts
  with /swarm, when acting as the orchestrator, or when an architect, coder,
  or reviewer finishes and must hand the same run to the next agent.
---

# Swarm

The swarm has exactly three agents, one of each: architect, coder, reviewer. Do not start a second instance of any role. Do not do the role's work yourself when you are the orchestrator.

## Invoke

A swarm run starts only when the user message begins with `/swarm`.

```text
/swarm [TASK]
```

`[TASK]` is the rest of the message, unchanged. If `/swarm` has no task, ask for one. Do not publish a job.

Before anything else, run `git remote get-url origin` in the workspace root. If the command fails because this is not a git repo or `origin` has no URL, tell the user and publish nothing. If it succeeds, that output is the run's `repo_url`. Use `origin` only. Do not handle multiple remotes.

You are the orchestrator for that message. Read the task, judge its complexity, choose the first agent, and publish one job. Then stop. Later agents publish the next job.

## Complexity

Judge the task before you publish. Do not break it into implementation steps. That is the architect's plan when this path includes the architect.

| Situation | First agent | Path |
|-----------|-------------|------|
| Localized change whose success is obvious from the task. Examples: change website colors, rename a field, fix a typo, adjust copy. | coder | coder → reviewer |
| A complete feature, a major bug fix, a new app, or work whose fit with the current code is unclear. | architect | architect → coder → reviewer |
| The user asked for a design only. | architect | architect |
| The user asked for a review of existing work. | reviewer | reviewer |

If you are unsure, start with the architect.

## Publish

Publish with the `publish_task` tool on the `swarm-redis` MCP server. That tool appends one entry to `tasks:<role>`.

Call it once per handoff:

- `role`: `architect`, `coder`, or `reviewer`
- `run_id`: one id for the whole run, reused on every later handoff
- `job_id`: a new id for this handoff
- `payload`: a JSON string with `goal`, `attempt`, `repo_url`, and `artifact` when there is one

`goal` is the original user task. `attempt` starts at `1`. `repo_url` is the `origin` URL from the check above, copied on every handoff. `artifact` is the previous agent's final message. Omit `artifact` on the first job.

```json
{"goal":"<user task>","attempt":1,"repo_url":"<origin url>"}
```

After a handoff, include the artifact and keep the same `repo_url`:

```json
{"goal":"<user task>","attempt":1,"repo_url":"<origin url>","artifact":"<previous final message>"}
```

Publish only the job that can run now. The next agent is idle until someone publishes to its stream.

## Roles

| Role | Does | Does not |
|------|------|----------|
| architect | Read the workspace and write the design and plan | Edit the workspace or implement |
| coder | Implement the task, following the architect's plan when one was published | Redesign the plan or take work marked out of scope |
| reviewer | Review the coder's result and report issues plus `approved` or `changes requested` | Implement or redesign |

The architect's final message is the coder's plan. The coder's final message is what the reviewer reviews.

## Handoff

When your role finishes, publish at most one next job on the same `run_id`. Keep the original `goal` and `repo_url` from the payload you received. Set `artifact` to your final message.

- Architect, and ## Open questions is `None`, and the path includes coder: publish to `coder` with `attempt` `1`.
- Architect, and an open question blocks the design: publish nothing.
- Coder, and ## Blocked is `None`, and the path includes reviewer: publish to `reviewer` with `attempt` `1`.
- Coder, and a step is blocked: publish nothing.
- Reviewer, and the approval line is `approved`: publish nothing. The run is complete.
- Reviewer, and the approval line is `changes requested`, and this is the first review: publish to `coder` with `attempt` `2` and your findings as `artifact`.
- Reviewer asks for changes again after that rework: publish nothing.
- Any other failure: publish the same role again with `attempt` `2`. A second failure publishes nothing.

A design-only path stops after the architect. A review-only path stops after the reviewer.

## Reply

After you publish, reply with the run and the job you published. If you published nothing because the run is finished or blocked, omit the job.

```markdown
## Run
- run_id: <id>
- goal: <user task>
- repo_url: <origin url>
- path: <role> → <role>
- status: ready | done | blocked | failed
- stage: <role that now owns the run, or none>
- attempt: <1 or 2>

## Job
- job_id: <id>
- role: <role>
- stream: tasks:<role>
- attempt: <1 or 2>
- artifact: <previous final message, or none>
```

## Examples

`/swarm Change the website header color to blue.`

The change is local and the result is obvious. Publish one job to `coder`. The coder, when finished, publishes the reviewer job. The reviewer publishes nothing when the approval line is `approved`.

`/swarm Add user accounts with email login.`

This is a feature and needs a plan. Publish one job to `architect`. The architect, when ## Open questions is `None`, publishes the coder job with the plan as `artifact`. The coder then publishes the reviewer job.
