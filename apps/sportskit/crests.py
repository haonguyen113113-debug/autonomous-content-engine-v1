"""Licensed club-crest store: resolve owner-supplied crest files.

Policy: only files the owner places in ``assets/crests/`` with a manifest
entry whose ``rights_reviewed`` is true may be used. Everything else
(including Man City / PSG until the owner supplies them) resolves to None
so renderers keep the monogram-initials fallback. Nothing here downloads
or copies anything from the network.

Integration spec for replacing monograms with crest images lives in
``assets/crests/README.md`` §5 (not implemented yet: render path, palette
gates and proof bytes must not change until the first licensed file lands).
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CRESTS_DIR = ROOT / "assets" / "crests"
MANIFEST = CRESTS_DIR / "manifest.json"
CLUBS_JSON = ROOT / "data" / "entities" / "clubs.json"

ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
REQUIRED_ENTRY_KEYS = {
    "club_slug": str,
    "file": (str, type(None)),
    "source": str,
    "license": str,
    "acquired_at": str,
    "rights_reviewed": bool,
    "allowed_use": str,
}


def normalize_club_key(value: str) -> str:
    """Case-insensitive, accent-stripped key (đ->d, non-alnum dropped)."""
    text = str(value or "").replace("Đ", "d").replace("đ", "d")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def _initials(canonical: str) -> str:
    words = re.findall(r"[A-Za-zÀ-ỹĐđ]+", str(canonical))
    return "".join(w[0] for w in words)


def _club_index() -> dict[str, str]:
    """Normalized name/alias/initials -> club slug from clubs.json."""
    try:
        records = json.loads(CLUBS_JSON.read_text(encoding="utf-8")).get("records", [])
    except (OSError, ValueError, AttributeError):
        return {}
    index: dict[str, str] = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        slug = str(rec.get("slug", "")).strip()
        if not slug:
            continue
        candidates = [slug, rec.get("canonical_name", ""), rec.get("entity_id", "")]
        entity_id = str(rec.get("entity_id", ""))
        if ":" in entity_id:
            candidates.append(entity_id.split(":", 1)[1])
        for alias in rec.get("aliases", []) or []:
            if isinstance(alias, dict) and alias.get("alias"):
                candidates.append(alias["alias"])
        initials = _initials(str(rec.get("canonical_name", "")))
        if len(initials) >= 2:
            candidates.append(initials)
        for cand in candidates:
            key = normalize_club_key(cand)
            if key and key not in index:
                index[key] = slug
    return index


def _manifest_entries() -> list[dict]:
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = data.get("crests", []) if isinstance(data, dict) else []
    return [e for e in entries if isinstance(e, dict)]


def _entry_file(entry: dict) -> Path | None:
    """Validated on-disk crest path, or None (unusable entry)."""
    if entry.get("rights_reviewed") is not True:
        return None
    name = entry.get("file")
    if not isinstance(name, str) or not name.strip():
        return None
    candidate = (CRESTS_DIR / Path(name.strip()).name).resolve()
    try:
        candidate.relative_to(CRESTS_DIR.resolve())
    except ValueError:
        return None
    if candidate.suffix.lower() not in ALLOWED_SUFFIXES:
        return None
    if not candidate.is_file():
        return None
    return candidate


def resolve_crest(club_name_or_slug: str) -> Path | None:
    """Return the licensed crest file for a club, or None (use monogram).

    Matches slug / canonical name / alias / entity id / initials,
    case-insensitive with accents stripped. Never raises; any miss,
    unreviewed entry, missing file or unreadable store means None.
    """
    try:
        key = normalize_club_key(club_name_or_slug)
        if not key:
            return None
        slug = _club_index().get(key)
        if slug is None:
            # Fall back to treating the input itself as a slug.
            slug = str(club_name_or_slug).strip().lower()
        for entry in _manifest_entries():
            if str(entry.get("club_slug", "")).strip().lower() != slug:
                continue
            found = _entry_file(entry)
            if found is not None:
                return found
            return None
        return None
    except Exception:
        return None


def crest_status(want: Iterable[str] | None = None) -> dict[str, dict]:
    """Audit helper: per-club licensing state (licensed/file/reason).

    ``want`` defaults to every slug present in the manifest. Slugs unknown
    to clubs.json are still reported (reason ``unknown-club``) so typos
    in the manifest surface in audits.
    """
    entries = {str(e.get("club_slug", "")).strip().lower(): e
               for e in _manifest_entries()}
    index = _club_index()
    index_slugs = set(index.values())

    def _to_slug(raw: str) -> str:
        key = normalize_club_key(raw)
        if key in index:
            return index[key]
        return str(raw).strip().lower()

    raw_want = ([str(w) for w in want] if want is not None else sorted(entries))
    slugs = [_to_slug(w) for w in raw_want]
    out: dict[str, dict] = {}
    for slug in slugs:
        entry = entries.get(slug)
        if entry is None:
            out[slug] = {"licensed": False, "file": None,
                         "reason": "no-manifest-entry",
                         "known_club": slug in index_slugs}
            continue
        path = _entry_file(entry)
        if path is not None:
            out[slug] = {"licensed": True, "file": str(path),
                         "reason": "ok",
                         "known_club": slug in index_slugs}
        elif entry.get("rights_reviewed") is not True:
            out[slug] = {"licensed": False, "file": None,
                         "reason": "rights-not-reviewed",
                         "known_club": slug in index_slugs}
        elif not isinstance(entry.get("file"), str) or not entry["file"].strip():
            out[slug] = {"licensed": False, "file": None,
                         "reason": "pending-owner-file",
                         "known_club": slug in index_slugs}
        else:
            out[slug] = {"licensed": False, "file": None,
                         "reason": "file-missing-or-invalid",
                         "known_club": slug in index_slugs}
    return out


__all__ = ["CRESTS_DIR", "resolve_crest", "crest_status", "normalize_club_key"]
