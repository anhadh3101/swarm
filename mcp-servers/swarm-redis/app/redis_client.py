import os, redis

DEFAULT_REDIS_URL = "redis://redis:6379/0"

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        url = os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
        _client = redis.from_url(url, decode_responses=True)
    return _client
