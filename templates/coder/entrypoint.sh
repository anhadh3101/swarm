#!/bin/sh
set -e
cp /app/config.toml "$CODEX_HOME/config.toml"
exec python3 /app/worker.py "$@"
