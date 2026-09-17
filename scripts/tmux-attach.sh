#!/usr/bin/env bash
set -euo pipefail

unset CLAUDECODE
unset CLAUDE_CODE_ENTRYPOINT
unset CLAUDE_CODE_ENTRY_VERSION
unset CLAUDE_CODE_ENV_VERSION

export LANG="C.UTF-8"
export LC_ALL="C.UTF-8"

exec /usr/bin/tmux new-session -A -s claude -c /home/ubuntu
