from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import re
import time
from pathlib import Path
import uuid
from datetime import datetime, timezone
import unicodedata
from typing import Any

from template_foundation import resolve_template
from apps.asset_library.asset_intelligence import ResourceRequirement
from apps.asset_library.discovery import DiscoveryError, search_candidates
from apps.asset_library.resource_workflow import evaluate_library_requirement
from apps.asset_library.registry import connect
from apps.llm import budget_usd_per_run, chat_json, cost_usd, load_config


TEMPLATE_IDS = {
    "short": "allen-knows-ball.shortform-analyst",
        "long": "allen-knows-ball.longform-analyst",
}

# Decomposed local generation: one small model call per story beat instead of
# a single large call. Small tasks fit weak local models far better, and a
# failed beat regenerates or falls back on its own without discarding the
# beats that already succeeded.
BEAT_ATTEMPTS = 2
BEAT_TIMEOUT_SECONDS = 300
ASSET_NEEDS_TIMEOUT_SECONDS = 180
EVIDENCE_CHARS_PER_CALL = 1500
# Wall-clock budgets so a draft degrades gracefully instead of running
# unbounded on weak machines. Short must fit a 5-10 minute slot.
SHORT_BUDGET_SECONDS = 540
LONG_BUDGET_SECONDS = 1500
VISUAL_MODES = {
    "tactical_explainer", "statline_scorecard", "source_card",
    "chart_comparison", "chart_timeline",
}


@dataclass(frozen=True)
class ScriptDraft:
    topic: str
    story_form: str
    locale: str
    duration_target_seconds: int
    status: str
    segments: tuple[dict[str, Any], ...]
    evidence: tuple[str, ...]
    evidence_needed: tuple[str, ...]
    generation_mode: str
    voiceover_ready: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def _new_ledger(env: dict[str, str]) -> dict[str, Any]:
    """Per-draft spend ledger; the cost budget degrades to outline, never debt."""
    return {"spent": 0.0, "calls": [], "budget": budget_usd_per_run(env), "budget_stops": 0}


def _normalize_timeline_events(items: Any, segment_start: int, segment_duration: int) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    allowed = {
        "item_type": {"caption", "stat_card", "tactical_diagram", "media", "lower_third", "chapter_card", "source_card"},
        "enter": {"cut", "fade", "slide", "draw"},
        "exit": {"cut", "fade", "wipe"},
        "transition_in": {"clean_cut", "chalk_line_wipe"},
        "effect": {"none", "freeze_and_trace", "number_pop", "pitch_grid"},
    }
    events: list[dict[str, Any]] = []
    for index, item in enumerate(items[:80]):
        if not isinstance(item, dict):
            continue
        try:
            start = max(0, min(int(item.get("start_offset_seconds", 0)), segment_duration - 1))
            end = max(start + 1, min(int(item.get("end_offset_seconds", segment_duration)), segment_duration))
        except (TypeError, ValueError):
            continue
        clean: dict[str, Any] = {
            "item_id": _normalise(str(item.get("item_id", f"event-{index + 1}")))[:80],
            "item_type": item.get("item_type") if item.get("item_type") in allowed["item_type"] else "caption",
            "text": _normalise(str(item.get("text", "")))[:1000],
            "start_seconds": segment_start + start,
            "end_seconds": segment_start + end,
        }
        for key, fallback in (("enter", "cut"), ("exit", "cut"), ("transition_in", "clean_cut"), ("effect", "none")):
            clean[key] = item.get(key) if item.get(key) in allowed[key] else fallback
        evidence_ref = item.get("evidence_ref")
        clean["evidence_ref"] = _normalise(str(evidence_ref))[:250] if evidence_ref else None
        events.append(clean)
    return events


