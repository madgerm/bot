#!/usr/bin/env bash
# Schnellprüfung nach git pull: Config, Tests, zentrale Module.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || {
  python3 -m venv .venv && source .venv/bin/activate
  pip install -U pip
  pip install -r requirements-lock.txt
  pip install -e . --no-deps
}
echo "=== bot config validate ==="
bot config validate
echo "=== pytest ==="
pytest -q
echo "=== Prüfe Kernmodule ==="
python -c "
from pathlib import Path
from bot.web.audit_middleware import PanelAuditMiddleware
from bot.audit import AuditStore
from bot.backup import create_backup
from bot.config.media_admin import load_media_global
assert Path('requirements-lock.txt').is_file()
print('OK — Audit, Backup, Medien-Admin, Lockfile vorhanden')
"
echo "Fertig."
