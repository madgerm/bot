"""LLM-Antworten in strukturierte Prüffragen / Bewertungen parsen."""

from __future__ import annotations

import json
import re
from typing import Any

from bot.verification.models import CheckMethod, Verdict


def parse_questions_json(text: str) -> list[dict[str, Any]]:
    """Erwartet JSON-Array oder ```json ... ``` Block."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return _parse_questions_fallback(text)
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for i, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue
        out.append(_normalize_question_item(item, default_seq=i))
    return out


def _parse_questions_fallback(text: str) -> list[dict[str, Any]]:
    """Zeilen mit Nummer oder 'Prüffrage:' als Notfall."""
    out: list[dict[str, Any]] = []
    blocks = re.split(r"\n(?=\d{2,3}\s*[-.)]|\#{2,3}\s)", text)
    seq = 0
    for block in blocks:
        block = block.strip()
        if len(block) < 10:
            continue
        seq += 1
        title_m = re.search(r"^\d{2,3}\s*[-.)]\s*(.+)$", block, re.M)
        title = title_m.group(1).strip() if title_m else f"Prüfung {seq}"
        q_m = re.search(
            r"(?:Prüffrage|Frage)\s*:\s*(.+?)(?:\n(?:Erwartung|$))",
            block,
            re.I | re.S,
        )
        question = q_m.group(1).strip() if q_m else block[:500]
        method_m = re.search(r"(?:Prüfmethode|Methode)\s*:\s*(\w+)", block, re.I)
        method = (method_m.group(1).lower() if method_m else "code")[:20]
        if method not in ("browser", "code", "db", "api", "mixed"):
            method = "code"
        out.append(
            _normalize_question_item(
                {
                    "title": title,
                    "question": question,
                    "check_method": method,
                },
                default_seq=seq,
            )
        )
    return out


def _normalize_question_item(item: dict[str, Any], *, default_seq: int) -> dict[str, Any]:
    method = str(item.get("check_method") or item.get("methode") or "code").lower()
    if method not in ("browser", "code", "db", "api", "mixed"):
        method = "code"
    return {
        "seq": int(item.get("seq") or item.get("id") or default_seq),
        "title": str(item.get("title") or item.get("titel") or f"Prüfung {default_seq}"),
        "question": str(
            item.get("question")
            or item.get("prueffrage")
            or item.get("frage")
            or ""
        ).strip(),
        "expectation": str(
            item.get("expectation") or item.get("erwartung") or ""
        ).strip(),
        "check_method": method,
        "success_criteria": str(
            item.get("success_criteria")
            or item.get("erfolgskriterien")
            or ""
        ).strip(),
    }


def parse_verdict_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return _normalize_verdict(data)
        except json.JSONDecodeError:
            pass
    return _normalize_verdict({"verdict": _verdict_from_text(text), "reasons": text})


def _verdict_from_text(text: str) -> Verdict:
    upper = text.upper()
    if "TEILWEISE" in upper:
        return "teilweise"
    if re.search(r"\bNEIN\b|\bNO\b|NICHT\s+ERF", upper):
        return "nein"
    if re.search(r"\bJA\b|\bYES\b|APPROVED", upper):
        return "ja"
    return "unklar"


def _normalize_verdict(data: dict[str, Any]) -> dict[str, Any]:
    raw = str(data.get("verdict") or data.get("ergebnis") or "unklar").lower()
    verdict: Verdict
    if raw.startswith("j") or raw == "yes":
        verdict = "ja"
    elif raw.startswith("n") or raw == "no":
        verdict = "nein"
    elif "teil" in raw:
        verdict = "teilweise"
    else:
        verdict = "unklar"
    gaps = data.get("gaps") or data.get("fehlend") or data.get("problems") or []
    if isinstance(gaps, list):
        gaps_text = "\n".join(f"- {g}" for g in gaps)
    else:
        gaps_text = str(gaps)
    return {
        "verdict": verdict,
        "reasons": str(data.get("reasons") or data.get("begruendung") or "").strip(),
        "gaps": gaps_text.strip(),
        "fix_needed": bool(data.get("fix_needed", verdict in ("nein", "teilweise"))),
        "next_fix": str(data.get("next_fix") or data.get("naechste_aufgabe") or "").strip(),
    }
