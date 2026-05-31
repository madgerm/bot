#!/usr/bin/env bash
# Ein Befehl: Panel + Team-Runner (Netzwerk 0.0.0.0:8080)
set -euo pipefail
ROOT="${BOT_ROOT:-${HOME}/bot}"
cd "$ROOT"
# shellcheck source=/dev/null
[[ -f "${HOME}/.config/bot/env" ]] && set -a && source "${HOME}/.config/bot/env" && set +a
[[ -f .venv/bin/activate ]] && source .venv/bin/activate
exec bot up "$@"
