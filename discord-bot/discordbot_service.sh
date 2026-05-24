#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$SCRIPT_DIR"
PID_FILE="$BASE_DIR/discordbot.pid"
LOG_FILE="$BASE_DIR/discordbot.log"

resolve_python() {
  if [[ -x "$BASE_DIR/.venv/bin/python" ]]; then
    echo "$BASE_DIR/.venv/bin/python"
    return 0
  fi
  if [[ -x "/opt/kusanagi/bin/python3" ]]; then
    echo "/opt/kusanagi/bin/python3"
    return 0
  fi
  command -v python3
}

PYTHON_BIN="$(resolve_python)"
CMD="$PYTHON_BIN $BASE_DIR/main.py"

is_running() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid=$(cat "$PID_FILE" || true)
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

start() {
  if is_running; then
    echo "already running: $(cat "$PID_FILE")"
    return 0
  fi

  cd "$BASE_DIR"
  nohup $CMD >> "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  sleep 1

  if is_running; then
    echo "started: $(cat "$PID_FILE")"
  else
    echo "failed to start"
    exit 1
  fi
}

stop() {
  if ! is_running; then
    echo "not running"
    rm -f "$PID_FILE"
    return 0
  fi

  local pid
  pid=$(cat "$PID_FILE")
  kill "$pid" 2>/dev/null || true
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
  echo "stopped"
}

status() {
  if is_running; then
    echo "running: $(cat "$PID_FILE")"
  else
    echo "stopped"
    return 1
  fi
}

ensure() {
  if ! is_running; then
    start
  else
    echo "ok: $(cat "$PID_FILE")"
  fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop || true; start ;;
  status) status ;;
  ensure) ensure ;;
  *)
    echo "usage: $0 {start|stop|restart|status|ensure}"
    exit 2
    ;;
esac
