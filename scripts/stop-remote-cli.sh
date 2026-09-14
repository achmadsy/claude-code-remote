#!/usr/bin/env bash
set -euo pipefail

if systemctl is-active --quiet claude-code-remote.service 2>/dev/null; then
    sudo systemctl stop claude-code-remote.service
    echo "Remote CLI service stopped."
else
    echo "Remote CLI service is not running."
fi

echo "tmux session 'claude' is preserved."
echo "To kill it too: tmux kill-session -t claude"
