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
from apps.scene_graph.intent import normalize_beat_intent


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
    "chart_comparison", "chart_timeline", "hook_card", "player_card",
    "comparison_duel", "stat_leader", "player_poster",
    "goal_card", "fixture_card", "score_card",
    "duel_columns", "player_poster_side", "player_poster_top",
    "fixture_list", "quote_card", "potm_card",
    "discipline_card", "welcome_card",
}

LAYOUT_MODES: set[str] = set()


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
    graphic_data = item.get("graphic_data", {})
    if not isinstance(graphic_data, dict):
        graphic_data = {}
    evidence_refs = item.get("evidence_refs", [])
    if not isinstance(evidence_refs, list):
        evidence_refs = []
    beat_index = 0
    beat_match = re.match(r"(?i)^beat-(\d+)$", str(item.get("id", "beat-1")).strip())
    if beat_match:
        beat_index = max(0, int(beat_match.group(1)) - 1)
    return {
        "id": str(item.get("id", "beat-1")),
        "narration": _normalise(narration),
        "visual": _normalise(str(item.get("visual", "Host analysis"))),
        "evidence_refs": [_normalise(str(ref))[:500] for ref in evidence_refs[:8] if ref],
        "beat_intent": normalize_beat_intent(
            item.get("beat_intent"), index=beat_index, graphic_data=graphic_data
        ),
        "graphic_data": graphic_data,
        "duration_seconds": duration,
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
    """Deterministic per-beat fallback; never invents facts the owner must verify.

    visual_mode is a SYSTEM fallback (tactical_explainer), never an LLM
    choice. The outline carries no tactical_diagram spec or reviewed
    graphic_data, so the beat cannot be composed to a verified card without
    owner review: the warning below is explicit so the planner never
    silently treats an outline fallback as render-ready.
    """
    goal = "establish_moment" if index == 0 else (
        "land_takeaway" if index >= len(arc) - 1 else "set_context")
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
        "beat_intent": {
            "image_goal": goal,
            "focus_subject": "",
            "evidence_type": "none",
            "emphasis_level": "hero" if index == 0 else "standard",
        },
        "graphic_data": {},
        "duration_seconds": max(1, int(target_seconds) // max(1, len(arc))),
        "timeline_events": [],
        "warnings": [
            "FALLBACK: visual_mode tactical_explainer is a system fallback "
            "(the model did not return a valid beat), not an LLM choice; no "
            "tactical_diagram spec or reviewed graphic_data is present, so "
            "composition is unverified and this beat requires owner review "
            "before render.",
        ],
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
        f"{duration_hint}s aloud without padding), visual (short shot description), "
        "evidence_refs (array of supplied evidence used), graphic_data (values and source only "
        "when explicitly present in supplied evidence, else {}), duration_seconds "
        f"(integer {lo}-{hi}), and beat_intent. "
        "Use a data visual only when its values and source are explicitly present "
        "in supplied evidence. For charts include graphic_data with headline, source, "
        "date, values (label, value), and chart_type among bar, column, pie, donut, "
        "line. Use bar for ranked comparisons; column for a few discrete categories; "
        "line only for ordered observations over match time or dates. Use pie or donut ONLY for mutually exclusive parts of one "
        "known whole with no more than four categories; otherwise choose bar or column. "
        "Never estimate or invent missing values, units, order, dates, or sources. "
        "Also return beat_intent, the ONLY visual decision you own: an object with "
        "image_goal (establish_moment, show_evidence, compare_numbers, "
        "introduce_player, set_context, or land_takeaway), focus_subject (who or "
        "what the frame focuses on, at most 120 characters), evidence_type "
        "(sourced_stat, sourced_quote, match_event, table_standing, "
        "tactical_observation, or none), and emphasis_level (quiet, standard, "
        "or hero). Do NOT choose layout, starter, camera, motion, transition, "
        "colors, or fonts: the planner determines composition from your "
        "beat_intent plus approved assets and the locked template."
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
    colorway: str = "cyber-pitch",
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
    try:
        LAYOUT_MODES.update(
            str(item.get("id")) for item in package.graphic_templates.get("layouts", [])
            if isinstance(item, dict) and item.get("id"))
    except (AttributeError, TypeError):
        pass
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
    colorway: str = "cyber-pitch",
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
            provider_statuses: list[dict[str, Any]] = []
            discovery_query = requirement.discovery_query or draft["topic"]
            if eligible_count < quantity and requirement.resource_type in {"image", "video"}:
                try:
                    found, statuses = search_candidates(
                        discovery_query,
                        resource_type=requirement.resource_type,
                        limit=12,
                    )
                    candidates = [asdict(item) for item in found]
                    provider_statuses = [
                        {"label": item.get("label"), "state": item.get("state")}
                        if isinstance(item, dict)
                        else {"label": str(getattr(item, "label", "?")),
                              "state": str(getattr(item, "state", "?"))}
                        for item in statuses
                    ]
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
                    "discovery_query": discovery_query,
                    "provider_statuses": provider_statuses,
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


def regenerate_beat(root: Path, run: dict[str, Any], beat_id: str, note: str) -> dict[str, Any]:
    """Regenerate one beat per an owner fix note; persists the run file.

    Reuses the same per-beat machinery (and guards) as drafting: the new
    narration must pass length/overlap/fact checks or a RuntimeError names
    the reason loudly. Slot timing (duration/start/end/chapter) is carried
    over so the production timeline stays stable; any attached media is
    dropped because the visual may have changed (reported in findings).
    Returns {"segment": ..., "llm_cost_usd": ...}.
    """
    from apps.llm import load_config

    if not isinstance(note, str) or not 1 <= len(note.strip()) <= 500:
        raise ValueError("Each script fix needs a note of 1-500 characters.")
    draft = run.get("draft")
    if not isinstance(draft, dict) or not isinstance(draft.get("segments"), list):
        raise ValueError("Production run has no script draft to fix.")
    segments = [s for s in draft["segments"] if isinstance(s, dict)]
    index = next((i for i, s in enumerate(segments) if str(s.get("id")) == beat_id), None)
    if index is None:
        raise ValueError(f"Beat was not found in the draft: {beat_id}.")
    old = segments[index]
    total = len(segments)
    position = f"beat {index + 1} of {total}"
    previous = segments[index - 1].get("narration", "") if index > 0 and isinstance(
        segments[index - 1].get("narration"), str) else ""
    used_facts: set[str] = set()
    for i, other in enumerate(segments):
        if i != index and isinstance(other.get("narration"), str):
            used_facts |= _fact_signature(other["narration"])
    try:
        duration_hint = max(1, int(old.get("duration_seconds", 8)))
    except (TypeError, ValueError):
        duration_hint = 8
    content_type = str(draft.get("content_type", "short")).strip().lower() or "short"
    env = load_config(root)
    ledger = _new_ledger(env)
    topic = str(draft.get("topic", run.get("topic", "")))
    evidence = list(draft.get("evidence", []) or [])
    segment, attempts, usage, last_error = _ollama_beat(
        env, topic=topic, beat_id=beat_id,
        purpose=(f"Revise {position} per owner note: {note.strip()}. "
                 "Keep the beat's story role and advance the idea."),
        position=position,
        previous_summary=previous[:300],
        evidence=evidence,
        duration_hint=duration_hint,
        num_predict=1024 if content_type == "short" else 1536,
        ledger=ledger,
        previous_narration=previous,
        used_facts=frozenset(used_facts),
    )
    if segment is None:
        raise RuntimeError(f"Beat {beat_id} could not be regenerated: {last_error}.")
    for key in ("duration_seconds", "start_seconds", "end_seconds", "chapter_id"):
        if key in old:
            segment[key] = old[key]
    segment["id"] = beat_id
    segment["generation"] = {"mode": "owner_fix", "attempts": attempts,
                             "usage": usage, "note": note.strip()[:500]}
    dropped_media = bool(old.get("media_asset_id"))
    segments[index] = segment
    draft["segments"] = segments
    fallback_beats = [b for b in draft.get("fallback_beats", []) if b != beat_id]
    draft["fallback_beats"] = fallback_beats
    cost = float(ledger.get("spent", 0.0) or 0.0)
    run["llm_cost_usd"] = round(float(run.get("llm_cost_usd", 0.0) or 0.0) + cost, 6)
    run_path = Path(root) / "runtime" / "runs" / f"{run.get('run_id', '')}.json"
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"segment": segment, "llm_cost_usd": cost, "dropped_media": dropped_media}
