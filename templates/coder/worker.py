"""Redis Streams worker: consumes tasks:<ROLE>, runs Codex, publishes to events:orchestrator."""

from __future__ import annotations

import json
import os
import re
import shlex
import socket
import subprocess
import tempfile

import redis

ROLE = os.environ["ROLE"]
STREAM = f"tasks:{ROLE}"
GROUP = ROLE
CONSUMER = socket.gethostname()
EVENTS = "events:orchestrator"
TIMEOUT = int(os.environ.get("JOB_TIMEOUT", "1800"))
CLAIM_IDLE_MS = (TIMEOUT + 60) * 1000
# Default bypass: Docker often blocks bubblewrap user namespaces; without it Codex stays read-only.
_DEFAULT_CODEX_FLAGS = "--dangerously-bypass-approvals-and-sandbox"
CODEX_FLAGS = shlex.split(
    os.environ.get("CODEX_FLAGS", _DEFAULT_CODEX_FLAGS).strip()
    or _DEFAULT_CODEX_FLAGS
)
NONE = {"", "none", "none."}

# XREADGROUP BLOCK can wait this long; socket_timeout must be greater or the client aborts mid-wait.
REDIS_BLOCK_MS = int(os.environ.get("REDIS_BLOCK_MS", "5000"))
_default_socket_timeout = float(os.environ.get("REDIS_SOCKET_TIMEOUT", "120"))
_block_sec = REDIS_BLOCK_MS / 1000.0
if _default_socket_timeout < _block_sec + 5:
    _default_socket_timeout = _block_sec + 5


def _redis_client() -> redis.Redis:
    pool = redis.ConnectionPool.from_url(
        os.environ["REDIS_URL"],
        decode_responses=True,
        socket_timeout=_default_socket_timeout,
        socket_connect_timeout=float(os.environ.get("REDIS_CONNECT_TIMEOUT", "30")),
    )
    return redis.Redis(connection_pool=pool)


_r = _redis_client()
_INSTRUCTIONS = open("/app/prompt.md", encoding="utf-8").read()


def section(text: str, title: str) -> str:
    m = re.search(
        rf"^##\s+{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)",
        text,
        re.M | re.S | re.I,
    )
    return m.group(1).strip() if m else ""


def approval_status_line(text: str) -> str | None:
    block = section(text, "Approval status")
    if not block:
        return None
    first = next((ln.strip() for ln in block.splitlines() if ln.strip()), None)
    return first


def classify_final(final: str) -> str:
    if not final.strip():
        return "error"
    if ROLE == "architect":
        oq = section(final, "Open questions").lower()
        return "ok" if oq in NONE else "blocked"
    if ROLE == "coder":
        blk = section(final, "Blocked").lower()
        return "ok" if blk in NONE else "blocked"
    if ROLE == "reviewer":
        line = approval_status_line(final)
        if line is None:
            return "error"
        normalized = line.lower().strip()
        if normalized == "approved":
            return "ok"
        if normalized == "changes requested":
            return "blocked"
        return "error"
    return "ok"


def ensure_group() -> None:
    try:
        _r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def parse_payload(raw: str) -> tuple[dict | None, str | None]:
    """Normalize stream `payload` into {goal, attempt?, artifact?}.

    Accepts:
    - Plain text (non-JSON): treated as the goal string.
    - JSON string: that string is the goal.
    - JSON object: requires a non-empty task in one of several keys (first non-empty wins).
      Optional: artifact, attempt (default 1).
    """
    if not raw.strip():
        return None, "payload must be non-empty"

    try:
        parsed: object = json.loads(raw)
    except json.JSONDecodeError:
        return {"goal": raw.strip(), "attempt": 1}, None

    if isinstance(parsed, str):
        if not parsed.strip():
            return None, "payload JSON string must be non-empty"
        return {"goal": parsed.strip(), "attempt": 1}, None

    if not isinstance(parsed, dict):
        return (
            None,
            f"payload JSON must be an object or string, got {type(parsed).__name__}",
        )

    _goal_keys = (
        "goal",
        "prompt",
        "task",
        "user_goal",
        "description",
        "body",
        "message",
        "instructions",
        "text",
        "content",
        "query",
        "objective",
        "summary",
        "title",
    )
    goal = None
    for key in _goal_keys:
        val = parsed.get(key)
        if val is not None:
            g = val.strip() if isinstance(val, str) else str(val).strip()
            if g:
                goal = val
                break
    if goal is None:
        return (
            None,
            "payload object needs a non-empty task in one of: "
            + ", ".join(_goal_keys),
        )
    goal_str = goal.strip() if isinstance(goal, str) else str(goal).strip()
    if not goal_str:
        return None, "task text (goal/prompt/task/...) must be non-empty"

    out: dict = {"goal": goal_str, "attempt": parsed.get("attempt", 1)}
    if "artifact" in parsed and parsed["artifact"] is not None:
        out["artifact"] = parsed["artifact"]
    return out, None


