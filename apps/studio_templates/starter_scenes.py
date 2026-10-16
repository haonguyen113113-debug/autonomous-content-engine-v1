"""Render video scenes from authored starter JSONs (single source of truth).

Short-form video previously drew generic pack boxes (arbitrary geometry,
literal *stars*). This module renders the SAME starter scenes Studio and
proofs use: load STARTERS_SHORT[mode], substitute reviewed graphic_data
into slotted texts, hide slots with no data, render pixel-exact via
render_design. Any failure returns None so the caller falls back to the
generic path; it never raises.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
TPL = ROOT / "apps" / "studio_templates"


def _strip_stars(text: str) -> str:
    """Drop *accent* markers (single-fill renderer has no two-tone run)."""
    return re.sub(r"\*([^*]+)\*", r"\1", str(text))


def _initials(name: str, limit: int = 3) -> str:
    parts = [p for p in re.split(r"\s+", str(name).strip()) if p]
    if len(parts) == 1:
        # Already abbreviated (PSG, MC): keep whole so "PSG" never becomes "P".
        return parts[0].upper()
    return "".join(p[0] for p in parts[:limit]).upper()


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
        top_name, top_goals, top_init = away, ag, _initials(away)
        bot_name, bot_goals, bot_init = home, hg, _initials(home)
    else:
        top_name, top_goals, top_init = home, hg, _initials(home)
        bot_name, bot_goals, bot_init = away, ag, _initials(away)
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
        slots["claim"] = _strip_stars(str(data["hook_text"]).strip())
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
        slots["crest-home"] = _initials(slots["team-home"])
        slots["crest-away"] = _initials(slots["team-away"])
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


def _prepare(mode: str, graphic_data: dict[str, Any],
             evidence: list[Any], starter_id: str | None) -> dict[str, Any] | None:
    """Load starter JSON + substitute reviewed values. None on any miss."""
    from apps.card_selector import STARTERS_SHORT
    if not starter_id:
        starter_id = STARTERS_SHORT.get(mode)
    if not starter_id:
        return None
    path = TPL / f"{starter_id}.short.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("width"), data.get("height")) != (1080, 1920):
        return None
    slots = _substitutions(mode, graphic_data or {}, evidence or [])
    if slots is None:
        return None
    return data, slots


def _compose(data: dict[str, Any], slots: dict[str, str]) -> dict[str, Any]:
    """Substitute reviewed values + data-driven decor. Mutates and returns."""
    from apps.studio_templates.render_starters import font_for as _font_for
    _winner = slots.pop("__winner", "")
    hidden_ids = set()
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
        # Shrink-to-fit: step down until the reviewed value fits its
        # box (generic overflow guard for every card and every topic).
        try:
            size = int(child.get("fontSize", 40))
            floor = max(20, size // 2)
            while size > floor:
                font = _font_for(str(child.get("fontFamily", "Be Vietnam Pro")),
                                 str(child.get("fontWeight", "normal")), size)
                box = font.getbbox(str(child.get("text", "")))
                if box[2] - box[0] <= float(child.get("width", 0)) + 2:
                    break
                size -= 2
            child["fontSize"] = size
        except Exception:
            pass
    # Data-driven winner dots: hide every baked dot/halo, then draw one
    # under the bigger number of each visible duel row (generic rule —
    # never sample luck again).
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
    return data


def render_starter_scene(mode: str, graphic_data: dict[str, Any],
                         evidence: list[Any], starter_id: str | None) -> Any | None:
    """Render the authored starter with reviewed values. None on any miss."""
    try:
        from apps.studio_templates.render_starters import render_design
        prepared = _prepare(mode, graphic_data, evidence, starter_id)
        if prepared is None:
            return None
        return render_design(_compose(*prepared))
    except Exception:
        return None


def render_starter_layers(mode: str, graphic_data: dict[str, Any],
                          evidence: list[Any],
                          starter_id: str | None) -> tuple[Any, Any] | None:
    """Background + text layers so video can entrance type after the plate.
    Returns (bg_image, text_image_or_None). None on any miss."""
    try:
        from apps.studio_templates.render_starters import render_design
        prepared = _prepare(mode, graphic_data, evidence, starter_id)
        if prepared is None:
            return None
        data = _compose(*prepared)
        bg = render_design(data, texts=False)
        has_text = any(isinstance(c, dict) and c.get("type") == "text"
                       and c.get("showInExport") is not False
                       for c in data["pages"][0]["children"])
        text = render_design(data, decor=False, transparent=True) if has_text else None
        return bg, text
    except Exception:
        return None
