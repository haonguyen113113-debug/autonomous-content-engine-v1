from __future__ import annotations

import hashlib
import json
import mimetypes
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AssetRecord:
    asset_id: str
    original_name: str
    stored_path: str
    asset_type: str
    mime_type: str | None
    size_bytes: int
    sha256: str
    source_type: str
    source_url: str | None
    creator: str | None
    license_type: str | None
    rights_state: str
    lifecycle_state: str
    market_code: str | None
    category_code: str | None
    subject_type: str | None
    subject_id: str | None
    competition_code: str | None
    purpose_code: str | None
    metadata: dict[str, Any]


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS markets (
    market_code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    language_code TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 100,
    lifecycle_state TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS categories (
    category_code TEXT PRIMARY KEY,
    market_code TEXT,
    name TEXT NOT NULL,
    parent_category_code TEXT,
    priority INTEGER NOT NULL DEFAULT 100,
    lifecycle_state TEXT NOT NULL DEFAULT 'active',
    FOREIGN KEY(market_code) REFERENCES markets(market_code),
    FOREIGN KEY(parent_category_code) REFERENCES categories(category_code)
);

CREATE TABLE IF NOT EXISTS competitions (
    competition_code TEXT PRIMARY KEY,
    category_code TEXT,
    name TEXT NOT NULL,
    scope TEXT NOT NULL,
    region TEXT,
    tier INTEGER NOT NULL,
    priority INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    FOREIGN KEY(category_code) REFERENCES categories(category_code)
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,
    original_name TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    source_url TEXT,
    creator TEXT,
    license_type TEXT,
    rights_state TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL,
    market_code TEXT,
    category_code TEXT,
    subject_type TEXT,
    subject_id TEXT,
    competition_code TEXT,
    purpose_code TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(market_code) REFERENCES markets(market_code),
    FOREIGN KEY(category_code) REFERENCES categories(category_code),
    FOREIGN KEY(competition_code) REFERENCES competitions(competition_code)
);

CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
CREATE INDEX IF NOT EXISTS idx_assets_rights ON assets(rights_state);
CREATE INDEX IF NOT EXISTS idx_assets_lifecycle ON assets(lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category_code);
CREATE INDEX IF NOT EXISTS idx_assets_competition ON assets(competition_code);
CREATE INDEX IF NOT EXISTS idx_assets_subject ON assets(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_assets_purpose ON assets(purpose_code);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    from .catalog import init_entity_schema
    init_entity_schema(conn)
    return conn


def file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def infer_asset_type(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg"}:
        return "image"
    if ext in {".mp4", ".mov", ".mkv", ".webm", ".avi"}:
        return "video"
    if ext in {".wav", ".mp3", ".flac", ".m4a", ".ogg"}:
        return "audio"
    if ext in {".ttf", ".otf", ".woff", ".woff2"}:
        return "font"
    return "other"


def read_sidecar(path: Path) -> dict[str, Any]:
    sidecar = path.with_suffix(path.suffix + ".json")
    if not sidecar.exists():
        return {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid provenance sidecar: {sidecar}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Provenance sidecar must be an object: {sidecar}")
    return data


def technical_metadata(path: Path, asset_type: str, mime_type: str | None) -> dict[str, Any]:
    metadata: dict[str, Any] = {"extension": path.suffix.lower()}
    if asset_type == "image":
        try:
            from PIL import Image

            with Image.open(path) as image:
                metadata.update({"width": image.width, "height": image.height, "format": image.format})
        except Exception as exc:
            metadata["technical_metadata_error"] = str(exc)
    return metadata


def upsert_asset(conn: sqlite3.Connection, record: AssetRecord) -> None:
    conn.execute(
        """
        INSERT INTO assets (
            asset_id, original_name, stored_path, asset_type, mime_type, size_bytes,
            sha256, source_type, source_url, creator, license_type, rights_state,
            lifecycle_state, market_code, category_code, subject_type, subject_id,
            competition_code, purpose_code, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.asset_id,
            record.original_name,
            record.stored_path,
            record.asset_type,
            record.mime_type,
            record.size_bytes,
            record.sha256,
            record.source_type,
            record.source_url,
            record.creator,
            record.license_type,
            record.rights_state,
            record.lifecycle_state,
            record.market_code,
            record.category_code,
            record.subject_type,
            record.subject_id,
            record.competition_code,
            record.purpose_code,
            json.dumps(record.metadata, ensure_ascii=False, sort_keys=True),
        ),
    )
