"""Card selector: script segments -> render-ready card decisions.

Given any script draft (segments with narration/visual/visual_mode/graphic_data)
plus fetched library assets, the engine decides which card each beat renders,
which Sprint 1 starter it maps to for Studio export, and which asset binds to
which segment — before the renderer runs.

Deterministic and rule-based (NSS-style 0-100 fit score, zero model cost):
slot coverage from graphic-templates.json, beat-role rules from
story-forms.json (beat 0 = hook), renderer rules mirrored from
video_renderer.py (media_asset_id forces media_b_roll outside portrait modes;
media_b_roll without an asset falls back to tactical_explainer), and the
slot-contract rights gates (verified/active images only; portraits must
depict the named player, else typographic fallback + warning).

No I/O, no LLM calls. Import-safe (no video_renderer import).
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Mapping

from apps.content_workflow import VISUAL_MODES
from apps.asset_library.rights_scope import is_usable_for

# Renderer accepts everything _clean_segment allows, plus media_b_roll which
# it derives itself from media_asset_id (video_renderer.py, scene loop).
SUPPORTED_MODES = set(VISUAL_MODES) | {"media_b_roll"}

# Modes where the renderer injects the bound asset as media_file.
PORTRAIT_MODES = {
    "player_card", "player_poster", "player_poster_side", "player_poster_top",
    "potm_card", "welcome_card", "score_card", "quote_card",
}

# Short starters live in apps/studio_templates/*.short.json, long ones in
# *.long.json. Starter is only suggested when its aspect matches the content.
STARTERS_SHORT = {
    "hook_card": "C-03", "quote_card": "C-05",
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


def _derive_hook_text(narration: str) -> tuple[str, str | None]:
    """First ≤8 words. Second value is a tightening warning, if any."""
    words = narration.split()
    if len(words) > 8:
        return (" ".join(words[:8]),
                "hook_text derived at the 8-word cap mid-sentence; tighten to a clean 5–8 word claim")
    if len(words) < 5:
        return " ".join(words), "hook_text shorter than the 5-word minimum; expand to 5–8 words"
    return " ".join(words), None


def _derive_claim(narration: str, limit: int = 220) -> str:
    first = re.split(r"[.!?…\n]", narration.strip())[0].strip()
    return first[:limit].strip()


def _eligible_asset(asset: dict[str, Any],
                    purpose: dict[str, Any] | None = None) -> bool:
    """Verified/active image; with a purpose, also rights-usable for that upload.

    ``rights_state == "verified"`` is identity/suitability only, never usage
    clearance: when a purpose is given the asset must additionally pass
    ``is_usable_for`` (platform, territory, commercial, monetization, ...).
    When purpose is None the historical verified/active image check is
    preserved and no scope-eligibility claim is made.
    """
    base = (asset.get("asset_type") == "image"
            and asset.get("rights_state") == "verified"
            and asset.get("lifecycle_state") == "active")
    if not base:
        return False
    if purpose is None:
        return True
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
        if _present(filled, key):
            continue
        if key == "hook_text" and key in DERIVABLE_SLOTS and narration.strip():
            filled[key], note = _derive_hook_text(narration)
            derived.append(key)
            if note:
                derive_warnings.append(note)
        elif key == "claim" and narration.strip():
            filled[key] = _derive_claim(narration)
            derived.append(key)
    covered = sum(1 for key in required if _present(filled, key))
    return covered / len(required), derived, filled, derive_warnings


def _score_candidate(mode: str, segment: dict[str, Any], data: dict[str, Any],
                     assets: list[dict[str, Any]], declared: bool,
                     prev_modes: list[str],
                     purpose: dict[str, Any] | None = None
                     ) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 50.0 if declared else 40.0
    narration = str(segment.get("narration", ""))
    coverage, derived, _, _ = _coverage(mode, data, narration)
    score += 30.0 * coverage
    if derived:
        reasons.append(f"derived {','.join(derived)} from narration")
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


def select_cards(segments: list[dict[str, Any]],
                 assets: list[dict[str, Any]] | None = None,
                 content_type: str = "short",
                 purpose: dict[str, Any] | None = None,
                 exact_terms: list[str] | None = None) -> dict[str, Any]:
    """Map every segment to a render-ready card decision.

    Returns {"decisions": [...], "plan": {...}}. Each decision carries
    segment_id, visual_mode, starter_id (Sprint 1 card for Studio, or None),
    graphic_data (completed), media_asset_id (validated), score, reasons and
    warnings. Never raises on bad input; problems become warnings.
    """
    assets = list(assets or [])
    if content_type not in ("short", "long"):
        content_type = "short"
    decisions: list[dict[str, Any]] = []
    prev_modes: list[str] = []
    plan_warnings: list[str] = []
    for index, raw in enumerate(segments or []):
        segment = raw if isinstance(raw, dict) else {}
        segment_id = str(segment.get("id", f"beat-{index + 1}"))
        narration = str(segment.get("narration", ""))
        data = segment.get("graphic_data")
        data = dict(data) if isinstance(data, dict) else {}
        declared = str(segment.get("visual_mode") or "tactical_explainer")
        warnings: list[str] = []
        if declared not in SUPPORTED_MODES:
            warnings.append(f"unknown visual_mode '{declared}'; fell back to tactical_explainer")
            declared = "tactical_explainer"

        # Renderer rule: a bound asset forces media_b_roll outside portrait modes.
        bound = segment.get("media_asset_id")
        asset_ok = False
        if bound:
            record = next((a for a in assets if str(a.get("asset_id")) == str(bound)), None)
            if record is None:
                warnings.append(f"media_asset_id '{bound}' not in fetched assets; binding dropped")
                bound = None
            elif not _eligible_asset(record, purpose):
                warnings.append(f"asset '{bound}' is not verified/active; binding dropped (render would fail)")
                bound = None
            else:
                asset_ok = True

        candidates = [declared]
        for mode in _signal_modes(narration, str(segment.get("visual", ""))):
            if mode not in candidates and mode in SUPPORTED_MODES:
                candidates.append(mode)
            if len(candidates) >= 3:
                break

        # Owner 16/10: a declared player/portrait mode with a named player
        # stays — reselecting to a nameless data card would silently drop
        # the player's identity from the frame.
        lock_player = (declared in PORTRAIT_MODES and _present(data, "player_name"))
        scored = []
        for mode in candidates:
            points, why = _score_candidate(mode, segment, data, assets,
                                           declared=(mode == declared),
                                           prev_modes=prev_modes,
                                           purpose=purpose)
            if lock_player and mode != declared:
                points -= 100.0
                why = why + ["player-mode lock: identity over fit"]
            scored.append((points, mode == declared, mode, why))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        best_points, _, best_mode, best_why = scored[0]

        if bound and best_mode not in PORTRAIT_MODES and best_mode != "media_b_roll":
            best_mode = "media_b_roll"
            best_why = best_why + ["bound asset forces b-roll outside portrait modes"]
        if best_mode == "media_b_roll" and not (bound and asset_ok):
            # Renderer rule mirrored: b-roll without an asset is a pitch plate.
            best_mode = "tactical_explainer"
            best_why = best_why + ["no asset bound; b-roll falls back to pitch plate"]
            if bound and not asset_ok:
                bound = None

        if best_mode in PORTRAIT_MODES and not bound and _present(data, "player_name"):
            hit = _match_portrait(str(data.get("player_name", "")), assets, purpose)
            if hit:
                # Owner standing order 2026-10-16: a verified/active library
                # portrait auto-attaches (reuse-first; acquisition still needs
                # owner approval per PROJECT_SPEC section 8). The old
                # suggest-only rule is retired with its tests.
                bound = hit
                asset_ok = True
                warnings.append(f"verified portrait '{hit}' auto-attached (owner standing order 16/10)")
            suggested = None
        else:
            suggested = None

        coverage, derived, filled, derive_warnings = _coverage(best_mode, data, narration)
        warned_keys = {w.rsplit("missing '", 1)[1].rstrip("'")
                       for w in warnings if "missing '" in w}
        for key in REQUIRED_SLOTS.get(best_mode, []):
            if not _present(filled, key):
                warnings.append(f"{best_mode} missing '{key}'")
        warnings.extend(derive_warnings)

        # Beat-0 rule (story-forms.json always_on_rules): open on the hook.
        if index == 0 and best_mode != "hook_card":
            best_mode = "hook_card"
            coverage, derived, filled, derive_warnings = _coverage(best_mode, data, narration)
            warnings.extend(derive_warnings)
            best_why = ["beat-0 opens on the hook"] + best_why
            for key in REQUIRED_SLOTS.get(best_mode, []):
                if not _present(filled, key) and key not in warned_keys:
                    warnings.append(f"{best_mode} missing '{key}'")

        starter = _starter_for(best_mode, segment, content_type, filled)
        if (best_mode == "tactical_explainer" and starter
                and starter.startswith("TA-") and content_type == "long"):
            # Renderer hook: long tactical beats render the authored plate.
            filled["tactical_card"] = starter
            best_why = best_why + [f"authored plate {starter}"]
        reasons = [f"fit {best_points:.0f}/100"] + best_why
        decisions.append({
            "segment_id": segment_id,
            "index": index,
            "visual_mode": best_mode,
            "starter_id": starter,
            "graphic_data": filled,
            "media_asset_id": bound,
            "suggested_asset_id": suggested,
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
    mode_counts: dict[str, int] = {}
    for d in decisions:
        mode_counts[d["visual_mode"]] = mode_counts.get(d["visual_mode"], 0) + 1
    return {
        "decisions": decisions,
        "plan": {
            "content_type": content_type,
            "purpose": purpose,
            "exact_terms": exact_terms,
            "beats": len(decisions),
            "mode_counts": mode_counts,
            "starters": sorted({d["starter_id"] for d in decisions if d["starter_id"]}),
            "warnings": plan_warnings,
        },
    }


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

    Copies each decision's visual_mode/graphic_data into its segment, keeps
    only validated media bindings (drops anything the renderer would crash
    on), auto-attaches verified portraits (owner standing order 16/10),
    auto-picks generic b-roll for closing hook beats from the broll-generic
    pool, and stores the full plan at run["card_plan"] for review surfaces.
    Returns the plan.
    """
    draft = run.get("draft") if isinstance(run.get("draft"), dict) else {}
    segments = draft.get("segments")
    if not isinstance(segments, list):
        plan = {"decisions": [], "plan": {"beats": 0, "warnings": ["run has no script segments"]}}
        run["card_plan"] = plan
        return plan
    content_type = draft.get("content_type", "short")
    assets, note = _fetch_verified_images(root)
    # Upload purpose: run-level first, then draft-level. A missing purpose
    # means select_cards makes no scope-eligibility claim for any asset.
    purpose = run.get("purpose")
    if purpose is None:
        purpose = draft.get("purpose")
    if not isinstance(purpose, Mapping):
        purpose = None
    plan = select_cards([s for s in segments if isinstance(s, dict)],
                        assets, content_type, purpose=purpose)
    by_id = {d["segment_id"]: d for d in plan["decisions"]}
    used_media: set[str] = set()
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        if isinstance(segment.get("media_asset_id"), str) and segment["media_asset_id"]:
            used_media.add(segment["media_asset_id"])
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            continue
        decision = by_id.get(str(segment.get("id")))
        if decision is None:
            continue
        segment["visual_mode"] = decision["visual_mode"]
        segment["graphic_data"] = decision["graphic_data"]
        if decision["media_asset_id"]:
            segment["media_asset_id"] = decision["media_asset_id"]
            used_media.add(str(decision["media_asset_id"]))
        else:
            segment.pop("media_asset_id", None)
            # B-roll pool: closing hook beats (takeaways) get a generic
            # verified illustration when the pool has an unused one. Owner
            # standing order 16/10; person photos never enter this pool —
            # identity-matched portraits attach only via the portrait rule.
            if (decision["visual_mode"] == "hook_card" and index > 0
                    and content_type == "short"):
                pick = _pick_broll(assets, used_media, purpose)
                if pick:
                    segment["media_asset_id"] = pick
                    decision["media_asset_id"] = pick
                    # Mirror the bound-asset rule: b-roll outside portrait.
                    segment["visual_mode"] = "media_b_roll"
                    decision["visual_mode"] = "media_b_roll"
                    used_media.add(pick)
                    decision["warnings"].append(
                        f"b-roll '{pick}' auto-picked from broll-generic pool")
    if note:
        plan["plan"]["warnings"].insert(0, note)
    run["card_plan"] = plan
    return plan


def _pick_broll(assets: list[dict[str, Any]], used: set[str],
                purpose: dict[str, Any] | None = None) -> str | None:
    """First unused verified broll-generic image, purpose-cleared, deterministic order."""
    for asset in sorted(assets, key=lambda a: str(a.get("asset_id", ""))):
        aid = str(asset.get("asset_id", ""))
        if not aid or aid in used:
            continue
        if not _eligible_asset(asset, purpose):
            continue
        if asset.get("purpose_code") != "broll-generic":
            continue
        return aid
    return None
