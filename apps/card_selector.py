"""Card selector: script segments -> render-ready card decisions.

Given any script draft (segments with narration/visual/beat_intent/graphic_data)
plus fetched library assets, the engine decides which card each beat renders,
which authored starter it maps to, and which asset binds to which declared
media slot — before the renderer runs.

Deterministic and rule-based (NSS-style 0-100 fit score, zero model cost):
semantic beat role + reviewed data + beat intent choose a contract grammar;
only cards whose C7 ``execution.status`` is exactly ``contract`` are
production-ready. ``partial`` and ``legacy_non_ready`` cards are explicit
fallbacks, never converted into fake variety. A declared mode is a planner
hint, not an owner of layout: a legacy declared mode may be replaced by a
contract-ready mode when the beat's reviewed data supports it.

Media follows the same contract boundary: an asset may bind only to a declared
``media_slots`` region (today the three player-portrait cards). No card without
a media slot receives an asset, and no bound asset is converted into a
``media_b_roll`` scene. A portrait must depict the named player and clear the
upload purpose.

No I/O, no LLM calls. Import-safe (no video_renderer import).
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from apps.content_workflow import VISUAL_MODES
from apps.asset_library.rights_scope import is_usable_for, normalize_purpose
from apps.measurement.render_qa import (
    measure_text_slot,
)
from apps.measurement.review_records import (
    review_readiness_fields,
    source_card_visual_approved,
)
from apps.measurement.content_review import content_review_readiness_fields
from apps.scene_graph.intent import IMAGE_GOALS
from apps.studio_templates.card_media import card_contract, load_contract

# Renderer accepts everything _clean_segment allows, plus media_b_roll which
# remains a legacy primitive route. The planner never selects media_b_roll for
# a production-ready beat: C7 declares no b-roll media slot.
SUPPORTED_MODES = set(VISUAL_MODES) | {"media_b_roll"}

# Legacy renderer modes that may carry a portrait image. Only the first five
# are C7 cards with a declared player_portrait media slot; score/quote/welcome
# are historical portrait routes and have no C7 media slot in 12.0.0.
PORTRAIT_MODES = {
    "player_card", "player_poster", "player_poster_side", "player_poster_top",
    "potm_card", "welcome_card", "score_card", "quote_card",
}
PLAYER_MODES = frozenset({
    "player_card", "player_poster", "player_poster_side", "player_poster_top",
    "potm_card",
})

# image_goal -> preferred visual modes (advisory tie-break, never a hard
# composition decision). The LLM owns image_goal meaning only; the planner
# uses these hints as a soft nudge when candidate fit scores are nearly equal.
# Keys come from apps.scene_graph.intent.IMAGE_GOALS; values are a subset of
# SUPPORTED_MODES chosen so the hinted mode is coherent with the goal meaning.
_INTENT_GOAL_MODE_HINTS: dict[str, list[str]] = {
    "establish_moment": ["hook_card"],
    "show_evidence": ["source_card", "quote_card", "statline_scorecard", "goal_card"],
    "compare_numbers": ["duel_columns", "stat_leader", "chart_comparison", "score_card"],
    "introduce_player": ["player_card", "player_poster",
                         "player_poster_side", "player_poster_top", "potm_card"],
    "set_context": ["fixture_card", "fixture_list", "welcome_card",
                    "chart_timeline"],
    "land_takeaway": ["media_b_roll", "tactical_explainer", "quote_card"],
}

# Soft bonus points applied when a candidate mode matches the intent hint.
# Small enough to break near-ties only; never overrides hard constraints
# (beat-0 hook, player lock, rights/purpose eligibility, mode support),
# which are applied before/after scoring independently of this bonus.
_INTENT_MODE_HINT_BONUS = 2.0

# Short starters live in apps/studio_templates/*.short.json, long ones in
# *.long.json. Starter is only suggested when its aspect matches the content.
STARTERS_SHORT = {
    "hook_card": "C-11", "quote_card": "C-05",
    "statline_scorecard": "C-07", "comparison_duel": "C-07", "duel_columns": "C-07",
    "stat_leader": "C-06", "chart_comparison": "C-06",
    "player_poster_side": "C-04", "player_poster_top": "C-04",
    "player_poster": "C-04", "player_card": "C-04", "potm_card": "C-04",
    "goal_card": "MR-04", "score_card": "MR-02",
    "fixture_card": "MR-11", "fixture_list": "MR-11",
    "discipline_card": "MR-06", "welcome_card": "BP-06",
    "chart_timeline": "MR-06", "source_card": "C-09",
}
STARTERS_LONG = {
    "chart_comparison": "TA-16", "chart_timeline": "TA-12",
    "hook_card": "TA-01", "fixture_card": "TA-02",
    "fixture_list": "TA-02", "score_card": "TA-02",
    "goal_card": "TA-02", "discipline_card": "TA-11",
}

# Contract-ready fallback cards for a grammar mode. Kept separate from
# STARTERS_SHORT/STARTERS_LONG: tools/build_card_contract.py hashes those
# historical mappings, and the C7 contract must remain byte-identical.
# Every card below is checked against the live C7 record before use.
CONTRACT_MODE_FALLBACK: dict[str, str] = {
    "hook_card": "C-11",
    "score_card": "MR-02",
    "duel_columns": "BP-14",
    "stat_leader": "BP-16",
    "player_card": "C-04",
    "player_poster": "C-04",
    "player_poster_side": "C-04",
    "player_poster_top": "C-04",
    "potm_card": "C-04",
    # 12.1.0: C-09 is the sole contract-executable source attribution card.
    # BP-20/MR-12/U-08 remain explicit legacy/non-ready suggestions.
    "source_card": "C-09",
}

# Roles that can be expressed by a C7 contract card. Roles absent here
# (tactical, context, quote, timeline, discipline, takeaway) stay explicit
# non-ready paths until a future pack authors a contract card for them. The
# source role is attribution-only in 12.1.0; fact-check and correction
# semantics are deliberately not mapped to C-09. Do not fabricate a mode to
# make the grammar count look better.
ROLE_CONTRACT_MODES: dict[str, tuple[str, ...]] = {
    "hook": ("hook_card",),
    "result": ("score_card", "stat_leader", "duel_columns"),
    "comparison": ("duel_columns", "stat_leader", "score_card"),
    "stat": ("stat_leader", "duel_columns", "score_card"),
    "player": (
        "player_card", "player_poster_side", "player_poster",
        "player_poster_top", "potm_card",
    ),
    "source": ("source_card",),
}

CONTRACT_READY = "contract"
MEDIA_FALLBACK = "fallback_no_asset"

# required graphic_data keys per mode (mirrors graphic-templates.json plus
# the renderer's data reads). Keys prefixed "graphic_data." in the package.
REQUIRED_SLOTS: dict[str, list[str]] = {
    "hook_card": ["hook_text"],
    "goal_card": ["hook_text"],
    "duel_columns": ["metrics", "source", "date"],
    "comparison_duel": ["metrics", "source", "date"],
    "statline_scorecard": ["metrics"],
    "stat_leader": ["stats", "source", "date"],
    "chart_comparison": ["values"],
    "chart_timeline": ["values"],
    "player_poster_side": ["player_name", "stats"],
    "player_poster_top": ["player_name", "stats"],
    "player_poster": ["player_name"],
    "player_card": ["player_name"],
    "potm_card": ["player_name"],
    "discipline_card": ["player_name"],
    "welcome_card": ["player_name"],
    "fixture_card": ["home", "away"],
    "fixture_list": ["fixtures", "source", "date"],
    "score_card": ["home", "away", "score"],
    "quote_card": ["claim"],
    "source_card": ["source", "date", "claim"],
    "tactical_explainer": [],
    "media_b_roll": [],
}

# Slots the filter may derive from narration (never numbers/sources/dates).
DERIVABLE_SLOTS = {"hook_text", "claim"}

# Signals are matched diacritics-insensitively against narration + visual.
MODE_SIGNALS: dict[str, tuple[str, ...]] = {
    "duel_columns": ("doi dau", "so sanh", "doi chieu", "hon thua", "hon han"),
    "stat_leader": ("ky luc", "dan dau", "nhieu nhat", "thong ke", "con so"),
    "score_card": ("ti so", "ket qua", "thang", "thua", "hoa"),
    "goal_card": ("ban thang", "goi", "an mung", "lap cong"),
    "discipline_card": ("the do", "the vang", "phat", "treo gio", "var"),
    "quote_card": ("noi rang", "chia se", "tuyen bo", "phat bieu", '"'),
    "source_card": ("nguon", "theo", "bao cao", "xac nhan", "du lieu"),
    "fixture_card": ("lich thi dau", "vong toi", "tiep don", "lam khach", "hen gio"),
    "tactical_explainer": ("so do", "chien thuat", "pressing", "doi hinh",
                           "phong ngu", "tan cong", "khoang trong", "phut"),
    "player_poster_side": ("cau thu", "tien dao", "tien ve", "hau ve", "thu mon"),
}


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower()).replace("đ", "d")
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _present(data: dict[str, Any], key: str) -> bool:
    value = data.get(key)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _normalize_hook_text(hook_text: str) -> tuple[str, str | None]:
    """Normalize (strip) and cap hook_text at 8 words from graphic_data.

    Never derives hook_text from narration: if graphic_data lacks hook_text,
    the slot stays empty (fail-closed, no fabricated claim).
    Second value is a tightening warning, if any.
    """
    text = hook_text.strip()
    words = text.split()
    if len(words) > 8:
        return (" ".join(words[:8]),
                "hook_text capped at 8 words from graphic_data; tighten to a clean 5–8 word claim")
    if len(words) < 5:
        return text, "hook_text shorter than the 5-word minimum; expand to 5–8 words"
    return text, None


def _derive_claim(narration: str, limit: int = 220) -> str:
    first = re.split(r"[.!?…\n]", narration.strip())[0].strip()
    return first[:limit].strip()


def _eligible_asset(asset: dict[str, Any],
                    purpose: dict[str, Any] | None = None) -> bool:
    """Verified/active image; with a purpose, also rights-usable for that upload.

    ``rights_state == "verified"`` is identity/suitability only, never usage
    clearance: when a purpose is given the asset must additionally pass
    ``is_usable_for`` (platform, territory, commercial, monetization, ...).
    When purpose is missing or not a valid mapping the asset is NOT eligible:
    verified/active is never treated as sufficient usage rights, so the
    selector fails closed and attaches no library asset as if cleared.
    """
    base = (asset.get("asset_type") == "image"
            and asset.get("rights_state") == "verified"
            and asset.get("lifecycle_state") == "active")
    if not base:
        return False
    if not isinstance(purpose, Mapping):
        return False
    return is_usable_for(asset, purpose)["allowed"] is True


def _match_portrait(player_name: str, assets: list[dict[str, Any]],
                    purpose: dict[str, Any] | None = None) -> str | None:
    """Find a verified image depicting the named player (advisory match).

    Exact identity lives in player_identity; here we match normalized names
    against asset subjects/original_name/metadata text. Returns asset_id.
    When a purpose is given, only assets that clear ``is_usable_for`` for that
    upload intent are eligible.
    """
    want = _strip_accents(player_name)
    if not want:
        return None
    want = re.sub(r"[-_]+", " ", want)
    want_tokens = set(want.split())
    for asset in assets:
        if not _eligible_asset(asset, purpose):
            continue
        subjects = asset.get("subjects") or []
        haystack = " ".join([str(asset.get("original_name", ""))]
                            + [str(s) for s in subjects])
        metadata = asset.get("metadata")
        if isinstance(metadata, dict):
            haystack += " " + " ".join(str(v) for v in metadata.values()
                                       if isinstance(v, str))
        norm = re.sub(r"[-_]+", " ", _strip_accents(haystack))
        if want and want in norm:
            return str(asset.get("asset_id"))
        if want_tokens and want_tokens <= set(norm.split()):
            return str(asset.get("asset_id"))
    return None


def _signal_modes(narration: str, visual: str) -> list[str]:
    text = _strip_accents(f"{narration} {visual}")
    return [mode for mode, keys in MODE_SIGNALS.items()
            if any(key in text for key in keys)][:4]


def _coverage(mode: str, data: dict[str, Any], narration: str) -> tuple[float, list[str], dict[str, Any], list[str]]:
    """Fraction of required slots present (after safe derivation).

    Returns (coverage, derived_keys, filled_data, derive_warnings).
    """
    required = REQUIRED_SLOTS.get(mode, [])
    if not required:
        return 1.0, [], dict(data), []
    filled = dict(data)
    derived: list[str] = []
    derive_warnings: list[str] = []
    for key in required:
        if key == "hook_text" and key in data and data[key].strip():
            filled[key], note = _normalize_hook_text(data[key])
            derived.append(key)
            if note:
                derive_warnings.append(note)
        elif _present(filled, key):
            continue
        elif key == "claim" and mode != "source_card" and narration.strip():
            # Source attribution requires a reviewed claim. Never derive it
            # from narration for source_card (and never substitute the source
            # name): missing claim must stay an explicit non-ready path.
            filled[key] = _derive_claim(narration)
            derived.append(key)
    covered = sum(1 for key in required if _present(filled, key))
    return covered / len(required), derived, filled, derive_warnings


def _score_candidate(mode: str, segment: dict[str, Any], data: dict[str, Any],
                     assets: list[dict[str, Any]], declared: bool,
                     prev_modes: list[str],
                     purpose: dict[str, Any] | None = None,
                     intent: dict[str, str] | None = None
                     ) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 50.0 if declared else 40.0
    narration = str(segment.get("narration", ""))
    coverage, derived, _, _ = _coverage(mode, data, narration)
    score += 30.0 * coverage
    if derived:
        parts = []
        for d in derived:
            if d == "hook_text":
                parts.append("hook_text normalized/capped from graphic_data")
            else:
                parts.append(f"{d} derived from narration")
        reasons.append("; ".join(parts))
    required = REQUIRED_SLOTS.get(mode, [])
    missing = [k for k in required if not _present(data, k) and k not in derived]
    if missing and mode != "tactical_explainer":
        reasons.append(f"missing {','.join(missing)}")
    if mode in PORTRAIT_MODES and _present(data, "player_name"):
        hit = _match_portrait(str(data.get("player_name", "")), assets, purpose)
        if hit:
            score += 10.0
            reasons.append("verified portrait available")
        else:
            score -= 25.0
            reasons.append("no verified portrait of the named player; typographic fallback")
    if prev_modes and mode == prev_modes[-1]:
        score -= 10.0
        reasons.append("same card as previous beat")
        if prev_modes[-3:].count(mode) >= 2:
            score -= 5.0
            reasons.append("card dominating recent beats")
    elif mode in prev_modes[-3:]:
        score -= 10.0
        reasons.append("card repeated within 3 beats")
    # Advisory intent tie-break: soft nudge toward modes that fit the
    # segment's image_goal when fit scores are nearly equal. Never overrides
    # hard constraints (applied before/after scoring: beat-0 hook, player
    # lock, rights/purpose eligibility, mode support). Missing/invalid intent
    # leaves scoring unchanged.
    if intent is not None:
        goal = str(intent.get("image_goal", ""))
        hints = _INTENT_GOAL_MODE_HINTS.get(goal)
        if hints and mode in hints:
            score += _INTENT_MODE_HINT_BONUS
            reasons.append(f"intent hint: {goal} fits {mode}")
    return max(0.0, min(100.0, score)), reasons


def _tactical_starter(segment: dict[str, Any], content_type: str) -> str | None:
    if content_type != "long":
        return None
    text = _strip_accents(str(segment.get("narration", "")) + " "
                          + str(segment.get("visual", "")))
    if "trap" in text or "bay" in text:
        return "TA-08"
    if "pressing" in text or "press" in text:
        return "TA-06"
    if "1v1" in text or "doi dau" in text:
        return "TA-13"
    if "trien khai" in text or "tuyen duoi" in text or "phat bong" in text:
        return "TA-07"
    if "khoang trong" in text or "khai thac" in text:
        return "TA-09"
    if "di chuyen" in text or "hoan doi" in text or "chong bien" in text or "overlap" in text:
        return "TA-10"
    if "ban do" in text or "heatmap" in text or "vung hoat dong" in text:
        return "TA-17"
    if "truoc" in text and "sau" in text:
        return "TA-15"
    if "dieu chinh" in text or "thay doi" in text:
        return "TA-14"
    if "doi hinh" in text or "xuat phat" in text or "lineup" in text:
        return "TA-04"
    if "cam bong" in text or "kiem soat" in text or "tan cong" in text:
        return "TA-05"
    if "dong bang" in text or "phut" in text or "khoanh khac" in text:
        return "TA-11"
    return "TA-03"


def _story_starter(mode: str, segment: dict[str, Any]) -> str | None:
    """Sprint 3 storytelling refinement for short-form beats.

    Returns a specific P1/P2 starter when narration carries a strong
    signal, else None (caller falls back to the Sprint 1 default table).
    Mirrors the Sprint 2 `_tactical_starter` pattern: signal-based,
    diacritics-insensitive, deterministic, zero model cost.
    """
    text = _strip_accents(str(segment.get("narration", "")) + " "
                          + str(segment.get("visual", "")))
    if mode == "hook_card":
        if "tin nong" in text or "breaking" in text or "ket qua moi" in text:
            return "MR-01"
        if ("cau chuyen" in text or "ngoai san" in text
                or "su that bat ngo" in text or "nghich ly" in text):
            return "BP-01"
        return None
    if mode == "score_card":
        if "hiep mot" in text or "half" in text or "nghi giua hiep" in text:
            return "MR-03"
        return None
    if mode in ("player_poster_side", "player_poster_top", "player_poster",
                "player_card", "potm_card"):
        if ("potm" in text or "xuat sac nhat" in text or "hay nhat" in text
                or "cau thu cua tran" in text):
            return "MR-08"
        if ("ho so" in text or "profile" in text or "su nghiep" in text
                or "tieu su" in text or "chan dung" in text):
            return "BP-03"
        return None
    if mode in ("duel_columns", "comparison_duel"):
        if ("chuyen nhuong" in text or "transfer" in text or "phi chuyen"
                in text or "gia tri" in text):
            return "BP-07"
        if ("kinh dich" in text or "derby" in text
                or "doi dau lich su" in text):
            return "BP-10"
        return None
    if mode in ("stat_leader", "chart_comparison"):
        if "top ghi" in text or "ranking" in text:
            return "BP-15"
        if ("bang xep hang" in text or "standings" in text
                or "diem so" in text or "hieu so" in text):
            return "MR-09"
        if "xep hang" in text or "danh sach" in text:
            return "BP-15"
        if ("kiem soat bong" in text or "cu sut" in text or "xg" in text
                or "chi so tran" in text):
            return "MR-07"
        return None
    if mode == "chart_timeline":
        if ("su nghiep" in text or "career" in text or "cot moc" in text):
            return "BP-04"
        if ("thang tien" in text or "sa sut" in text or "tai sinh" in text
                or "rise" in text):
            return "BP-05"
        if ("lich su" in text or "history" in text or "di san" in text):
            return "BP-11"
        if ("buoc ngoat" in text or "turning" in text):
            return "BP-17"
        if ("timeline" in text or "trinh tu" in text or "dien bien tran" in text):
            return "MR-05"
        return None
    if mode == "source_card":
        if ("kiem chung" in text or "fact check" in text or "xac minh" in text):
            return "BP-20"
        if ("sua loi" in text or "dinh chinh" in text or "correction" in text
                or "cap nhat lai" in text):
            return "U-08"
        if "du lieu tran" in text or "nguon tran" in text:
            return "MR-12"
        return None
    return None


def _starter_for(mode: str, segment: dict[str, Any], content_type: str,
                 data: dict[str, Any]) -> str | None:
    if mode == "tactical_explainer":
        return _tactical_starter(segment, content_type)
    if mode == "statline_scorecard":
        hero = data.get("hero")
        if isinstance(hero, dict) and not data.get("metrics"):
            return "C-06" if content_type == "short" else None
        return "C-07" if content_type == "short" else None
    if content_type == "short":
        refined = _story_starter(mode, segment)
        if refined is not None:
            return refined
        return STARTERS_SHORT.get(mode)
    table = STARTERS_LONG
    return table.get(mode)


def _card_execution(
    starter: str | None, mode: str, content_type: str
) -> tuple[str, str | None]:
    """Classify the chosen card/mode against the executable card contract.

    The selector may still suggest a legacy card for review, but the decision
    must say so: the builder will freeze a primitive fallback rather than
    silently execute an unsupported authored design.
    """
    if not starter:
        return "none", None
    if content_type != "short":
        return "legacy_long", "long-form cards are not contract-executable yet"
    record = card_contract(starter)
    if record is None:
        return "no_contract", f"no contract record for starter {starter}"
    if mode in record["execution"]["modes"]:
        return str(record["execution"]["status"]), None
    return "legacy_non_ready", str(record["execution"].get("reason") or
                                    f"mode {mode} is not executable")


# ---------------------------------------------------------------------------
# Contract-aware grammar planning (C7)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def contract_grammar_modes() -> dict[str, tuple[str, ...]]:
    """Return C7 card-level-contract modes -> sorted card ids.

    Only ``execution.status == "contract"`` records are included. ``partial``
    cards remain explicit non-ready for grammar selection even when one of
    their modes is technically executable, because the card as a whole has a
    named legacy surface. This is the production-ready allowlist.
    """
    contract = load_contract()
    if contract is None:
        return {}
    modes: dict[str, list[str]] = {}
    for card in contract.get("cards") or []:
        if not isinstance(card, dict):
            continue
        execution = card.get("execution") or {}
        if execution.get("status") != CONTRACT_READY:
            continue
        for mode in execution.get("modes") or []:
            if mode in SUPPORTED_MODES:
                modes.setdefault(str(mode), []).append(str(card["card_id"]))
    return {mode: tuple(sorted(set(card_ids)))
            for mode, card_ids in sorted(modes.items())}


def _contract_record_ready(card_id: str | None,
                           mode: str) -> dict[str, Any] | None:
    """Return the C7 record only when card+mode are card-level contract-ready."""
    if not card_id:
        return None
    record = card_contract(card_id)
    if record is None:
        return None
    if record.get("execution", {}).get("status") != CONTRACT_READY:
        return None
    if mode not in record.get("execution", {}).get("modes", []):
        return None
    return record


def _is_money_stat(segment: dict[str, Any], data: dict[str, Any]) -> bool:
    """Money/transfer stat beats may use BP-08 instead of the generic BP-16."""
    text = _strip_accents(str(segment.get("narration", "")) + " "
                          + str(segment.get("visual", "")))
    stats = data.get("stats") if isinstance(data.get("stats"), list) else []
    labels = " ".join(
        _strip_accents(str(item.get("label", "")))
        for item in stats if isinstance(item, dict)
    )
    haystack = f"{text} {labels}"
    return any(token in haystack for token in (
        "chuyen nhuong", "phi chuyen", "gia tri", "dinh gia",
        "doanh thu", "muc luong", "tien luong", "trieu",
    ))


def _contract_starter_for(
    mode: str,
    segment: dict[str, Any],
    content_type: str,
    data: dict[str, Any],
) -> str | None:
    """Pick a card-level contract card for a mode, or None.

    The historical ``_story_starter`` may still return a partial card (for
    example BP-15/MR-09/MR-07 for stat rows). Those are intentionally rejected
    here and replaced with a generic contract card of the same grammar.
    """
    if content_type != "short":
        return None
    refined = _story_starter(mode, segment)
    if refined and _contract_record_ready(refined, mode):
        return refined
    if mode == "stat_leader" and _is_money_stat(segment, data):
        if _contract_record_ready("BP-08", mode):
            return "BP-08"
    fallback = CONTRACT_MODE_FALLBACK.get(mode)
    if fallback and _contract_record_ready(fallback, mode):
        return fallback
    for card_id in contract_grammar_modes().get(mode, ()):
        if _contract_record_ready(card_id, mode):
            return card_id
    return None


def _declared_role(declared: str | None) -> str | None:
    if not declared:
        return None
    if declared == "hook_card":
        return "hook"
    if declared in ("score_card", "goal_card"):
        return "result"
    if declared in ("duel_columns", "comparison_duel",
                    "statline_scorecard", "chart_comparison"):
        return "comparison"
    if declared == "stat_leader":
        return "stat"
    if declared in PLAYER_MODES or declared == "welcome_card":
        return "player"
    if declared in ("fixture_card", "fixture_list"):
        return "context"
    if declared == "source_card":
        return "source"
    if declared == "quote_card":
        return "quote"
    if declared == "discipline_card":
        return "discipline"
    if declared == "chart_timeline":
        return "timeline"
    if declared == "tactical_explainer":
        return "tactical"
    if declared == "media_b_roll":
        return "media"
    return None


def _data_roles(data: dict[str, Any]) -> list[str]:
    """Reviewed-data shapes, strongest factual signal first."""
    roles: list[str] = []
    if (_present(data, "home") and _present(data, "away")
            and _present(data, "score")):
        roles.append("result")
    if _present(data, "metrics"):
        roles.append("comparison")
    if _present(data, "stats"):
        roles.append("stat")
    if _present(data, "player_name"):
        roles.append("player")
    return roles


def _role_for_beat(
    *,
    index: int,
    declared: str | None,
    beat_intent: dict[str, Any] | None,
    data: dict[str, Any],
    segment: dict[str, Any],
) -> str:
    """Classify the beat's story role from meaning/data, never the beat index.

    The only index rule is the locked story-form invariant: beat 0 opens on
    the hook. Other beats are classified by intent, reviewed data shape,
    declared mode (a planner hint), and narration signals. A tactical
    declaration never prevents a data-backed score/stat/comparison card.
    """
    if index == 0:
        return "hook"
    role = _declared_role(declared)
    data_roles = _data_roles(data)
    signals = set(_signal_modes(str(segment.get("narration", "")),
                                str(segment.get("visual", ""))))
    goal = None
    if isinstance(beat_intent, dict):
        candidate = beat_intent.get("image_goal")
        if candidate in IMAGE_GOALS:
            goal = str(candidate)

    if goal == "introduce_player":
        return "player"
    if goal == "compare_numbers":
        if "comparison" in data_roles:
            return "comparison"
        if "stat" in data_roles:
            return "stat"
        if "result" in data_roles:
            return "result"
        return "comparison"
    if goal == "show_evidence":
        if role in ("source", "quote", "discipline", "timeline") and not data_roles:
            return role
        if "result" in data_roles:
            return "result"
        if "comparison" in data_roles and "stat" in data_roles:
            return ("comparison" if role == "comparison"
                    or "stat_leader" not in signals else "stat")
        if "comparison" in data_roles:
            return "comparison"
        if "stat" in data_roles:
            return "stat"
        if "player" in data_roles and (role == "player"
                                       or "player_poster_side" in signals):
            return "player"
        if role:
            return role
        if "tactical_explainer" in signals:
            return "tactical"
        return "evidence"
    if goal == "set_context":
        for candidate in ("result", "comparison", "stat"):
            if candidate in data_roles:
                return candidate
        if role in ("context", "player"):
            return role
        if "player" in data_roles and "player_poster_side" in signals:
            return "player"
        return "context"
    if goal == "land_takeaway":
        return "takeaway"
    if goal == "establish_moment":
        if declared == "hook_card" or _present(data, "hook_text"):
            return "hook"
        return "context"

    # No usable intent: an explicitly declared contract mode wins; a legacy
    # tactical/context declaration yields to reviewed data when that data
    # supports a contract grammar. Quote/source/discipline/timeline/media
    # declarations keep their meaning even if a player name is present.
    if role in ("quote", "source", "discipline", "timeline", "media"):
        return role
    if role in ("tactical", "context") and data_roles:
        for candidate in ("result", "comparison", "stat"):
            if candidate in data_roles:
                return candidate
        if "player" in data_roles and "player_poster_side" in signals:
            return "player"
        return role
    if role in ("hook", "result", "comparison", "stat", "player"):
        return role
    if role:
        return role
    if data_roles:
        if "result" in data_roles:
            return "result"
        if "comparison" in data_roles and "stat" in data_roles:
            return ("stat" if "stat_leader" in signals else "comparison")
        if "comparison" in data_roles:
            return "comparison"
        if "stat" in data_roles:
            return "stat"
        if "player" in data_roles and "player_poster_side" in signals:
            return "player"
    if "score_card" in signals:
        return "result"
    if "duel_columns" in signals:
        return "comparison"
    if "stat_leader" in signals:
        return "stat"
    if "tactical_explainer" in signals:
        return "tactical"
    if "source_card" in signals:
        return "source"
    if "quote_card" in signals:
        return "quote"
    if "fixture_card" in signals:
        return "context"
    return "context"


def _candidate_modes_for_role(
    role: str,
    declared: str | None,
    segment: dict[str, Any],
) -> list[str]:
    """Ordered contract modes worth testing for this role."""
    if role == "player":
        modes: list[str] = []
        if declared in PLAYER_MODES:
            modes.append(declared)
        text = _strip_accents(str(segment.get("narration", "")) + " "
                             + str(segment.get("visual", "")))
        if declared in PLAYER_MODES:
            refined = _story_starter(declared, segment)
        else:
            refined = _story_starter("player_poster_side", segment)
        if "potm" in text or "xuat sac nhat" in text or "hay nhat" in text:
            modes.append("potm_card")
        if refined == "BP-03" or "ho so" in text or "profile" in text:
            modes.append("player_poster_side")
        # A profile/stat mode can require stats the beat does not have; the
        # generic player card is the deterministic fallback for identity.
        modes.append("player_card")
        return list(dict.fromkeys(modes))
    return list(ROLE_CONTRACT_MODES.get(role, ()))


def _score_contract_candidate(
    *,
    mode: str,
    primary: bool,
    segment: dict[str, Any],
    data: dict[str, Any],
    assets: list[dict[str, Any]],
    purpose: dict[str, Any] | None,
    prev_modes: list[str],
    declared: str | None,
    beat_intent: dict[str, Any] | None,
) -> tuple[float, list[str]]:
    declared_bonus = (declared == mode
                      and mode in contract_grammar_modes())
    points, why = _score_candidate(
        mode, segment, data, assets, declared=declared_bonus,
        prev_modes=prev_modes, purpose=purpose, intent=beat_intent,
    )
    if primary:
        points = min(100.0, points + 8.0)
        why.append(f"primary contract grammar for this beat role: {mode}")
    else:
        why.append(f"secondary contract grammar for this beat role: {mode}")
    if declared == mode and declared_bonus:
        why.append(f"declared contract mode retained: {declared}")
    return points, why


def _choose_contract_candidate(
    candidates: list[dict[str, Any]],
    prev_modes: list[str],
) -> tuple[dict[str, Any], str | None]:
    """Choose a contract candidate with a hard anti-repetition guard.

    Diversity never beats a hard constraint: every candidate here is already
    C7-contract-ready for the card, has full required data, and (for portraits)
    has a purpose-cleared asset. The guard only chooses among those valid
    alternatives. If no alternative exists, the repeated valid mode is kept.
    """
    def rank(item: dict[str, Any]) -> tuple[float, int, str]:
        return (float(item["points"]), 1 if item["primary"] else 0,
                str(item["mode"]))

    best = max(candidates, key=rank)
    if len(candidates) <= 1:
        return best, None
    alternatives = [item for item in candidates
                    if item["mode"] != best["mode"]]
    if not alternatives:
        return best, None
    fresh = [item for item in alternatives
             if item["mode"] not in prev_modes[-3:]]
    # First priority: never repeat the immediately previous mode when any
    # valid alternative exists. Prefer an alternative that has not appeared in
    # the last three beats; if none, the least-recent valid alternative.
    if prev_modes and best["mode"] == prev_modes[-1]:
        chosen = max(fresh or alternatives, key=rank)
        return chosen, (
            f"repetition guard: avoided {best['mode']} from the previous "
            f"beat; chose {chosen['mode']} which is also contract-ready")
    # Second priority: avoid a third appearance in a short window when a
    # genuinely fresh contract mode exists. If every alternative is also
    # recent, keep the best (avoids an immediate repeat just to rotate).
    if best["mode"] in prev_modes[-3:] and fresh:
        chosen = max(fresh, key=rank)
        return chosen, (
            f"repetition guard: avoided {best['mode']} used in the previous "
            f"3 beats; chose fresh contract-ready {chosen['mode']}")
    return best, None


def _media_slot_roles(starter: str | None, mode: str) -> list[str]:
    """Declared media roles for the chosen card+mode (empty if none)."""
    if not starter:
        return []
    record = card_contract(starter)
    if record is None or mode not in record.get("execution", {}).get("modes", []):
        return []
    return [str(slot.get("role", ""))
            for slot in record.get("media_slots") or []]


def _source_semantics(segment: dict[str, Any]) -> str:
    """Classify source-beat meaning before choosing a card.

    C-09 is an attribution slip, not a universal source grammar. Fact-check
    and correction beats keep their own (legacy/non-ready) cards; match-data
    timestamps may use C-09 only with an explicit replacement warning.
    """
    text = _strip_accents(
        str(segment.get("narration", "")) + " "
        + str(segment.get("visual", ""))
    )
    if any(token in text for token in (
        "kiem chung", "fact check", "fact-check", "xac minh",
    )):
        return "fact_check"
    if any(token in text for token in (
        "sua loi", "dinh chinh", "correction", "cap nhat lai",
    )):
        return "correction"
    if "du lieu tran" in text or "nguon tran" in text:
        return "match_source"
    return "attribution"


def _extract_evidence_sources(segment: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Extract structured source identity from a segment.

    Reads the optional ``evidence_identity`` field on the segment. This is
    real source identity (URL/document_id, publisher, publication date,
    quote/location) — NOT credit display text from ``graphic_data.source``/
    ``graphic_data.date`` and not inferred from narration.

    Returns a list of source dicts in the shape expected by
    ``content_review_readiness_fields``, or None when no structured source
    identity is present (fail-closed: content review stays ``missing``).
    """
    identity = segment.get("evidence_identity")
    if not isinstance(identity, dict):
        return None
    raw_sources = identity.get("sources")
    if not isinstance(raw_sources, list) or len(raw_sources) == 0:
        return None
    sources: list[dict[str, Any]] = []
    for item in raw_sources:
        if not isinstance(item, dict):
            continue
        url_or_id = str(item.get("url", "") or item.get("document_id", "")).strip()
        if not url_or_id:
            continue
        sources.append({
            "url": item.get("url") or None,
            "document_id": item.get("document_id") or None,
            "publisher": str(item.get("publisher", "")).strip() or None,
            "published_at": str(item.get("published_at", "")).strip() or None,
            "accessed_at": str(item.get("accessed_at", "")).strip() or None,
            "quote_or_location": str(item.get("quote_or_location", "")).strip(),
            "supports_claim": bool(item.get("supports_claim", False)),
            "role": str(item.get("role", "supporting")).strip() or "supporting",
        })
    return sources or None


