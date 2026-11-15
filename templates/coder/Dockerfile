# Coder worker: Claude Code CLI. Auth at runtime from repo-root .env:
#   ANTHROPIC_API_KEY  — Anthropic API
#   GH_TOKEN           — GitHub (git/gh)
# Example: docker run --rm -it --env-file .env swarm-coder   # shell in /workspace; run claude manually
FROM node:22-bookworm-slim

ARG CLAUDE_VERSION=2.1.325

USER root

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git curl ca-certificates ripgrep less gh \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g @anthropic-ai/claude-code@${CLAUDE_VERSION}

ENV DISABLE_AUTOUPDATER=1

RUN useradd -m -s /bin/bash agent \
    && mkdir -p /home/agent/.claude /workspace /opt/swarm \
    && chown -R agent:agent /home/agent/.claude /workspace /opt/swarm

COPY prompt.md /opt/swarm/role-prompt.md
RUN chown agent:agent /opt/swarm/role-prompt.md

USER agent

ENV CLAUDE_CONFIG_DIR=/home/agent/.claude

WORKDIR /workspace

CMD ["/bin/bash"]