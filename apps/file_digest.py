"""Canonical file digests for frozen contracts.

Contract artifacts (card contract, Scene Graph provenance) pin the SHA-256 of
authored files. A plain byte-for-byte hash makes every pin depend on the
checkout's line endings: the contract was generated on Windows (CRLF) and then
fails closed on every LF checkout, which turns a content bug into an
unexplainable "starter drifted" failure on CI, macOS and Linux.

Every digest of an authored *text* artifact is therefore computed over
newline-normalised bytes (CRLF -> LF). Binary artifacts (PNG/JPG/TTF/MP3) are
hashed verbatim. The normalisation is stable and idempotent, so the same
contract validates identically on Windows, macOS, Linux and inside Docker.

This module is the single source of truth; contract producers
(``tools/build_card_contract.py``) and consumers
(``apps/studio_templates/card_media.py``, ``apps/scene_graph/schema.py``) must
call it instead of hashing raw bytes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Suffixes hashed after newline normalisation. Anything else (images, fonts,
# audio, archives) is hashed exactly as stored.
TEXT_SUFFIXES = frozenset(
    {
        ".json", ".jsonl", ".md", ".txt", ".py", ".js", ".mjs", ".cjs",
        ".ts", ".css", ".html", ".htm", ".svg", ".xml", ".yaml", ".yml",
        ".csv", ".toml", ".ini", ".cfg", ".srt", ".vtt",
    }
)

CRLF = b"\r\n"
LF = b"\n"


def normalise_newlines(data: bytes) -> bytes:
    """Return ``data`` with every CRLF collapsed to LF (idempotent)."""
    return data.replace(CRLF, LF)


def digest_bytes(data: bytes, *, normalise: bool = False) -> str:
    """SHA-256 of ``data``, optionally newline-normalised first."""
    if normalise:
        data = normalise_newlines(data)
    return hashlib.sha256(data).hexdigest()


def is_text_artifact(path: Path | str) -> bool:
    """True when ``path`` is a text artifact whose newlines must be pinned."""
    return Path(path).suffix.lower() in TEXT_SUFFIXES


def file_digest(path: Path | str) -> str:
    """SHA-256 of an authored artifact, newline-normalised for text files.

    Raises ``OSError`` when the file cannot be read; callers turn that into
    their own contract-specific error message.
    """
    file_path = Path(path)
    payload = file_path.read_bytes()
    return digest_bytes(payload, normalise=is_text_artifact(file_path))


__all__ = [
    "TEXT_SUFFIXES",
    "digest_bytes",
    "file_digest",
    "is_text_artifact",
    "normalise_newlines",
]