def _source_plan_fit(starter: str | None, data: dict[str, Any]) -> dict[str, Any]:
    record = card_contract(starter) if starter else None
    if record is None:
        return {
            "status": "NEEDS_REVIEW",
            "slots": [],
            "detail": f"no contract record for {starter}",
        }
    by_slot = {
        str(slot.get("slot_id")): slot for slot in record.get("data_slots") or []
    }
    results: list[dict[str, Any]] = []
    for slot_id in ("src-body", "credit"):
        slot = by_slot.get(slot_id)
        if slot is None:
            return {
                "status": "NEEDS_REVIEW",
                "slots": results,
                "detail": f"contract has no {slot_id} slot",
            }
        sources = [str(source) for source in slot.get("sources") or []]
        joiner = slot.get("join")
        pieces = [str(data.get(source, "") or "").strip() for source in sources]
        if joiner:
            if not all(pieces):
                return {
                    "status": "NEEDS_REVIEW",
                    "slots": results,
                    "detail": f"{slot_id} is missing source/date",
                }
            value = str(joiner).join(pieces)
        else:
            value = next((piece for piece in pieces if piece), "")
        if not value:
            return {
                "status": "NEEDS_REVIEW",
                "slots": results,
                "detail": f"{slot_id} has no value",
            }
        results.append(measure_text_slot(slot, value))
    statuses = {item["status"] for item in results}
    if "FAIL" in statuses:
        status = "FAIL"
    elif "NEEDS_REVIEW" in statuses:
        status = "NEEDS_REVIEW"
    else:
        status = "PASS"
    return {
        "status": status,
        "slots": results,
        "detail": "; ".join(
            f"{item['slot_id']} {item['status']} at {item['size_px']}px"
            for item in results
        ),
    }


