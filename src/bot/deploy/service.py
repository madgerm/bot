"""Provisioning: systemd-Unit + Team-User-Skripte."""

from __future__ import annotations

import textwrap
from pathlib import Path

from bot.config import load_runtime_config


class DeployServiceError(Exception):
    pass


class DeployService:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        runtime = load_runtime_config(self.root)
        self.deployment = runtime.system.deployment

    def team_linux_user(self, team_id: str) -> str:
        prefix = "team_"
        if self.deployment:
            prefix = self.deployment.team_user_prefix
        return f"{prefix}{team_id}"

    def generate_systemd_unit(self, team_id: str, bot_binary: str = "bot") -> str:
        user = self.team_linux_user(team_id)
        home = f"/home/{user}"
        template = "bot-team@.service"
        if self.deployment:
            template = self.deployment.systemd_template
        unit_name = template.replace("@.", f"@{team_id}.")
        return textwrap.dedent(
            f"""
            # {unit_name}
            [Unit]
            Description=Bot Team Runner — {team_id}
            After=network.target

            [Service]
            Type=simple
            User={user}
            WorkingDirectory={home}/bot
            Environment=BOT_ROOT={home}/bot
            ExecStart={bot_binary} run --team {team_id}
            Restart=on-failure
            RestartSec=5
            MemoryMax=2G
            CPUQuota=80%

            [Install]
            WantedBy=multi-user.target
            """
        ).strip()

    def generate_provision_script(self, team_id: str) -> str:
        user = self.team_linux_user(team_id)
        return textwrap.dedent(
            f"""#!/bin/bash
            set -euo pipefail
            # Provision Team '{team_id}' als Linux-User (root erforderlich)
            TEAM_USER="{user}"
            if ! id "$TEAM_USER" &>/dev/null; then
              useradd -m -s /bin/bash "$TEAM_USER"
            fi
            install -d -o "$TEAM_USER" -g "$TEAM_USER" "/home/$TEAM_USER/bot"
            echo "Kopiere Projekt nach /home/$TEAM_USER/bot und setze BOT_TEAM_API_TOKEN"
            echo "systemctl enable bot-team@{team_id}.service"
            """
        ).strip()

    def write_artifacts(self, team_id: str, output_dir: Path | None = None) -> dict[str, str]:
        out = output_dir or (self.root / "deploy" / team_id)
        out.mkdir(parents=True, exist_ok=True)
        unit_path = out / f"bot-team@{team_id}.service"
        script_path = out / f"provision-{team_id}.sh"
        unit_path.write_text(self.generate_systemd_unit(team_id) + "\n", encoding="utf-8")
        script_path.write_text(self.generate_provision_script(team_id) + "\n", encoding="utf-8")
        script_path.chmod(0o755)
        return {"systemd": str(unit_path), "provision": str(script_path)}
