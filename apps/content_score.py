"""Script Score: rule-based draft quality scoring (NSS-style, zero model cost).

Mirrors the key Visibly AI lesson: separate *scoring* (deterministic,
free, reproducible) from *generation* (LLM, paid, variable). The same
normalized segments always produce the same score, so the filter, the
owner review, and any external writer share one basis.

Components (weights sum to 100):

* grounding (30): beats free of unresolved ``[CẦN NGUỒN]`` markers, and
  numeric claims backed by ``evidence_refs``.
* entity (20): beats naming a known club/player/competition alias from
  the domain seeds (specificity beats generic talk).
* speech (20): narration length fits its duration slot
  (``CHARS_PER_SECOND`` pace with floor/overrun guards).
* variety (15): adjacent beats do not restate each other (5-gram overlap).
* readability (15): short Vietnamese sentences, no broadcast filler.

No I/O, no LLM calls, no clock. Import-safe (no engine imports).
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

SCORE_VERSION = "1.0"

# Mirrors apps/content_workflow.py (kept local so this module stays import-safe).
CHARS_PER_SECOND = 14
MAX_SPEECH_OVERRUN = 1.25

UNRESOLVED_MARKERS = ("[CẦN NGUỒN]", "[CAN NGUON]", "[KẾT LUẬN CỦA ALLEN]", "[KET LUAN CUA ALLEN]")

_FACT_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:m\b|triệu|trieu|euro|bàn|ban|trận|tran|tuổi|tuoi|%|ngày|ngay|tháng|thang|năm|nam)?",
    re.IGNORECASE,
)

# Broadcast filler the channel voice rules reject (channel.json voice_rules.avoid).
FILLER_PATTERNS = (
    "đăng ký kênh", "dang ky kenh", "nhấn like", "nhan like",
    "follow for more", "follow ngay", "không thể bỏ lỡ", "khong the bo lo",
    "sốc", "soc ", "căng đét", "cang det",
)

WEIGHTS = {
    "grounding": 30,
    "entity": 20,
    "speech": 20,
    "variety": 15,
    "readability": 15,
}


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _word_5grams(text: str) -> set[tuple[str, ...]]:
    tokens = re.findall(r"\w+", text.lower())
    return {tuple(tokens[i:i + 5]) for i in range(len(tokens) - 4)}


def _overlap(previous: str, current: str) -> float:
    earlier, later = _word_5grams(previous), _word_5grams(current)
    if not earlier or not later:
        return 0.0
    return len(earlier & later) / min(len(earlier), len(later))


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"[.!?…\n]+", text) if s.strip()]


def _has_unresolved(narration: str) -> bool:
    upper = narration.upper()
    return any(marker in upper for marker in UNRESOLVED_MARKERS)


def _has_numeric_claim(narration: str) -> bool:
    return bool(_FACT_RE.search(narration))


def load_entity_aliases(root: Path | str = Path(__file__).resolve().parent.parent) -> list[str]:
    """Collect known alias strings from the domain seeds; [] when unavailable."""
    aliases: set[str] = set()
    entities_dir = Path(root) / "data" / "entities"
    for name in ("clubs.json", "players.json", "competitions.json", "national_teams.json"):
        try:
            raw = json.loads((entities_dir / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        records = raw if isinstance(raw, list) else raw.get("records", [])
        for record in records:
            if not isinstance(record, dict):
                continue
            for key in ("canonical_name", "slug"):
                value = record.get(key)
                if isinstance(value, str) and value.strip():
                    aliases.add(value.strip().replace("-", " "))
            for alias in record.get("aliases", []) or []:
                text = alias.get("alias") if isinstance(alias, dict) else alias
                if isinstance(text, str) and len(text.strip()) >= 3:
                    aliases.add(text.strip())
    return sorted(aliases)


def _entity_hits(narration: str, aliases: list[str]) -> list[str]:
    norm = _strip_accents(narration)
    return [alias for alias in aliases if _strip_accents(alias) in norm]


def score_script(
    segments: list[dict[str, Any]] | Any,
    *,
    entity_aliases: list[str] | None = None,
) -> dict[str, Any]:
    """Score draft segments 0-100 with per-component breakdown and findings.

    Never raises on bad input; problems become findings and lower the score.
    ``entity_aliases=None`` loads the repo domain seeds (read-only).
    """
    findings: list[dict[str, str]] = []
    if not isinstance(segments, list) or not segments:
        findings.append({"component": "overall", "severity": "warn",
                         "message": "no script segments to score"})
        return {"score": 0, "version": SCORE_VERSION,
                "components": {key: 0 for key in WEIGHTS}, "findings": findings}
    clean = [seg for seg in segments if isinstance(seg, dict)]
    if len(clean) != len(segments):
        findings.append({"component": "overall", "severity": "info",
                         "message": f"{len(segments) - len(clean)} non-segment item(s) skipped"})
    if not clean:
        findings.append({"component": "overall", "severity": "warn",
                         "message": "no valid script segments to score"})
        return {"score": 0, "version": SCORE_VERSION,
                "components": {key: 0 for key in WEIGHTS}, "findings": findings}

    if entity_aliases is None:
        entity_aliases = load_entity_aliases()
    entity_unavailable = not entity_aliases

    grounding: list[float] = []
    entity_covered = 0
    speech: list[float] = []
    readability: list[float] = []

    for index, seg in enumerate(clean):
        narration = seg["narration"] if isinstance(seg.get("narration"), str) else ""
        refs = seg.get("evidence_refs")
        refs = refs if isinstance(refs, list) and refs else []
        try:
            duration = max(1, int(seg.get("duration_seconds", 8)))
        except (TypeError, ValueError):
            duration = 8

        # Grounding: unresolved research markers fail the beat; numeric
        # claims without evidence refs score low; sourced beats score full.
        if _has_unresolved(narration):
            grounding.append(0.0)
            findings.append({"component": "grounding", "severity": "warn",
                             "message": f"beat {index + 1} carries an unresolved research marker"})
        elif _has_numeric_claim(narration) and not refs:
            grounding.append(0.4)
            findings.append({"component": "grounding", "severity": "warn",
                             "message": f"beat {index + 1} states numbers without evidence_refs"})
        elif refs:
            grounding.append(1.0)
        else:
            grounding.append(0.7)

        # Entity specificity against the domain seeds.
        hits = _entity_hits(narration, entity_aliases)
        if hits:
            entity_covered += 1
        elif not entity_unavailable:
            findings.append({"component": "entity", "severity": "info",
                             "message": f"beat {index + 1} names no known club/player/competition"})

        # Speech fit: narration must fill its slot without truncation.
        budget = max(40, duration * CHARS_PER_SECOND)
        floor = max(30, int(budget * 0.55))
        length = len(narration)
        if length < floor:
            speech.append(length / floor)
            findings.append({"component": "speech", "severity": "info",
                             "message": f"beat {index + 1} is brief for its {duration}s slot"})
        elif length <= budget * MAX_SPEECH_OVERRUN:
            speech.append(1.0)
        else:
            speech.append(max(0.0, 1.0 - (length - budget * MAX_SPEECH_OVERRUN) / budget))
            findings.append({"component": "speech", "severity": "warn",
                             "message": f"beat {index + 1} overruns its {duration}s slot and will truncate"})

        # Readability: short sentences, no broadcast filler.
        sentences = _sentences(narration) or [narration]
        words = [len(s.split()) for s in sentences]
        avg_words = sum(words) / len(words)
        readability_beat = max(0.0, min(1.0, (35.0 - avg_words) / (35.0 - 18.0))) if avg_words > 18 else 1.0
        norm = _strip_accents(narration)
        filler_hits = [pat for pat in FILLER_PATTERNS if pat in norm]
        if filler_hits:
            readability_beat = max(0.0, readability_beat - 0.08 * len(filler_hits))
            findings.append({"component": "readability", "severity": "warn",
                             "message": f"beat {index + 1} uses broadcast filler ({', '.join(filler_hits)})"})
        readability.append(readability_beat)

    # Variety: worst adjacent-beat restatement decides.
    narrations = [s["narration"] if isinstance(s.get("narration"), str) else "" for s in clean]
    if len(narrations) < 2:
        variety = 1.0
    else:
        worst = max(_overlap(a, b) for a, b in zip(narrations, narrations[1:]))
        variety = max(0.0, 1.0 - worst)
        if worst >= 0.7:
            findings.append({"component": "variety", "severity": "warn",
                             "message": f"adjacent beats restate each other (overlap {worst:.2f})"})

    components = {
        "grounding": round(100 * sum(grounding) / len(grounding)),
        "entity": 50 if entity_unavailable else round(100 * entity_covered / len(clean)),
        "speech": round(100 * sum(speech) / len(speech)),
        "variety": round(100 * variety),
        "readability": round(100 * sum(readability) / len(readability)),
    }
    if entity_unavailable:
        findings.append({"component": "entity", "severity": "info",
                         "message": "domain seeds unavailable; entity scored neutral"})
    total = round(sum(components[key] * weight for key, weight in WEIGHTS.items()) / 100)
    return {"score": total, "version": SCORE_VERSION,
            "components": components, "findings": findings}