def build_prompt(p: dict) -> str:
    parts = [_INSTRUCTIONS, "## Goal\n" + str(p["goal"])]
    artifact = p.get("artifact")
    if artifact:
        parts.append("## Input from previous stage\n" + str(artifact))
    return "\n\n".join(parts)


def run_codex(prompt: str) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "last.md")
        try:
            proc = subprocess.run(
                [
                    "codex",
                    "exec",
                    "--cd",
                    "/workspace",
                    "--skip-git-repo-check",
                    "--output-last-message",
                    out,
                    *CODEX_FLAGS,
                    "-",
                ],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
            )
        except FileNotFoundError:
            return (
                127,
                "",
                "codex: command not found in PATH (check base image)",
            )
        final = ""
        if os.path.exists(out):
            final = open(out, encoding="utf-8").read()
        stderr = proc.stderr or ""
        stdout = proc.stdout or ""
        err = stderr
        if stdout.strip():
            err = (
                f"{stderr}\n--- codex stdout (tail) ---\n{stdout[-3500:]}"
            ).strip()
        err = err[-8000:]
        return proc.returncode, final, err


def handle(msg_id: str, f: dict[str, str]) -> None:
    done_key = f"job:{f['job_id']}:done"
    if _r.exists(done_key):
        _r.xack(STREAM, GROUP, msg_id)
        return

    p, parse_err = parse_payload(f["payload"])
    if parse_err is not None:
        pipe = _r.pipeline()
        pipe.xadd(
            EVENTS,
            {
                "run_id": f.get("run_id", ""),
                "job_id": f["job_id"],
                "role": ROLE,
                "attempt": "1",
                "status": "error",
                "final": "",
                "stderr": parse_err,
            },
        )
        pipe.set(done_key, "1", ex=7 * 86400)
        pipe.xack(STREAM, GROUP, msg_id)
        pipe.execute()
        print(f"[{ROLE}] {f['job_id']} -> error (bad payload)", flush=True)
        return

    assert p is not None
    code: int | None = None
    try:
        code, final, err = run_codex(build_prompt(p))
        if code != 0:
            status = "error"
        elif not final.strip():
            status = "error"
            err = (
                err or ""
            ) + "\nexit 0 but no final message file (--output-last-message empty)"
        else:
            status = classify_final(final)
            if status == "error":
                err = (
                    err or ""
                ) + "\noutput failed role validation (see final field in events stream)"
    except subprocess.TimeoutExpired:
        code = None
        final, err, status = "", "codex subprocess timeout", "error"

    pipe = _r.pipeline()
    pipe.xadd(
        EVENTS,
        {
            "run_id": f["run_id"],
            "job_id": f["job_id"],
            "role": ROLE,
            "attempt": str(p.get("attempt", 1)),
            "status": status,
            "final": final,
            "stderr": err if status == "error" else "",
        },
    )
    pipe.set(done_key, "1", ex=7 * 86400)
    pipe.xack(STREAM, GROUP, msg_id)
    pipe.execute()
    if status == "error":
        detail = (err or "").strip().replace("\n", " ")
        if len(detail) > 500:
            detail = detail[:500] + "..."
        prefix = f"exit={code} " if code not in (None, 0) else ""
        print(f"[{ROLE}] {f['job_id']} -> {status} {prefix}{detail}", flush=True)
    else:
        print(f"[{ROLE}] {f['job_id']} -> {status}", flush=True)


def reclaim() -> None:
    _, msgs, *_ = _r.xautoclaim(
        STREAM, GROUP, CONSUMER, min_idle_time=CLAIM_IDLE_MS, start_id="0-0"
    )
    for mid, fields in msgs:
        handle(mid, fields)


def main() -> None:
    ensure_group()
    print(f"[{ROLE}] waiting on {STREAM}", flush=True)
    reclaim()
    while True:
        resp = _r.xreadgroup(
            GROUP, CONSUMER, {STREAM: ">"}, count=1, block=REDIS_BLOCK_MS
        )
        if not resp:
            reclaim()
            continue
        for _, msgs in resp:
            for msg_id, fields in msgs:
                handle(msg_id, fields)


if __name__ == "__main__":
    main()