def _add_production_timeline(
    segments: list[dict[str, Any]],
    total_duration: int,
    timeline: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []
    cursor = 0
    chapters = timeline.get("chapters", [])
    raw_durations = []
    for segment in segments:
        try:
            raw_durations.append(max(1, int(segment.get("duration_seconds", 1))))
        except (TypeError, ValueError):
            raw_durations.append(1)
    raw_total = sum(raw_durations) or 1
    scaled_durations = [max(1, round(total_duration * duration / raw_total)) for duration in raw_durations]
    if scaled_durations:
        scaled_durations[-1] = max(1, scaled_durations[-1] + total_duration - sum(scaled_durations))
    for index, raw in enumerate(segments):
        segment = dict(raw)
        duration = scaled_durations[index]
        segment["duration_seconds"] = duration
        segment["start_seconds"] = cursor
        segment["end_seconds"] = cursor + duration
        segment["chapter_id"] = segment.get("chapter_id") or (chapters[min(index, len(chapters) - 1)].get("id") if chapters else f"chapter-{index + 1}")
        source_duration = raw_durations[index]
        raw_events = segment.get("timeline_events")
        if isinstance(raw_events, list):
            raw_events = [
                {
                    **event,
                    "start_offset_seconds": round(int(event.get("start_offset_seconds", 0)) * duration / source_duration),
                    "end_offset_seconds": round(int(event.get("end_offset_seconds", source_duration)) * duration / source_duration),
                }
                for event in raw_events
                if isinstance(event, dict)
            ]
        segment["timeline_events"] = _normalize_timeline_events(raw_events, cursor, duration)
        normalized.append(segment)
        cursor += duration

    # Place deterministic editorial chapter markers over the segment timeline. These
    # are fixed template events; the model only supplies per-beat overlays.
    chapter_events = []
    for chapter in chapters:
        ranges = chapter.get("range_percent", [0, 100])
        start = min(total_duration - 1, max(0, round(total_duration * float(ranges[0]) / 100)))
        end = min(total_duration, max(start + 1, round(total_duration * float(ranges[1]) / 100)))
        chapter_events.append({
            "item_id": chapter["id"],
            "item_type": "chapter_card",
            "text": chapter.get("purpose", chapter["id"]),
            "start_seconds": start,
            "end_seconds": min(total_duration, start + 2),
            "enter": "fade" if start else "cut",
            "exit": "cut",
            "transition_in": "clean_cut",
            "effect": "none",
            "evidence_ref": None,
        })
    return normalized, chapter_events


def _ollama_call(
    env: dict[str, str],
    system: str,
    user_payload: dict[str, Any],
    *,
    num_predict: int,
    timeout: int,
    ledger: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """One bounded model call through the configured provider.

    Usage is charged to the ledger. When the cost budget is spent, the call
    is skipped (recorded as a budget stop) so the draft degrades to outline
    instead of accumulating uncapped spend.
    """
    record = {
        "provider": env.get("LLM_PROVIDER", "ollama").strip().lower(),
        "model": env.get("LLM_MODEL", "").strip(),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cost_usd": 0.0,
    }
    if ledger["budget"] > 0 and ledger["spent"] >= ledger["budget"]:
        ledger["budget_stops"] += 1
        ledger["calls"].append(record)
        return None, record
    body, usage = chat_json(
        env, system, user_payload, num_predict=num_predict, timeout=timeout
    )
    cost, _ = cost_usd(env, usage)
    record.update(
        model=usage.get("model") or record["model"],
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        cost_usd=cost,
    )
    ledger["spent"] = round(ledger["spent"] + cost, 6)
    ledger["calls"].append(record)
    return body, record


def _cap_evidence(evidence: list[str], limit: int = EVIDENCE_CHARS_PER_CALL) -> list[str]:
    """Fit evidence into a weak model's context; callers keep the full list."""
    kept: list[str] = []
    used = 0
    for line in evidence:
        if used + len(line) + 1 > limit:
            break
        kept.append(line)
        used += len(line) + 1
    return kept


def _clean_segment(item: Any) -> dict[str, Any] | None:
    """Validate one model-supplied beat shape; None means this attempt failed."""
    if not isinstance(item, dict):
        return None
    narration = item.get("narration")
    if not isinstance(narration, str) or not narration.strip():
        return None
    try:
        duration = max(1, min(int(item.get("duration_seconds", 8)), 900))
    except (TypeError, ValueError):
        return None
    mode = item.get("visual_mode", "tactical_explainer")
    if mode not in VISUAL_MODES:
        mode = "tactical_explainer"
    graphic_data = item.get("graphic_data", {})
    if not isinstance(graphic_data, dict):
        graphic_data = {}
    evidence_refs = item.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        evidence_refs = []
    timeline_events = item.get("timeline_events", [])
    if not isinstance(timeline_events, list):
        timeline_events = []
    return {
        "id": str(item.get("id", "beat-1")),
        "narration": _normalise(narration),
        "visual": _normalise(str(item.get("visual", "Host analysis"))),
        "evidence_refs": [_normalise(str(ref))[:500] for ref in evidence_refs[:8] if ref],
        "visual_mode": mode,
        "graphic_data": graphic_data,
        "duration_seconds": duration,
        "timeline_events": timeline_events,
    }


def _clean_asset_needs(items: Any) -> list[dict[str, Any]]:
    """Validate model-supplied variable-media needs; invalid entries are dropped."""
    asset_needs: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return asset_needs
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        resource_type = item.get("resource_type")
        purpose = item.get("purpose")
        if resource_type not in {"image", "video"} or purpose not in {
            "match_analysis_evidence", "player_context", "visual_context"
        }:
            continue
        query = _normalise(str(item.get("query", "")))[:250]
        if not query:
            continue
        try:
            quantity = max(1, min(int(item.get("quantity", 1)), 3))
        except (TypeError, ValueError):
            quantity = 1
        asset_needs.append(
            {
                "requirement_id": f"variable-media-{len(asset_needs) + 1}",
                "resource_type": resource_type,
                "purpose": purpose,
                "quantity": quantity,
                "discovery_query": query,
                "context": _normalise(str(item.get("exact_context", ""))) or None,
                "reason": _normalise(str(item.get("reason", ""))),
            }
        )
    return asset_needs


def _word_5grams(text: str) -> set[tuple[str, ...]]:
    tokens = re.findall(r"\w+", text.lower())
    return {tuple(tokens[i:i + 5]) for i in range(len(tokens) - 4)}


def _overlap_ratio(previous: str, current: str) -> float:
    """Shared 5-gram overlap; guards against beats restating each other."""
    earlier, later = _word_5grams(previous), _word_5grams(current)
    if not earlier or not later:
        return 0.0
    return len(earlier & later) / min(len(earlier), len(later))


def _fact_signature(text: str) -> set[str]:
    """Number-like fact tokens (1,94m, 25 triệu euro, 4 bàn...).

    Beats paraphrase shared facts without tripping the wording guard, so
    facts themselves are tracked separately.
    """
    return set(re.findall(r"\d+(?:[.,]\d+)?\s*(?:m\b|triệu|trieu|euro|bàn|ban|trận|tran|tuổi|tuoi|%|ngày|ngay|tháng|thang|năm|nam)?", text.lower()))


MAX_BEAT_OVERLAP = 0.7
# Vietnamese voiceover pace: ~14 characters per second. Beats written longer
# than their slot produce voice previews the video must truncate.
CHARS_PER_SECOND = 14
MAX_SPEECH_OVERRUN = 1.25


def _outline_beat(topic: str, arc: list[Any], index: int, target_seconds: int) -> dict[str, Any]:
    """Deterministic per-beat fallback; never invents facts the owner must verify."""
    return {
        "id": f"beat-{index + 1}",
        "narration": (
            f"{topic}{'' if topic.endswith(('?', '!', '…', '.')) else '?'} Đây là câu hỏi cần trả lời trước."
            if index == 0
            else "[CẦN NGUỒN] Thêm một quan sát cụ thể hoặc nguồn có ngày tháng."
            if index < len(arc) - 1
            else "[KẾT LUẬN CỦA ALLEN] Một góc nhìn ngắn gọn, có giới hạn rõ ràng."
        ),
        "visual": (
            "Allen mở đầu trực diện"
            if index == 0
            else "Bảng chiến thuật thuộc Template Foundation"
            if index < len(arc) - 1
            else "Allen chốt ý và wordmark cố định"
        ),
        "evidence_refs": [],
        "visual_mode": "tactical_explainer",
        "graphic_data": {},
        "duration_seconds": max(1, int(target_seconds) // max(1, len(arc))),
        "timeline_events": [],
    }


def _ollama_beat(
    env: dict[str, str],
    *,
    topic: str,
    beat_id: str,
    purpose: str,
    position: str,
    previous_summary: str,
    evidence: list[str],
    duration_hint: int,
    num_predict: int,
    ledger: dict[str, Any],
    previous_narration: str = "",
    used_facts: frozenset[str] = frozenset(),
) -> tuple[dict[str, Any] | None, int, dict[str, Any], str]:
    """Generate one beat; returns (segment, attempts, usage, last_error)."""
    lo = max(1, duration_hint // 4)
    hi = max(10, duration_hint * 2)
    speech_budget = max(40, duration_hint * CHARS_PER_SECOND)
    speech_floor = max(30, int(speech_budget * 0.55))
    system = (
        "You write ONE beat of a Vietnamese soccer-analysis video script for Allen Knows Ball. "
        "Sound conversational, specific, calm, and human; avoid broadcast clichés and forced CTAs. "
        "Only state football facts supported by supplied evidence. Never invent match details, "
        "statistics, quotes, or sources. If evidence is insufficient, "
        "write a clear [CẦN NGUỒN] placeholder instead of an assertion. "
        "Open with a different sentence than the previous beat and do not "
        "restate facts it already stated; advance the idea instead. "
        "When facts_already_stated are supplied, treat them as used up: "
        "do not repeat them unless this beat adds a new fact of its own. "
        "Return only a JSON object with narration (Vietnamese voiceover, "
        f"between {speech_floor} and {speech_budget} characters so it fills "
        f"{duration_hint}s aloud without padding), visual "        "(short shot description), evidence_refs (array of supplied evidence used), "
        "visual_mode (tactical_explainer, statline_scorecard, source_card, "
        "chart_comparison, or chart_timeline), graphic_data (values and source only "
        "when explicitly present in supplied evidence, else {}), duration_seconds "
        f"(integer {lo}-{hi}), and timeline_events (on-screen items with item_id, "
        "item_type among caption, stat_card, tactical_diagram, media, lower_third, "
        "text, start_offset_seconds, end_offset_seconds, enter, exit, transition_in, "
        "effect, evidence_ref; offsets relative to this beat). "
        "Use a data visual only when its values and source are explicitly present "
        "in supplied evidence. For statline_scorecard include graphic_data.metrics "
        "(label, home, away). For charts include graphic_data with headline, source, "
        "date, values (label, value), and chart_type among bar, column, pie, donut, "
        "line. Use bar for ranked comparisons; column for a few discrete categories; "
        "line only for ordered observations over match time or dates with visual_mode "
        "chart_timeline. Use pie or donut ONLY for mutually exclusive parts of one "
        "known whole with no more than four categories; otherwise choose bar or column. "
        "Never estimate or invent missing values, units, order, dates, or sources."
    )
    user_payload = {
        "locale": "vi-VN",
        "topic": topic,
        "beat_id": beat_id,
        "beat_purpose": purpose,
        "position": position,
        "previous_beat_summary": previous_summary,
        "evidence": _cap_evidence(evidence),
    }
    if used_facts:
        user_payload["facts_already_stated"] = sorted(used_facts)[:20]
    attempts = 0
    usage: dict[str, Any] = {"provider": "", "model": "", "prompt_tokens": 0,
                             "completion_tokens": 0, "cost_usd": 0.0}
    last_error = ""
    while attempts < BEAT_ATTEMPTS:
        attempts += 1
        body, usage = _ollama_call(
            env, system, user_payload,
            num_predict=num_predict, timeout=BEAT_TIMEOUT_SECONDS,
            ledger=ledger,
        )
        if body is None:
            last_error = "transport_or_provider_error"
            continue
        segment = _clean_segment(body)
        if segment is None:
            last_error = "invalid_segment_reply"
            continue
        length_issue = _length_error(segment["narration"], duration_hint)
        if length_issue:
            last_error = length_issue
            segment = None
            continue
        if (previous_narration
                and _overlap_ratio(previous_narration, segment["narration"]) > MAX_BEAT_OVERLAP):
            last_error = "repetitive_beat"
            segment = None
            continue
        signature = _fact_signature(segment["narration"])
        if used_facts and signature and signature <= used_facts:
            last_error = "repeated_facts"
            segment = None
            continue
        segment["id"] = beat_id
        return segment, attempts, usage, ""
    return None, attempts, usage, last_error

def _length_error(narration: str, duration_hint: int) -> str:
    """Speech-length verdict for a beat: too_long, too_brief, or empty."""
    size = len(_normalise(narration))
    if size > max(40, duration_hint * CHARS_PER_SECOND):
        return "too_long"
    if size < max(30, int(duration_hint * CHARS_PER_SECOND * 0.55)):
        return "too_brief"
    return ""


def _ollama_asset_needs(
    env: dict[str, str],
    topic: str,
    beat_visuals: list[str],
    content_type: str,
    ledger: dict[str, Any],
) -> list[dict[str, Any]]:
    system = (
        "You suggest variable real media for a Vietnamese soccer-analysis video. "
        "Return only a JSON object with asset_needs: a list of only variable real "
        "media that materially improves this exact topic; each need has "
        "resource_type (image or video), purpose (match_analysis_evidence, "
        "player_context, or visual_context for venue/atmosphere only; never "
        "represent contextual media as exact-match evidence), quantity (1-3), "
        "query, exact_context, and reason. Use an empty list when the locked "
        "authored pitch-board is enough."
    )
    body, _ = _ollama_call(
        env, system,
        {"locale": "vi-VN", "topic": topic, "beats": beat_visuals,
         "content_type": content_type},
        num_predict=512, timeout=ASSET_NEEDS_TIMEOUT_SECONDS,
        ledger=ledger,
    )
    if body is None:
        return []
    return _clean_asset_needs(body.get("asset_needs", []))


def _draft_budget_seconds(env: dict[str, str], content_type: str) -> int:
    """Wall-clock budget; override per machine via DRAFT_BUDGET_*_SECONDS."""
    key = "DRAFT_BUDGET_LONG_SECONDS" if content_type == "long" else "DRAFT_BUDGET_SHORT_SECONDS"
    default = LONG_BUDGET_SECONDS if content_type == "long" else SHORT_BUDGET_SECONDS
    try:
        return max(1, int(env.get(key, default)))
    except (TypeError, ValueError):
        return default


def _ollama_draft(
    env: dict[str, str],
    topic: str,
    form: dict[str, Any],
    evidence: list[str],
    content_type: str,
    *,
    on_beat: Any = None,
    budget_seconds: int | None = None,
) -> dict[str, Any]:
    """Draft beat by beat; always returns the draft with per-beat provenance.

    Even a total model failure returns usable outline segments plus the
    fallback list, spend ledger, and failure reasons — never a bare None
    that discards all diagnostics.
    """
    arc = form.get("arc", [])
    if not arc:
        return {"model_beats": 0, "segments": [], "asset_needs": [],
                "fallback_beats": [], "budget_exceeded": False,
                "llm_cost_usd": 0.0, "llm_calls": 0,
                "llm_provider": env.get("LLM_PROVIDER", "ollama").strip().lower(),
                "llm_model": env.get("LLM_MODEL", "").strip(),
                "llm_models_used": []}
    target = int(form.get("target_seconds", 45))
    duration_hint = max(1, target // max(1, len(arc)))
    num_predict = 1024 if content_type == "short" else 1536
    total = len(arc)
    budget = budget_seconds if budget_seconds is not None else _draft_budget_seconds(env, content_type)
    started = time.monotonic()

    segments: list[dict[str, Any]] = []
    fallback_beats: list[str] = []
    previous_summary = ""
    previous_full = ""
    used_facts: set[str] = set()
    model_beats = 0
    budget_fallbacks = 0
    ledger = _new_ledger(env)
    for index, purpose in enumerate(arc):
        beat_id = f"beat-{index + 1}"
        position = f"beat {index + 1} of {total}"
        elapsed = time.monotonic() - started
        if elapsed >= budget:
            # Budget spent: remaining beats use the deterministic outline so
            # the draft still completes instead of stalling the pipeline.
            segment = _outline_beat(topic, arc, index, target)
            segment["generation"] = {"mode": "outline_fallback", "attempts": 0}
            fallback_beats.append(beat_id)
            budget_fallbacks += 1
        else:
            segment, attempts, usage, last_error = _ollama_beat(
                env, topic=topic, beat_id=beat_id,
                purpose=str(purpose), position=position,
                previous_summary=previous_summary, evidence=evidence,
                duration_hint=duration_hint, num_predict=num_predict,
                ledger=ledger, previous_narration=previous_full,
                used_facts=frozenset(used_facts),
            )
            if segment is None:
                segment = _outline_beat(topic, arc, index, target)
                segment["generation"] = {"mode": "outline_fallback", "attempts": attempts,
                                         "error": last_error}
                fallback_beats.append(beat_id)
            else:
                model_beats += 1
                segment["generation"] = {"mode": "local_ollama", "attempts": attempts,
                                         "usage": usage}
                previous_summary = segment["narration"][:300]
                previous_full = segment["narration"]
                used_facts |= _fact_signature(segment["narration"])
        segments.append(segment)
        if on_beat is not None:
            on_beat(index, total, segment["generation"]["mode"],
                     segment["generation"]["attempts"], time.monotonic() - started)

    beat_visuals = [str(item.get("visual", ""))[:200] for item in segments]
    asset_needs: list[dict[str, Any]] = []
    if model_beats > 0:
        # No model output means no grounded media needs; skip the extra call
        # instead of burning quota to decorate an outline.
        asset_needs = _ollama_asset_needs(env, topic, beat_visuals, content_type, ledger)
    models_used = sorted({
        call["model"] for call in ledger["calls"]
        if call.get("completion_tokens", 0) > 0 and call.get("model")
    })
    return {
        "model_beats": model_beats,
        "segments": segments,
        "asset_needs": asset_needs,
        "fallback_beats": fallback_beats,
        "budget_exceeded": bool(budget_fallbacks or ledger["budget_stops"]),
        "llm_cost_usd": ledger["spent"],
        "llm_calls": len(ledger["calls"]),
        "llm_provider": env.get("LLM_PROVIDER", "ollama").strip().lower(),
        "llm_model": env.get("LLM_MODEL", "").strip(),
        "llm_models_used": models_used,
    }


def create_script_draft(
    root: Path,
    topic: str,
    story_form_id: str,
    evidence_text: str = "",
    content_type: str = "short",
    colorway: str = "match-night",
    *,
    on_beat: Any = None,
    budget_seconds: int | None = None,
) -> dict[str, Any]:
    topic = _normalise(topic)
    if len(topic) < 4 or len(topic) > 500:
        raise ValueError("Chủ đề cần dài từ 4 đến 500 ký tự.")

    content_type = content_type.strip().lower()
    template_id = TEMPLATE_IDS.get(content_type)
    if template_id is None:
        raise ValueError("Content type must be either short or long.")
    package = resolve_template(root, template_id, allow_draft=True)
    supported_colorways = {item.get("id") for item in package.color_systems.get("colorways", [])}
    if colorway not in supported_colorways:
        raise ValueError("Colorway is not included in the selected template package.")
    forms = package.story_forms.get("forms", [])
    form = next((item for item in forms if item.get("id") == story_form_id), None)
    if form is None:
        raise ValueError("Không tìm thấy story form trong Template Foundation.")

    evidence = [
        _normalise(line)
        for line in evidence_text.splitlines()
        if _normalise(line)
    ][:12]
    generated = _ollama_draft(
        load_config(root), topic, form, evidence, content_type,
        on_beat=on_beat, budget_seconds=budget_seconds,
    )
    asset_needs: list[dict[str, Any]] = []
    chapter_events: list[dict[str, Any]] = []
    fallback_beats: list[str] = []
    llm_cost_usd = 0.0
    llm_calls = 0
    llm_provider = "ollama"
    llm_model = ""
    llm_models_used: list[str] = []
    budget_exceeded = False
    segments = generated["segments"]
    asset_needs = generated["asset_needs"]
    fallback_beats = generated["fallback_beats"]
    llm_cost_usd = generated["llm_cost_usd"]
    llm_calls = generated["llm_calls"]
    llm_provider = generated["llm_provider"]
    llm_model = generated["llm_model"]
    llm_models_used = generated["llm_models_used"]
    budget_exceeded = generated["budget_exceeded"]
    if generated["model_beats"] == 0:
        # Total model failure keeps the per-beat outline segments with their
        # failure reasons instead of a bare outline with no diagnostics.
        mode = "outline_fallback"
    else:
        mode = "local_ollama" if not fallback_beats else "local_ollama_partial"

    total_duration = int(form.get("target_seconds", 45))
    segments, chapter_events = _add_production_timeline(segments, total_duration, package.timeline)

    factual_segments = [
        item for item in segments if "[CẦN NGUỒN]" in item["narration"]
    ]
    evidence_needed = (
        ("Nguồn và ngày cho từng tình huống/trận đấu được nhắc tới",)
        if not evidence
        else ("Đối chiếu từng nhận định với nguồn gốc và thời điểm của nó",)
        if factual_segments
        else ()
    )
    draft = ScriptDraft(
        topic=topic,
        story_form=story_form_id,
        locale=package.manifest.get("locale", "vi-VN"),
        duration_target_seconds=total_duration,
        status="NEEDS_OWNER_REVIEW" if not evidence_needed else "NEEDS_EVIDENCE",
        segments=tuple(segments),
        evidence=tuple(evidence),
        evidence_needed=evidence_needed,
        generation_mode=mode,
    )
    result = draft.as_dict()
    result["asset_needs"] = asset_needs
    result["asset_need_reason"] = (
        "Model selected variable media for this story."
        if asset_needs
        else "The fixed host framing and tactical board cover the visuals; no variable library media was requested."
    )
    result["content_type"] = content_type
    result["template_id"] = template_id
    result["template_version"] = package.manifest["version"]
    result["colorway"] = colorway
    result["timeline"] = package.timeline
    result["chapter_events"] = chapter_events
    result["timeline_events"] = [event for segment in segments for event in segment["timeline_events"]] + chapter_events
    result["fallback_beats"] = fallback_beats
    result["budget_exceeded"] = budget_exceeded
    result["llm_cost_usd"] = llm_cost_usd
    result["llm_calls"] = llm_calls
    result["llm_provider"] = llm_provider
    result["llm_model"] = llm_model
    result["llm_models_used"] = llm_models_used
    return result


def run_content_agent(
    root: Path,
    db_path: Path,
    topic: str,
    story_form_id: str,
    evidence_text: str = "",
    content_type: str = "short",
    colorway: str = "match-night",
) -> dict[str, Any]:
    """Run the bounded local agent and stop before owner-controlled actions."""
    from apps.voice_tts import voice_profile_status

    run_id = uuid.uuid4().hex[:12]
    runs_dir = root / "runtime/runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_path = runs_dir / f"{run_id}.json"

    def _save_progress(run: dict[str, Any]) -> None:
        run_path.write_text(
            json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # Publish the run immediately so Runs & queue shows live progress while
    # the local model drafts (minutes on CPU) instead of appearing only at
    # the end. Owner review still gates everything downstream.
    run: dict[str, Any] = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "DRAFTING_SCRIPT",
        "steps": [
            {"id": "script", "status": "RUNNING"},
            {"id": "asset_needs", "status": "PENDING", "count": 0},
            {"id": "library", "status": "PENDING", "count": 0},
            {"id": "owner_checkpoint", "status": "WAITING"},
        ],
        "draft": None,
        "asset_checks": [],
        "human_approval_required": True,
        "no_assets_saved_or_selected": True,
    }
    _save_progress(run)

    try:
        def _report_beat(index: int, total: int, mode: str, attempts: int, elapsed: float) -> None:
            run["current_beat"] = index + 1
            run["total_beats"] = total
            run["last_beat_mode"] = mode
            _save_progress(run)

        draft = create_script_draft(
            root, topic, story_form_id, evidence_text, content_type, colorway,
            on_beat=_report_beat,
        )
    except Exception as error:
        run["status"] = "DRAFT_FAILED"
        run["error"] = str(error)
        _save_progress(run)
        raise
    run["status"] = "CHECKING_ASSETS"
    run["steps"][0] = {"id": "script", "status": draft["status"], "local_model": draft["generation_mode"]}
    _save_progress(run)
    checks: list[dict[str, Any]] = []
    conn = connect(db_path)
    try:
        for need in draft["asset_needs"]:
            requirement = ResourceRequirement(
                requirement_id=need["requirement_id"],
                resource_type=need["resource_type"],
                purpose=need["purpose"],
                context=need["context"],
                rights_state="verified",
                lifecycle_state="active",
                discovery_query=need["discovery_query"],
                content_objective=draft["topic"],
            )
            evaluation = evaluate_library_requirement(conn, requirement)
            quantity = int(need["quantity"])
            eligible_count = len(evaluation.eligible_assets)
            candidates = []
            discovery_error = None
            if eligible_count < quantity and requirement.resource_type in {"image", "video"}:
                try:
                    found, _ = search_candidates(
                        requirement.discovery_query or draft["topic"],
                        resource_type=requirement.resource_type,
                        limit=12,
                    )
                    candidates = [asdict(item) for item in found]
                except DiscoveryError as error:
                    discovery_error = str(error)
            checks.append(
                {
                    "need": need,
                    "requirement": asdict(requirement),
                    "evaluation": asdict(evaluation),
                    "required_count": quantity,
                    "eligible_count": eligible_count,
                    "shortfall": max(0, quantity - eligible_count),
                    "web_candidates": candidates,
                    "candidate_status": "SUGGESTIONS_ONLY" if candidates else "NO_CANDIDATES",
                    "discovery_error": discovery_error,
                }
            )
    finally:
        conn.close()

    run_id = run["run_id"]
    run.update(
        {
            "status": "WAITING_FOR_OWNER_REVIEW",
            "steps": [
                {"id": "script", "status": draft["status"], "local_model": draft["generation_mode"]},
                {"id": "asset_needs", "status": "ASSESSED", "count": len(draft["asset_needs"])},
                {"id": "library", "status": "ASSESSED_AND_DISCOVERY_OFFERED", "count": len(checks)},
                {"id": "owner_checkpoint", "status": "WAITING"},
            ],
            "draft": draft,
            "asset_checks": checks,
            "human_approval_required": True,
            "no_assets_saved_or_selected": True,
            "llm_cost_usd": draft.get("llm_cost_usd", 0.0),
            "voice_status": voice_profile_status(root),
        }
    )
    _save_progress(run)
    return run
