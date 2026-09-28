from __future__ import annotations

import json
import sqlite3
from typing import Any


PLAYER_IDENTITY_SCHEMA = """
CREATE TABLE IF NOT EXISTS entity_name_history (
    name_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    name TEXT NOT NULL,
    language_code TEXT,
    name_type TEXT NOT NULL,
    valid_from TEXT,
    valid_to TEXT,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    dataset_version TEXT,
    notes TEXT,
    UNIQUE(entity_id, name, language_code, name_type, valid_from, valid_to, source_url),
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS person_profiles (
    entity_id TEXT PRIMARY KEY,
    birth_date TEXT,
    birth_place TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entity_nationalities (
    entity_id TEXT NOT NULL,
    country_code TEXT NOT NULL,
    nationality_type TEXT NOT NULL DEFAULT 'nationality',
    valid_from TEXT,
    valid_to TEXT,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    dataset_version TEXT,
    PRIMARY KEY(entity_id, country_code, nationality_type, valid_from, valid_to),
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_name_history_entity ON entity_name_history(entity_id);
CREATE INDEX IF NOT EXISTS idx_name_history_name ON entity_name_history(name);
CREATE INDEX IF NOT EXISTS idx_nationalities_entity ON entity_nationalities(entity_id);
CREATE INDEX IF NOT EXISTS idx_nationalities_country ON entity_nationalities(country_code);
"""

VALID_NAME_TYPES = {
    'display',
    'common',
    'short',
    'nickname',
    'transliteration',
    'historical',
    'legal',
}

VALID_NATIONALITY_TYPES = {'nationality', 'citizenship', 'heritage'}
VALID_VERIFICATION_STATES = {'unverified', 'verified', 'revoked'}


def init_player_identity_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(PLAYER_IDENTITY_SCHEMA)


def _ensure_external_ref_columns(conn: sqlite3.Connection) -> None:
    columns = {row['name'] for row in conn.execute('PRAGMA table_info(entity_external_refs)').fetchall()}
    if 'verification_state' not in columns:
        conn.execute("ALTER TABLE entity_external_refs ADD COLUMN verification_state TEXT NOT NULL DEFAULT 'unverified'")
    if 'source_name' not in columns:
        conn.execute("ALTER TABLE entity_external_refs ADD COLUMN source_name TEXT")


def init_player_identity_migrations(conn: sqlite3.Connection) -> None:
    _ensure_external_ref_columns(conn)


def add_name_history(
    conn: sqlite3.Connection,
    entity_id: str,
    name: str,
    *,
    language_code: str | None = None,
    name_type: str = 'common',
    valid_from: str | None = None,
    valid_to: str | None = None,
    source_name: str,
    source_url: str,
    dataset_version: str | None = None,
    notes: str | None = None,
) -> None:
    if name_type not in VALID_NAME_TYPES:
        raise ValueError(f'Unsupported name_type: {name_type}')
    if not name.strip():
        raise ValueError('name is required')
    if not source_name or not source_url:
        raise ValueError('source_name and source_url are required')
    conn.execute(
        """
        INSERT OR IGNORE INTO entity_name_history
        (entity_id, name, language_code, name_type, valid_from, valid_to,
         source_name, source_url, dataset_version, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (entity_id, name, language_code, name_type, valid_from, valid_to,
         source_name, source_url, dataset_version, notes),
    )


def upsert_person_profile(
    conn: sqlite3.Connection,
    entity_id: str,
    *,
    birth_date: str | None = None,
    birth_place: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    row = conn.execute('SELECT entity_type FROM entities WHERE entity_id = ?', (entity_id,)).fetchone()
    if row is None:
        raise ValueError(f'Unknown entity: {entity_id}')
    if row['entity_type'] not in {'player', 'manager', 'official'}:
        raise ValueError(f'Entity is not a person-type entity: {entity_id}')
    conn.execute(
        """
        INSERT INTO person_profiles(entity_id, birth_date, birth_place, metadata_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(entity_id) DO UPDATE SET
            birth_date=excluded.birth_date,
            birth_place=excluded.birth_place,
            metadata_json=excluded.metadata_json
        """,
        (entity_id, birth_date, birth_place, json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)),
    )


def add_nationality(
    conn: sqlite3.Connection,
    entity_id: str,
    country_code: str,
    *,
    nationality_type: str = 'nationality',
    valid_from: str | None = None,
    valid_to: str | None = None,
    source_name: str,
    source_url: str,
    dataset_version: str | None = None,
) -> None:
    if nationality_type not in VALID_NATIONALITY_TYPES:
        raise ValueError(f'Unsupported nationality_type: {nationality_type}')
    if not source_name or not source_url:
        raise ValueError('source_name and source_url are required')
    conn.execute(
        """
        INSERT OR IGNORE INTO entity_nationalities
        (entity_id, country_code, nationality_type, valid_from, valid_to,
         source_name, source_url, dataset_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (entity_id, country_code, nationality_type, valid_from, valid_to,
         source_name, source_url, dataset_version),
    )
