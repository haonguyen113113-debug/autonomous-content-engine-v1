"""Pre-production summary: one gate instead of per-component reviews.

Flow the owner asked for: enter a title, the engine drafts + checks +
plans, then reports ONE summary (script, narrative, assets, template,
voice). The owner approves the summary as a whole, or ticks per-section
fix checkboxes (section + target + note) for targeted rework.

Safety is preserved, not removed: bulk approval runs the exact same
validations as the individual gates (no unresolved markers, verified
assets only, voice duration fit). What disappears is the waiting between
five separate clicks, not the checks themselves.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from dataclasses import fields as dc_fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apps.card_selector import _fetch_verified_images, select_cards
from apps.asset_library.discovery import (
    DiscoveryError,
    save_commons_candidate,
    search_candidates_tiered,
)
from apps.content_score import score_script
from apps.content_workflow import TEMPLATE_IDS, VISUAL_MODES, regenerate_beat
from apps.video_renderer import _ensure_voice_fits_script, render_full_run
from apps.voice_tts import synthesize_voice_preview, voice_profile_status

SUMMARY_VERSION = "1.0"

FIXABLE_SECTIONS = ("script", "narrative", "asset", "template", "voice", "sound")

UNRESOLVED_MARKERS = ("[CẦN NGUỒN]", "[KẾT LUẬN CỦA ALLEN]")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_run(root: Path, run_id: str) -> dict[str, Any]:
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{12}", run_id):
        raise ValueError("Production run ID is invalid.")
    path = Path(root) / "runtime" / "runs" / f"{run_id}.json"
    if not path.is_file():
        raise ValueError("Production run was not found.")
    run = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(run, dict):
        raise ValueError("Production run file is corrupt.")
    return run


def _write_run(root: Path, run: dict[str, Any]) -> None:
    path = Path(root) / "runtime" / "runs" / f"{run.get('run_id', '')}.json"
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _env_file_values(root: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = (Path(root) / ".env").read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip("\"'")
    return values


def _env_flag(root: Path, key: str) -> bool:
    raw = os.environ.get(key, _env_file_values(root).get(key, ""))
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _discovery_keys(root: Path) -> dict[str, str]:
    file_values = _env_file_values(root)
    keys: dict[str, str] = {}
    for key in ("PEXELS_API_KEY", "PIXABAY_API_KEY"):
        value = os.environ.get(key, file_values.get(key, "")).strip()
        if value:
            keys[key] = value
    return keys


def _summary_path(root: Path, run_id: str) -> Path:
    return Path(root) / "runtime" / "summaries" / f"{run_id}.json"


def _segments(run: dict[str, Any]) -> list[dict[str, Any]]:
    draft = run.get("draft")
    if not isinstance(draft, dict) or not isinstance(draft.get("segments"), list):
        raise ValueError("Production run has no script draft to summarize.")
    clean = [s for s in draft["segments"] if isinstance(s, dict)]
    if not clean:
        raise ValueError("Production run has no script beats to summarize.")
    return clean


def _unresolved_beats(segments: list[dict[str, Any]]) -> list[str]:
    bad = []
    for seg in segments:
        narration = seg.get("narration", "") if isinstance(seg.get("narration"), str) else ""
        if any(marker in narration for marker in UNRESOLVED_MARKERS):
            bad.append(str(seg.get("id", "?")))
    return bad


def _story_arc(root: Path, run: dict[str, Any]) -> dict[str, Any]:
    """Story form arc for the narrative section (derived, read-only)."""
    from template_foundation import resolve_template

    draft = run.get("draft", {}) if isinstance(run.get("draft"), dict) else {}
    content_type = str(draft.get("content_type", "short")).strip().lower() or "short"
    template_id = TEMPLATE_IDS.get(content_type, "")
    form_id = str(draft.get("story_form", ""))
    try:
        package = resolve_template(Path(root), template_id, allow_draft=True)
    except Exception as error:  # noqa: BLE001 - summary must degrade, not crash
        return {"form_id": form_id, "label": "", "arc": [], "error": str(error)[:200]}
    forms = package.story_forms.get("forms", []) if isinstance(package.story_forms, dict) else []
    form = next((f for f in forms if isinstance(f, dict) and f.get("id") == form_id), None)
    if form is None:
        return {"form_id": form_id, "label": "", "arc": []}
    return {"form_id": form_id, "label": str(form.get("label_vi", "")),
            "arc": [str(p) for p in form.get("arc", []) if isinstance(p, str)],
            "must_have": [str(m) for m in form.get("must_have", []) if isinstance(m, str)]}


def _autosave_assets(root: Path, run: dict[str, Any]) -> list[dict[str, Any]]:
    """Owner-granted auto-save: top shortfall candidates enter the library.

    Runs only when ASSET_AUTOSAVE is enabled. Uses the same strict intake
    as manual saving (pinned-host download, size caps, type match) with
    rights_reviewed=True per the owner's standing grant, and records every
    attribute needed for reuse under the locked library structure.
    Returns per-need autosave records. Never raises: failures are recorded.
    """
    from apps.asset_library.asset_intelligence import ResourceRequirement
    from apps.asset_library.registry import connect
    from apps.asset_library.resource_workflow import evaluate_library_requirement

    if not _env_flag(root, "ASSET_AUTOSAVE"):
        return []
    root = Path(root)
    outcomes: list[dict[str, Any]] = []
    conn = connect(root / "runtime/engine.db")
    try:
        for check in run.get("asset_checks", []) or []:
            if not isinstance(check, dict):
                continue
            if int(check.get("shortfall", 0) or 0) <= 0:
                continue
            candidates = check.get("web_candidates", []) or []
            if not candidates:
                continue
            saved = None
            for candidate in candidates[:3]:
                if not isinstance(candidate, dict):
                    continue
                try:
                    req_fields = {f.name for f in dc_fields(ResourceRequirement)}
                    saved = save_commons_candidate(
                        root, str(candidate.get("candidate_id", "")),
                        ResourceRequirement(**{
                            key: value for key, value in (check.get("requirement", {}) or {}).items()
                            if key in req_fields}),
                        rights_reviewed=True,
                        api_keys=_discovery_keys(root),
                    )
                except Exception as error:  # noqa: BLE001 - try next candidate
                    saved = {"status": "FAILED", "error": str(error)[:200]}
                    continue
                break
            record = {"requirement_id": check.get("requirement_id")
                      or (check.get("requirement", {}) or {}).get("requirement_id"),
                      "candidate_id": (candidates[0] or {}).get("candidate_id")
                      if isinstance(candidates[0], dict) else None,
                      "result": saved}
            outcomes.append(record)
            check.setdefault("autosaved", []).append(record)
            try:
                req_fields = {f.name for f in dc_fields(ResourceRequirement)}
                evaluation = evaluate_library_requirement(
                    conn, ResourceRequirement(**{
                        key: value for key, value in (check.get("requirement", {}) or {}).items()
                        if key in req_fields}))
                check["eligible_count"] = len(evaluation.eligible_assets)
                check["shortfall"] = max(0, int(check.get("required_count", 0) or 0)
                                         - len(evaluation.eligible_assets))
            except Exception:  # noqa: BLE001 - counts refresh next review
                pass
    finally:
        conn.close()
    if outcomes:
        _write_run(root, run)
    return outcomes


def build_summary(root: Path | str, run_id: str) -> dict[str, Any]:
    """Aggregate draft + checks + plans into one reviewable summary file."""
    root = Path(root)
    run = _load_run(root, run_id)
    segments = _segments(run)
    draft = run["draft"]
    content_type = str(draft.get("content_type", "short")).strip().lower() or "short"

    unresolved = _unresolved_beats(segments)
    score = score_script(segments)
    fallback = set(draft.get("fallback_beats", []) or [])
    script_section = {
        "status": "blocked" if unresolved else "ready",
        "beats": [{
            "id": str(seg.get("id", f"beat-{i + 1}")),
            "narration": seg.get("narration", "") if isinstance(seg.get("narration"), str) else "",
            "duration_seconds": seg.get("duration_seconds"),
            "visual_mode": seg.get("visual_mode"),
            "evidence_refs": seg.get("evidence_refs", []) or [],
            "generation": (seg.get("generation", {}) or {}).get("mode", "unknown")
            if isinstance(seg.get("generation"), dict)
            else ("outline_fallback" if str(seg.get("id")) in fallback else "unknown"),
            "media_attached": bool(seg.get("media_asset_id")),
        } for i, seg in enumerate(segments)],
        "unresolved_beats": unresolved,
        "score": score["score"],
        "score_components": score["components"],
        "score_findings": score["findings"][:12],
        "generation_mode": draft.get("generation_mode"),
        "llm_cost_usd": run.get("llm_cost_usd", 0.0),
    }

    arc = _story_arc(root, run)
    total_chars = sum(len(str(s.get("narration", ""))) for s in segments)
    total_seconds = sum(int(s.get("duration_seconds", 0) or 0) for s in segments
                        if isinstance(s.get("duration_seconds"), int))
    target_seconds = draft.get("duration_target_seconds")
    narrative_section = {
        "status": "ready",
        "topic": draft.get("topic", ""),
        "story_form": arc,
        "beat_roles": [{
            "beat_id": str(seg.get("id", f"beat-{i + 1}")),
            "role": arc["arc"][i] if i < len(arc["arc"]) else "continuation",
        } for i, seg in enumerate(segments)],
        "total_chars": total_chars,
        "total_seconds": total_seconds,
        "target_seconds": target_seconds,
    }

    autosaved = _autosave_assets(root, run)
    asset_section = {
        "status": "ready",
        "autosave_enabled": _env_flag(root, "ASSET_AUTOSAVE"),
        "needs": [{
            "requirement_id": check.get("requirement_id")
            or (check.get("requirement", {}) or {}).get("requirement_id"),
            "query": check.get("discovery_query", ""),
            "quantity": check.get("required_count"),
            "eligible_count": check.get("eligible_count"),
            "shortfall": check.get("shortfall"),
            "candidate_status": check.get("candidate_status"),
            "autosaved": check.get("autosaved", []) or [],
            "candidates": [{
                "candidate_id": cand.get("candidate_id"),
                "provider": cand.get("provider"),
                "title": cand.get("title"),
                "license_name": cand.get("license_name"),
                "source_tier": cand.get("source_tier", "unknown"),
            } for cand in (check.get("web_candidates", []) or [])[:5]
            if isinstance(cand, dict)],
        } for check in (run.get("asset_checks", []) or []) if isinstance(check, dict)],
    }
    if any((need.get("shortfall") or 0) > 0 and not need.get("candidates")
           and (need.get("eligible_count") or 0) == 0 for need in asset_section["needs"]):
        asset_section["status"] = "blocked"
    elif any((need.get("shortfall") or 0) > 0 for need in asset_section["needs"]):
        asset_section["status"] = "attention"

    assets, assets_note = _fetch_verified_images(root)
    decisions = select_cards(
        [dict(s) for s in segments if isinstance(s, dict)], assets, content_type)
    template_section = {
        "status": "attention" if decisions["plan"].get("warnings") else "ready",
        "decisions": [{
            "segment_id": dec["segment_id"],
            "visual_mode": dec["visual_mode"],
            "starter_id": dec["starter_id"],
            "score": dec["score"],
            "reasons": dec["reasons"],
            "warnings": dec["warnings"],
            "suggested_asset_id": dec.get("suggested_asset_id"),
        } for dec in decisions["decisions"]],
        "mode_counts": decisions["plan"].get("mode_counts", {}),
        "starters": decisions["plan"].get("starters", []),
        "warnings": decisions["plan"].get("warnings", []),
    }

    profile = voice_profile_status(root)
    preset = ""  # resolved inside voice_tts from env at synthesis time
    est_seconds = round(total_chars / 14) if total_chars else 0
    voice_section = {
        "status": "ready" if profile.get("reference_ready") else "blocked",
        "total_chars": total_chars,
        "est_seconds": est_seconds,
        "target_seconds": target_seconds,
        "preset_or_reference": preset or ("allen-reference"
                                          if profile.get("reference_ready") else "none"),
        "engine": profile.get("tts_model"),
        "note": ("Voice preview synthesizes automatically on summary approval; "
                 "listening is delegated to automated fit checks (see review).")
        if profile.get("reference_ready") else
        "Import a voice reference (or set TTS_VOICE) before approving the summary.",
    }

    sound_section = _sound_section(root, run)

    sections = {"script": script_section, "narrative": narrative_section,
                "asset": asset_section, "template": template_section,
                "voice": voice_section, "sound": sound_section}
    overall = "ready"
    for section in sections.values():
        if section["status"] == "blocked":
            overall = "blocked"
            break
        if section["status"] == "attention":
            overall = "attention"
    summary = {
        "version": SUMMARY_VERSION,
        "run_id": run_id,
        "created_at": _now(),
        "approved": bool(run.get("summary_approved")),
        "overall_status": overall,
        "sections": sections,
        "fix_requests": [],
    }
    path = _summary_path(root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def _validate_fixes(fixes: Any) -> list[dict[str, Any]]:
    if not isinstance(fixes, list):
        raise ValueError("fixes must be a list of {section, target, note}.")
    cleaned = []
    for item in fixes:
        if not isinstance(item, dict):
            raise ValueError("Each fix must be an object with section/target/note.")
        section = str(item.get("section", "")).strip().lower()
        if section not in FIXABLE_SECTIONS:
            raise ValueError(f"Fix section must be one of {', '.join(FIXABLE_SECTIONS)}.")
        target = str(item.get("target", "")).strip()
        note = str(item.get("note", "")).strip()
        if not target or not 1 <= len(note) <= 500:
            raise ValueError("Each fix needs a target and a note of 1-500 characters.")
        cleaned.append({"section": section, "target": target, "note": note})
    return cleaned


def _apply_script_fix(root: Path, run: dict[str, Any], target: str, note: str) -> dict[str, Any]:
    result = regenerate_beat(root, run, target, note)
    return {"section": "script", "target": target,
            "action": "beat regenerated per owner note",
            "llm_cost_usd": result["llm_cost_usd"],
            "dropped_media": result["dropped_media"]}


def _apply_asset_fix(root: Path, run: dict[str, Any], target: str, note: str) -> dict[str, Any]:
    checks = [c for c in (run.get("asset_checks", []) or []) if isinstance(c, dict)]
    check = next((c for c in checks
                  if c.get("requirement_id") == target
                  or (c.get("requirement", {}) or {}).get("requirement_id") == target), None)
    if check is None:
        raise ValueError(f"Asset need was not found in this run: {target}.")
    query = f"{check.get('discovery_query', '')} {note}".strip()[:250]
    resource_type = ((check.get("requirement", {}) or {}).get("resource_type") or "image")
    try:
        found, statuses, _ = search_candidates_tiered(
            query, resource_type=resource_type, limit=12, api_keys=_discovery_keys(root))
    except DiscoveryError as error:
        raise ValueError(f"Re-discovery failed: {error}") from error
    check["web_candidates"] = [asdict(item) for item in found]
    check["provider_statuses"] = [{"label": item.get("label"), "state": item.get("state")}
                                  for item in statuses]
    check["candidate_status"] = "SUGGESTIONS_ONLY" if found else "NO_CANDIDATES"
    check["discovery_query"] = query
    _write_run(root, run)
    return {"section": "asset", "target": target,
            "action": f"re-discovered with refined query ({len(found)} candidates)"}


def _apply_template_fix(root: Path, run: dict[str, Any], target: str, note: str) -> dict[str, Any]:
    draft = run.get("draft", {}) if isinstance(run.get("draft"), dict) else {}
    segments = [s for s in (draft.get("segments", []) or []) if isinstance(s, dict)]
    segment = next((s for s in segments if str(s.get("id")) == target), None)
    if segment is None:
        raise ValueError(f"Beat was not found in the draft: {target}.")
    wanted = note.strip().lower().replace(" ", "_")
    matches = [mode for mode in VISUAL_MODES if mode.lower() == wanted]
    if not matches:
        raise ValueError("Template fix note must name a visual mode "
                         f"({', '.join(sorted(VISUAL_MODES))}).")
    segment["visual_mode"] = matches[0]
    _write_run(root, run)
    return {"section": "template", "target": target,
            "action": f"visual mode set to {matches[0]}; card plan recomputed on rebuild"}


def _sound_section(root: Path, run: dict[str, Any]) -> dict[str, Any]:
    """Locked soundpack choice for this run (no discovery, no synthesis)."""
    from apps.soundpack.pack import PACK_VERSION, bed_ids, resolve_sound, sound_enabled

    draft = run.get("draft", {}) if isinstance(run.get("draft"), dict) else {}
    override = run.get("soundpack_override")
    if not sound_enabled(root):
        return {"status": "ready", "enabled": False, "pack_version": PACK_VERSION,
                "note": "SOUNDPACK_ENABLED=false: renders voice-only."}
    try:
        resolved = resolve_sound(root, str(draft.get("story_form", "")),
                                 str(draft.get("content_type", "short")), override=override)
    except ValueError as error:
        return {"status": "attention", "enabled": False, "pack_version": PACK_VERSION,
                "override": override, "note": f"{error} Renders voice-only."}
    if not resolved.get("enabled"):
        return {"status": "ready", "enabled": False, "pack_version": PACK_VERSION,
                "note": str(resolved.get("reason", "disabled by owner override"))}
    return {"status": "ready", "enabled": True, "pack_version": PACK_VERSION,
            "bed_id": resolved["bed_id"], "mood": resolved.get("mood", ""),
            "file": Path(resolved["bed_file"]).name, "license": resolved.get("license", ""),
            "stingers": [s.get("sting_id") for s in resolved.get("stingers", [])],
            "override": override,
            "choices": bed_ids(root) + ["none"],
            "note": "Fixed mapping story → bed. Fix with a bed id or none to change."}


def _apply_sound_fix(root: Path, run: dict[str, Any], target: str, note: str) -> dict[str, Any]:
    from apps.soundpack.pack import bed_ids, resolve_sound

    _ = target
    choice = note.strip().lower()
    if choice != "none":
        valid = bed_ids(root)
        if choice not in valid:
            raise ValueError("Sound fix note must be a bed id "
                             f"({', '.join(valid)}) or none.")
        draft = run.get("draft", {}) if isinstance(run.get("draft"), dict) else {}
        resolve_sound(root, str(draft.get("story_form", "")),
                      str(draft.get("content_type", "short")), override=choice)
    run["soundpack_override"] = choice
    _write_run(root, run)
    return {"section": "sound", "target": "soundpack",
            "action": f"sound override set to {choice}; applies at next render"}


def _attach_suggested_assets(root: Path, run: dict[str, Any]) -> list[dict[str, Any]]:
    """Bulk-attach verified suggested images (same rules as manual attach)."""
    import sqlite3

    from apps.asset_library.registry import connect

    segments = _segments(run)
    assets, _ = _fetch_verified_images(root)
    decisions = select_cards([dict(s) for s in segments],
                             assets, str((run.get("draft", {}) or {}).get(
                                 "content_type", "short")))
    by_id = {dec["segment_id"]: dec for dec in decisions["decisions"]}
    conn = connect(Path(root) / "runtime/engine.db")
    report: list[dict[str, Any]] = []
    try:
        for segment in segments:
            decision = by_id.get(str(segment.get("id")))
            suggested = (decision or {}).get("suggested_asset_id")
            if not suggested:
                report.append({"beat": str(segment.get("id")), "attached": None,
                               "reason": "no verified portrait suggested"})
                continue
            try:
                row = conn.execute(
                    "SELECT asset_type, rights_state, lifecycle_state, stored_path "
                    "FROM assets WHERE asset_id = ?", (suggested,)).fetchone()
            except sqlite3.Error:
                row = None
            if row is None or tuple(row[:3]) != ("image", "verified", "active"):
                report.append({"beat": str(segment.get("id")), "attached": None,
                               "reason": "suggested asset is not verified/active"})
                continue
            stored = (Path(root) / "runtime/assets/library" / str(row[3])).resolve()
            library_root = (Path(root) / "runtime/assets/library").resolve()
            if library_root not in stored.parents or not stored.is_file():
                report.append({"beat": str(segment.get("id")), "attached": None,
                               "reason": "suggested asset file is missing"})
                continue
            segment["media_asset_id"] = suggested
            report.append({"beat": str(segment.get("id")), "attached": suggested})
    finally:
        conn.close()
    _write_run(root, run)
    return report


def _bulk_approve(root: Path, run: dict[str, Any]) -> dict[str, Any]:
    """One approval driving script + assets + voice + render automatically."""
    run_id = str(run.get("run_id", ""))
    segments = _segments(run)
    bad = _unresolved_beats(segments)
    if bad:
        raise ValueError("Resolve research markers before approval: " + ", ".join(bad) + ".")
    run["script_owner_approved"] = True
    run["evidence_verified_by_owner"] = True
    run["script_approved_at"] = _now()
    run["status"] = "SCRIPT_APPROVED"
    _write_run(root, run)

    attached = _attach_suggested_assets(root, run)
    run = _load_run(root, run_id)

    voice = synthesize_voice_preview(root, run_id)
    run = _load_run(root, run_id)
    _ensure_voice_fits_script(root, run)
    run["voice_preview_audited"] = True
    run["voice_preview_audited_at"] = _now()
    run["voice_audit_method"] = "summary-bulk-auto"
    run["voice_audit_note"] = ("Owner delegated listening via summary approval; "
                               "automated checks passed: preview file present, "
                               "duration fits the video slot.")
    _write_run(root, run)

    render = render_full_run(root, run_id)
    run = _load_run(root, run_id)
    run["summary_approved"] = True
    _write_run(root, run)
    return {
        "attached": attached,
        "voice": {"audio_url": voice.get("audio_url"), "engine": voice.get("engine"),
                  "audited": True, "method": "summary-bulk-auto"},
        "render": {"path": f"runtime/renders/{run_id}/full-render.mp4",
                   "report": f"runtime/renders/{run_id}/render-report.json",
                   "detail": render},
        "next_action": "Review the render in Runs, then plan/stage distribution (publish stays manual).",
    }


def review_summary(
    root: Path | str, run_id: str, approved: bool, fixes: Any = None,
) -> dict[str, Any]:
    """Apply fix checkboxes or drive the bulk-approval chain. Returns fresh summary."""
    root = Path(root)
    fixes = _validate_fixes(fixes or [])
    if approved and fixes:
        raise ValueError("Approve with no open fixes, or send fixes with approved=false.")
    run = _load_run(root, run_id)
    _segments(run)

    applied: list[dict[str, Any]] = []
    results: dict[str, Any] = {}
    if fixes:
        for fix in fixes:
            section, target, note = fix["section"], fix["target"], fix["note"]
            if section == "script":
                applied.append(_apply_script_fix(root, run, target, note))
                run = _load_run(root, run_id)
            elif section == "asset":
                applied.append(_apply_asset_fix(root, run, target, note))
                run = _load_run(root, run_id)
            elif section == "template":
                applied.append(_apply_template_fix(root, run, target, note))
                run = _load_run(root, run_id)
            elif section == "sound":
                applied.append(_apply_sound_fix(root, run, target, note))
                run = _load_run(root, run_id)
            else:
                applied.append({"section": section, "target": target,
                                "action": "noted; voice regenerates after approval, "
                                          "narrative recomputes from script"})
        run["summary_approved"] = False
        _write_run(root, run)
    if approved:
        results = _bulk_approve(root, run)
        run = _load_run(root, run_id)

    summary = build_summary(root, run_id)
    summary["fix_requests"] = applied
    if results:
        summary["results"] = results
    path = _summary_path(root, run_id)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
