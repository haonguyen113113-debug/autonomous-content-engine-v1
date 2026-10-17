"""Per-purpose rights scope for library assets.

Problem this solves: the library gates reuse on ``rights_state`` (``verified``
vs ``unverified``), which only answers "is this image suitable / identity-checked".
It never answers "may this asset be used for THIS upload" — target platform,
territory, commercial/monetization use, expiry, edit, credit, clip count.
``verified`` must therefore NEVER be read as "usable for every video".

This module owns the second gate. The unified entry point consumed by
discovery / planner / QA is::

    is_usable_for(asset, purpose) -> {
        "allowed": bool,
        "reasons": [...],
        "required_action": "human_review" | "none",
        "scope": {
            "platforms": [...], "territories": [...],
            "commercial": bool, "monetization": bool,
            "expires_at": "YYYY-MM-DD" | None,
            "edit_allowed": bool,
            "credit": {"required": bool, "text": str | None},
            "clip_limit": int | None,
        },
    }

Hard rules (non-negotiable):

* Unknown rights default to ``allowed=False``. YouTube-sourced or otherwise
  unclear provenance/license is denied and routed to ``human_review``.
* A copyright exception (disputed ownership, rights-managed / editorial-only
  grant, takedown risk, unlicensed mark) ALWAYS denies and requires a human.
  An LLM must never clear or conclude such a case; the flag can only be
  cleared by a human re-review that records new evidence.
* Storage is a versioned JSON scope (``RIGHTS_SCOPE_SCHEMA_VERSION``) in the
  ``rights_scope_json`` column, added/backfilled idempotently by
  :func:`ensure_rights_scope_schema` without touching any other table or the
  shared ``database.py`` migration chain.

Ownership note: this file (``apps/asset_library/rights*.py``) plus
``tests/test_*rights*.py`` and ``docs/rights-scope*.md`` are the only paths
this workstream edits. Discovery adapters, renderers, ``crests.py`` and the
released 12.0.0 pack are intentionally NOT modified; crest entries are
*read* through :func:`crest_entry_to_scope` as a rights-gated sample.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlparse

RIGHTS_SCOPE_SCHEMA_VERSION = 1

REQUIRED_HUMAN_REVIEW = "human_review"
REQUIRED_NONE = "none"

# Reasons that force a human decision (LLM/planner must not conclude).
_HUMAN_REVIEW_REASONS = frozenset({
    "rights-scope-missing",
    "rights-scope-version-unsupported",
    "rights-scope-invalid",
    "copyright-exception-requires-human",
    "rights-not-verified",
    "unknown-source-or-license",
    "rights-expired",
    "rights-expiry-unclear",
})

_UNKNOWN_SOURCES = frozenset({
    "", "unknown", "unclear", "pending", "youtube",
    "owner-supplied (pending)", "tbd",
})

_UNKNOWN_LICENSES = frozenset({
    "", "unknown", "unclear", "pending", "pending owner grant",
    "tbd", "to be confirmed",
})

_YOUTUBE_HOSTS = frozenset({
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "youtu.be", "www.youtu.be", "youtube-nocookie.com",
})

_OWNED_LICENSES = frozenset({
    "owned", "self-created", "self_created", "owner-supplied",
    "owner_supplied", "owner", "channel-owned", "channel_owned",
})

_WILDCARD_TERRITORIES = frozenset({"*", "worldwide", "global", "ww", "all"})

_SOCIAL_GRANT = ["youtube", "tiktok", "facebook", "instagram"]


def _norm_token(value: Any) -> str:
    return str(value or "").strip().casefold()


def _today_str(now: Any = None) -> str:
    if now is None:
        return datetime.now(timezone.utc).date().isoformat()
    if isinstance(now, datetime):
        return now.date().isoformat()
    if isinstance(now, date):
        return now.isoformat()
    text = str(now).strip()
    if not text:
        return datetime.now(timezone.utc).date().isoformat()
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        pass
    match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)
    raise ValueError(f"Unparseable date: {now!r}")


def _parse_expires_at(value: Any) -> str | None:
    """Normalize an expiry to ``YYYY-MM-DD``; None means no known expiry."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        pass
    match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"Unparseable expires_at: {value!r}")


