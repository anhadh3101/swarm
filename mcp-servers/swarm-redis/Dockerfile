FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    REDIS_URL=redis://redis:6379/0

# Runtime deps only (full requirements.txt includes unused packages like torch).
RUN pip install --no-cache-dir \
    "mcp==1.28.0" \
    "redis==8.1.0" \
    "pydantic>=2.14,<3"

COPY app/ ./app/

WORKDIR /app/app

EXPOSE 8000

CMD ["python", "server.py"]
