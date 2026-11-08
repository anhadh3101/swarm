import os

from mcp.server import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from model import TaskMessage, task_stream
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

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
