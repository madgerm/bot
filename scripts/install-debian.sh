#!/usr/bin/env bash
# Bot — interaktive Installation auf Debian/Ubuntu
# Ausführung: aus dem geklonten Repo (scripts/install-debian.sh) oder per Download (siehe README).
set -euo pipefail

BOT_VERSION_LABEL="0.1.0"
BOT_REPO_URL="${BOT_REPO_URL:-https://github.com/madgerm/bot.git}"
BOT_REPO_BRANCH="${BOT_REPO_BRANCH:-main}"
BOT_MIN_PYTHON="3.11"

# --- Hilfsfunktionen ----------------------------------------------------------

log() { printf '\033[1;34m[bot-install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[bot-install]\033[0m %s\n' "$*" >&2; }
err() { printf '\033[1;31m[bot-install]\033[0m %s\n' "$*" >&2; exit 1; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || return 1
}

prompt() {
  local msg="$1" default="${2:-}"
  local reply
  if [[ -n "$default" ]]; then
    read -r -p "$msg [$default]: " reply
    echo "${reply:-$default}"
  else
    read -r -p "$msg: " reply
    echo "$reply"
  fi
}

prompt_yn() {
  local msg="$1" default="${2:-n}"
  local dflag="n"
  [[ "$default" =~ ^[JjYy] ]] && dflag="j"
  local reply
  read -r -p "$msg (j/n) [$dflag]: " reply
  reply="${reply:-$dflag}"
  [[ "$reply" =~ ^[JjYy] ]]
}

as_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    if ! need_cmd sudo; then
      err "Für systemweite Installation wird root oder sudo benötigt."
    fi
    sudo "$@"
  fi
}

detect_os() {
  if [[ -f /etc/os-release ]]; then
    # shellcheck source=/dev/null
    . /etc/os-release
    case "${ID:-}" in
      debian | ubuntu | linuxmint | pop) return 0 ;;
      *) err "Nur Debian/Ubuntu werden unterstützt (gefunden: ${ID:-unbekannt})." ;;
    esac
  else
    err "Kein /etc/os-release — bitte Debian/Ubuntu verwenden."
  fi
}

python_version_ok() {
  local py="$1"
  "$py" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null
}

find_python() {
  local c
  for c in python3.12 python3.11 python3; do
    if need_cmd "$c" && python_version_ok "$c"; then
      echo "$c"
      return 0
    fi
  done
  return 1
}

resolve_script_dir() {
  if [[ -n "${BOT_INSTALL_SRC:-}" ]] && [[ -f "${BOT_INSTALL_SRC}/pyproject.toml" ]]; then
    echo "$(cd "${BOT_INSTALL_SRC}" && pwd)"
    return 0
  fi
  if [[ -n "${BASH_SOURCE[0]:-}" ]] && [[ -f "${BASH_SOURCE[0]}" ]]; then
    local base
    base="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    if [[ -f "${base}/pyproject.toml" ]]; then
      echo "$base"
      return 0
    fi
  fi
  if [[ -f "./pyproject.toml" ]] && grep -q 'name = "bot"' ./pyproject.toml 2>/dev/null; then
    echo "$(pwd)"
    return 0
  fi
  return 1
}

clone_or_use_source() {
  local dest="$1"
  local src
  if src="$(resolve_script_dir)"; then
    log "Verwende vorhandenes Quellverzeichnis: $src"
    if [[ "$(readlink -f "$src")" != "$(readlink -f "$dest")" ]]; then
      mkdir -p "$dest"
      if need_cmd rsync; then
        rsync -a --exclude '.venv' --exclude '.git' "$src/" "$dest/"
      else
        cp -a "$src/." "$dest/"
      fi
    fi
    return 0
  fi
  log "Klone Repository nach $dest …"
  need_cmd git || err "git fehlt — bitte Pakete installieren lassen."
  if [[ -d "$dest/.git" ]]; then
    git -C "$dest" fetch --depth 1 origin "$BOT_REPO_BRANCH"
    git -C "$dest" checkout "$BOT_REPO_BRANCH"
    git -C "$dest" pull --ff-only origin "$BOT_REPO_BRANCH" || true
  else
    git clone --depth 1 --branch "$BOT_REPO_BRANCH" "$BOT_REPO_URL" "$dest"
  fi
}

