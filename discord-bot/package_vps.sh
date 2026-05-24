#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARCHIVE_PATH="${1:-$SCRIPT_DIR/../DiscordBot-vps.tar.gz}"

cd "$SCRIPT_DIR"

tar \
  --exclude='.env' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='discordbot.log' \
  --exclude='discordbot.pid' \
  --exclude='*.pyc' \
  -czf "$ARCHIVE_PATH" \
  .

echo "created: $ARCHIVE_PATH"