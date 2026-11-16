# Coder worker: Claude Code CLI. Auth at runtime from repo-root .env:
#   ANTHROPIC_API_KEY  — Anthropic API
#   GH_TOKEN           — GitHub (git/gh)
# Role ships as ~/.claude/CLAUDE.md; skills under ~/.claude/skills/.
# Example: docker run --rm -it --env-file .env swarm-coder
#   bash -lc 'claude --dangerously-skip-permissions'
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
    && mkdir -p /home/agent/.claude /workspace \
    && chown -R agent:agent /home/agent/.claude /workspace

COPY prompt.md /home/agent/.claude/CLAUDE.md
COPY skills/ /home/agent/.claude/skills/
RUN chown agent:agent /home/agent/.claude/CLAUDE.md \
    && chown -R agent:agent /home/agent/.claude/skills

USER agent

ENV CLAUDE_CONFIG_DIR=/home/agent/.claude

WORKDIR /workspace

CMD ["/bin/bash"]