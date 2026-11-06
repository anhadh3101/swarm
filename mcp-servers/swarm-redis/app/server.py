import os

from mcp.server import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from model import TaskMessage, task_stream
from redis_client import get_redis

mcp = FastMCP(
    "swarm-redis",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "9001")),
)


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    try:
        get_redis().ping()
    except Exception as exc:
        return JSONResponse(
            {"status": "error", "detail": str(exc)},
            status_code=503,
        )
    return JSONResponse({"status": "ok"})


@mcp.tool()
def publish_task(
    role: str,
    run_id: str,
    job_id: str,
    payload: str,
) -> str:
    """Publish a job to tasks:<role> (architect, coder, reviewer). Returns Redis message id."""
    msg = TaskMessage(run_id=run_id, job_id=job_id, payload=payload)
    return get_redis().xadd(task_stream(role), msg.to_redis_fields())

@mcp.tool()
def stream_add(stream: str, fields: dict[str, str]) -> str:
    """XADD arbitrary string fields to any stream. Returns message id."""
    return get_redis().xadd(stream, fields)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
