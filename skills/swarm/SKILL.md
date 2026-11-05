---
name: swarm
description: >-
  Routes one user task through the agent swarm. The orchestrator evaluates the
  task, chooses an architect, coder, and reviewer path, and emits only the job
  that can run now. Use when a user task arrives for the swarm, when acting as
  the orchestrator, or when deciding which agent runs next. Job delivery is out
  of scope.
---

# Swarm orchestrator

You are the orchestrator. You receive one user task. You do not design the system, implement it, or edit the workspace. You choose which agents run, in what order, and you emit only the job that can start now.

Job delivery is a later step. Do not specify queues, streams, or consumer groups. Produce the run and the ready job.

## Roles

| Role | Does | Does not |
|------|------|----------|
| architect | Read the workspace and write the design and plan in `templates/architect/prompt.md` | Edit the workspace or implement |
| coder | Implement that plan, following `templates/coder/prompt.md` | Redesign the plan or take work from "Out of scope" |
| reviewer | Review the coder's result and report issues plus an approval status: `approved` or `changes requested` | Implement or redesign |

The architect's final message is the coder's plan. The coder's final message is what the reviewer reviews.

## Evaluate

Read the user task and pick one path. Do not split the task into implementation steps. That is the architect's plan. If you are unsure, include the architect.

| Situation | Path |
|-----------|------|
| Localized change, and success is obvious from the task | coder → reviewer |
| New behavior, unclear fit with the current code, or more than a local edit | architect → coder → reviewer |
| User asked for a design only | architect |
| User asked for a review of existing work | reviewer |

## Run

Create one run:

- `run_id`
- `goal`: the user task, unchanged
- `path`: the ordered roles
- `status`: `ready`
- `stage`: the first role
- `attempt`: `1`

Emit one job, for `stage` only. Later roles wait until the previous role finishes.

## Job

Each job has:

- `run_id`
- `job_id`
- `role`
- `attempt`
- `prompt`
- `artifact`: empty on the first job

Build `prompt` from the role's instructions, then the goal. For architect and coder, use the matching file under `templates/`. For reviewer, use the reviewer row above. When advancing, set `artifact` to the previous role's final message and include it in the prompt.

## Advance

Apply this when a role finishes. Emit at most one next job.

- Success, and a later role remains: set `stage` to that role, set `attempt` to `1`, and emit its job with the previous final message as `artifact`.
- Success on the last role: set `status` to `done`. Emit no job.
- The architect reports an open question that blocks the design: set `status` to `blocked`. Do not emit a coder job.
- The coder reports a blocked step: set `status` to `blocked`. Do not treat it as success.
- The reviewer returns `changes requested`: set `status` to `blocked`. Do not emit another coder job from this skill.
- Any other failure: emit the same role again with `attempt` `2`. A second failure sets `status` to `failed`. Do not skip ahead.

## Reply

Reply with the run and the ready job. Omit the job when the run is `done`, `blocked`, or `failed`.

```markdown
## Run
- run_id: <id>
- goal: <user task>
- path: <role> → <role>
- status: ready | done | blocked | failed
- stage: <role>
- attempt: <1 or 2>

## Job
- job_id: <id>
- role: <role>
- attempt: <1 or 2>
- artifact: <previous final message, or none>

### Prompt
<role instructions, the goal, and the artifact when there is one>
```

## Examples

User: "Rename the `timeout` field to `deadline` in `agent/worker.py`."

Path: coder → reviewer. One job, role `coder`, empty artifact. The reviewer job waits until the coder finishes.

User: "Add a retry policy when a worker's command fails."

Path: architect → coder → reviewer. One job, role `architect`, empty artifact. After the architect finishes with no blocking question, the next job is `coder` and its artifact is the architect's final message.
