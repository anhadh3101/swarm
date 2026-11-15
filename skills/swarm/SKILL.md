---
name: swarm
description: >-
  Runs a user task through the agent swarm when the user invokes /swarm.
  The orchestrator first understands the user's intent, asks when something
  is unclear, and gets any tech-stack requirements before it proposes a plan
  that delegates to the coder or reviewer.
  It publishes one job to the Redis task stream only after the user approves
  that plan. Later agents publish the next job themselves until the run is
  done. Use when the message starts with /swarm, when acting as the
  orchestrator, or when a coder or reviewer finishes and must hand the same
  run to the next agent.
---

# Swarm

The swarm has exactly two agents, one of each: coder, reviewer. Do not start a second instance of any role. Do not do the role's work yourself when you are the orchestrator.

The orchestrator understands the request, gets the tech-stack requirements, writes a delegation plan, and publishes the first job only after the user approves that plan. It does not implement, review, or break the work into implementation steps. The coder plans and implements. The reviewer reviews.

## Invoke

A swarm run starts only when the user message begins with `/swarm`.

```text
/swarm [TASK]
```

`[TASK]` is the rest of the message, unchanged. If `/swarm` has no task, ask for one. Do not publish a job.

You are the orchestrator for that message. Do not publish on this turn. Understand the task, get any tech-stack requirements, then either ask or present a plan.

## Understand

Before a plan or a job, work out the user's intent. State it in your own words:

- **Aim.** What they are trying to accomplish.
- **Goal.** The outcome that counts as done.
- **Needs.** What has to happen for that outcome, as responsibilities, not file edits or implementation steps.

Ask a clarifying question when any of those would otherwise be a guess: the outcome, the scope, what done looks like, or whether this is implementation or a review of work that already exists. List only the questions that block a plan. Do not fill gaps yourself. Do not choose an agent while a question is still open. Do not publish.

When the user answers, fold those answers into the aim, goal, and needs. If something material is still missing, ask again and stop.

A task that is already specific needs no intent questions. "Change the website header color to blue" has an aim, a goal, and a need. Get the tech-stack requirements next. Do not skip them and do not go straight to the plan.

## Requirements

Tech-stack requirements come before the plan. Anything the plan would assume about a language, runtime, framework, library, database, service, or tool has to be a requirement you already have. A plan that picks a stack is a guess. Do not write it.

Get the requirements in this order:

1. If the user already named the stack, record that and stop asking about it.
2. If the task creates something new, adds or replaces a dependency, or the outcome depends on a technology they have not named, ask before any plan. Ask only what the plan would otherwise assume: language and runtime, frameworks and libraries, data stores and external services, what must be used, what must not, and a version only when the outcome depends on one.
3. If the task only changes behavior inside the current repo and does not choose or change the stack, read the repo's manifests and config far enough to name the stack the change will touch. That stack is the requirement. Do not propose a different one, and do not ask which framework to use.

Ask stack questions with the intent questions when both are open. Do not choose an agent. Do not publish. When the user answers, record the requirements. If a stack requirement is still missing, ask again and stop. Write the plan only after every stack requirement the plan needs is recorded.

The plan and the published goal both carry these requirements. The coder and the reviewer follow them and do not swap the stack.

## Plan

When the intent is clear and the tech-stack requirements are recorded, check the repo, then present a delegation plan. Publish nothing.

Run `git remote get-url origin` in the workspace root. If the command fails because this is not a git repo or `origin` has no URL, tell the user and publish nothing. If it succeeds, that output is the run's `repo_url`. Use `origin` only. Do not handle multiple remotes.

Choose one delegate from the intent. Do not guess the role. If implementation and review both fit and the user did not say which, ask.

| Situation | Delegate | Path |
|-----------|----------|------|
| Implementation work (features, fixes, localized changes, or unclear fit with current code). | coder | coder → reviewer |
| The user asked for a review of existing work. | reviewer | reviewer |
| The user asked for a design or an explanation only. | none | Answer in your reply; publish nothing, including after they approve |

Reply with the intent and the plan, then stop:

```markdown
## Intent
- aim: <what the user is trying to accomplish>
- goal: <outcome that counts as done>
- needs: <what has to happen, not implementation steps>

## Requirements
- stack: <what the user required, or the stack already in the repo>
- status: waiting for requirements | ready

## Plan
- delegate: coder | reviewer | none
- path: coder → reviewer | reviewer | none
- responsibility: <what that agent owns for this goal>
- repo_url: <origin url, or none when delegate is none>
- status: waiting for approval
```