def _select_contract_grammar(
    *,
    segment: dict[str, Any],
    index: int,
    declared: str | None,
    data: dict[str, Any],
    content_type: str,
    assets: list[dict[str, Any]],
    purpose: dict[str, Any] | None,
    beat_intent: dict[str, Any] | None,
    prev_modes: list[str],
) -> dict[str, Any] | None:
    """Find a C7-contract candidate for this beat, or explain why none exists.

    Returns ``{"role", "chosen", "considered_modes", "candidates"}`` for a
    short-form beat. ``chosen`` is None when the role has no contract card,
    required data is incomplete, or a portrait has no purpose-cleared asset.
    The caller must then use an explicit legacy/non-ready fallback.
    """
    if content_type != "short":
        return None
    role = _role_for_beat(
        index=index, declared=declared, beat_intent=beat_intent,
        data=data, segment=segment,
    )
    modes = _candidate_modes_for_role(role, declared, segment)
    source_semantics = _source_semantics(segment) if role == "source" else None
    if role == "source" and source_semantics in ("fact_check", "correction"):
        return {
            "role": role,
            "chosen": None,
            "considered_modes": modes,
            "candidates": [],
            "source_semantics": source_semantics,
            "blocked_reason": (
                f"source beat means {source_semantics}; C-09 is an "
                "attribution-only card and must not silently stand in for "
                "fact-check or correction grammar"
            ),
        }
    basic: list[dict[str, Any]] = []
    for mode in modes:
        coverage, derived, filled, derive_warnings = _coverage(
            mode, data, str(segment.get("narration", "")))
        if coverage < 1.0:
            continue
        if mode in PLAYER_MODES:
            player_name = str(filled.get("player_name", "") or "")
            if not player_name or not _match_portrait(player_name, assets, purpose):
                continue
        starter = _contract_starter_for(mode, segment, content_type, filled)
        if not starter or not _contract_record_ready(starter, mode):
            continue
        basic.append({
            "mode": mode,
            "starter": starter,
            "coverage": coverage,
            "derived": derived,
            "filled": filled,
            "derive_warnings": derive_warnings,
        })
    if not basic:
        return {
            "role": role,
            "chosen": None,
            "considered_modes": modes,
            "candidates": [],
            "source_semantics": source_semantics,
        }

    primary_mode = basic[0]["mode"]
    candidates: list[dict[str, Any]] = []
    for item in basic:
        points, why = _score_contract_candidate(
            mode=item["mode"], primary=item["mode"] == primary_mode,
            segment=segment, data=data, assets=assets, purpose=purpose,
            prev_modes=prev_modes, declared=declared, beat_intent=beat_intent,
        )
        candidates.append({
            **item,
            "points": points,
            "primary": item["mode"] == primary_mode,
            "reasons": why,
        })
    chosen, repetition_reason = _choose_contract_candidate(candidates, prev_modes)
    return {
        "role": role,
        "chosen": chosen,
        "considered_modes": modes,
        "candidates": candidates,
        "source_semantics": source_semantics,
        "repetition_reason": repetition_reason,
    }


