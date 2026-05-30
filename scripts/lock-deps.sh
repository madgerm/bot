#!/usr/bin/env bash
# Erzeugt requirements-lock.txt aus pyproject.toml (pip-tools).
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pip install -U pip pip-tools
pip-compile pyproject.toml --extra dev -o requirements-lock.txt
echo "Geschrieben: requirements-lock.txt"
