"""Deterministic Scene Graph builder (planner side).

Canonical home of ALL layout decisions. Logic moved here verbatim from:
- apps/studio_templates/starter_scenes.py: _initials/_source_date/
  _parse_score/_fill_score (winner-first)/_substitutions/_prepare/_compose
  (hide-empty-slots, row-tied decor hiding, shrink-to-fit, winner dots).
- apps/studio_templates/render_starters.py + apps/video_renderer.py:
  *accent* split/two-tone definition (builder pre-splits every text layer
  into segments; the renderer primitive only draws the given segments).
- apps/pack_import/importer.py render_pack_plate: normalized box -> absolute
  pixels, shrink-until-fits, *accent* two-tone (see layout_pack_boxes).
- assets/crests policy: crest slots fall back to monogram initials until a
  licensed file lands (resolve_crest -> None today); builder records the
  fallback explicitly so the executor never guesses.

The builder is pure + deterministic: same
(card_plan decision, graphic_data, evidence, timing) -> same graph JSON.
It NEVER selects a composition: starter_id/visual_mode arrive frozen from
the planner (apps.card_selector). A substitutable miss yields a primitive
graph with a fallback reason; the executor renders it verbatim and must
not remap it either.

No network, no clock, no randomness. Starter JSON loads are local reads.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from apps.scene_graph import SCENE_GRAPH_VERSION
from apps.scene_graph.intent import normalize_beat_intent
from apps.scene_graph.schema import (
    LONG_CANVAS,
    SHORT_CANVAS,
    SUPPORTED_MODES,
    graph_hash as _graph_hash,
)

ROOT = Path(__file__).resolve().parent.parent.parent
TPL = ROOT / "apps" / "studio_templates"

# Released pack the graphs freeze against (read-only; never mutated).
# Pinned by test to the resolved template manifest version: a pack bump
# changes every graph_hash by design (same input + same version = same hash).
TEMPLATE_VERSION_FALLBACK = "12.0.0"

# Modes whose reviewed graphic_data maps onto starter slots. Anything else
# (charts, source cards, b-roll, tactical plates, ...) is a primitive graph;
# the executor renders the frozen mode verbatim without slot mapping.
STARTER_MODES = frozenset({
    "hook_card", "score_card", "goal_card",
    "duel_columns", "stat_leader", "player_card",
})

# Modes where a bound library image is the player's portrait (it lives in
# roles.player_focus.portrait, never duplicated into hero_image). Mirrors
# apps.card_selector.PORTRAIT_MODES literally (no import: selector is
# planner-side, builder must not depend on it).
PORTRAIT_MODES = frozenset({
    "player_card", "player_poster", "player_poster_side", "player_poster_top",
    "potm_card", "welcome_card", "score_card", "quote_card",
})

# chalk_line_wipe candidates (template timeline: tactical boards or between
# two evidence beats, max 2 per video). Beat-0 always opens clean_cut.
CHALK_CANDIDATE_MODES = frozenset({"tactical_explainer", "chart_timeline"})
MAX_CHALK_PER_CLIP = 2

_ACCENT_RE = re.compile(r"\*([^*]+)\*")


# ---------------------------------------------------------------------------
# Moved from starter_scenes.py (verbatim semantics)
# ---------------------------------------------------------------------------

def _initials(name: str, limit: int = 3) -> str:
    parts = [p for p in re.split(r"\s+", str(name).strip()) if p]
    if len(parts) == 1:
        # Already abbreviated (PSG, MC): keep whole so "PSG" never becomes "P".
        return parts[0].upper()
    return "".join(p[0] for p in parts[:limit]).upper()


def _crest_monogram(name: str) -> str:
    """Crest fallback: monogram initials until a licensed file lands.

    Policy (assets/crests/README.md + apps/sportskit/crests.py): only
    owner-supplied files with rights_reviewed=true may render as images.
    Today resolve_crest() returns None for every clip club, so every
    crest-* slot carries initials. The graph records crest="monogram-fallback"
    in provenance; the executor must not attempt its own crest lookup.
    """
    return _initials(name)


def _source_date(evidence: list[Any]) -> tuple[str, str]:
    if evidence:
        first = str(evidence[0]).strip()
        m = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})\s*$", first)
        if m:
            return first[:m.start()].strip(" •"), m.group(1)
        return first, ""
    return "", ""


def _parse_score(score: str) -> tuple[str, str]:
    m = re.match(r"\s*(\d+)\s*[-–:]\s*(\d+)\s*$", str(score))
    return (m.group(1), m.group(2)) if m else ("", "")


def _fill_score(slots: dict[str, str], data: dict[str, Any]) -> None:
    """Winner-first ordering: the winning side always fills the top
    (winner) slots, whoever is home. Names/numbers/crests travel together;
    home/away factual order is NOT preserved because these starters have
    no neutral-side geometry (generic rule for every score/goal card)."""
    home = str(data.get("home", "")).strip()
    away = str(data.get("away", "")).strip()
    hg, ag = _parse_score(str(data.get("score", "")))
    home_wins = hg.isdigit() and ag.isdigit() and int(hg) > int(ag)
    away_wins = hg.isdigit() and ag.isdigit() and int(ag) > int(hg)
    if away_wins:
        top_name, top_goals, top_init = away, ag, _crest_monogram(away)
        bot_name, bot_goals, bot_init = home, hg, _crest_monogram(home)
    else:
        top_name, top_goals, top_init = home, hg, _crest_monogram(home)
        bot_name, bot_goals, bot_init = away, ag, _crest_monogram(away)
    slots["home"] = top_name
    slots["away"] = bot_name
    slots["score"] = top_goals
    slots["score-away"] = bot_goals
    slots["crest-winner"] = top_init
    slots["crest-loser"] = bot_init
    if data.get("context"):
        slots["context"] = str(data["context"]).strip()
    slots["__winner"] = "home" if home_wins else ("away" if away_wins else "")


def _substitutions(mode: str, data: dict[str, Any], evidence: list[Any]) -> dict[str, str] | None:
    """Map reviewed graphic_data onto starter slot names. None = no fit."""
    src, date = _source_date(evidence if isinstance(evidence, list) else [])
    src = str(data.get("source", src) or src).strip()
    date = str(data.get("date", date) or date).strip()
    credit = f"{src} • {date}".strip(" •") if (src or date) else ""
    slots: dict[str, str] = {}
    if mode == "hook_card":
        if not str(data.get("hook_text", "")).strip():
            return None
        # Keep *accent* markers: the executor draws two-tone (magenta).
        slots["claim"] = str(data["hook_text"]).strip()
    elif mode in ("score_card", "goal_card"):
        if not (data.get("home") and data.get("away") and data.get("score")):
            return None
        _fill_score(slots, data)
    elif mode == "duel_columns":
        metrics = data.get("metrics")
        m = metrics[0] if isinstance(metrics, list) and metrics else {}
        if not isinstance(m, dict) or not m.get("label"):
            return None
        slots["title"] = str(m.get("label", "")).strip()
        slots["team-home"] = str(data.get("home", "")).strip()
        slots["team-away"] = str(data.get("away", "")).strip()
        slots["crest-home"] = _crest_monogram(slots["team-home"])
        slots["crest-away"] = _crest_monogram(slots["team-away"])
        slots["m-0-home"] = str(m.get("home", "")).strip()
        slots["m-0-away"] = str(m.get("away", "")).strip()
        if len(metrics) > 1 and isinstance(metrics[1], dict):
            slots["label-1"] = str(metrics[1].get("label", "")).strip()
            slots["m-1-home"] = str(metrics[1].get("home", "")).strip()
            slots["m-1-away"] = str(metrics[1].get("away", "")).strip()
    elif mode == "stat_leader":
        stats = data.get("stats") if isinstance(data.get("stats"), list) else []
        first = stats[0] if stats and isinstance(stats[0], dict) else {}
        if not str(first.get("value", "")).strip():
            return None
        slots["kicker"] = str(first.get("label", "")).strip().upper()
        slots["claim"] = str(first.get("value", "")).strip()
        if len(stats) > 1 and isinstance(stats[1], dict):
            slots["support"] = ("%s %s" % (stats[1].get("value", ""), stats[1].get("label", ""))).strip().upper()
    elif mode == "player_card":
        if not str(data.get("player_name", "")).strip():
            return None
        stats = data.get("stats") if isinstance(data.get("stats"), list) else []
        first = stats[0] if stats and isinstance(stats[0], dict) else {}
        name = str(data["player_name"]).strip()
        stat_v = str(first.get("value", "")).strip()
        stat_l = str(first.get("label", "")).strip().upper()
        meta_v = ""
        if len(stats) > 1 and isinstance(stats[1], dict):
            meta_v = ("%s %s" % (stats[1].get("value", ""), stats[1].get("label", ""))).strip().upper()
        # Fill BOTH starter vocabularies (profile-* and spot-*); only the
        # slots of the chosen starter exist, the rest are ignored.
        slots["profile-name"] = name
        slots["spot-name"] = name
        slots["profile-stat"] = stat_v
        slots["spot-stat"] = stat_v
        if stat_l:
            slots["profile-tag"] = stat_l
            slots["spot-tag"] = stat_l
        if meta_v:
            slots["profile-meta"] = meta_v
            slots["spot-meta"] = meta_v
    else:
        return None
    if credit:
        slots["credit"] = credit
    if not any(v for k, v in slots.items() if not k.startswith("__")):
        return None
    return slots


# ---------------------------------------------------------------------------
# Moved from render_starters.py / video_renderer.py + pack importer
# ---------------------------------------------------------------------------

def _accent_split(text: str) -> list[tuple[str, bool]]:
    """Split *accent* markup into (segment, is_accent) pieces.

    Canonical definition (was duplicated in render_starters +
    video_renderer + pack importer). The builder pre-splits; the executor
    draws the given segments without re-parsing asterisks.
    """
    parts = _ACCENT_RE.split(str(text or ""))
    out: list[tuple[str, bool]] = []
    for index, part in enumerate(parts):
        if part:
            out.append((part, index % 2 == 1))
    return out or [(str(text or ""), False)]


def _has_accent(text: str) -> bool:
    return "*" in str(text or "") and _ACCENT_RE.search(str(text or "")) is not None


def split_accent_segments(text: str) -> list[dict[str, Any]]:
    """Public pre-split form stored on the graph (deterministic)."""
    return [{"text": part, "accent": bool(is_acc)} for part, is_acc in _accent_split(text)]


def _shrink_to_fit(text: str, family: str, weight: str, size: int, max_width: float) -> int:
    """Shrink-to-fit: step down until the value fits its box.

    Generic overflow guard for every card and every topic (moved from
    starter_scenes._compose). Uses the locked brand fonts only.
    """
    from apps.studio_templates.render_starters import font_for as _font_for

    size = int(size)
    floor = max(20, size // 2)
    while size > floor:
        try:
            font = _font_for(str(family), str(weight), size)
            box = font.getbbox(str(text))
        except Exception:
            break
        if box[2] - box[0] <= float(max_width) + 2:
            break
        size -= 2
    return size


def _compose_design(data: dict[str, Any], slots: dict[str, str]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    """Substitute reviewed values + data-driven decor. Mutates and returns.

    Moved verbatim from starter_scenes._compose: hide slots with no data,
    hide row-tied decor (dot-/halo-*) of hidden rows, shrink-to-fit every
    visible text, then draw one winner dot+halo under the bigger number of
    each visible duel row (generic rule, never sample luck). Also returns
    the pre-split accent segments per visible text element id.
    """
    from apps.studio_templates.render_starters import font_for as _font_for

    slots = dict(slots)
    _winner = slots.pop("__winner", "")
    hidden_ids: set[str] = set()
    for child in data["pages"][0]["children"]:
        if not isinstance(child, dict) or child.get("type") != "text":
            continue
        slot = (child.get("custom") or {}).get("slot", "")
        if slot in slots and slots[slot]:
            child["text"] = slots[slot]
        elif slot:
            # No reviewed value: hide rather than ship sample text.
            child["showInExport"] = False
            if child.get("id"):
                hidden_ids.add(str(child["id"]))
    if hidden_ids:
        # Row-tied decor (winner dots/halos keyed dot-<textid>) must not
        # survive its hidden row.
        for child in data["pages"][0]["children"]:
            if not isinstance(child, dict) or child.get("type") != "figure":
                continue
            cid = str(child.get("id", ""))
            for hid in hidden_ids:
                if cid == f"dot-{hid}" or cid == f"halo-{hid}":
                    child["showInExport"] = False
    _ = _winner
    for child in data["pages"][0]["children"]:
        if not isinstance(child, dict) or child.get("type") != "text":
            continue
        if child.get("showInExport") is False:
            continue
        # Shrink-to-fit: step down until the reviewed value fits its box.
        try:
            size = int(child.get("fontSize", 40))
            fitted = _shrink_to_fit(
                str(child.get("text", "")),
                str(child.get("fontFamily", "Be Vietnam Pro")),
                str(child.get("fontWeight", "normal")),
                size,
                float(child.get("width", 0)),
            )
            child["fontSize"] = fitted
        except Exception:
            pass
    # Data-driven winner dots: hide every baked dot/halo, then draw one
    # under the bigger number of each visible duel row.
    rows: dict[str, dict[str, Any]] = {}
    for child in data["pages"][0]["children"]:
        if not isinstance(child, dict):
            continue
        cid = str(child.get("id", ""))
        if child.get("type") == "figure" and (
                cid.startswith("dot-") or cid.startswith("halo-")):
            child["showInExport"] = False
            continue
        if child.get("type") != "text" or child.get("showInExport") is False:
            continue
        slot = (child.get("custom") or {}).get("slot", "")
        m = re.match(r"^(m-\d+)-(home|away)$", slot)
        if not m:
            continue
        rows.setdefault(m.group(1), {})[m.group(2)] = child
    for key in sorted(rows):
        pair = rows[key]
        if "home" not in pair or "away" not in pair:
            continue
        try:
            hv = float(str(pair["home"].get("text", "")).replace(",", "."))
            av = float(str(pair["away"].get("text", "")).replace(",", "."))
        except (TypeError, ValueError):
            continue
        if hv == av:
            continue  # draw: no marker
        win = pair["home"] if hv > av else pair["away"]
        cx = float(win["x"]) + float(win["width"]) / 2
        top = float(win["y"]) + float(win["height"]) + 14
        kids = data["pages"][0]["children"]
        idx = kids.index(win)
        kids.insert(idx + 1, {
            "id": f"dot-{win['id']}", "type": "figure", "subType": "circle",
            "x": cx - 17, "y": top, "width": 34, "height": 34,
            "fill": "#FFB03A", "selectable": False, "draggable": False,
            "resizable": False, "removable": False})
        kids.insert(idx + 1, {
            "id": f"halo-{win['id']}", "type": "figure", "subType": "circle",
            "x": cx - 22, "y": top - 5, "width": 44, "height": 44,
            "fill": "#FFB03A", "opacity": 0.25, "selectable": False,
            "draggable": False, "resizable": False, "removable": False})
    segments: dict[str, list[dict[str, Any]]] = {}
    for child in data["pages"][0]["children"]:
        if not isinstance(child, dict) or child.get("type") != "text":
            continue
        if child.get("showInExport") is False:
            continue
        cid = str(child.get("id", ""))
        if cid:
            segments[cid] = split_accent_segments(str(child.get("text", "")))
    return data, segments


def _load_starter_design(starter_id: str) -> dict[str, Any] | None:
    """Load an authored short starter (1080x1920). None on any miss."""
    if not starter_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,20}", starter_id):
        return None
    path = TPL / f"{starter_id}.short.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if (data.get("width"), data.get("height")) != (1080, 1920):
        return None
    if not isinstance(data.get("pages"), list) or len(data["pages"]) != 1:
        return None
    return copy.deepcopy(data)


def layout_pack_boxes(
    boxes: list[dict[str, Any]],
    data: dict[str, Any],
    canvas: tuple[int, int] = (1080, 1920),
) -> list[dict[str, Any]]:
    """Owner-pack boxes (normalized 0-1) -> absolute text layers.

    Moved from apps/pack_import/importer.py render_pack_plate: dotted-path
    lookup, shrink-until-fits, *accent* two-tone split. Pure + deterministic;
    the executor draws the returned layers verbatim (no re-layout).
    """
    target_w, target_h = canvas

    def _lookup(payload: Any, key: str) -> str:
        current: Any = payload
        for part in str(key).split("."):
            if isinstance(current, dict):
                current = current.get(part, "")
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return ""
            else:
                return ""
        if isinstance(current, (dict, list)):
            return ""
        return str(current)[:120]

    layers: list[dict[str, Any]] = []
    for box in boxes or []:
        if not isinstance(box, dict):
            continue
        key = str(box.get("key", ""))
        raw_value = " ".join(_lookup(data, key).split())
        if not raw_value:
            continue
        stripped = re.sub(r"\*([^*]+)\*", r"\1", raw_value) if "*" in raw_value else raw_value
        coords = box.get("box") or [0, 0, 0, 0]
        try:
            x, y, w, h = (float(v) for v in coords)
        except (TypeError, ValueError):
            continue
        box_px = [round(x * target_w), round(y * target_h),
                  round(w * target_w), round(h * target_h)]
        layers.append({
            "key": key,
            "box_px": box_px,
            "align": box.get("align", "center"),
            "font": box.get("font", "body"),
            "color": str(box.get("color", "#FFFFFF")),
            "size_px": int(box.get("size", 40)),
            "value": stripped,
            "segments": split_accent_segments(raw_value),
        })
    return layers


# ---------------------------------------------------------------------------
# Visual-planner freeze: beat intent -> roles/motion/transition (planner side)
# ---------------------------------------------------------------------------

def _strip_stars(text: str) -> str:
    return re.sub(r"\*([^*]+)\*", r"\1", str(text or ""))


def _credit_source(data: dict[str, Any], evidence: list[Any]) -> str:
    src, date = _source_date(evidence if isinstance(evidence, list) else [])
    src = str(data.get("source", src) or src).strip()
    date = str(data.get("date", date) or date).strip()
    if src and date:
        return f"{src} • {date}"
    return src or date


def _headline_for(mode: str, data: dict[str, Any]) -> str:
    """Reviewed-text headline. Never invents: '' when no reviewed text fits."""
    if mode in ("hook_card", "goal_card"):
        return _strip_stars(str(data.get("hook_text", ""))).strip()
    if mode == "score_card":
        home = str(data.get("home", "")).strip()
        away = str(data.get("away", "")).strip()
        hg, ag = _parse_score(str(data.get("score", "")))
        if home and away and hg and ag:
            return f"{home} {hg}–{ag} {away}".strip()
        return ""
    if mode in ("duel_columns", "comparison_duel"):
        metrics = data.get("metrics")
        if isinstance(metrics, list) and metrics and isinstance(metrics[0], dict):
            return str(metrics[0].get("label", "")).strip()
        return str(data.get("label", "")).strip()
    if mode == "stat_leader":
        stats = data.get("stats")
        if isinstance(stats, list) and stats and isinstance(stats[0], dict):
            value = str(stats[0].get("value", "")).strip()
            label = str(stats[0].get("label", "")).strip()
            return f"{value} {label}".strip()
        return ""
    if mode in ("player_card", "player_poster", "player_poster_side",
                "player_poster_top", "potm_card"):
        name = str(data.get("player_name", "")).strip()
        stats = data.get("stats")
        if (isinstance(stats, list) and stats and isinstance(stats[0], dict)
                and str(stats[0].get("value", "")).strip()):
            return f"{name} — {stats[0]['value']} {stats[0].get('label', '')}".strip(" —")
        return name
    if mode in ("source_card", "quote_card"):
        claim = str(data.get("claim", "")).strip()
        return _strip_stars(claim)[:220]
    if mode in ("chart_comparison", "chart_timeline"):
        return str(data.get("headline", "")).strip()
    if mode in ("fixture_card", "fixture_list"):
        fixtures = data.get("fixtures")
        if isinstance(fixtures, list) and fixtures and isinstance(fixtures[0], dict):
            first = fixtures[0]
            return f"{first.get('home', '')} – {first.get('away', '')}".strip(" –")
        return ""
    return ""


def _data_chart_for(mode: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """Reviewed numbers only (pass-through, never recomputed)."""
    kinds = {
        "duel_columns": "duel_bars",
        "comparison_duel": "duel_bars",
        "statline_scorecard": "hero_number",
        "stat_leader": "leader_list",
        "chart_comparison": "comparison",
        "chart_timeline": "timeline",
        "score_card": "scoreline",
        "goal_card": "scoreline",
        "player_card": "player_stats",
        "player_poster": "player_stats",
        "player_poster_side": "player_stats",
        "player_poster_top": "player_stats",
        "potm_card": "player_stats",
    }
    kind = kinds.get(mode)
    if kind is None:
        return None
    values: Any = None
    for key in ("metrics", "stats", "values", "hero"):
        if data.get(key) not in (None, "", [], {}):
            values = copy.deepcopy(data[key])
            break
    if values is None and mode in ("score_card", "goal_card") and data.get("score"):
        values = {"home": str(data.get("home", "")),
                  "away": str(data.get("away", "")),
                  "score": str(data.get("score", ""))}
    if values is None:
        return None
    chart: dict[str, Any] = {"chart_kind": kind, "values": values}
    if mode == "chart_comparison" and isinstance(data.get("chart_type"), str):
        chart["chart_kind"] = str(data["chart_type"]).strip() or kind
    return chart


def _asset_ref(
    asset_id: str | None,
    asset_info: dict[str, Any] | None,
    *,
    kind: str = "library_image",
) -> dict[str, Any]:
    """Asset reference carrying Rights/Discovery-compatible rights fields.

    Approval is derived from the persisted ``rights_scope_json`` (the source
    of truth), NOT from ``rights_state``/``lifecycle_state`` alone: a
    verified/active record is not automatically cleared.

    - scope JSON valid and ``granted_by == "human"`` -> ``approved`` with a
      summarized ``rights_scope`` (non-empty string).
    - scope JSON valid and ``granted_by == "deny-default"`` -> ``"deny-default"``,
      ``pending``.
    - scope missing / unparseable / invalid / any other grant -> ``"rights-scope-missing"``,
      ``pending``.

    The graph never implies clearance it was not given. Renderer/QA still
    re-check against the real purpose via ``is_usable_for``.
    """
    from apps.asset_library.rights_scope import validate_scope

    info = asset_info if isinstance(asset_info, dict) else {}
    rights_scope = "rights-scope-missing"
    approval_status = "pending"
    granted_by = None
    scope = None
    raw = info.get("rights_scope_json")
    if isinstance(raw, str) and raw.strip():
        try:
            scope = json.loads(raw)
        except (ValueError, TypeError):
            scope = None
    elif isinstance(raw, dict):
        scope = raw
    if isinstance(scope, dict) and not validate_scope(scope):
        granted_by = scope.get("granted_by")
    if granted_by == "human":
        platforms = [
            str(p) for p in (scope.get("platforms") or []) if str(p).strip()
        ]
        rights_scope = (
            "human-granted:" + ",".join(platforms) if platforms else "human-granted"
        )
        approval_status = "approved"
    elif granted_by == "deny-default":
        rights_scope = "deny-default"
        approval_status = "pending"
    # any other case keeps "rights-scope-missing" / "pending"
    return {
        "asset_id": asset_id,
        "kind": kind,
        "rights_scope": rights_scope,
        "approval_status": approval_status,
        "license_type": info.get("license_type"),
        "purpose_code": info.get("purpose_code"),
    }


def _roles_for(
    *,
    visual_mode: str,
    graphic_data: dict[str, Any],
    evidence: list[Any],
    media_asset_id: str | None,
    asset_info: dict[str, Any] | None,
) -> dict[str, Any]:
    data = graphic_data if isinstance(graphic_data, dict) else {}
    player_name = str(data.get("player_name", "")).strip()
    player_focus: dict[str, Any] | None = None
    if player_name and visual_mode in PORTRAIT_MODES:
        portrait: dict[str, Any] | None = None
        if media_asset_id:
            portrait = _asset_ref(media_asset_id, asset_info)
        else:
            portrait = {
                "asset_id": None,
                "kind": "monogram_fallback",
                "rights_scope": "typographic-no-asset",
                "approval_status": "approved",
                "license_type": None,
                "purpose_code": None,
            }
        player_focus = {"player_name": player_name, "portrait": portrait}
    hero_image: dict[str, Any] | None = None
    if media_asset_id and visual_mode not in PORTRAIT_MODES:
        hero_image = _asset_ref(media_asset_id, asset_info)
    return {
        "hero_image": hero_image,
        "data_chart": _data_chart_for(visual_mode, data),
        "player_focus": player_focus,
        "headline": _headline_for(visual_mode, data),
        "source": _credit_source(data, evidence),
    }


def _motion_for(visual_mode: str, index: int) -> dict[str, Any]:
    """Deterministic motion from mode + template motion language.

    The LLM's emphasis_level is recorded in provenance intent for QA; it
    does not change the locked motion vocabulary (no per-beat invention).
    """
    if visual_mode == "hook_card" and index == 0:
        return {"enter": "hook_punch_in", "stagger_seconds": 0.18,
                "effect": "none", "count_up_steps": 0}
    if visual_mode == "media_b_roll":
        return {"enter": "fade_0_3s", "effect": "none", "count_up_steps": 0}
    effect = "none"
    if visual_mode in ("score_card", "goal_card", "duel_columns",
                       "comparison_duel", "statline_scorecard", "stat_leader",
                       "chart_comparison", "chart_timeline"):
        effect = "number_pop"
    elif visual_mode == "tactical_explainer":
        effect = "pitch_grid"
    motion: dict[str, Any] = {"enter": "slide_in_right_0_3s", "effect": effect,
                              "count_up_steps": 6 if effect == "number_pop" else 0}
    return motion


def _transition_for(visual_mode: str, index: int, chalk_allowed: bool) -> dict[str, str]:
    if index == 0:
        return {"in": "clean_cut", "out": "clean_cut"}
    if chalk_allowed and visual_mode in CHALK_CANDIDATE_MODES:
        return {"in": "chalk_line_wipe", "out": "clean_cut"}
    return {"in": "clean_cut", "out": "clean_cut"}


def _finalize_graph(
    graph: dict[str, Any],
    *,
    starter_id: str | None,
    template_version: str,
    beat_intent: dict[str, str],
) -> dict[str, Any]:
    """Attach provenance + deterministic hash. Same input/version → same hash."""
    graph["provenance"] = {
        **graph.get("provenance", {}),
        "starter_id": starter_id,
        "template_version": template_version,
        "beat_intent": dict(beat_intent),
    }
    graph["provenance"]["graph_hash"] = _graph_hash(graph)
    return graph


# ---------------------------------------------------------------------------
# Public builder API
# ---------------------------------------------------------------------------

def build_scene_graph(
    *,
    segment_id: str,
    visual_mode: str,
    starter_id: str | None,
    graphic_data: dict[str, Any] | None,
    evidence: list[Any] | None,
    content_type: str = "short",
    start_seconds: float = 0.0,
    end_seconds: float = 5.0,
    index: int = 0,
    media_asset_id: str | None = None,
    beat_intent: dict[str, Any] | None = None,
    template_version: str | None = None,
    asset_info: dict[str, Any] | None = None,
    transition_in: str | None = None,
    tactical_diagram: dict[str, Any] | None = None,
    media_caption: str | None = None,
    overlays: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Freeze one planner decision into a deterministic Scene Graph.

    Inputs arrive frozen from the planner (card_plan decision + reviewed
    graphic_data + evidence_refs + beat timing). Unknown modes raise
    ValueError (schema contract); starter misses yield a primitive graph
    with a fallback reason instead of re-selecting.

    Planner freeze (new v1 blocks): ``beat_intent`` (LLM meaning only) +
    the frozen decision determine ``roles``; ``motion`` comes from the
    locked template motion language; ``transition`` defaults to clean_cut
    unless the clip planner passes ``transition_in="chalk_line_wipe"``
    for a budgeted board/evidence beat. ``asset_info`` (verified/active
    library record when the Rights workstream has cleared the asset)
    decides the asset ``approval_status``; without it the ref is an
    explicit pending placeholder. Every graph carries
    ``provenance{starter_id, template_version, graph_hash}``: same
    input + same version -> same hash.

    Optional additive top-level blocks (frozen verbatim, covered by
    ``graph_hash``): ``tactical_diagram`` (players + pass/run/press
    vectors on the normalized 0..1 canvas), ``media_caption`` (str or
    None), and ``overlays`` (list of dicts). They are emitted on the
    graph and mirrored into ``params`` for primitive graphs so the
    executor can read them (top-level first, ``params`` fallback).
    """
    if visual_mode not in SUPPORTED_MODES:
        raise ValueError(f"scene graph: unknown visual_mode {visual_mode!r}")
    if content_type not in ("short", "long"):
        content_type = "short"
    if transition_in is not None and transition_in not in ("clean_cut", "chalk_line_wipe"):
        raise ValueError(f"scene graph: transition_in must be clean_cut/chalk_line_wipe, got {transition_in!r}")
    canvas = SHORT_CANVAS if content_type == "short" else LONG_CANVAS
    data = dict(graphic_data) if isinstance(graphic_data, dict) else {}
    ev = list(evidence) if isinstance(evidence, list) else []
    start = float(start_seconds)
    end = float(end_seconds)
    if not end > start:
        raise ValueError("scene graph: timing.end must be > timing.start")
    version = (template_version.strip()
               if isinstance(template_version, str) and template_version.strip()
               else TEMPLATE_VERSION_FALLBACK)
    intent = normalize_beat_intent(beat_intent, mode=visual_mode,
                                   index=int(index), graphic_data=data)

    design: dict[str, Any] | None = None
    segments: dict[str, list[dict[str, Any]]] = {}
    slots: dict[str, str] = {}
    fallback: str | None = None

    if (starter_id and content_type == "short" and visual_mode in STARTER_MODES):
        raw = _load_starter_design(starter_id)
        if raw is None:
            fallback = f"starter file missing/unreadable: {starter_id}"
        else:
            mapped = _substitutions(visual_mode, data, ev)
            if mapped is None:
                fallback = f"graphic_data does not fit starter {starter_id} for {visual_mode}"
            else:
                slots = {k: v for k, v in mapped.items() if not k.startswith("__")}
                composed, segments = _compose_design(raw, mapped)
                design = composed

    if design is not None:
        graph: dict[str, Any] = {
            "version": SCENE_GRAPH_VERSION,
            "kind": "starter",
            "mode": visual_mode,
            "starter_id": starter_id,
            "canvas": {"width": canvas[0], "height": canvas[1]},
            "timing": {"start": start, "end": end},
            "segment_id": str(segment_id),
            "index": int(index),
            "design": design,
            "segments": segments,
            "slots": slots,
            "params": None,
            "fallback": None,
            "provenance": {
                "builder": "apps.scene_graph.builder",
                "starter_file": f"{starter_id}.short.json",
                "crest": "monogram-fallback",
            },
        }
    else:
        if fallback is None:
            fallback = (
                f"no starter composition for mode={visual_mode} "
                f"starter={starter_id} content={content_type}"
            )
        graph = {
            "version": SCENE_GRAPH_VERSION,
            "kind": "primitive",
            "mode": visual_mode,
            "starter_id": starter_id,
            "canvas": {"width": canvas[0], "height": canvas[1]},
            "timing": {"start": start, "end": end},
            "segment_id": str(segment_id),
            "index": int(index),
            "design": None,
            "segments": {},
            "slots": {},
            "params": {
                "graphic_data": copy.deepcopy(data),
                "evidence": list(ev),
                "media_asset_id": media_asset_id,
            },
            "fallback": fallback,
            "provenance": {
                "builder": "apps.scene_graph.builder",
                "crest": "monogram-fallback",
            },
        }
    if transition_in is None:
        transition: dict[str, str] = {"in": "clean_cut", "out": "clean_cut"}
        if int(index) > 0 and visual_mode in CHALK_CANDIDATE_MODES:
            # Single-beat call without clip context: candidate boards may
            # claim chalk; clip builds (build_clip_graphs) re-budget to the
            # max-2 cap and pass transition_in explicitly.
            transition = {"in": "chalk_line_wipe", "out": "clean_cut"}
    elif int(index) == 0:
        # Beat-0 always opens clean_cut (cold-open punch invariant).
        transition = {"in": "clean_cut", "out": "clean_cut"}
    else:
        transition = {"in": transition_in, "out": "clean_cut"}
    graph["roles"] = _roles_for(
        visual_mode=visual_mode,
        graphic_data=data,
        evidence=ev,
        media_asset_id=media_asset_id,
        asset_info=asset_info if isinstance(asset_info, dict) else None,
    )
    graph["motion"] = _motion_for(visual_mode, int(index))
    graph["transition"] = transition
    # Additive top-level blocks (frozen verbatim, covered by graph_hash).
    graph["tactical_diagram"] = tactical_diagram
    graph["media_caption"] = media_caption
    graph["overlays"] = overlays
    if isinstance(graph.get("params"), dict):
        graph["params"]["tactical_diagram"] = tactical_diagram
        graph["params"]["media_caption"] = media_caption
        graph["params"]["overlays"] = overlays
    return _finalize_graph(graph, starter_id=starter_id,
                           template_version=version, beat_intent=intent)


