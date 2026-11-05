import os
import redis
from mcp.server import MCPServer

mcp = MCPServer("redis-streams")
r = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

@mcp.tool()
def add_message(stream: str, fields: dict[str, str]) -> str:
    """Append one message to a Redis stream. Returns the new message id."""
    return r.xadd(stream, fields)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")