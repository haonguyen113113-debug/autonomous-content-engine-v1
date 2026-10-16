"""Owner-ordered auto-acquisition (standing order 2026-10-16).

When the library lacks a verified asset, the engine searches built-in
providers itself, verifies each candidate (identity terms, license
allowlist, resolution floor) and ingests the best one — no per-item
download approval round-trip. Every decision is logged with reasons;
rejected candidates carry their reject reason. External *acquisition*
still never invents provenance: download + sidecar + registry ingest go
through the existing save_commons_candidate path.
"""
from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

_ALLOWED_LICENSE_HINTS = ("CC0", "PUBLIC DOMAIN", "PIXABAY")


def _license_ok(license_name: str) -> bool:
    text = str(license_name or "").upper()
    if any(hint in text for hint in _ALLOWED_LICENSE_HINTS):
        return True
    if "CC BY" in text and "NC" not in text and "ND" not in text:
        return True
    return False


def _title_ok(title: str, include_terms: list[str], exclude_terms: list[str]) -> tuple[bool, str]:
    lowered = str(title or "").lower()
    for term in exclude_terms:
        if term.lower() in lowered:
            return False, f"exclude term: {term}"
    for term in include_terms:
        if term.lower() not in lowered:
            return False, f"missing include term: {term}"
    return True, ""


def auto_acquire(root: Path, *, query: str, resource_type: str = "image",
                 include_terms: list[str] | None = None,
                 exclude_terms: list[str] | None = None,
                 min_width: int = 960, limit: int = 12,
                 api_keys: dict | None = None,
                 requirement_id: str = "auto-acquire-1",
                 purpose: str = "match_analysis_evidence",
                 context: str = "") -> dict[str, Any]:
    """Search, verify, ingest top-1. Returns audit trail + asset_id."""
    from apps.asset_library.asset_intelligence import ResourceRequirement
    from apps.asset_library.discovery import save_commons_candidate, search_candidates_tiered

    include_terms = include_terms or []
    exclude_terms = exclude_terms or []
    candidates, statuses, report = search_candidates_tiered(
        query, resource_type=resource_type, limit=limit, api_keys=api_keys)
    seen: list[dict[str, Any]] = []
    for cand in candidates:
        ok_license = _license_ok(getattr(cand, "license_name", ""))
        ok_title, title_reason = _title_ok(getattr(cand, "title", ""), include_terms, exclude_terms)
        width = int(getattr(cand, "width", 0) or 0)
        ok_size = width >= min_width
        reasons = []
        if not ok_license:
            reasons.append(f"license rejected: {getattr(cand, 'license_name', '')}")
        if not ok_title:
            reasons.append(title_reason)
        if not ok_size:
            reasons.append(f"too small: {width}px < {min_width}px")
        entry = {"candidate_id": cand.candidate_id, "title": cand.title,
                 "license": cand.license_name, "width": width,
                 "accepted": not reasons, "reasons": reasons}
        seen.append(entry)
        if reasons:
            continue
        requirement = ResourceRequirement(
            requirement_id=requirement_id, resource_type=resource_type,
            purpose=purpose, context=context or None)
        saved = save_commons_candidate(
            root, cand.candidate_id, requirement,
            rights_reviewed=True, api_keys=api_keys)
        saved["standing_order"] = "owner 16/10: auto-find + auto-add when verified"
        return {"status": "INGESTED", "asset_id": saved["asset_id"],
                "candidate": entry, "seen": seen, "tier_report": report,
                "standing_order": saved["standing_order"]}
    return {"status": "NO_QUALIFIED_CANDIDATE", "asset_id": None,
            "seen": seen, "tier_report": report,
            "standing_order": "owner 16/10: auto-find + auto-add when verified"}
