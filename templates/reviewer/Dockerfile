# Worker image: Codex CLI + Redis Streams consumer for the reviewer role.
# Build from this directory: docker build -t swarm-reviewer .
FROM ghcr.io/icoretech/codex-docker:latest

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /app/requirements.txt

COPY worker.py prompt.md config.toml entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /codex-home

ENV ROLE=reviewer \
    CODEX_HOME=/codex-home \
    REDIS_URL=redis://redis:6379/0 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

ENTRYPOINT ["/app/entrypoint.sh"]
