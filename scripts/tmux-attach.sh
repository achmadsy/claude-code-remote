#!/usr/bin/env bash
set -euo pipefail

unset CLAUDECODE
unset CLAUDE_CODE_ENTRYPOINT
unset CLAUDE_CODE_ENTRY_VERSION
unset CLAUDE_CODE_ENV_VERSION

export LANG="C.UTF-8"
export LC_ALL="C.UTF-8"

# Required: without mouse, xterm wheel becomes Up/Down → zsh INPUT history.
# With mouse on, tmux owns wheel and scrolls terminal scrollback.
/usr/bin/tmux set -g mouse on >/dev/null 2>&1 || true

exec /usr/bin/tmux new-session -A -s claude -c /home/ubuntu
