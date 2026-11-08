import os

from mcp.server import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

# Initialize the FastMCP server
mcp = FastMCP(
    "swarm-docker",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "9002")),
)

# Endpoint to check the health of the server
@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
