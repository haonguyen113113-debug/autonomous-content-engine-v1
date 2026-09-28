from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from typing import Any, Iterable

from .entities import EntityRecord, validate_entity, validate_relationship


ENTITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    country_code TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entity_aliases (
    alias_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    alias TEXT NOT NULL,
    language_code TEXT,
    alias_type TEXT NOT NULL DEFAULT 'common',
    UNIQUE(entity_id, alias, language_code),
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entity_external_refs (
    ref_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    external_id TEXT NOT NULL,
    source_url TEXT,
    UNIQUE(provider, external_id),
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entity_relationships (
    relationship_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_entity_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    object_entity_id TEXT NOT NULL,
    valid_from TEXT,
    valid_to TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(subject_entity_id, relation_type, object_entity_id, valid_from, valid_to),
    FOREIGN KEY(subject_entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE,
    FOREIGN KEY(object_entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS asset_entities (
    asset_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'subject',
    confidence REAL,
    source TEXT NOT NULL DEFAULT 'manual',
    PRIMARY KEY(asset_id, entity_id, role),
    FOREIGN KEY(asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE,
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_aliases_alias ON entity_aliases(alias);
CREATE INDEX IF NOT EXISTS idx_external_refs_provider ON entity_external_refs(provider, external_id);
CREATE INDEX IF NOT EXISTS idx_relationship_subject ON entity_relationships(subject_entity_id);
CREATE INDEX IF NOT EXISTS idx_relationship_object ON entity_relationships(object_entity_id);
CREATE INDEX IF NOT EXISTS idx_asset_entities_entity ON asset_entities(entity_id);

CREATE TABLE IF NOT EXISTS entity_sources (
    source_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    dataset_version TEXT,
    notes TEXT,
    UNIQUE(entity_id, source_name, source_url, dataset_version),
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entity_sources_entity ON entity_sources(entity_id);
"""


def init_entity_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(ENTITY_SCHEMA)


def upsert_entity(conn: sqlite3.Connection, record: EntityRecord) -> None:
    validate_entity(record)
    conn.execute(
        """
        INSERT INTO entities (entity_id, entity_type, canonical_name, slug, country_code, status, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(entity_id) DO UPDATE SET
            entity_type=excluded.entity_type,
            canonical_name=excluded.canonical_name,
            slug=excluded.slug,
            country_code=excluded.country_code,
            status=excluded.status,
            metadata_json=excluded.metadata_json,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            record.entity_id,
            record.entity_type,
            record.canonical_name,
            record.slug,
            record.country_code,
            record.status,
            json.dumps(record.metadata or {}, ensure_ascii=False, sort_keys=True),
        ),
    )


def add_alias(conn: sqlite3.Connection, entity_id: str, alias: str, language_code: str | None = None, alias_type: str = 'common') -> None:
    conn.execute(
        "INSERT OR IGNORE INTO entity_aliases(entity_id, alias, language_code, alias_type) VALUES (?, ?, ?, ?)",
        (entity_id, alias, language_code, alias_type),
    )


def add_external_ref(conn: sqlite3.Connection, entity_id: str, provider: str, external_id: str, source_url: str | None = None) -> None:
    conn.execute(
        """
        INSERT INTO entity_external_refs(entity_id, provider, external_id, source_url)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(provider, external_id) DO UPDATE SET
            entity_id=excluded.entity_id,
            source_url=excluded.source_url
        """,
        (entity_id, provider, external_id, source_url),
    )


def add_relationship(
    conn: sqlite3.Connection,
    subject_entity_id: str,
    relation_type: str,
    object_entity_id: str,
    valid_from: str | None = None,
    valid_to: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    validate_relationship(relation_type)
    conn.execute(
        """
        INSERT OR IGNORE INTO entity_relationships
        (subject_entity_id, relation_type, object_entity_id, valid_from, valid_to, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            subject_entity_id,
            relation_type,
            object_entity_id,
            valid_from,
            valid_to,
            json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
        ),
    )


def link_asset_entity(conn: sqlite3.Connection, asset_id: str, entity_id: str, role: str = 'subject', confidence: float | None = None, source: str = 'manual') -> None:
    if confidence is not None and not 0.0 <= confidence <= 1.0:
        raise ValueError('confidence must be between 0 and 1')
    conn.execute(
        """
        INSERT OR REPLACE INTO asset_entities(asset_id, entity_id, role, confidence, source)
        VALUES (?, ?, ?, ?, ?)
        """,
        (asset_id, entity_id, role, confidence, source),
    )
