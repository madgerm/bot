"""Öffnungszeiten aus Seiteninhalt extrahieren (LLM + Fallback)."""

from __future__ import annotations

import json
import re
from typing import Any

from bot.hours.master import HoursConfigError, HoursMaster
from bot.llm import LlmError, LlmStack

_EXTRACTION_SYSTEM = """Du extrahierst Öffnungszeiten aus Webseiten-Text.
Antworte NUR mit JSON (kein Markdown):
{
  "timezone": "Europe/Berlin",
  "weekly": {
    "monday": {"open": "09:00", "close": "17:00", "closed": false},
    "tuesday": {"open": "09:00", "close": "17:00", "closed": false},
    "wednesday": {"open": "09:00", "close": "17:00", "closed": false},
    "thursday": {"open": "09:00", "close": "17:00", "closed": false},
    "friday": {"open": "09:00", "close": "17:00", "closed": false},
    "saturday": {"open": null, "close": null, "closed": true},
    "sunday": {"open": null, "close": null, "closed": true}
  },
  "exceptions": [],
  "note": "kurze Zusammenfassung auf Deutsch"
}
Wochentage auf Englisch (monday … sunday). Zeiten HH:MM. Nichts erfinden."""


def extract_hours_from_markdown(
    markdown: str,
    llm_stack: LlmStack,
    *,
    task_category: str = "review",
) -> tuple[dict[str, Any], str]:
    embedded = _try_embedded_test_json(markdown)
    if embedded is not None:
        return HoursMaster.model_validate(embedded).normalized(), "embedded"

    heuristic = _heuristic_extract(markdown)
    model = llm_stack.router.resolve(task_category, role="hours_checker")
    fallbacks = llm_stack.router.fallbacks(task_category, role="hours_checker")
    snippet = markdown[:12000]
    if len(markdown) > 12000:
        snippet += "\n\n[… gekürzt …]"
    messages = [
        {"role": "system", "content": _EXTRACTION_SYSTEM},
        {"role": "user", "content": f"Seiteninhalt:\n\n{snippet}"},
    ]
    try:
        raw = llm_stack.client.complete(model, messages, fallbacks=fallbacks or None)
    except LlmError as exc:
        if heuristic is not None:
            return HoursMaster.model_validate(heuristic).normalized(), "heuristic_fallback"
        raise HoursConfigError(f"LLM-Extraktion fehlgeschlagen: {exc}") from exc

    if "[llm-stub" in raw and heuristic is not None:
        return HoursMaster.model_validate(heuristic).normalized(), "heuristic_stub"

    try:
        parsed = _parse_json_from_llm(raw)
        return HoursMaster.model_validate(parsed).normalized(), "llm"
    except (HoursConfigError, ValueError):
        if heuristic is not None:
            return HoursMaster.model_validate(heuristic).normalized(), "heuristic_fallback"
        raise HoursConfigError(f"Öffnungszeiten nicht parsebar: {raw[:400]}")


def _parse_json_from_llm(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", stripped)
        if not match:
            raise HoursConfigError("Kein JSON in LLM-Antwort") from None
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise HoursConfigError("LLM-JSON muss ein Objekt sein")
    return data


def _try_embedded_test_json(markdown: str) -> dict[str, Any] | None:
    match = re.search(r"<!--\s*hours-json:\s*(\{[\s\S]*?\})\s*-->", markdown)
    return json.loads(match.group(1)) if match else None


_DAY_ALIASES = {
    "montag": "monday",
    "mo": "monday",
    "dienstag": "tuesday",
    "di": "tuesday",
    "mittwoch": "wednesday",
    "mi": "wednesday",
    "donnerstag": "thursday",
    "do": "thursday",
    "freitag": "friday",
    "fr": "friday",
    "samstag": "saturday",
    "sa": "saturday",
    "sonntag": "sunday",
    "so": "sunday",
}


def _heuristic_extract(markdown: str) -> dict[str, Any] | None:
    weekly: dict[str, dict[str, Any]] = {}
    time_re = re.compile(
        r"(?P<day>montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag|"
        r"mo|di|mi|do|fr|sa|so)\s*[:.\-]?\s*"
        r"(?:(?P<open>\d{1,2}[:.]\d{2})\s*[-–bis]+\s*(?P<close>\d{1,2}[:.]\d{2})|geschlossen|zu)",
        re.IGNORECASE,
    )
    for match in time_re.finditer(markdown):
        day_key = _DAY_ALIASES.get(match.group("day").lower())
        if not day_key:
            continue
        if match.group("open") and match.group("close"):
            open_t = match.group("open").replace(".", ":")
            close_t = match.group("close").replace(".", ":")
            if len(open_t) == 4:
                open_t = "0" + open_t
            if len(close_t) == 4:
                close_t = "0" + close_t
            weekly[day_key] = {"open": open_t, "close": close_t, "closed": False}
        else:
            weekly[day_key] = {"open": None, "close": None, "closed": True}
    if not weekly:
        return None
    return {
        "timezone": "Europe/Berlin",
        "weekly": weekly,
        "exceptions": [],
        "note": "Heuristisch extrahiert",
    }
