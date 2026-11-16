import os
from datetime import datetime, timezone
from uuid import uuid4

from mcp.server import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from model import (
    EVENTS,
    MESSAGES,
    STATUS_AVAILABLE,
    STATUS_COMPLETE,
    STATUS_IN_PROGRESS,
    EVENT_CODER,
    EVENT_REVIEWER,
    event_fields,
    event_status_key,
    message_fields,
    task_fields,
)
from redis_client import get_redis

# Initialize the FastMCP server
mcp = FastMCP(
    "swarm-redis",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "9001")),
)

# Endpoint to check the health of the server
@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    try:
        # Ping the redis client, if it fails then redis isn't connected
        get_redis().ping()
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "detail": str(exc)},
            status_code=503,
        )
    return JSONResponse({"status": "ok"})


def _require(value: str, name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _write(stream: str, fields: dict[str, str]) -> str:
    return get_redis().xadd(stream, fields)


def _read(stream: str, after: str = "-") -> list[dict[str, str]]:
    cursor = after.strip()
    start = "-" if cursor in ("", "-") else f"({cursor}"
    rows = get_redis().xrange(stream, min=start, max="+")
    return [{"id": entry_id, **fields} for entry_id, fields in rows]


CLAIM_SCRIPT = """
local current = redis.call('HGET', KEYS[1], 'status')
if current == false then
  return {0, ''}
end
if current ~= ARGV[1] then
  return {0, current}
end
redis.call('HSET', KEYS[1], 'status', ARGV[2])
return {1, ARGV[2]}
"""

def _message_sort_key(entry: dict[str, str]) -> tuple[int, str]:
    raw = entry.get("messageNum", "")
    try:
        return (int(raw), raw)
    except ValueError:
        return (10**9, raw)


@mcp.tool()
def publish_event(prompt: str, repo_url: str, working_branch: str) -> dict[str, str]:
    """Append one task to the events stream.

    traceID is a new UUID and startTime is the time of this call. The caller
    supplies prompt, repo_url, and working_branch. Status is stored on the
    hash event:<traceID> as AVAILABLE. Returns the Redis entry id and traceID.
    """
    trace_id = str(uuid4())
    start_time = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    fields = event_fields(
        trace_id,
        start_time,
        _require(prompt, "prompt"),
        _require(repo_url, "repo_url"),
        _require(working_branch, "working_branch"),
    )
    pipe = get_redis().pipeline()
    pipe.xadd(EVENTS, fields)
    
    key = event_status_key(trace_id=trace_id)
    pipe.hset(key, "status", STATUS_AVAILABLE)
    entry_id, _ = pipe.execute()
    return {"id": entry_id, "traceID": trace_id}


@mcp.tool()
def claim_event(trace_id: str) -> dict[str, str]:
    """Set the event status to IN_PROGRESS when it is AVAILABLE.

    Status lives on the hash event:<traceID>. Returns claimed true when this
    call won, otherwise claimed false and the status already stored.
    """
    trace = _require(trace_id, "trace_id")
    won, status = get_redis().eval(
        CLAIM_SCRIPT,
        1,
        event_status_key(trace),
        STATUS_AVAILABLE,
        STATUS_IN_PROGRESS,
    )
    return {
        "claimed": "true" if int(won) == 1 else "false",
        "status": status or "",
    }


@mcp.tool()
def complete_event(trace_id: str) -> dict[str, str]:
    """Set the event status to COMPLETE when it is IN_PROGRESS.

    Status lives on the hash event:<traceID>. Returns completed true when this
    call updated the status, otherwise completed false and the status already
    stored. Call when the run for this traceID is finished and no further
    swarm work is required.
    """
    trace = _require(trace_id, "trace_id")
    won, status = get_redis().eval(
        CLAIM_SCRIPT,
        1,
        event_status_key(trace),
        STATUS_IN_PROGRESS,
        STATUS_COMPLETE,
    )
    return {
        "completed": "true" if int(won) == 1 else "false",
        "status": status or "",
    }


@mcp.tool()
def read_events(after: str = "-") -> list[dict[str, str]]:
    """Read events. Pass the last seen entry id as after to read only newer ones.

    after defaults to "-" (the whole stream). Each returned object includes the
    Redis entry id plus traceID, startTime, prompt, repoUrl, and workingBranch.
    status is read from the hash event:<traceID> and is AVAILABLE, IN_PROGRESS,
    or COMPLETE.
    """
    entries = _read(EVENTS, after)
    if not entries:
        return entries
    pipe = get_redis().pipeline()
    for entry in entries:
        pipe.hget(event_status_key(entry["traceID"]), "status")
    for entry, live in zip(entries, pipe.execute()):
        if live:
            entry["status"] = live
    return entries


@mcp.tool()
def write_message(trace_id: str, message_num: str, body: str) -> str:
    """Append one progress note to the messages stream. Returns the Redis entry id.

    That id is the messageID and is not stored as a field. message_num is the
    next number on this traceID's board (1, 2, 3, ...).
    """
    fields = message_fields(
        _require(trace_id, "trace_id"),
        _require(message_num, "message_num"),
        _require(body, "body"),
    )
    return _write(MESSAGES, fields)


@mcp.tool()
def read_messages(trace_id: str) -> list[dict[str, str]]:
    """Read one trace's message board from the messages stream, ordered by messageNum.

    Each object includes the Redis entry id (the messageID) plus traceID,
    messageNum, and body.
    """
    trace = _require(trace_id, "trace_id")
    board = [entry for entry in _read(MESSAGES) if entry.get("traceID") == trace]
    board.sort(key=_message_sort_key)
    return board


@mcp.tool()
def write_coder_task(trace_id: str, prompt: str, repo_url: str, from_role: str) -> str:
    """Append one delegated task to event:coder. Returns the Redis entry id."""
    fields = task_fields(
        _require(trace_id, "trace_id"),
        _require(prompt, "prompt"),
        _require(repo_url, "repo_url"),
        _require(from_role, "from_role"),
    )
    return _write(EVENT_CODER, fields)


@mcp.tool()
def read_coder_tasks(after: str = "-") -> list[dict[str, str]]:
    """Read event:coder. Pass the last seen entry id as after to read only newer ones.

    after defaults to "-" (the whole stream). Each object includes the Redis
    entry id plus traceID, prompt, repoUrl, and from. This lists entries; it
    does not claim them.
    """
    return _read(EVENT_CODER, after)


@mcp.tool()
def write_reviewer_task(trace_id: str, prompt: str, repo_url: str, from_role: str) -> str:
    """Append one delegated task to event:reviewer. Returns the Redis entry id."""
    fields = task_fields(
        _require(trace_id, "trace_id"),
        _require(prompt, "prompt"),
        _require(repo_url, "repo_url"),
        _require(from_role, "from_role"),
    )
    return _write(EVENT_REVIEWER, fields)


@mcp.tool()
def read_reviewer_tasks(after: str = "-") -> list[dict[str, str]]:
    """Read event:reviewer. Pass the last seen entry id as after to read only newer ones.

    after defaults to "-" (the whole stream). Each object includes the Redis
    entry id plus traceID, prompt, repoUrl, and from. This lists entries; it
    does not claim them.
    """
    return _read(EVENT_REVIEWER, after)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
