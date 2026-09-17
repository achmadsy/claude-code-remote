#!/usr/bin/env bash
set -euo pipefail

unset CLAUDECODE
unset CLAUDE_CODE_ENTRYPOINT
unset CLAUDE_CODE_ENTRY_VERSION
unset CLAUDE_CODE_ENV_VERSION

export LANG="C.UTF-8"
export LC_ALL="C.UTF-8"

# Swipe→wheel needs mouse tracking so tmux owns scroll (copy-mode),
# not zsh. Re-apply every attach in case server started with it off.
/usr/bin/tmux set -g mouse on >/dev/null 2>&1 || true

exec /usr/bin/tmux new-session -A -s claude -c /home/ubuntu