def build_from_decision(
    decision: dict[str, Any],
    *,
    evidence: list[Any] | None = None,
    start_seconds: float = 0.0,
    end_seconds: float = 5.0,
    content_type: str = "short",
    beat_intent: dict[str, Any] | None = None,
    template_version: str | None = None,
    asset_info: dict[str, Any] | None = None,
    transition_in: str | None = None,
    tactical_diagram: dict[str, Any] | None = None,
    media_caption: str | None = None,
    overlays: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Wrap a card_plan decision (planner output) into a Scene Graph."""
    if not isinstance(decision, dict):
        raise ValueError("scene graph: decision must be an object")
    # Additive blocks: explicit argument wins, otherwise fall back to the
    # decision's own fields so plain decision wrapping carries them through.
    if tactical_diagram is None:
        tactical_diagram = decision.get("tactical_diagram")
    if media_caption is None:
        media_caption = decision.get("media_caption")
    if overlays is None:
        overlays = decision.get("overlays")
    graphic = decision.get("graphic_data")
    ev = evidence
    if ev is None:
        ev_candidate = decision.get("evidence")
        ev = ev_candidate if isinstance(ev_candidate, list) else []
    intent = beat_intent
    if intent is None:
        candidate = decision.get("beat_intent")
        intent = candidate if isinstance(candidate, dict) else None
    return build_scene_graph(
        segment_id=str(decision.get("segment_id", "beat-1")),
        visual_mode=str(decision.get("visual_mode", "")),
        starter_id=decision.get("starter_id"),
        graphic_data=graphic if isinstance(graphic, dict) else {},
        evidence=ev if isinstance(ev, list) else [],
        content_type=content_type,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        index=int(decision.get("index", 0)),
        media_asset_id=decision.get("media_asset_id"),
        beat_intent=intent,
        template_version=template_version,
        asset_info=asset_info,
        transition_in=transition_in,
        tactical_diagram=tactical_diagram,
        media_caption=media_caption,
        overlays=overlays,
    )


def build_clip_graphs(
    decisions: list[dict[str, Any]],
    segments_by_id: dict[str, dict[str, Any]] | None = None,
    content_type: str = "short",
    *,
    template_version: str | None = None,
    asset_map: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Freeze a whole card_plan (ordered decisions) into Scene Graphs.

    Clip-level planner duties live here: beat timing from the production
    timeline, beat_intent carried from the draft segments (LLM meaning),
    asset records looked up from ``asset_map`` (Rights-cleared when the
    Rights workstream supplies them, else pending placeholders), and the
    chalk_line_wipe budget (max 2 per clip, first candidates win).
    Deterministic: same decisions + same version -> same graphs + hashes.
    """
    segments_by_id = segments_by_id or {}
    asset_map = asset_map or {}
    ordered = [d for d in (decisions or []) if isinstance(d, dict)]
    chalk_winners: set[str] = set()
    for decision in ordered:
        mode = str(decision.get("visual_mode", ""))
        sid = str(decision.get("segment_id", ""))
        if (mode in CHALK_CANDIDATE_MODES and len(chalk_winners) < MAX_CHALK_PER_CLIP
                and decision.get("index", 0) != 0):
            chalk_winners.add(sid)
    graphs: list[dict[str, Any]] = []
    for order, decision in enumerate(ordered):
        sid = str(decision.get("segment_id", f"beat-{order + 1}"))
        seg = segments_by_id.get(sid) if isinstance(segments_by_id, dict) else None
        seg = seg if isinstance(seg, dict) else {}
        evidence = seg.get("evidence_refs")
        if not isinstance(evidence, list):
            evidence = decision.get("evidence") or []
        intent = seg.get("beat_intent")
        if not isinstance(intent, dict):
            intent = decision.get("beat_intent")
        # Additive blocks: planner decision first, per-beat segment data
        # overrides when present; None when absent on both.
        tactical_diagram = decision.get("tactical_diagram")
        media_caption = decision.get("media_caption")
        overlays = decision.get("overlays")
        if isinstance(seg, dict):
            if seg.get("tactical_diagram") is not None:
                tactical_diagram = seg.get("tactical_diagram")
            if seg.get("media_caption") is not None:
                media_caption = seg.get("media_caption")
            if seg.get("overlays") is not None:
                overlays = seg.get("overlays")
        if overlays is not None and not isinstance(overlays, list):
            raise ValueError("scene graph: overlays must be a list when provided")
        media_id = decision.get("media_asset_id")
        info = asset_map.get(str(media_id)) if isinstance(media_id, str) else None
        try:
            start = float(seg.get("start_seconds", decision.get("start_seconds", 0.0)))
        except (TypeError, ValueError):
            start = 0.0
        try:
            end = float(seg.get("end_seconds", decision.get("end_seconds", start + 5.0)))
        except (TypeError, ValueError):
            end = start + 5.0
        if not end > start:
            end = start + 5.0

        # Chuyển đổi timeline_events (timebase tuyệt đối từ content_workflow)
        # thành overlay clip-relative (0 = đầu beat) cho beat này.
        # Overlays rõ ràng (từ decision/segment, đã gán vào `overlays` ở trên)
        # được bảo toàn trước; overlay từ timeline append sau cùng sau dedup.
        timeline_events = seg.get("timeline_events")
        if isinstance(timeline_events, list):
            beat_duration = end - start
            for event in timeline_events:
                if not isinstance(event, dict):
                    continue
                item_type = event.get("item_type")
                if item_type not in ("caption", "lower_third"):
                    continue
                item_id = event.get("item_id", "<unknown>")
                text = event.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError(
                        f"scene graph: timeline event {item_id!r} text must be "
                        "a non-empty string"
                    )
                abs_start = event.get("start_seconds")
                abs_end = event.get("end_seconds")
                if (
                    isinstance(abs_start, bool)
                    or isinstance(abs_end, bool)
                    or not isinstance(abs_start, (int, float))
                    or not isinstance(abs_end, (int, float))
                ):
                    raise ValueError(
                        f"scene graph: timeline event {item_id!r} "
                        "start_seconds/end_seconds must be real numbers"
                    )
                start_rel = float(abs_start) - start
                end_rel = float(abs_end) - start
                if not (
                    start_rel >= 0
                    and end_rel > start_rel
                    and end_rel <= beat_duration
                ):
                    raise ValueError(
                        f"scene graph: timeline event {item_id!r} times "
                        f"[{start_rel}, {end_rel}] outside beat window "
                        f"[0, {beat_duration}]"
                    )
                overlay = {
                    "type": item_type,
                    "text": text.strip(),
                    "start_seconds": start_rel,
                    "end_seconds": end_rel,
                }
                role = event.get("role")
                if isinstance(role, str) and role.strip():
                    overlay["role"] = role.strip()
                # Dedup: bỏ qua nếu đã có overlay trùng type+text+start+end
                # (tránh trùng khi cùng sự kiện đến từ nhiều nguồn).
                if any(
                    isinstance(o, dict)
                    and o.get("type") == overlay["type"]
                    and o.get("text") == overlay["text"]
                    and o.get("start_seconds") == overlay["start_seconds"]
                    and o.get("end_seconds") == overlay["end_seconds"]
                    for o in (overlays or [])
                ):
                    continue
                if overlays is None:
                    overlays = []
                overlays.append(overlay)

        graphs.append(build_from_decision(
            decision,
            evidence=evidence if isinstance(evidence, list) else [],
            start_seconds=start,
            end_seconds=end,
            content_type=content_type,
            beat_intent=intent if isinstance(intent, dict) else None,
            template_version=template_version,
            asset_info=info if isinstance(info, dict) else None,
            transition_in=("chalk_line_wipe" if sid in chalk_winners else "clean_cut"),
            tactical_diagram=tactical_diagram,
            media_caption=media_caption,
            overlays=overlays,
        ))
    return graphs


from apps.scene_graph.schema import validate_scene_graph as validate


__all__ = [
    "STARTER_MODES",
    "PORTRAIT_MODES",
    "CHALK_CANDIDATE_MODES",
    "MAX_CHALK_PER_CLIP",
    "TEMPLATE_VERSION_FALLBACK",
    "build_scene_graph",
    "build_from_decision",
    "build_clip_graphs",
    "layout_pack_boxes",
    "split_accent_segments",
    "validate",
    "_substitutions",
    "_fill_score",
    "_initials",
    "_crest_monogram",
    "_accent_split",
]
