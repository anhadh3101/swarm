FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=9002

RUN pip install --no-cache-dir \
    "mcp==1.28.0"

COPY app/ ./app/

WORKDIR /app/app

EXPOSE 9002

CMD ["python", "server.py"]
