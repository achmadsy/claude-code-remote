#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_DIR/.venv/bin/python}"
BIND_HOST="${BIND_HOST:-127.0.0.1}"
TTYD_PORT="${TTYD_PORT:-7681}"
WRAPPER_PORT="${WRAPPER_PORT:-7682}"
PUBLIC_URL="${PUBLIC_URL:-https://claude.zlink.my.id}"

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $1" >&2
        exit 1
    fi
}

require_command tailscale
require_command ttyd
require_command tmux

if [ ! -x "$PYTHON_BIN" ]; then
    echo "ERROR: Python environment not found: $PYTHON_BIN" >&2
    exit 1
fi

TAILSCALE_IP="$(tailscale ip -4 2>/dev/null || true)"
if [ -z "$TAILSCALE_IP" ]; then
    echo "ERROR: Tailscale not running or no IPv4 address" >&2
    exit 1
fi

for port in "$TTYD_PORT" "$WRAPPER_PORT"; do
    if ss -H -ltn "sport = :$port" | grep -q .; then
        echo "ERROR: port $port is already in use" >&2
        exit 1
    fi
done

TTYD_PID=""
WRAPPER_PID=""

cleanup() {
    trap - EXIT TERM INT
    [ -z "$WRAPPER_PID" ] || kill "$WRAPPER_PID" 2>/dev/null || true
    [ -z "$TTYD_PID" ] || kill "$TTYD_PID" 2>/dev/null || true
    wait 2>/dev/null || true
}
trap cleanup EXIT TERM INT

echo "Tailscale IP: $TAILSCALE_IP"

ttyd \
    --port "$TTYD_PORT" \
    --interface "$BIND_HOST" \
    --base-path /terminal \
    --check-origin \
    --writable \
    -t fontSize=14 \
    -t lineHeight=1.2 \
    -t cursorBlink=true \
    -t cursorStyle=block \
    -t scrollback=10000 \
    -t 'fontFamily="Menlo, Monaco, Consolas, monospace, Apple Color Emoji, Segoe UI Emoji"' \
    "$SCRIPT_DIR/tmux-attach.sh" &
TTYD_PID=$!

BIND_HOST="$BIND_HOST" TTYD_PORT="$TTYD_PORT" WRAPPER_PORT="$WRAPPER_PORT" \
    "$PYTHON_BIN" "$SCRIPT_DIR/voice-wrapper.py" &
WRAPPER_PID=$!

sleep 1
if ! kill -0 "$TTYD_PID" 2>/dev/null; then
    echo "ERROR: ttyd failed to start" >&2
    exit 1
fi
if ! kill -0 "$WRAPPER_PID" 2>/dev/null; then
    echo "ERROR: voice wrapper failed to start" >&2
    exit 1
fi

for port in "$TTYD_PORT" "$WRAPPER_PORT"; do
    if ! ss -H -ltn "sport = :$port" | grep -Fq "$BIND_HOST:$port"; then
        echo "ERROR: port $port is not bound to $BIND_HOST" >&2
        exit 1
    fi
done

echo "=== Remote CLI Ready ==="
echo "Private URL: $PUBLIC_URL"
echo "Terminal backend: http://$BIND_HOST:$TTYD_PORT/terminal/"
echo "Voice backend: http://$BIND_HOST:$WRAPPER_PORT"

wait -n "$TTYD_PID" "$WRAPPER_PID"
echo "ERROR: remote CLI component exited" >&2
exit 1
