import os

from mcp.server import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from model import (
    EVENTS,
    MESSAGES,
    TASKS_CODER,
    TASKS_REVIEWER,
    event_fields,
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


def _message_sort_key(entry: dict[str, str]) -> tuple[int, str]:
    raw = entry.get("messageNum", "")
    try:
        return (int(raw), raw)
    except ValueError:
        return (10**9, raw)


@mcp.tool()
def write_event(trace_id: str, start_time: str, turns: str, prompt: str, repo_url: str) -> str:
    """Append one task to the events stream. Returns the Redis entry id."""
    fields = event_fields(
        _require(trace_id, "trace_id"),
        _require(start_time, "start_time"),
        _require(turns, "turns"),
        _require(prompt, "prompt"),
        _require(repo_url, "repo_url"),
    )
    return _write(EVENTS, fields)


@mcp.tool()
def read_events(after: str = "-") -> list[dict[str, str]]:
    """Read events. Pass the last seen entry id as after to read only newer ones.

    after defaults to "-" (the whole stream). Each returned object includes the
    Redis entry id plus traceID, startTime, turns, prompt, and repoUrl.
    """
    return _read(EVENTS, after)


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
    """Append one delegated task to tasks:coder. Returns the Redis entry id."""
    fields = task_fields(
        _require(trace_id, "trace_id"),
        _require(prompt, "prompt"),
        _require(repo_url, "repo_url"),
        _require(from_role, "from_role"),
    )
    return _write(TASKS_CODER, fields)


@mcp.tool()
def read_coder_tasks(after: str = "-") -> list[dict[str, str]]:
    """Read tasks:coder. Pass the last seen entry id as after to read only newer ones.

    after defaults to "-" (the whole stream). Each object includes the Redis
    entry id plus traceID, prompt, repoUrl, and from. This lists entries; it
    does not claim them.
    """
    return _read(TASKS_CODER, after)


@mcp.tool()
def write_reviewer_task(trace_id: str, prompt: str, repo_url: str, from_role: str) -> str:
    """Append one delegated task to tasks:reviewer. Returns the Redis entry id."""
    fields = task_fields(
        _require(trace_id, "trace_id"),
        _require(prompt, "prompt"),
        _require(repo_url, "repo_url"),
        _require(from_role, "from_role"),
    )
    return _write(TASKS_REVIEWER, fields)


@mcp.tool()
def read_reviewer_tasks(after: str = "-") -> list[dict[str, str]]:
    """Read tasks:reviewer. Pass the last seen entry id as after to read only newer ones.

    after defaults to "-" (the whole stream). Each object includes the Redis
    entry id plus traceID, prompt, repoUrl, and from. This lists entries; it
    does not claim them.
    """
    return _read(TASKS_REVIEWER, after)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
