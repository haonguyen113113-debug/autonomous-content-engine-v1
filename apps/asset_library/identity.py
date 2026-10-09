from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .registry import connect

PERSON_TYPES = {"player", "manager", "official"}


@dataclass(frozen=True)
class IdentityProfile:
    """Everything the generic screener needs; all knowledge comes from data."""

    entity_id: str
    display_name: str
    include_terms: tuple[str, ...]
    exclude_terms: tuple[str, ...]
    other_names: tuple[tuple[str, str], ...]


def _term_hit(text: str, term: str) -> bool:
    if " " in term.strip():
        return term.lower() in text
    return re.search(rf"\b{re.escape(term.lower())}\b", text) is not None


def load_identity_profile(conn: sqlite3.Connection, entity_id: str) -> IdentityProfile | None:
    """Build a screening profile from entities, aliases, and name history."""
    row = conn.execute(
        "SELECT entity_id, entity_type, canonical_name, metadata_json "
        "FROM entities WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()
    if row is None or row["entity_type"] not in PERSON_TYPES:
        return None
    try:
        metadata = json.loads(row["metadata_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    identity = metadata.get("identity", {})
    if not isinstance(identity, dict):
        identity = {}

    include = {str(term).lower() for term in identity.get("include_terms", []) if str(term).strip()}
    include.add(str(row["canonical_name"]).lower())
    try:
        aliases = conn.execute(
            "SELECT alias FROM entity_aliases WHERE entity_id = ?", (entity_id,)
        ).fetchall()
        for alias_row in aliases:
            if alias_row["alias"]:
                include.add(str(alias_row["alias"]).lower())
    except sqlite3.Error:
        pass

    exclude = {str(term).lower() for term in identity.get("exclude_terms", []) if str(term).strip()}

    others: list[tuple[str, str]] = []
    try:
        people = conn.execute(
            "SELECT entity_id, canonical_name FROM entities "
            "WHERE entity_type IN ('player', 'manager', 'official') AND entity_id != ?",
            (entity_id,),
        ).fetchall()
        for person in people:
            if person["canonical_name"]:
                others.append((person["entity_id"], str(person["canonical_name"])))
        alias_rows = conn.execute(
            "SELECT entity_id, alias FROM entity_aliases WHERE entity_id != ?",
            (entity_id,),
        ).fetchall()
        for alias_row in alias_rows:
            if alias_row["alias"]:
                others.append((alias_row["entity_id"], str(alias_row["alias"])))
    except sqlite3.Error:
        pass

    return IdentityProfile(
        entity_id=row["entity_id"],
        display_name=str(row["canonical_name"]),
        include_terms=tuple(sorted(include)),
        exclude_terms=tuple(sorted(exclude)),
        other_names=tuple(others),
    )


def screen_candidates(
    candidates: list[Any],
    profile: IdentityProfile,
) -> tuple[list[Any], list[dict[str, str]]]:
    """Split candidates into kept and wrong-person removals.

    A candidate is removed only on positive evidence against it: the title
    names a different known person, or hits an explicit exclude term.
    Everything else is kept; items with no include-term support are flagged
    uncertain for owner review instead of being dropped.
    """
    kept: list[Any] = []
    removed: list[dict[str, str]] = []
    for candidate in candidates:
        text = f"{getattr(candidate, 'title', '')} {getattr(candidate, 'provider', '')}".lower()
        candidate_id = str(getattr(candidate, "candidate_id", ""))
        title = str(getattr(candidate, "title", ""))
        hit_other = next(
            (name for _, name in profile.other_names if name.lower() in text),
            None,
        )
        if hit_other is not None:
            removed.append({
                "candidate_id": candidate_id,
                "title": title,
                "reason": f"names a different person: {hit_other}",
            })
            continue
        hit_exclude = next(
            (term for term in profile.exclude_terms if _term_hit(text, term)),
            None,
        )
        if hit_exclude is not None:
            removed.append({
                "candidate_id": candidate_id,
                "title": title,
                "reason": f"matches exclude term: {hit_exclude}",
            })
            continue
        matched = any(_term_hit(text, term) for term in profile.include_terms)
        kept.append(replace(candidate, identity="match" if matched else "uncertain"))
    return kept, removed


def apply_identity_filter(
    candidates: list[Any],
    entity_id: str,
    db_path: Path,
) -> tuple[list[Any], dict[str, Any]]:
    """Screen candidates against an entity; fail open when identity is unknown."""
    conn = connect(db_path)
    try:
        profile = load_identity_profile(conn, entity_id)
    finally:
        conn.close()
    if profile is None:
        return list(candidates), {
            "entity_id": entity_id,
            "status": "unknown_entity",
            "kept": len(candidates),
            "removed": [],
        }
    kept, removed = screen_candidates(candidates, profile)
    return kept, {
        "entity_id": entity_id,
        "display_name": profile.display_name,
        "status": "screened",
        "kept": len(kept),
        "removed": removed,
    }