def validate_scope(scope: Mapping[str, Any]) -> list[str]:
    """Return a list of validation errors ([] means valid)."""
    errors: list[str] = []
    if not isinstance(scope, Mapping):
        return ["scope-must-be-a-mapping"]
    if scope.get("schema_version") != RIGHTS_SCOPE_SCHEMA_VERSION:
        errors.append(
            f"unsupported-schema-version:{scope.get('schema_version')!r}"
        )
        return errors
    for key in ("platforms", "territories"):
        value = scope.get(key)
        if not isinstance(value, list) or not all(
            isinstance(v, str) and v.strip() for v in value
        ):
            errors.append(f"{key}-must-be-a-list-of-non-empty-strings")
    for key in ("commercial", "monetization", "edit_allowed"):
        if not isinstance(scope.get(key), bool):
            errors.append(f"{key}-must-be-boolean")
    try:
        expires = scope.get("expires_at")
        if expires is not None:
            _parse_expires_at(expires)
    except ValueError:
        errors.append("expires_at-unparseable")
    credit = scope.get("credit")
    if not isinstance(credit, Mapping):
        errors.append("credit-must-be-a-mapping")
    else:
        if not isinstance(credit.get("required"), bool):
            errors.append("credit.required-must-be-boolean")
        text = credit.get("text")
        if text is not None and not isinstance(text, str):
            errors.append("credit.text-must-be-string-or-null")
    clip_limit = scope.get("clip_limit")
    if clip_limit is not None and (
        not isinstance(clip_limit, int) or isinstance(clip_limit, bool)
        or clip_limit < 0
    ):
        errors.append("clip_limit-must-be-a-non-negative-int-or-null")
    return errors


def build_rights_scope(
    *,
    platforms: list[str] | None = None,
    territories: list[str] | None = None,
    commercial: bool = False,
    monetization: bool = False,
    expires_at: Any = None,
    edit_allowed: bool = False,
    credit_required: bool = False,
    credit_text: str | None = None,
    clip_limit: int | None = None,
    license: str | None = None,  # noqa: A002 - stored grant label, not builtin use
    source: str | None = None,
    reviewed_by: str | None = None,
    reviewed_at: Any = None,
    copyright_exception: bool = False,
    notes: str | None = None,
) -> dict[str, Any]:
    """Construct a human-granted scope; raises ValueError when invalid.

    Call this at approval time (owner/human review UI): the human fills the
    upload-intent grant explicitly instead of the machine inferring it.
    """
    scope: dict[str, Any] = {
        "schema_version": RIGHTS_SCOPE_SCHEMA_VERSION,
        "platforms": [str(p).strip() for p in (platforms or []) if str(p).strip()],
        "territories": [str(t).strip() for t in (territories or []) if str(t).strip()],
        "commercial": bool(commercial),
        "monetization": bool(monetization),
        "expires_at": _parse_expires_at(expires_at),
        "edit_allowed": bool(edit_allowed),
        "credit": {
            "required": bool(credit_required),
            "text": str(credit_text).strip() or None
            if credit_text is not None else None,
        },
        "clip_limit": clip_limit,
        # Provenance extras: stored with the grant, stripped from the
        # is_usable_for() output scope so the cross-workstream shape stays stable.
        "license": str(license).strip() if license else None,
        "source": str(source).strip() if source else None,
        "granted_by": "human",
        "reviewed_by": reviewed_by,
        "reviewed_at": _today_str(reviewed_at) if reviewed_at else None,
        "copyright_exception": bool(copyright_exception),
        "notes": notes,
    }
    errors = validate_scope(scope)
    if errors:
        raise ValueError(f"Invalid rights scope: {errors}")
    return scope


