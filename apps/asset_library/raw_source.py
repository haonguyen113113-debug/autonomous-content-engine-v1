from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RawSource:
    data: bytes
    locator: str
    media_type: str | None = None