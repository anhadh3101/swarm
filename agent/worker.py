#!/usr/bin/env python3
"""Redis Stream consumer; runs codex exec for each job (prototype)."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import redis

REDIS_URL = os.environ["REDIS_URL"]
ROLE = os.environ["ROLE"]
TASK_STREAM = os.environ["TASK_STREAM"]
CONSUMER_GROUP = os.environ["CONSUMER_GROUP"]
REPLY_STREAM = os.environ.get("REPLY_STREAM", "events:orchestrator")
RUNS_ROOT = os.environ.get("RUNS_ROOT", "/swarm/runs")
CONSUMER_NAME = os.environ.get("HOSTNAME", f"{ROLE}-worker")


def ensure_group(r: redis.Redis) -> None:
    try:
        r.xgroup_create(TASK_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def default_prompt(payload: dict) -> str:
    goal = payload.get("goal") or payload.get("prompt") or json.dumps(payload)
    templates = {
        "architect": (
            f"You are the architect agent. Produce a concise implementation plan "
            f"for: {goal}\nWrite plan.md under the run directory if one exists."
        ),
        "coder": (
            f"You are the coder agent. Implement the following task in the workspace: "
            f"{goal}"
        ),
        "reviewer": (
            f"You are the reviewer agent. Review recent changes and report issues "
            f"and approval status for: {goal}"
        ),
    }
    return templates.get(ROLE, goal)


def run_codex(prompt: str, run_id: str) -> subprocess.CompletedProcess[str]:
    run_dir = os.path.join(RUNS_ROOT, run_id)
    os.makedirs(run_dir, exist_ok=True)
    cmd = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "-C",
        "/workspace",
        prompt,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )


def main() -> None:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    ensure_group(r)
    print(f"[{ROLE}] listening on {TASK_STREAM} group={CONSUMER_GROUP}", flush=True)

    while True:
        messages = r.xreadgroup(
            CONSUMER_GROUP,
            CONSUMER_NAME,
            {TASK_STREAM: ">"},
            count=1,
            block=5000,
        )
        if not messages:
            continue

        for _stream, entries in messages:
            for msg_id, fields in entries:
                try:
                    run_id = fields.get("run_id", "unknown")
                    job_id = fields.get("job_id", msg_id)
                    raw = fields.get("payload", "{}")
                    payload = json.loads(raw) if raw else {}
                    prompt = payload.get("prompt") or default_prompt(payload)

                    print(f"[{ROLE}] job={job_id} run={run_id}", flush=True)
                    result = run_codex(prompt, run_id)

                    r.xadd(
                        REPLY_STREAM,
                        {
                            "role": ROLE,
                            "run_id": run_id,
                            "job_id": job_id,
                            "status": "ok" if result.returncode == 0 else "error",
                            "exit_code": str(result.returncode),
                            "stdout": (result.stdout or "")[-8000:],
                            "stderr": (result.stderr or "")[-8000:],
                        },
                    )
                    r.xack(TASK_STREAM, CONSUMER_GROUP, msg_id)
                except Exception as exc:  # noqa: BLE001 — prototype worker
                    r.xadd(
                        REPLY_STREAM,
                        {
                            "role": ROLE,
                            "run_id": fields.get("run_id", "unknown"),
                            "job_id": fields.get("job_id", msg_id),
                            "status": "error",
                            "error": str(exc),
                        },
                    )
                    r.xack(TASK_STREAM, CONSUMER_GROUP, msg_id)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
