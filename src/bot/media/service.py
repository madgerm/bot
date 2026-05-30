"""Medien-APIs: Vision (LiteLLM), STT/TTS (HTTP), Bilder (Webhook/MiniMax)."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx

from bot.config import load_runtime_config
from bot.config.models import ImageGenerationConfig, MediaChannelConfig
from bot.media.config import (
    MediaConfigError,
    load_team_media,
    resolve_channel,
    resolve_secret,
)


class MediaServiceError(Exception):
    pass


class MediaService:
    def __init__(self, root: Path, team_id: str) -> None:
        self.root = root.resolve()
        self.team_id = team_id
        runtime = load_runtime_config(self.root)
        self._global = runtime.system.media_global
        self._team = load_team_media(self.root, team_id)

    def channel_status(self) -> dict[str, dict[str, str]]:
        """Stub vs. live pro Kanal (für Admin-UI)."""
        channels: dict[str, dict[str, str]] = {}
        for name in ("vision", "stt", "tts", "image_generation"):
            try:
                cfg = resolve_channel(self._global, self._team, name)
            except MediaConfigError:
                channels[name] = {"mode": "unconfigured", "detail": "Konfiguration fehlt"}
                continue
            source = getattr(cfg, "source", "global")
            if name == "stt":
                if isinstance(cfg, MediaChannelConfig) and cfg.endpoint:
                    mode = "live"
                    detail = cfg.endpoint
                else:
                    mode = "stub"
                    detail = "Kein STT-Endpoint — LiteLLM oder Stub"
            elif name == "tts":
                if isinstance(cfg, MediaChannelConfig) and cfg.endpoint:
                    mode = "live"
                    detail = cfg.endpoint
                else:
                    mode = "stub"
                    detail = "Kein TTS-Endpoint"
            elif name == "vision":
                if isinstance(cfg, MediaChannelConfig) and (cfg.api_base or cfg.model):
                    mode = "live"
                    detail = cfg.model or cfg.api_base or "litellm"
                else:
                    mode = "stub"
                    detail = "Vision nicht konfiguriert"
            else:
                img = cfg if isinstance(cfg, ImageGenerationConfig) else None
                if img and img.type == "webhook" and img.url:
                    mode = "live"
                    detail = f"webhook {img.url}"
                elif img and img.type == "minimax" and img.api_base:
                    mode = "live"
                    detail = "minimax"
                elif img and (img.url or img.api_base):
                    mode = "live"
                    detail = img.type
                else:
                    mode = "stub"
                    detail = "selfhosted ohne URL — Stub-Antwort"
            channels[name] = {"mode": mode, "source": source, "detail": detail}
        return channels

    @classmethod
    def for_team(cls, root: Path | str, team_id: str) -> MediaService:
        return cls(Path(root), team_id)

    def describe_image(self, image_path: Path, prompt: str = "Beschreibe das Bild.") -> str:
        cfg = resolve_channel(self._global, self._team, "vision")
        if not isinstance(cfg, MediaChannelConfig):
            raise MediaServiceError("Vision-Konfiguration fehlt")
        data = image_path.read_bytes()
        b64 = base64.standard_b64encode(data).decode()
        try:
            import litellm

            api_key = resolve_secret(cfg.secret_ref)
            model = cfg.model or "gpt-4o-mini"
            response = litellm.completion(
                model=model,
                api_base=cfg.api_base,
                api_key=api_key,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"},
                            },
                        ],
                    }
                ],
                timeout=cfg.timeout_seconds,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            raise MediaServiceError(f"Vision: {exc}") from exc

    def speech_to_text(self, audio_path: Path) -> str:
        cfg = resolve_channel(self._global, self._team, "stt")
        if isinstance(cfg, MediaChannelConfig) and cfg.endpoint:
            return self._http_transcribe(cfg, audio_path)
        return self._stt_litellm_or_stub(audio_path)

    def text_to_speech(self, text: str, out_path: Path) -> Path:
        cfg = resolve_channel(self._global, self._team, "tts")
        if not isinstance(cfg, MediaChannelConfig) or not cfg.endpoint:
            out_path.write_bytes(b"")
            out_path.with_suffix(".txt").write_text(text, encoding="utf-8")
            return out_path
        headers: dict[str, str] = {}
        token = resolve_secret(cfg.secret_ref)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        payload = {"text": text, "voice_id": cfg.voice_id}
        try:
            resp = httpx.post(
                cfg.endpoint,
                json=payload,
                headers=headers,
                timeout=cfg.timeout_seconds,
            )
            resp.raise_for_status()
            out_path.write_bytes(resp.content)
            return out_path
        except httpx.HTTPError as exc:
            raise MediaServiceError(f"TTS: {exc}") from exc

    def generate_image(self, prompt: str) -> dict[str, Any]:
        cfg = resolve_channel(self._global, self._team, "image_generation")
        if not isinstance(cfg, ImageGenerationConfig):
            raise MediaServiceError("Bild-Konfiguration fehlt")
        if cfg.type == "webhook":
            return self._image_webhook(cfg, prompt)
        if cfg.type == "minimax":
            return self._image_minimax(cfg, prompt)
        return self._image_selfhosted(cfg, prompt)

    def _http_transcribe(self, cfg: MediaChannelConfig, audio_path: Path) -> str:
        headers: dict[str, str] = {}
        token = resolve_secret(cfg.secret_ref)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with audio_path.open("rb") as f:
            files = {"file": (audio_path.name, f)}
            resp = httpx.post(
                cfg.endpoint or "",
                files=files,
                headers=headers,
                timeout=cfg.timeout_seconds,
            )
        resp.raise_for_status()
        data = resp.json()
        return data.get("text", data.get("transcript", str(data)))

    def _image_webhook(self, cfg: ImageGenerationConfig, prompt: str) -> dict[str, Any]:
        if not cfg.url:
            raise MediaConfigError("webhook url fehlt")
        headers: dict[str, str] = {}
        token = resolve_secret(cfg.secret_ref)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        resp = httpx.post(
            cfg.url,
            json={"prompt": prompt, "aspect": cfg.default_aspect, "team_id": self.team_id},
            headers=headers,
            timeout=cfg.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()

    def _stt_litellm_or_stub(self, audio_path: Path) -> str:
        try:
            import litellm

            api_key = resolve_secret(
                self._global.stt.secret_ref if self._global else None
            )
            model = (self._global.stt.model if self._global else None) or "whisper-1"
            with audio_path.open("rb") as f:
                response = litellm.transcription(
                    model=model,
                    file=f,
                    api_key=api_key,
                )
            text = getattr(response, "text", None) or str(response)
            if text.strip():
                return text.strip()
        except Exception:
            pass
        return f"[stt-stub] {audio_path.name} — STT-Endpoint oder LITELLM_API_KEY konfigurieren"

    def _image_minimax(self, cfg: ImageGenerationConfig, prompt: str) -> dict[str, Any]:
        base = cfg.api_base or "https://api.minimax.io"
        token = resolve_secret(cfg.secret_ref)
        if not token:
            raise MediaServiceError("MINIMAX API-Key fehlt (secret_ref)")
        headers = {"Authorization": f"Bearer {token}"}
        resp = httpx.post(
            f"{base.rstrip('/')}/v1/image_generation",
            json={"model": cfg.model or "image-01", "prompt": prompt},
            headers=headers,
            timeout=cfg.timeout_seconds,
        )
        if resp.status_code >= 400:
            raise MediaServiceError(
                f"MiniMax HTTP {resp.status_code}: {resp.text[:500]}"
            )
        return resp.json()

    def _image_selfhosted(self, cfg: ImageGenerationConfig, prompt: str) -> dict[str, Any]:
        url = cfg.url or cfg.api_base
        if not url:
            return {"status": "stub", "prompt": prompt}
        resp = httpx.post(
            url,
            json={"prompt": prompt},
            timeout=cfg.timeout_seconds,
        )
        resp.raise_for_status()
        return resp.json()