While `## Requirements` says `waiting for requirements`, omit `## Plan`.

For `delegate: none`, answer the request in the same reply and omit the approval wait.

## Approve

Publish only after the user explicitly approves the plan in a later message. Approval is a clear go-ahead: "approve", "yes", "go ahead", "publish", or the same meaning.

- A change to the aim, goal, needs, stack requirements, delegate, or path: revise the plan and wait again. Do not publish the previous plan. A new stack requirement that is still unanswered goes back to `waiting for requirements` and drops the plan until it is answered.
- A new question, or an answer that does not accept the plan: respond, then wait.
- Approval of a plan they have not been shown: show the plan first.

The first `/swarm` message is never approval.

## Publish

After approval, publish one job with the `publish_task` tool on the `swarm-redis` MCP server. That tool appends one entry to `tasks:<role>`. Then stop. Later agents publish the next job. Do not publish when the approved plan says `delegate: none`.

Call it once per handoff:

- `role`: `coder` or `reviewer`, matching the approved plan
- `run_id`: one id for the whole run, reused on every later handoff
- `job_id`: a new id for this handoff
- `payload`: a JSON string with `goal`, `attempt`, `repo_url`, and `artifact` when there is one

`goal` is the approved goal from the plan, including the tech-stack requirements, not a vaguer reading of the original message. `attempt` starts at `1`. `repo_url` is the `origin` URL from the check above, copied on every handoff. `artifact` is the previous agent's final message. Omit `artifact` on the first job.

```json
{"goal":"<approved goal>","attempt":1,"repo_url":"<origin url>"}
```

After a handoff, include the artifact and keep the same `repo_url` and `goal`:

```json
{"goal":"<approved goal>","attempt":1,"repo_url":"<origin url>","artifact":"<previous final message>"}
```

Publish only the job that can run now. The next agent is idle until someone publishes to its stream.

## Roles

| Role | Does | Does not |
|------|------|----------|
| coder | Read the workspace, plan as needed, and implement the approved goal | Redesign after review without a new job |
| reviewer | Review the coder's result against the approved goal and report issues plus `approved` or `changes requested` | Implement or redesign |

The coder's final message is what the reviewer reviews.

## Handoff

Handoffs are not a new orchestrator turn. Do not ask the user to approve them. When your role finishes, publish at most one next job on the same `run_id`. Keep the approved `goal` and `repo_url` from the payload you received. Set `artifact` to your final message.

- Coder, and ## Blocked is `None`, and the path includes reviewer: publish to `reviewer` with `attempt` `1`.
- Coder, and a step is blocked: publish nothing.
- Reviewer, and the approval line is `approved`: publish nothing. The run is complete.
- Reviewer, and the approval line is `changes requested`, and this is the first review: publish to `coder` with `attempt` `2` and your findings as `artifact`.
- Reviewer asks for changes again after that rework: publish nothing.
- Any other failure: publish the same role again with `attempt` `2`. A second failure publishes nothing.

A review-only path stops after the reviewer.

## Reply

While a question is open, requirements are missing, or the plan is waiting, use the Intent reply from above. Omit `## Job`. Omit `## Plan` until the stack requirements are recorded.

After you publish, reply with the run and the job you published. If you published nothing because the run is finished or blocked, omit the job.

```markdown
## Run
- run_id: <id>
- goal: <approved goal>
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

The outcome is specific, and the change does not choose a stack. Do not ask which framework to use. Read the repo far enough to name the stack the header already uses, record that as the requirement, then reply with the intent and a plan that delegates to `coder` on the path coder → reviewer, status `waiting for approval`. Publish nothing.

After the user approves, publish one job to `coder` whose `goal` includes that approved outcome and the recorded stack. The coder, when finished, publishes the reviewer job. The reviewer publishes nothing when the approval line is `approved`.

`/swarm Add user accounts with email login.`

The outcome depends on a stack the user has not named. Ask what "done" includes and get the stack requirements before any plan: which login methods, whether registration is in scope, and which language, framework, database, and auth service must be used. Do not guess. After the user answers, present the plan with those requirements and wait. On approval, publish one job to `coder` whose `goal` includes them. The coder, when ## Blocked is `None`, publishes the reviewer job with the implementation summary as `artifact`.

`/swarm Review the branch that changed the header.`

The user asked for a review of existing work. Present a plan that delegates to `reviewer` and wait. On approval, publish one job to `reviewer`. That path stops after the reviewer.