def normalize_upload_purpose(
    run: Mapping[str, Any] | None,
    draft: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return ONE normalized upload intent for ``run``/``draft``, or None.

    Accepts a flat purpose ``{platform, territory, commercial, monetization,
    ...}`` (normalized via ``rights_scope.normalize_purpose``; run-level wins
    over draft-level) or a ``destinations`` / ``distribution`` list of
    ``{platform, market|territory, commercial, monetization}`` items (the
    first destination with a real platform, i.e. not ``local_file``, is used).
    Returns None when there is no usable platform+territory intent, so the
    selector and the renderer fail closed instead of guessing an upload scope.
    Selector and renderer share this normalizer so both see identical
    platform/territory/commercial/monetization.
    """
    containers = tuple(c for c in (run, draft) if isinstance(c, Mapping))

    # 1. Flat purpose: run-level first, then draft-level.
    purpose: Mapping[str, Any] | None = None
    for container in containers:
        candidate = container.get("purpose")
        if isinstance(candidate, Mapping):
            purpose = candidate
            break

    # 2. destinations / distribution: {platform, market|territory,
    #    commercial, monetization}.
    if purpose is None:
        picked: dict[str, Any] | None = None
        for container in containers:
            destinations: list[dict[str, Any]] | None = None
            for key in ("destinations", "distribution"):
                value = container.get(key)
                if isinstance(value, dict):
                    value = value.get("destinations")
                if isinstance(value, list):
                    destinations = [item for item in value if isinstance(item, dict)]
                    break
            if not destinations:
                continue
            for item in destinations:
                platform = str(item.get("platform", "")).strip()
                if platform and platform != "local_file":
                    picked = item
                    break
            if picked is None:
                picked = destinations[0]
            break
        if picked is None:
            return None
        run_container = run if isinstance(run, Mapping) else {}
        purpose = {
            "platform": picked.get("platform"),
            "territory": picked.get("market") or picked.get("territory"),
            "commercial": picked.get(
                "commercial", run_container.get("commercial", False)),
            "monetization": picked.get(
                "monetization", run_container.get("monetization", False)),
        }

    normalized = normalize_purpose(purpose)
    if not normalized.get("platform") or not normalized.get("territory"):
        return None
    return normalized


def select_cards(segments: list[dict[str, Any]],
                 assets: list[dict[str, Any]] | None = None,
                 content_type: str = "short",
                 purpose: dict[str, Any] | None = None,
                 exact_terms: list[str] | None = None) -> dict[str, Any]:
    """Map every segment to a card decision, with contract status made explicit.

    Returns {"decisions": [...], "plan": {...}}. Each decision carries
    segment_id, visual_mode, starter_id, card_execution, graphic_data,
    media_asset_id, production_ready, grammar (role/source/candidates) and
    warnings. Never raises on bad input; problems become warnings.

    ``beat_intent`` is semantic input from the LLM (already normalized). The
    planner uses it to choose a story role and contract grammar. It does not
    choose pixels, coordinates, typography or motion. A legacy declared mode
    is only a hint; reviewed data can replace it with a C7 contract mode.

    Variety rule: when several contract candidates fit, a hard guard avoids a
    mode used in the previous three beats. When only one valid choice exists
    (or no alternative carries complete data), the valid mode is retained and
    the repetition is reported. Legacy modes are never used just to make the
    mode count look varied.
    """
    assets = list(assets or [])
    if content_type not in ("short", "long"):
        content_type = "short"
    # A missing or invalid upload purpose means no scope-eligibility claim is
    # made for any asset: the selector fails closed (verified/active is never
    # sufficient usage clearance by itself).
    if not isinstance(purpose, Mapping):
        purpose = None
    decisions: list[dict[str, Any]] = []
    library_skipped_no_purpose = False
    prev_modes: list[str] = []
    plan_warnings: list[str] = []
    for index, raw in enumerate(segments or []):
        segment = raw if isinstance(raw, dict) else {}
        segment_id = str(segment.get("id", f"beat-{index + 1}"))
        narration = str(segment.get("narration", ""))
        data = segment.get("graphic_data")
        data = dict(data) if isinstance(data, dict) else {}
        beat_intent = segment.get("beat_intent")
        if not isinstance(beat_intent, dict):
            beat_intent = None
        declared_raw = segment.get("visual_mode")
        declared: str | None = None
        declared_bonus = False
        warnings: list[str] = []
        if declared_raw is not None:
            declared = str(declared_raw)
            if declared not in SUPPORTED_MODES:
                warnings.append(
                    f"unknown visual_mode '{declared}'; fell back to tactical_explainer")
                declared = "tactical_explainer"
            declared_bonus = True

        # A supplied media binding is only a proposal. It must exist in the
        # fetched asset set and clear the upload purpose before it can be
        # considered; the card's declared media slots are checked later.
        bound = segment.get("media_asset_id")
        if bound:
            record = next((a for a in assets if str(a.get("asset_id")) == str(bound)), None)
            if record is None:
                warnings.append(f"media_asset_id '{bound}' not in fetched assets; binding dropped")
                bound = None
            elif not _eligible_asset(record, purpose):
                if purpose is None:
                    warnings.append(
                        f"asset '{bound}' skipped: no purpose/scope — library asset not attached without upload purpose")
                    library_skipped_no_purpose = True
                else:
                    warnings.append(f"asset '{bound}' is not usable for this purpose; binding dropped (render would fail)")
                bound = None

        grammar = _select_contract_grammar(
            segment=segment, index=index, declared=declared, data=data,
            content_type=content_type, assets=assets, purpose=purpose,
            beat_intent=beat_intent, prev_modes=prev_modes,
        )
        grammar_role = (grammar["role"] if grammar else
                        _role_for_beat(index=index, declared=declared,
                                       beat_intent=beat_intent, data=data,
                                       segment=segment))
        source_semantics = grammar.get("source_semantics") if grammar else None
        if grammar and grammar.get("blocked_reason"):
            warnings.append(str(grammar["blocked_reason"]))
        contract_candidates = list(grammar.get("candidates") or []) if grammar else []
        considered_modes = list(grammar.get("considered_modes") or []) if grammar else []
        chosen = grammar.get("chosen") if grammar else None
        repetition_reason: str | None = None
        grammar_source = "fallback"
        starter: str | None = None
        best_why: list[str] = []
        best_points = 0.0
        coverage = 0.0
        derived: list[str] = []
        filled = dict(data)
        derive_warnings: list[str] = []

        if chosen is not None:
            best_mode = str(chosen["mode"])
            starter = str(chosen["starter"])
            coverage = float(chosen["coverage"])
            derived = list(chosen["derived"])
            filled = dict(chosen["filled"])
            derive_warnings = list(chosen["derive_warnings"])
            best_points = float(chosen["points"])
            best_why = list(chosen["reasons"])
            grammar_source = "contract"
            repetition_reason = grammar.get("repetition_reason") if grammar else None
            warnings.extend(derive_warnings)
            if repetition_reason:
                best_why.append(repetition_reason)
            elif prev_modes and best_mode in prev_modes[-3:]:
                # The guard could not rotate without either repeating the
                # immediate previous beat or using a non-contract mode. Keep
                # the valid mode and say why in the decision itself.
                if len(contract_candidates) <= 1:
                    best_why.append(
                        f"only one valid contract grammar for this beat; "
                        f"{best_mode} repeats by constraint, not by choice")
                else:
                    best_why.append(
                        f"{best_mode} repeats within 3 beats; every valid "
                        "contract alternative is also recent")
            if declared and declared != best_mode:
                warnings.append(
                    f"declared visual_mode '{declared}' overridden: contract "
                    f"grammar '{best_mode}' fits story role '{grammar_role}' "
                    "and the reviewed data/intent")
            historical = _starter_for(best_mode, segment, content_type, filled)
            if (historical and historical != starter
                    and not _contract_record_ready(historical, best_mode)):
                best_why.append(
                    f"contract starter {starter} replaces non-contract "
                    f"historical starter {historical}")
                if best_mode == "source_card":
                    warnings.append(
                        f"source_card semantics '{source_semantics or 'attribution'}' "
                        f"resolved to C-09; legacy source starter {historical} "
                        "was not treated as the same grammar and remains "
                        "non-ready")
            if best_mode == "source_card" and source_semantics == "match_source":
                warnings.append(
                    "match-source timestamp is using the C-09 attribution "
                    "card; it does not claim MR-12's legacy source grammar")
        else:
            # Explicit legacy/non-ready path. This path is allowed to suggest
            # a card for review, but it never claims production readiness.
            candidates: list[str] = []
            if declared is not None:
                candidates.append(declared)
            for mode in _signal_modes(narration, str(segment.get("visual", ""))):
                if mode not in candidates and mode in SUPPORTED_MODES:
                    candidates.append(mode)
                if len(candidates) >= 3:
                    break
            if not candidates:
                warnings.append(
                    "no visual_mode declared; deterministic pitch-plate fallback")
                candidates = ["tactical_explainer"]

            lock_player = (declared in PORTRAIT_MODES
                           and _present(data, "player_name"))
            scored: list[tuple[float, bool, str, list[str]]] = []
            for mode in candidates:
                # The planner never picks a media-bearing mode without a
                # purpose-cleared asset. A declared player mode is retained as
                # an author hint, but is marked non-ready below if media is
                # missing.
                if mode == "media_b_roll" and mode != declared:
                    continue
                if mode in PLAYER_MODES and mode != declared:
                    player_name = str(data.get("player_name", "") or "")
                    if not player_name or not _match_portrait(player_name, assets, purpose):
                        continue
                points, why = _score_candidate(
                    mode, segment, data, assets,
                    declared=(declared_bonus and mode == declared),
                    prev_modes=prev_modes, purpose=purpose, intent=beat_intent,
                )
                if lock_player and mode != declared:
                    points -= 100.0
                    why = why + ["player-mode lock: identity over fit"]
                scored.append((points, mode == declared, mode, why))
            if not scored:
                warnings.append(
                    "no media-eligible mode candidate; deterministic pitch-plate fallback")
                points, why = _score_candidate(
                    "tactical_explainer", segment, data, assets,
                    declared=False, prev_modes=prev_modes, purpose=purpose,
                    intent=beat_intent,
                )
                scored = [(points, False, "tactical_explainer", why)]
            scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
            best_points, _, best_mode, best_why = scored[0]

            if best_mode == "media_b_roll":
                warnings.append(
                    "media_b_roll has no C7 media slot; production path "
                    "disabled and deterministic pitch-plate fallback used")
                best_mode = "tactical_explainer"
                best_why = best_why + ["media_b_roll is legacy-only in the contract"]
                bound = None

            coverage, derived, filled, derive_warnings = _coverage(
                best_mode, data, narration)
            warnings.extend(derive_warnings)
            starter = _starter_for(best_mode, segment, content_type, filled)
            if best_mode == "tactical_explainer" and not starter:
                best_why.append(
                    "deterministic pitch-plate fallback (no authored contract card)")
            if grammar is not None and considered_modes:
                warnings.append(
                    f"no eligible contract grammar for role '{grammar_role}' "
                    f"from considered modes {', '.join(considered_modes)}; "
                    f"selected '{best_mode}' is fallback/non-ready")
            elif content_type == "short":
                warnings.append(
                    f"no contract-ready card grammar for role '{grammar_role}' "
                    f"in the contract; selected '{best_mode}' is fallback/non-ready")

        # Beat-0 rule is a hard invariant even if a contract candidate was
        # somehow rejected.
        if index == 0 and best_mode != "hook_card":
            best_mode = "hook_card"
            grammar_source = "fallback"
            starter = _starter_for(best_mode, segment, content_type, filled)
            coverage, derived, filled, derive_warnings = _coverage(
                best_mode, data, narration)
            warnings.extend(derive_warnings)
            best_why = ["beat-0 opens on the hook"] + best_why
        elif index == 0 and not any("beat-0" in r for r in best_why):
            best_why = ["beat-0 opens on the hook"] + best_why

        if grammar_source == "fallback":
            for key in REQUIRED_SLOTS.get(best_mode, []):
                if not _present(filled, key):
                    warnings.append(f"{best_mode} missing '{key}'")

        # Renderer hook retained for the deferred long-form path: a long
        # tactical beat renders its authored plate, never a short card.
        if (content_type == "long" and best_mode == "tactical_explainer"
                and starter and starter.startswith("TA-")):
            filled["tactical_card"] = starter
            best_why.append(f"authored long-form plate {starter}")

        card_execution, contract_reason = _card_execution(
            starter, best_mode, content_type)
        if grammar_source == "contract" and card_execution != CONTRACT_READY:
            warnings.append(
                f"contract candidate '{best_mode}' lost its contract status "
                f"({card_execution}); treating it as fallback")
            grammar_source = "fallback"
        elif grammar_source == "fallback":
            if card_execution == "partial":
                warnings.append(
                    f"card {starter}/{best_mode} is card-level partial in C7; "
                    "not production-ready even though one mode is executable")
            elif card_execution in ("legacy_non_ready", "legacy_long", "no_contract", "none"):
                if starter is None and best_mode == "tactical_explainer":
                    warnings.append(
                        "no authored contract card for 'tactical_explainer'; "
                        "deterministic pitch-plate fallback is non-ready")
                else:
                    warnings.append(
                        f"card {starter}/{best_mode} is {card_execution or 'non-ready'} "
                        "in C7 (legacy/non-ready); the builder will freeze a "
                        "primitive/fallback path, not a production-ready "
                        "authored design")
                    if contract_reason:
                        warnings.append(f"card contract: {contract_reason}")
            elif card_execution == CONTRACT_READY:
                warnings.append(
                    f"card {starter}/{best_mode} is contract-executable, but "
                    "the grammar selection fell back; not production_ready")

        # Media binds only to a declared C7 media slot. Today those are the
        # player-portrait cards. Everything else drops the proposed binding.
        media_slot_roles = _media_slot_roles(starter, best_mode)
        media_status = "not_applicable"
        if media_slot_roles and best_mode in PLAYER_MODES:
            player_name = str(filled.get("player_name", "") or "")
            match = (_match_portrait(player_name, assets, purpose)
                     if player_name else None)
            if match:
                if bound and str(bound) != match:
                    warnings.append(
                        f"bound asset '{bound}' does not match named player "
                        f"'{player_name}'; replaced with purpose-cleared '{match}'")
                elif not bound:
                    warnings.append(
                        f"verified portrait '{match}' auto-attached for "
                        f"declared portrait slot (owner standing order 16/10)")
                bound = match
                media_status = "bound"
            else:
                if bound:
                    warnings.append(
                        f"bound asset '{bound}' dropped: no purpose-cleared "
                        "portrait of the named player")
                bound = None
                media_status = MEDIA_FALLBACK
                if purpose is None and player_name:
                    warnings.append(
                        f"portrait for '{player_name}' skipped: no purpose/scope "
                        "— library asset not attached")
                    library_skipped_no_purpose = True
                warnings.append(
                    "portrait media fallback: no purpose-cleared portrait; "
                    "authored pack artwork will be used")
        elif media_slot_roles:
            if bound:
                warnings.append(
                    f"card {starter}/{best_mode} declares media slot(s) "
                    f"{', '.join(media_slot_roles)} but no eligible binder; "
                    f"media_asset_id '{bound}' dropped")
            bound = None
            media_status = MEDIA_FALLBACK
        else:
            if bound:
                card_label = f"{starter}/{best_mode}" if starter else best_mode
                warnings.append(
                    f"card {card_label} declares no media slot; "
                    f"media_asset_id '{bound}' dropped (asset cannot be painted)")
            bound = None

        source_readiness: dict[str, Any] | None = None
        source_review_pending = False
        if best_mode == "source_card" and card_execution == CONTRACT_READY:
            source_fit = _source_plan_fit(starter, filled)
            # C-09 is contract-executable only in pack 12.1.0. The static
            # visual review record is scoped to card/mode/pack version and
            # approves only the visual inspection of the static PNG. It does
            # not verify the claim, source, or date, and no separate
            # content/source verification gate exists yet. Production
            # readiness therefore cannot be claimed from visual approval +
            # text fit alone.
            source_template_version = str(
                (card_contract("C-09") or {}).get("template_version")
                or "12.1.0"
            )
            source_review_pending = not source_card_visual_approved(
                "C-09", "source_card", source_template_version
            )
            if source_fit["status"] == "FAIL":
                warnings.append(
                    f"C-09 text fit FAIL at plan time ({source_fit['detail']}); "
                    "source beat is not production-ready")
            elif source_fit["status"] == "NEEDS_REVIEW":
                warnings.append(
                    f"C-09 text fit NEEDS_REVIEW at plan time "
                    f"({source_fit['detail']}); shorten or re-review the copy")
            if source_review_pending:
                warnings.append(
                    "C-09 attribution contract is graph-level executable, but "
                    "rendered frame inspection and owner visual approval are "
                    "pending; source beat is not production-ready")
            # The owner visual review record covers visual inspection only. A
            # separate content/source/date verification gate decides whether the
            # factual claim itself may be published.
            #
            # Source identity comes from the segment's optional
            # ``evidence_identity`` field (structured source identity: URL /
            # document_id, publisher, publication date, quote/location). It is
            # NOT derived from ``graphic_data.source``/``graphic_data.date``
            # (credit display text) or from narration. When the beat/run
            # contract carries no stable source identity, ``sources`` is None
            # and the gate stays at ``missing`` — never approved.
            review_fields = review_readiness_fields(
                "C-09", "source_card", source_template_version
            )
            content_sources = _extract_evidence_sources(segment)
            # Credit display text from graphic_data.source / graphic_data.date
            # is verified against reviewed sources (publisher / publication
            # date) but is never used as source identity itself.
            credit = {
                "source": str(filled.get("source", "") or "").strip() or None,
                "date": str(filled.get("date", "") or "").strip() or None,
            }
            credit = credit if (credit["source"] or credit["date"]) else None
            content_review = content_review_readiness_fields(
                claim=str(filled.get("claim", "") or ""),
                beat_id=segment_id,
                semantics=str(source_semantics or "attribution"),
                sources=content_sources,
                credit=credit,
            )
            # Production readiness for a source beat requires every independent
            # gate: contract execution, text fit, visual approval, AND content
            # review. A missing/rejected/needs-review content review blocks it.
            content_approved = content_review["content_review"] == "approved"
            content_status = str(content_review["content_review"])
            if content_status == "missing":
                warnings.append(
                    "C-09 source beat has no claim/source/date verification "
                    "gate; visual approval and text fit do not imply "
                    "production readiness")
            elif content_status == "needs_review":
                warnings.append(
                    f"C-09 content review needs owner review: "
                    f"{content_review['content_review_detail']}")
            elif content_status == "rejected":
                warnings.append(
                    f"C-09 content review was rejected: "
                    f"{content_review['content_review_detail']}")
            source_readiness = {
                "text_fit": source_fit["status"],
                "text_fit_detail": source_fit["detail"],
                "text_slots": source_fit["slots"],
                "rendered_inspection": review_fields["rendered_inspection"],
                "owner_approved": review_fields["owner_approved"],
                "content_review": content_review["content_review"],
                "content_review_detail": content_review["content_review_detail"],
                "content_review_invalidated": bool(
                    content_review.get("content_review_invalidated")
                ),
                "content_review_record_id": content_review.get(
                    "content_review_record_id", ""
                ),
                "production_ready": (
                    source_fit["status"] == "PASS"
                    and review_fields["rendered_inspection"] == "approved"
                    and review_fields["owner_approved"]
                    and content_approved
                ),
            }
        production_ready = (
            grammar_source == "contract"
            and card_execution == CONTRACT_READY
            and media_status != MEDIA_FALLBACK
            and coverage >= 1.0
            and (best_mode != "source_card" or (
                source_readiness is not None
                and source_readiness["production_ready"]
            ))
        )
        reasons = [f"fit {best_points:.0f}/100"] + best_why
        if grammar_source != "contract":
            reasons.append(
                f"no production contract grammar selected; fallback {best_mode}")
        warnings = list(dict.fromkeys(warnings))
        decisions.append({
            "segment_id": segment_id,
            "index": index,
            "visual_mode": best_mode,
            "starter_id": starter,
            "card_execution": card_execution,
            "production_ready": production_ready,
            "media_status": media_status,
            "grammar": {
                "role": grammar_role,
                "source": grammar_source,
                "source_semantics": source_semantics,
                "declared_mode": declared,
                "considered_modes": considered_modes,
                "candidates": [
                    {
                        "mode": item["mode"],
                        "starter_id": item["starter"],
                        "score": round(float(item["points"]), 1),
                        "primary": bool(item["primary"]),
                    }
                    for item in contract_candidates
                ],
                "repetition": repetition_reason,
            },
            "graphic_data": filled,
            "media_asset_id": bound,
            "suggested_asset_id": None,
            "readiness": source_readiness,
            "score": round(best_points, 1),
            "reasons": reasons,
            "warnings": warnings,
        })
        prev_modes.append(best_mode)

    missing_source = sum(
        1 for d in decisions
        if any("missing 'source'" in w or "missing 'date'" in w for w in d["warnings"]))
    if missing_source:
        plan_warnings.append(f"{missing_source} beat(s) make data claims without source+date")
    if library_skipped_no_purpose:
        plan_warnings.append(
            "purpose missing — library assets not attached (fail-closed): no media_asset_id cleared without an upload purpose")
    contract_starters = sorted({
        d["starter_id"] for d in decisions
        if d["starter_id"] and d["card_execution"] == CONTRACT_READY
    })
    partial_starters = sorted({
        d["starter_id"] for d in decisions
        if d["starter_id"] and d["card_execution"] == "partial"
    })
    legacy_starters = sorted({
        d["starter_id"] for d in decisions
        if d["starter_id"] and d["card_execution"] in (
            "legacy_non_ready", "legacy_long", "no_contract"
        )
    })
    production_starters = sorted({
        d["starter_id"] for d in decisions
        if d["starter_id"] and d["production_ready"]
    })
    contract_beats = sum(1 for d in decisions if d["card_execution"] == CONTRACT_READY)
    partial_beats = sum(1 for d in decisions if d["card_execution"] == "partial")
    legacy_beats = sum(
        1 for d in decisions
        if d["card_execution"] in ("legacy_non_ready", "legacy_long", "no_contract", "none")
    )
    non_ready = [d for d in decisions if not d["production_ready"]]
    non_ready_roles = sorted({str(d["grammar"]["role"]) for d in non_ready})
    media_fallbacks = [d for d in decisions if d["media_status"] == MEDIA_FALLBACK]
    source_contract_beats = [
        d["segment_id"] for d in decisions
        if d["visual_mode"] == "source_card"
        and d["card_execution"] == CONTRACT_READY
    ]
    source_text_fit = {
        d["segment_id"]: (d.get("readiness") or {}).get("text_fit")
        for d in decisions
        if d["visual_mode"] == "source_card"
        and d["card_execution"] == CONTRACT_READY
    }
    rendered_review_pending = [
        d["segment_id"] for d in decisions
        if (d.get("readiness") or {}).get("rendered_inspection") == "pending"
        and (d.get("readiness") or {}).get("owner_approved") is False
    ]
    if source_text_fit:
        failed_fit = [
            beat for beat, status in source_text_fit.items() if status == "FAIL"
        ]
        review_fit = [
            beat for beat, status in source_text_fit.items()
            if status == "NEEDS_REVIEW"
        ]
        if failed_fit:
            plan_warnings.append(
                "C-09 text fit FAIL at plan time for "
                f"{', '.join(failed_fit)}; source beats are not production-ready")
        if review_fit:
            plan_warnings.append(
                "C-09 text fit NEEDS_REVIEW at plan time for "
                f"{', '.join(review_fit)}; shorten or re-review the copy")
    if rendered_review_pending:
        plan_warnings.append(
            "C-09 rendered inspection/owner visual approval is pending for "
            f"{', '.join(rendered_review_pending)}; graph-level contract "
            "execution is not an aesthetic/visual PASS")
    if partial_beats:
        plan_warnings.append(
            f"{partial_beats} beat(s) use the executable mode of a partial card; "
            "the card is still not production-ready under C7")
    if legacy_beats:
        plan_warnings.append(
            f"{legacy_beats} beat(s) use a legacy/non-ready card path; QA "
            "must not PASS them")
    if non_ready:
        plan_warnings.append(
            f"{len(non_ready)} beat(s) are not production-ready (roles: "
            f"{', '.join(non_ready_roles) or 'unknown'}); R3 S3.1 cannot be "
            "cleared for them")
    if media_fallbacks:
        plan_warnings.append(
            f"{len(media_fallbacks)} beat(s) use a declared portrait slot with "
            "no purpose-cleared matching asset; authored fallback is not a media PASS")
    mode_counts: dict[str, int] = {}
    mode_runs: dict[str, int] = {}
    previous_mode: str | None = None
    current_run = 0
    for d in decisions:
        mode = d["visual_mode"]
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        if mode == previous_mode:
            current_run += 1
        else:
            previous_mode = mode
            current_run = 1
        mode_runs[mode] = max(mode_runs.get(mode, 0), current_run)
    # Variety is about the sequence, not total frequency: alternating two
    # contract grammars across six beats is varied. A run of three or more in
    # a row is the blocker signal.
    over_repeated = {mode: run for mode, run in mode_runs.items() if run > 2}
    grammar_variety_ok = not over_repeated
    if over_repeated:
        plan_warnings.append(
            "visual grammar repeated more than twice in a row: "
            f"{over_repeated}; no legacy mode was substituted merely to "
            "manufacture variety, so R3 S3.1 remains blocked where no "
            "contract-ready alternative exists")
    plan = {
        "content_type": content_type,
        "purpose": purpose,
        "exact_terms": exact_terms,
        "beats": len(decisions),
        "mode_counts": mode_counts,
        "mode_runs": mode_runs,
        "max_mode_repeat": max(mode_runs.values(), default=0),
        "grammar_variety_ok": grammar_variety_ok,
        "over_repeated_modes": over_repeated,
        "starters": sorted({d["starter_id"] for d in decisions if d["starter_id"]}),
        "contract_starters": contract_starters,
        "partial_starters": partial_starters,
        "legacy_starters": legacy_starters,
        "production_starters": production_starters,
        "contract_beats": contract_beats,
        "partial_beats": partial_beats,
        "legacy_beats": legacy_beats,
        "source_contract_beats": source_contract_beats,
        "source_text_fit": source_text_fit,
        "rendered_review_pending": rendered_review_pending,
        "production_ready": bool(decisions) and not non_ready,
        "non_ready_beats": [d["segment_id"] for d in non_ready],
        "non_ready_roles": non_ready_roles,
        "grammar": {
            "contract_beats": contract_beats,
            "partial_beats": partial_beats,
            "legacy_beats": legacy_beats,
            "production_ready": bool(decisions) and not non_ready,
            "variety_ok": grammar_variety_ok,
            "mode_runs": mode_runs,
            "over_repeated_modes": over_repeated,
        },
        "warnings": plan_warnings,
    }
    return {"decisions": decisions, "plan": plan}


def _fetch_verified_images(root: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Verified/active library images for portrait matching (advisory only).

    Returns (assets, note); a missing/unreadable library yields ([], note)
    instead of failing, so card selection still works without portraits.
    """
    import sqlite3

    try:
        from apps.asset_library.registry import connect

        conn = connect(Path(root) / "runtime/engine.db")
        try:
            rows = conn.execute(
                "SELECT asset_id, asset_type, rights_state, lifecycle_state, "
                "original_name, subject_type, subject_id, metadata_json, purpose_code FROM assets "
                "WHERE asset_type = 'image' AND rights_state = 'verified' "
                "AND lifecycle_state = 'active'"
            ).fetchall()
        finally:
            conn.close()
    except (OSError, sqlite3.Error) as error:
        return [], f"asset library unavailable ({error}); portrait matching skipped"
    assets: list[dict[str, Any]] = []
    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"] or "{}")
        except (json.JSONDecodeError, TypeError, KeyError):
            metadata = {}
        subjects = []
        if row["subject_id"]:
            subjects.append(str(row["subject_id"]))
        if isinstance(metadata, dict) and metadata.get("subjects") and isinstance(metadata["subjects"], list):
            subjects += [str(s) for s in metadata["subjects"]]
        assets.append({
            "asset_id": str(row["asset_id"]),
            "asset_type": str(row["asset_type"]),
            "rights_state": str(row["rights_state"]),
            "lifecycle_state": str(row["lifecycle_state"]),
            "original_name": str(row["original_name"] or ""),
            "subjects": subjects,
            "metadata": metadata if isinstance(metadata, dict) else {},
            "purpose_code": row["purpose_code"] if "purpose_code" in row.keys() else None,
        })
    return assets, None


def apply_card_plan(root: Path, run: dict[str, Any]) -> dict[str, Any]:
    """Feed a production run's segments from the card selector (render prep).

    Copies each decision's visual_mode/graphic_data into its segment and keeps
    only media bindings the planner proved belong to a declared C7 media slot.
    It never converts a beat into media_b_roll and never auto-picks b-roll:
    C7 12.0.0 has no general b-roll slot. Verified portraits may auto-attach
    only to the declared player-portrait slot when the named player and upload
    purpose match. Stores the full plan at run["card_plan"] for review.
    """
    draft = run.get("draft") if isinstance(run.get("draft"), dict) else {}
    segments = draft.get("segments")
    if not isinstance(segments, list):
        plan = {"decisions": [], "plan": {"beats": 0, "warnings": ["run has no script segments"]}}
        run["card_plan"] = plan
        return plan
    content_type = draft.get("content_type", "short")
    assets, note = _fetch_verified_images(root)
    # Upload purpose: one normalized intent for the whole run/draft, via the
    # same normalizer the renderer uses. A missing purpose means
    # select_cards makes no scope-eligibility claim for any asset
    # (fail-closed).
    purpose = normalize_upload_purpose(run, draft)
    plan = select_cards([s for s in segments if isinstance(s, dict)],
                        assets, content_type, purpose=purpose)
    by_id = {d["segment_id"]: d for d in plan["decisions"]}
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        decision = by_id.get(str(segment.get("id")))
        if decision is None:
            continue
        segment["visual_mode"] = decision["visual_mode"]
        segment["graphic_data"] = decision["graphic_data"]
        if decision["media_asset_id"]:
            segment["media_asset_id"] = decision["media_asset_id"]
        else:
            segment.pop("media_asset_id", None)
    if note:
        plan["plan"]["warnings"].insert(0, note)
    run["card_plan"] = plan
    return plan