apt_packages_missing() {
  local missing=()
  local pkg
  for pkg in "$@"; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
      missing+=("$pkg")
    fi
  done
  if ((${#missing[@]})); then
    printf '%s\n' "${missing[@]}"
  fi
}

ensure_apt_dependencies() {
  local pyver="$1"
  local pkgs=(ca-certificates curl git sqlite3 build-essential)
  if [[ "$pyver" == "python3" ]]; then
    pkgs+=(python3 python3-venv python3-dev)
  else
    pkgs+=("${pyver}" "${pyver}-venv" "${pyver}-dev")
  fi
  local miss
  miss="$(apt_packages_missing "${pkgs[@]}" 2>/dev/null || true)"
  if [[ -z "$miss" ]]; then
    log "APT-Abhängigkeiten sind bereits installiert."
    return 0
  fi
  warn "Fehlende Pakete: $(echo "$miss" | tr '\n' ' ')"
  if [[ "${BOT_INSTALL_NONINTERACTIVE:-}" == "1" ]] || [[ "${BOT_INSTALL_YES:-}" == "1" ]]; then
    :
  elif ! prompt_yn "Sollen fehlende Pakete jetzt per apt installiert werden?" "j"; then
    err "Installation abgebrochen — bitte Pakete manuell nachinstallieren."
  fi
  log "apt update && apt install …"
  as_root apt-get update -qq
  as_root apt-get install -y --no-install-recommends "${pkgs[@]}"
}

setup_venv() {
  local root="$1"
  local py="$2"
  cd "$root"
  if [[ ! -d .venv ]]; then
    log "Erstelle virtuelle Umgebung (.venv) …"
    "$py" -m venv .venv
  fi
  # shellcheck source=/dev/null
  source .venv/bin/activate
  python -m pip install -U pip wheel
  if [[ -f requirements-lock.txt ]]; then
    pip install -r requirements-lock.txt
    pip install -e . --no-deps
  else
    pip install -e .
  fi
  log "Python-Paket 'bot' installiert ($(bot --help >/dev/null 2>&1 && echo OK || echo prüfen))"
}

write_env_file() {
  local env_path="$1"
  local root="$2"
  local mode="$3" # runner | web | both
  mkdir -p "$(dirname "$env_path")"
  if [[ -f "$env_path" ]]; then
    warn "Vorhandene Datei wird nicht überschrieben: $env_path"
    return 0
  fi
  local secret team_token
  secret="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  team_token="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  cat >"$env_path" <<EOF
# Bot — generiert von scripts/install-debian.sh
BOT_ROOT=${root}
EOF
  if [[ "$mode" == "web" || "$mode" == "both" ]]; then
    cat >>"$env_path" <<EOF
BOT_SESSION_SECRET=${secret}
BOT_WEB_CSRF=true
EOF
  fi
  if [[ "$mode" == "runner" || "$mode" == "both" ]]; then
    cat >>"$env_path" <<EOF
# Optional für Remote-API (bot team serve):
# BOT_TEAM_API_TOKEN=${team_token}
EOF
  fi
  cat >>"$env_path" <<'EOF'
# LLM (optional)
# LITELLM_API_KEY=
EOF
  chmod 600 "$env_path"
  log "Umgebungsdatei angelegt: $env_path"
}

install_wrapper_system() {
  local root="$1"
  local bin_path="/usr/local/bin/bot"
  as_root tee "$bin_path" >/dev/null <<EOF
#!/bin/sh
export BOT_ROOT="${root}"
set -a
[ -f /etc/bot/env ] && . /etc/bot/env
set +a
exec "${root}/.venv/bin/bot" "\$@"
EOF
  as_root chmod 755 "$bin_path"
  log "System-Binary: $bin_path"
}

install_wrapper_user() {
  local root="$1"
  local bindir="${HOME}/.local/bin"
  mkdir -p "$bindir"
  tee "${bindir}/bot" >/dev/null <<EOF
#!/bin/sh
export BOT_ROOT="${root}"
set -a
[ -f "\${HOME}/.config/bot/env" ] && . "\${HOME}/.config/bot/env"
set +a
exec "${root}/.venv/bin/bot" "\$@"
EOF
  chmod 755 "${bindir}/bot"
  log "Benutzer-Binary: ${bindir}/bot (PATH ergänzen: export PATH=\"\$HOME/.local/bin:\$PATH\")"
}

create_system_user() {
  local user="$1"
  if id "$user" &>/dev/null; then
    log "Systembenutzer '$user' existiert bereits."
    return 0
  fi
  as_root useradd --system --home-dir /opt/bot --shell /usr/sbin/nologin "$user" 2>/dev/null \
    || as_root useradd --system --home-dir /opt/bot --shell /bin/false "$user"
  log "Systembenutzer '$user' angelegt."
}

install_systemd_units() {
  local root="$1"
  local mode="$2"
  local svc_user="$3"
  local env_file="$4"
  local unit_dir="/etc/systemd/system"
  local bot_bin="${root}/.venv/bin/bot"

  if [[ "$mode" == "runner" || "$mode" == "both" ]]; then
    as_root tee "${unit_dir}/bot-team-runner.service" >/dev/null <<EOF
[Unit]
Description=Bot Team-Runner (Multi-Agent Supervisor)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${svc_user}
Group=${svc_user}
WorkingDirectory=${root}
EnvironmentFile=${env_file}
ExecStart=${bot_bin} run
Restart=on-failure
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
    log "systemd: bot-team-runner.service"
  fi

  if [[ "$mode" == "web" || "$mode" == "both" ]]; then
    as_root tee "${unit_dir}/bot-web-panel.service" >/dev/null <<EOF
[Unit]
Description=Bot Web-Panel (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${svc_user}
Group=${svc_user}
WorkingDirectory=${root}
EnvironmentFile=${env_file}
ExecStart=${bot_bin} web --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=5
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF
    log "systemd: bot-web-panel.service"
  fi

  as_root systemctl daemon-reload
  local units=()
  [[ "$mode" == "runner" || "$mode" == "both" ]] && units+=(bot-team-runner.service)
  [[ "$mode" == "web" || "$mode" == "both" ]] && units+=(bot-web-panel.service)
  if [[ "${BOT_INSTALL_NONINTERACTIVE:-}" == "1" ]] || [[ "${BOT_INSTALL_START_SERVICES:-}" == "1" ]]; then
    for u in "${units[@]}"; do
      as_root systemctl enable "$u"
      as_root systemctl restart "$u" || warn "Start von $u fehlgeschlagen — Logs: journalctl -u $u"
    done
  elif prompt_yn "systemd-Dienste jetzt aktivieren und starten?" "j"; then
    for u in "${units[@]}"; do
      as_root systemctl enable "$u"
      as_root systemctl restart "$u" || warn "Start von $u fehlgeschlagen — Logs: journalctl -u $u"
    done
  else
    warn "Manuell: sudo systemctl enable --now ${units[*]}"
  fi
}

install_systemd_user_units() {
  local root="$1"
  local mode="$2"
  local env_file="${HOME}/.config/bot/env"
  local unit_dir="${HOME}/.config/systemd/user"
  mkdir -p "$unit_dir"
  local bot_bin="${root}/.venv/bin/bot"

  if [[ "$mode" == "runner" || "$mode" == "both" ]]; then
    tee "${unit_dir}/bot-team-runner.service" >/dev/null <<EOF
[Unit]
Description=Bot Team-Runner (Benutzer)
After=default.target

[Service]
Type=simple
WorkingDirectory=${root}
EnvironmentFile=${env_file}
ExecStart=${bot_bin} run
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
  fi
  if [[ "$mode" == "web" || "$mode" == "both" ]]; then
    tee "${unit_dir}/bot-web-panel.service" >/dev/null <<EOF
[Unit]
Description=Bot Web-Panel (Benutzer)
After=default.target

[Service]
Type=simple
WorkingDirectory=${root}
EnvironmentFile=${env_file}
ExecStart=${bot_bin} web --host 127.0.0.1 --port 8080
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF
  fi
  systemctl --user daemon-reload 2>/dev/null || true
  log "Benutzer-systemd-Units in $unit_dir"
  if prompt_yn "Benutzer-Dienste (systemctl --user) aktivieren?" "n"; then
    local units=()
    [[ "$mode" == "runner" || "$mode" == "both" ]] && units+=(bot-team-runner.service)
    [[ "$mode" == "web" || "$mode" == "both" ]] && units+=(bot-web-panel.service)
    systemctl --user enable "${units[@]}"
    systemctl --user start "${units[@]}" || warn "Start fehlgeschlagen — journalctl --user -u bot-web-panel"
  fi
}

run_config_validate() {
  local root="$1"
  # shellcheck source=/dev/null
  source "${root}/.venv/bin/activate"
  cd "$root"
  if bot config validate; then
    log "Konfiguration gültig."
  else
    warn "config validate meldete Probleme — config/ und teams/ prüfen."
  fi
}

print_initial_passwords() {
  cat <<'EOF'

═══════════════════════════════════════════════════════════════
  Web-Login (config/users.json — Demo, sofort ändern!)
═══════════════════════════════════════════════════════════════
  Benutzer    Passwort     Rolle / Hinweis
  ─────────────────────────────────────────────────────────────
  admin       changeme     Admin, alle Demo-Teams
  demo        changeme     Operator für Team demo
  reader      changeme     Nur Lesen (reader) für Team story

  Produktion:  bot auth hash-password
               Passwörter in config/users.json ersetzen
═══════════════════════════════════════════════════════════════
EOF
}

print_summary() {
  local root="$1"
  local mode="$2"
  local scope="$3"
  local env_file="$4"
  cat <<EOF

Installation abgeschlossen (Bot ${BOT_VERSION_LABEL})
  Projektverzeichnis : ${root}
  Modus              : ${mode}
  Geltungsbereich    : ${scope}
  Umgebung           : ${env_file}

Nächste Schritte:
EOF
  case "$mode" in
    runner)
      cat <<EOF
  • Team-Runner starten:  cd ${root} && source .venv/bin/activate && bot run
  • Ein Team testen:      bot run --team demo --once
  • Remote-API (optional): bot team token --write-config && bot team serve
EOF
      ;;
    web)
      cat <<EOF
  • Secrets laden:        set -a && source ${env_file} && set +a
  • Web-Panel starten:    bot web
  • Browser:              http://127.0.0.1:8080
EOF
      ;;
    both)
      cat <<EOF
  • Terminal 1 (Runner):  set -a && source ${env_file} && set +a && bot run
  • Terminal 2 (Panel):   set -a && source ${env_file} && set +a && bot web
  • Browser:              http://127.0.0.1:8080
EOF
      ;;
  esac
  print_initial_passwords
  cat <<EOF
Dokumentation: README.md · docs/OPERATIONS.md
EOF
}

# --- Hauptprogramm ------------------------------------------------------------

main() {
  detect_os
  log "Bot-Installer für Debian/Ubuntu (${BOT_VERSION_LABEL})"

  # Nicht-interaktiv (CI/Automatisierung):
  #   BOT_INSTALL_MODE=runner|web|both BOT_INSTALL_SCOPE=user|system BOT_INSTALL_NONINTERACTIVE=1
  if [[ "${BOT_INSTALL_NONINTERACTIVE:-}" == "1" ]]; then
    : "${BOT_INSTALL_MODE:=both}"
    : "${BOT_INSTALL_SCOPE:=user}"
    : "${BOT_INSTALL_DIR:=${HOME}/bot}"
    export BOT_INSTALL_MODE BOT_INSTALL_SCOPE BOT_INSTALL_DIR
  fi

  echo ""
  echo "Was soll installiert werden?"
  echo "  1) Team-Runner  — Agents ausführen (bot run)"
  echo "  2) Web-Panel    — Bedienoberfläche (bot web)"
  echo "  3) Beides       — Runner + Panel auf diesem Rechner"
  echo ""
  local mode scope system_install=false
  local install_dir env_file svc_user

  if [[ "${BOT_INSTALL_NONINTERACTIVE:-}" == "1" ]]; then
    case "${BOT_INSTALL_MODE}" in
      runner | web | both) mode="${BOT_INSTALL_MODE}" ;;
      *) err "BOT_INSTALL_MODE muss runner, web oder both sein." ;;
    esac
    case "${BOT_INSTALL_SCOPE}" in
      system | s)
        scope="systemweit"
        system_install=true
        install_dir="${BOT_INSTALL_DIR:-/opt/bot}"
        env_file="/etc/bot/env"
        svc_user="${BOT_SYSTEM_USER:-bot}"
        ;;
      user | u)
        scope="Benutzer"
        install_dir="${BOT_INSTALL_DIR:-${HOME}/bot}"
        env_file="${HOME}/.config/bot/env"
        svc_user="${USER}"
        ;;
      *) err "BOT_INSTALL_SCOPE muss user oder system sein." ;;
    esac
  else
    local choice
    choice="$(prompt "Auswahl (1/2/3)" "3")"
    case "$choice" in
      1) mode="runner" ;;
      2) mode="web" ;;
      3) mode="both" ;;
      *) err "Ungültige Auswahl: $choice" ;;
    esac

    echo ""
    echo "Installationsumfang:"
    echo "  s) systemweit — /opt/bot, Benutzer 'bot', optional systemd (sudo/root)"
    echo "  u) Benutzer   — ~/bot, nur Ihr Login (kein root nötig)"
    echo ""
    local scope_choice
    scope_choice="$(prompt "Auswahl (s/u)" "u")"

    case "$scope_choice" in
      s | S)
        scope="systemweit"
        system_install=true
        install_dir="${BOT_INSTALL_DIR:-/opt/bot}"
        env_file="/etc/bot/env"
        svc_user="${BOT_SYSTEM_USER:-bot}"
        ;;
      u | U)
        scope="Benutzer"
        install_dir="${BOT_INSTALL_DIR:-${HOME}/bot}"
        env_file="${HOME}/.config/bot/env"
        svc_user="${USER}"
        ;;
      *) err "Ungültige Auswahl: $scope_choice" ;;
    esac

    install_dir="$(prompt "Installationsverzeichnis" "$install_dir")"
  fi

  local py
  py="$(find_python)" || py=""
  if [[ -z "$py" ]]; then
    warn "Python >= ${BOT_MIN_PYTHON} nicht gefunden — versuche Installation per apt."
    ensure_apt_dependencies "python3"
    py="$(find_python)" || err "Python >= ${BOT_MIN_PYTHON} weiterhin nicht verfügbar."
  else
    local py_pkg
    py_pkg="$("$py" -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}")')"
    if ! dpkg -s "${py_pkg}-venv" >/dev/null 2>&1 && ! dpkg -s python3-venv >/dev/null 2>&1; then
      ensure_apt_dependencies "$py_pkg"
    else
      ensure_apt_dependencies "$py_pkg" 2>/dev/null || ensure_apt_dependencies "python3"
    fi
  fi
  log "Verwende: $($py --version)"

  if [[ "$system_install" == true ]]; then
    if [[ "$(id -u)" -ne 0 ]]; then
      log "Starte systemweite Installation mit sudo …"
      exec sudo BOT_INSTALL_SRC="${BOT_INSTALL_SRC:-}" BOT_INSTALL_DIR="$install_dir" \
        BOT_REPO_URL="$BOT_REPO_URL" BOT_REPO_BRANCH="$BOT_REPO_BRANCH" \
        bash "$0" "$@"
    fi
    create_system_user "$svc_user"
    mkdir -p "$install_dir"
    chown "${svc_user}:${svc_user}" "$install_dir"
    clone_or_use_source "$install_dir"
    chown -R "${svc_user}:${svc_user}" "$install_dir"
    sudo -u "$svc_user" env HOME="$install_dir" bash -c "
      set -euo pipefail
      cd '$install_dir'
      '$py' -m venv .venv
      source .venv/bin/activate
      python -m pip install -U pip wheel
      if [[ -f requirements-lock.txt ]]; then
        pip install -r requirements-lock.txt
        pip install -e . --no-deps
      else
        pip install -e .
      fi
    "
    log "Virtuelle Umgebung unter $install_dir/.venv (Benutzer $svc_user)"
  else
    mkdir -p "$install_dir"
    clone_or_use_source "$install_dir"
    setup_venv "$install_dir" "$py"
  fi

  if [[ "$system_install" == true ]]; then
    as_root mkdir -p /etc/bot
    if [[ ! -f /etc/bot/env ]]; then
      write_env_file "/etc/bot/env" "$install_dir" "$mode"
    fi
    as_root chown root:"${svc_user}" /etc/bot/env 2>/dev/null || true
    as_root chmod 640 /etc/bot/env
    install_wrapper_system "$install_dir"
    as_root chown -R "${svc_user}:${svc_user}" "$install_dir"
    env_file="/etc/bot/env"
  else
    write_env_file "$env_file" "$install_dir" "$mode"
    install_wrapper_user "$install_dir"
  fi

  if [[ "$system_install" == true ]]; then
    sudo -u "$svc_user" bash -c "cd '$install_dir' && source .venv/bin/activate && bot config validate" || true
  else
    run_config_validate "$install_dir"
  fi

  local setup_systemd=false
  if [[ "${BOT_INSTALL_NONINTERACTIVE:-}" == "1" ]]; then
    setup_systemd=false
  elif prompt_yn "systemd-Dienste für Autostart einrichten?" "$([[ "$system_install" == true ]] && echo j || echo n)"; then
    setup_systemd=true
  fi
  if [[ "$setup_systemd" == true ]]; then
    if [[ "$system_install" == true ]]; then
      install_systemd_units "$install_dir" "$mode" "$svc_user" "$env_file"
    else
      install_systemd_user_units "$install_dir" "$mode"
    fi
  fi

  print_summary "$install_dir" "$mode" "$scope" "$env_file"
}

main "$@"
