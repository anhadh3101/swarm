#!/usr/bin/env python3
"""Orchestrator prototype: ensure streams/groups and forward pipeline stages."""

from __future__ import annotations

import json
import os
import uuid

import redis

REDIS_URL = os.environ["REDIS_URL"]
EVENTS_STREAM = "events:orchestrator"

PIPELINE = ("architect", "coder", "reviewer")


def ensure_infrastructure(r: redis.Redis) -> None:
    for role in PIPELINE:
        stream = f"tasks:{role}"
        group = f"{role}-workers"
        try:
            r.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise


def enqueue(r: redis.Redis, role: str, run_id: str, payload: dict) -> str:
    job_id = str(uuid.uuid4())
    r.xadd(
        f"tasks:{role}",
        {
            "run_id": run_id,
            "job_id": job_id,
            "payload": json.dumps(payload),
        },
    )
    return job_id


def handle_event(r: redis.Redis, fields: dict) -> None:
    role = fields.get("role")
    run_id = fields.get("run_id")
    status = fields.get("status")
    if not role or not run_id or status != "ok":
        return

    try:
        idx = PIPELINE.index(role)
    except ValueError:
        return

    if idx + 1 >= len(PIPELINE):
        print(f"[orchestrator] run={run_id} pipeline complete", flush=True)
        return

    next_role = PIPELINE[idx + 1]
    job_id = enqueue(
        r,
        next_role,
        run_id,
        {
            "goal": f"Continue run {run_id} after {role}",
            "prior_role": role,
            "prior_stdout": (fields.get("stdout") or "")[:4000],
        },
    )
    print(
        f"[orchestrator] run={run_id} {role} -> {next_role} job={job_id}",
        flush=True,
    )


def main() -> None:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    ensure_infrastructure(r)

    try:
        r.xgroup_create(EVENTS_STREAM, "orchestrator", id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise

    print("[orchestrator] ready (consume events, chain architect->coder->reviewer)", flush=True)

    while True:
        messages = r.xreadgroup(
            "orchestrator",
            "orchestrator-1",
            {EVENTS_STREAM: ">"},
            count=10,
            block=5000,
        )
        if not messages:
            continue
        for _stream, entries in messages:
            for msg_id, fields in entries:
                handle_event(r, fields)
                r.xack(EVENTS_STREAM, "orchestrator", msg_id)


if __name__ == "__main__":
    main()