def default_deny_scope(
    *,
    license: str | None = None,
    source: str | None = None,
    copyright_exception: bool = False,
    notes: str | None = None,
) -> dict[str, Any]:
    """Deny-by-default scope for new/unclear assets (never grants anything)."""
    return {
        "schema_version": RIGHTS_SCOPE_SCHEMA_VERSION,
        "platforms": [],
        "territories": [],
        "commercial": False,
        "monetization": False,
        "expires_at": None,
        "edit_allowed": False,
        "credit": {"required": True, "text": None},
        "clip_limit": 0,
        "license": str(license).strip() if license else None,
        "source": str(source).strip() if source else None,
        "granted_by": "deny-default",
        "reviewed_by": None,
        "reviewed_at": None,
        "copyright_exception": bool(copyright_exception),
        "notes": notes or "deny by default: rights unclear, needs human review",
    }


def _classify_license(license_name: Any) -> str:
    """Classify a stored license label: owned/open/restricted/unknown."""
    text = str(license_name or "").strip()
    if _norm_token(text) in _UNKNOWN_LICENSES:
        return "unknown"
    upper = text.upper()
    if _norm_token(text).replace("_", "-") in _OWNED_LICENSES or _norm_token(text) in _OWNED_LICENSES:
        return "owned"
    if re.search(r"\bNC\b", upper):
        return "restricted-nc"
    if re.search(r"\bND\b", upper):
        return "restricted-nd"
    if "RIGHTS-MANAGED" in upper or "RIGHTS MANAGED" in upper:
        return "restricted-managed"
    if "EDITORIAL" in upper:
        return "restricted-editorial"
    if "CC0" in upper or "PUBLIC DOMAIN" in upper or re.search(r"\bPDM\b", upper):
        return "open"
    if re.search(r"\bCC\b.*\bBY\b", upper) or "CC BY" in upper:
        return "open-attribution"
    if "PIXABAY" in upper or "PEXELS" in upper:
        return "open-attribution"
    return "unknown"


def _credit_text(asset: Mapping[str, Any], license_name: str | None) -> str | None:
    metadata = asset.get("metadata")
    if isinstance(metadata, Mapping):
        for key in ("license_credit", "credit", "attribution"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    creator = asset.get("creator")
    if isinstance(creator, str) and creator.strip() and license_name:
        return f"{creator.strip()} / {license_name.strip()}"
    if isinstance(creator, str) and creator.strip():
        return creator.strip()
    return None


def _metadata_dict(asset: Mapping[str, Any]) -> dict[str, Any]:
    metadata = asset.get("metadata")
    if isinstance(metadata, Mapping):
        return dict(metadata)
    raw = asset.get("metadata_json")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def scope_from_legacy(asset: Mapping[str, Any]) -> dict[str, Any]:
    """Best-effort backfill scope for rows that predate rights scopes.

    Known open / owner licenses keep a conservative social grant so
    previously working inventory keeps working; anything unclear becomes a
    deny-default that forces human review. Deterministic and safe to rerun.
    """
    asset = dict(asset or {})
    metadata = _metadata_dict(asset)
    asset["metadata"] = metadata
    license_name = asset.get("license_type")
    if license_name is None:
        license_name = metadata.get("license_type")
    source_type = _norm_token(asset.get("source_type") or metadata.get("source_type"))
    classification = _classify_license(license_name)
    exception = bool(
        asset.get("copyright_exception") is True
        or metadata.get("copyright_exception") is True
        or metadata.get("rights_disputed") is True
        or classification in {"restricted-managed", "restricted-editorial"}
    )
    expires_at: str | None = None
    for key in ("expires_at", "expiry", "rights_expires_at"):
        candidate = metadata.get(key, asset.get(key))
        if candidate:
            try:
                expires_at = _parse_expires_at(candidate)
            except ValueError:
                expires_at = None
            break
    clip_limit: int | None = None
    for key in ("clip_limit", "max_clips", "use_limit"):
        candidate = metadata.get(key, asset.get(key))
        if isinstance(candidate, int) and not isinstance(candidate, bool) and candidate >= 0:
            clip_limit = candidate
            break
    if classification == "owned":
        scope = build_rights_scope(
            platforms=list(_SOCIAL_GRANT),
            territories=["*"],
            commercial=True,
            monetization=True,
            expires_at=expires_at,
            edit_allowed=True,
            credit_required=False,
            credit_text=None,
            clip_limit=clip_limit,
            license=str(license_name) if license_name else None,
            source=asset.get("source_type"),
            copyright_exception=exception,
            notes="backfilled-v1: owner/owned license",
        )
        scope["granted_by"] = "backfill-allow"
        return scope
    if classification in {"open", "open-attribution"}:
        needs_credit = classification == "open-attribution"
        scope = build_rights_scope(
            platforms=list(_SOCIAL_GRANT),
            territories=["*"],
            commercial=True,
            monetization=True,
            expires_at=expires_at,
            edit_allowed=classification != "restricted-nd",
            credit_required=needs_credit,
            credit_text=_credit_text(asset, str(license_name)) if needs_credit else None,
            clip_limit=clip_limit,
            license=str(license_name) if license_name else None,
            source=asset.get("source_type"),
            copyright_exception=exception,
            notes="backfilled-v1: open license allowlist",
        )
        scope["granted_by"] = "backfill-allow"
        return scope
    if classification in {"restricted-nc", "restricted-nd"}:
        # Terms are known but narrow: keep the grant explicit and narrow so
        # planner denials carry the exact reason instead of a vague unknown.
        scope = build_rights_scope(
            platforms=list(_SOCIAL_GRANT),
            territories=["*"],
            commercial=False,
            monetization=False,
            expires_at=expires_at,
            edit_allowed=False,
            credit_required=True,
            credit_text=_credit_text(asset, str(license_name)),
            clip_limit=clip_limit,
            license=str(license_name) if license_name else None,
            source=asset.get("source_type"),
            copyright_exception=exception,
            notes=f"backfilled-v1: {classification}, non-commercial/no-derivs",
        )
        scope["granted_by"] = "backfill-allow"
        return scope
    return default_deny_scope(
        license=str(license_name) if license_name else None,
        source=asset.get("source_type"),
        copyright_exception=True if source_type in _UNKNOWN_SOURCES or exception else exception,
        notes="backfilled-v1: license/source unclear, needs human review",
    )


def _parse_crest_allowed_use(text: Any) -> dict[str, Any]:
    """Parse a crest manifest ``allowed_use`` string into grant tokens.

    Freeform owner text (e.g. ``"broadcast+social 2026-27"``, ``"pending"``).
    Anything unrecognized stays conservative: no platforms granted, which
    denies with a human-review routing instead of guessing.
    """
    raw = str(text or "")
    lowered = raw.casefold()
    if not lowered.strip() or "pending" in lowered or "tbd" in lowered:
        return {"platforms": [], "territories": [], "expires_at": None}
    platforms: list[str] = []
    if "social" in lowered:
        platforms.extend(_SOCIAL_GRANT)
    for token in ("youtube", "tiktok", "facebook", "instagram", "broadcast"):
        if token in lowered and token not in platforms:
            platforms.append(token)
    territories = ["*"]
    if re.search(r"\bvietnam\b|\bvn\b", lowered):
        territories = ["VN"]
    expires_at: str | None = None
    range_match = re.search(r"(19|20)\d{2}\s*[-\u2013/\s]\s*(\d{2,4})", lowered)
    if range_match:
        tail = range_match.group(2)
        start_year = int(range_match.group(0)[:4])
        end_year = int(tail) if len(tail) == 4 else (start_year // 100 * 100 + int(tail))
        expires_at = f"{end_year:04d}-12-31"
    else:
        single = re.search(r"\b((?:19|20)\d{2})\b", lowered)
        if single:
            expires_at = f"{single.group(1)}-12-31"
    return {"platforms": platforms, "territories": territories, "expires_at": expires_at}


def crest_entry_to_scope(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt an ``assets/crests/manifest.json`` entry to a rights scope.

    Read-only adapter (``apps/sportskit/crests.py`` is NOT modified). An entry
    is grant-bearing only when the owner reviewed it AND ``allowed_use``
    parses to at least one platform; otherwise it is a deny-default so the
    renderer keeps the monogram fallback.
    """
    entry = dict(entry or {})
    reviewed = entry.get("rights_reviewed") is True
    parsed = _parse_crest_allowed_use(entry.get("allowed_use"))
    license_name = entry.get("license")
    if reviewed and parsed["platforms"]:
        return build_rights_scope(
            platforms=parsed["platforms"],
            territories=parsed["territories"],
            commercial=True,
            monetization=True,
            expires_at=parsed["expires_at"],
            # Fit-to-slot placement (resize/circle-crop into the crest ring)
            # only; no recolor, distortion, or overlay on the mark.
            edit_allowed=True,
            credit_required=False,
            credit_text=None,
            clip_limit=None,
            license=str(license_name) if license_name else None,
            source=entry.get("source"),
            reviewed_at=entry.get("acquired_at") or None,
            copyright_exception=False,
            notes=f"crest grant: {entry.get('club_slug')} (placement fit only)",
        )
    return default_deny_scope(
        license=str(license_name) if license_name else None,
        source=entry.get("source"),
        copyright_exception=True,
        notes=f"crest not cleared: {entry.get('club_slug', '?')}; use monogram",
    )


def scope_from_asset(asset: Mapping[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(scope, derivation)`` for any asset-like mapping.

    Accepts library rows (explicit ``rights_scope`` / ``rights_scope_json`` /
    ``metadata.rights_scope``), crest manifest entries, and legacy rows
    (derived via :func:`scope_from_legacy`). Never raises on shape variance:
    unparseable stored scopes become deny-defaults with the parse error noted.
    """
    asset = dict(asset or {})
    derivation: dict[str, Any] = {"origin": "deny-default", "errors": []}
    # Precedence is fixed: the persisted rights_scope_json column is the
    # source of truth, then an in-memory rights_scope mapping, then a
    # metadata-embedded scope. First valid scope wins.
    candidates: list[Any] = [asset.get("rights_scope_json"), asset.get("rights_scope")]
    metadata = asset.get("metadata")
    if isinstance(metadata, Mapping) and "rights_scope" in metadata:
        candidates.append(metadata["rights_scope"])
    else:
        raw_meta = asset.get("metadata_json")
        if isinstance(raw_meta, str) and "rights_scope" in raw_meta:
            try:
                parsed_meta = json.loads(raw_meta)
                if isinstance(parsed_meta, dict) and "rights_scope" in parsed_meta:
                    candidates.append(parsed_meta["rights_scope"])
            except (ValueError, TypeError) as exc:
                derivation["errors"].append(f"metadata_json-unparseable:{exc}")
    for candidate in candidates:
        if candidate is None or candidate == "":
            continue
        if isinstance(candidate, str):
            try:
                candidate = json.loads(candidate)
            except (ValueError, TypeError) as exc:
                derivation["errors"].append(f"rights_scope_json-unparseable:{exc}")
                continue
        if isinstance(candidate, Mapping):
            scope = dict(candidate)
            errors = validate_scope(scope)
            if errors:
                derivation["errors"].append(f"stored-scope-invalid:{errors}")
                continue
            derivation["origin"] = scope.get("granted_by", "explicit")
            return scope, derivation
        derivation["errors"].append("stored-scope-not-a-mapping")
    # Crest manifest shape (club_slug + rights_reviewed + allowed_use).
    if "club_slug" in asset and "rights_reviewed" in asset:
        derivation["origin"] = "crest-manifest"
        return crest_entry_to_scope(asset), derivation
    if asset:
        derivation["origin"] = "legacy-backfill"
        return scope_from_legacy(asset), derivation
    return default_deny_scope(notes="no asset supplied"), derivation


def normalize_purpose(purpose: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize an upload-intent purpose; missing fields stay explicit Nones."""
    purpose = dict(purpose or {})
    territories = purpose.get("territories")
    territory = purpose.get("territory")
    if territory is None and isinstance(territories, (list, tuple)) and territories:
        territory = territories[0]
    return {
        "platform": str(purpose.get("platform")).strip() if purpose.get("platform") else None,
        "territory": str(territory).strip() if territory else None,
        "commercial": bool(purpose.get("commercial", False)),
        "monetization": bool(purpose.get("monetization", False)),
        "edit": bool(purpose.get("edit", False)),
        "credit_planned": bool(purpose.get("credit_planned", False)),
        "credit_text": purpose.get("credit_text"),
        "use_count": int(purpose.get("use_count", 0) or 0),
        "now": _today_str(purpose.get("now")),
    }


def _output_scope(scope: Mapping[str, Any]) -> dict[str, Any]:
    credit = scope.get("credit") if isinstance(scope.get("credit"), Mapping) else {}
    return {
        "platforms": list(scope.get("platforms") or []),
        "territories": list(scope.get("territories") or []),
        "commercial": bool(scope.get("commercial", False)),
        "monetization": bool(scope.get("monetization", False)),
        "expires_at": scope.get("expires_at"),
        "edit_allowed": bool(scope.get("edit_allowed", False)),
        "credit": {
            "required": bool(credit.get("required", False)),
            "text": credit.get("text"),
        },
        "clip_limit": scope.get("clip_limit"),
    }


def _source_is_youtube(source_url: Any) -> bool:
    try:
        host = (urlparse(str(source_url)).hostname or "").casefold()
    except (ValueError, TypeError):
        return False
    return any(host == known or host.endswith(f".{known}") for known in _YOUTUBE_HOSTS)


def is_usable_for(
    asset: Mapping[str, Any] | None,
    purpose: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Decide whether ``asset`` may be used for upload intent ``purpose``.

    ``purpose`` keys: ``platform`` (e.g. ``"youtube"``), ``territory`` (ISO,
    e.g. ``"VN"``), ``commercial`` / ``monetization`` / ``edit`` /
    ``credit_planned`` bools, ``use_count`` int (clips already using the
    asset), ``now`` (ISO date, defaults to today UTC).

    ``verified`` (image suitability) is necessary but never sufficient: an
    asset with no usable scope is denied even when verified.
    """
    scope, derivation = scope_from_asset(asset)
    asset_map = dict(asset or {})
    metadata = _metadata_dict(asset_map)
    want = normalize_purpose(purpose)
    reasons: list[str] = []

    if derivation["origin"] == "deny-default" and not asset:
        reasons.append("rights-scope-missing")
    if derivation["errors"]:
        reasons.append("rights-scope-invalid")

    if scope.get("copyright_exception") is True or asset_map.get(
        "copyright_exception"
    ) is True or metadata.get("copyright_exception") is True or metadata.get(
        "rights_disputed"
    ) is True:
        reasons.append("copyright-exception-requires-human")

    rights_state = str(asset_map.get("rights_state") or "")
    rights_ok = rights_state.strip().casefold().startswith("verified") or (
        asset_map.get("rights_reviewed") is True
    )
    if not rights_ok:
        reasons.append("rights-not-verified")

    lifecycle = asset_map.get("lifecycle_state")
    if lifecycle is not None and _norm_token(lifecycle) != "active":
        reasons.append("lifecycle-not-active")

    granted_by = scope.get("granted_by", "deny-default")
    if granted_by != "human":
        license_label = scope.get("license")
        source_label = scope.get("source") or asset_map.get("source_type")
        source_url = asset_map.get("source_url") or metadata.get("source_url")
        unclear = (
            _norm_token(license_label) in _UNKNOWN_LICENSES
            or _norm_token(source_label) in _UNKNOWN_SOURCES
            or _source_is_youtube(source_url)
            or (not license_label and not scope.get("platforms"))
        )
        if unclear:
            reasons.append("unknown-source-or-license")

    expires_at = scope.get("expires_at")
    if expires_at:
        try:
            if want["now"] > _parse_expires_at(expires_at):
                reasons.append("rights-expired")
        except ValueError:
            reasons.append("rights-expiry-unclear")

    if not want["platform"]:
        reasons.append("platform-not-specified")
    elif not any(
        _norm_token(p) == "*" or _norm_token(p) == _norm_token(want["platform"])
        for p in (scope.get("platforms") or [])
    ):
        reasons.append(f"platform-not-granted:{want['platform']}")

    if not want["territory"]:
        reasons.append("territory-not-specified")
    elif not any(
        _norm_token(t) in _WILDCARD_TERRITORIES
        or _norm_token(t) == _norm_token(want["territory"])
        for t in (scope.get("territories") or [])
    ):
        reasons.append(f"territory-not-granted:{want['territory']}")

    if want["commercial"] and not scope.get("commercial"):
        reasons.append("commercial-not-granted")
    if want["monetization"] and not scope.get("monetization"):
        reasons.append("monetization-not-granted")
    if want["edit"] and not scope.get("edit_allowed"):
        reasons.append("edit-not-allowed")

    credit = scope.get("credit") if isinstance(scope.get("credit"), Mapping) else {}
    if credit.get("required") is True and not want["credit_planned"]:
        reasons.append("credit-required-unplanned")

    clip_limit = scope.get("clip_limit")
    if isinstance(clip_limit, int) and not isinstance(clip_limit, bool):
        if want["use_count"] >= clip_limit:
            reasons.append(f"clip-limit-reached:{want['use_count']}/{clip_limit}")

    if not reasons:
        reasons = ["ok"]
        if credit.get("required") is True:
            reasons.append("credit-planned")

    allowed = reasons == ["ok"] or reasons == ["ok", "credit-planned"]
    if allowed:
        required_action = REQUIRED_NONE
    else:
        required_action = (
            REQUIRED_HUMAN_REVIEW
            if any(
                r in _HUMAN_REVIEW_REASONS or r.startswith("rights-expired")
                for r in reasons
            )
            else REQUIRED_NONE
        )

    return {
        "allowed": allowed,
        "reasons": reasons,
        "required_action": required_action,
        "scope": _output_scope(scope),
    }


def ensure_rights_scope_schema(conn: sqlite3.Connection) -> dict[str, Any]:
    """Idempotent storage migration for rights scopes.

    Adds ``assets.rights_scope_json`` when missing and backfills NULL rows
    from legacy license/source fields. Existing non-NULL scopes are never
    overwritten, so reruns only fill gaps left by concurrent writers.
    Deliberately does NOT touch ``schema_migrations`` (owned by
    ``apps/asset_library/database.py``); a future migration-4 wiring can call
    this function instead of duplicating the logic.
    """
    tables = {
        row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    if "assets" not in tables:
        return {
            "schema_version": RIGHTS_SCOPE_SCHEMA_VERSION,
            "added_column": False,
            "backfilled": 0,
            "preserved": 0,
            "note": "no-assets-table",
        }
    columns = {row[1] for row in conn.execute("PRAGMA table_info(assets)").fetchall()}
    added_column = False
    if "rights_scope_json" not in columns:
        conn.execute("ALTER TABLE assets ADD COLUMN rights_scope_json TEXT")
        added_column = True
    backfilled = 0
    preserved = 0
    cursor = conn.execute(
        "SELECT asset_id, license_type, source_type, source_url, creator,"
        " rights_state, lifecycle_state, metadata_json, rights_scope_json"
        " FROM assets"
    )
    col_names = [description[0] for description in cursor.description or ()]
    for row in cursor.fetchall():
        record = dict(zip(col_names, row))
        if record.get("rights_scope_json"):
            try:
                stored = json.loads(record["rights_scope_json"])
                if not validate_scope(stored):
                    preserved += 1
                    continue
            except (ValueError, TypeError, AttributeError):
                pass  # corrupt stored scope: backfill below overwrites it
            else:
                preserved += 1
                continue
        scope = scope_from_legacy(record)
        conn.execute(
            "UPDATE assets SET rights_scope_json = ? WHERE asset_id = ?",
            (
                json.dumps(scope, ensure_ascii=False, sort_keys=True),
                record["asset_id"],
            ),
        )
        backfilled += 1
    conn.commit()
    return {
        "schema_version": RIGHTS_SCOPE_SCHEMA_VERSION,
        "added_column": added_column,
        "backfilled": backfilled,
        "preserved": preserved,
    }


__all__ = [
    "RIGHTS_SCOPE_SCHEMA_VERSION",
    "REQUIRED_HUMAN_REVIEW",
    "REQUIRED_NONE",
    "build_rights_scope",
    "crest_entry_to_scope",
    "default_deny_scope",
    "ensure_rights_scope_schema",
    "is_usable_for",
    "normalize_purpose",
    "scope_from_asset",
    "scope_from_legacy",
    "validate_scope",
]
