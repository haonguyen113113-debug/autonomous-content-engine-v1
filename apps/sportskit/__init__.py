"""Shared font loader for engine-drawn text (pack plates, audits).

Kit live-data plates were removed; the 69 authored starters carry the visual
system. This package keeps only the locked brand font loader used by the
owner-pack renderer and tooling.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class KitFonts:
    def __init__(self, resource_dir: Path) -> None:
        from PIL import ImageFont

        def load(name: str, size: int) -> Any:
            return ImageFont.truetype(str(resource_dir / name), size)

        self._load = load
        self._dir = resource_dir

    def barlow(self, size: int) -> Any:
        return self._load("BarlowCondensed-Bold.ttf", size)

    def barlow_sb(self, size: int) -> Any:
        return self._load("BarlowCondensed-SemiBold.ttf", size)

    def bev(self, size: int) -> Any:
        return self._load("BeVietnamPro-Regular.ttf", size)

    def bev_b(self, size: int) -> Any:
        return self._load("BeVietnamPro-Bold.ttf", size)

    def brush(self, size: int) -> Any:
        try:
            return self._load("PermanentMarker-Regular.woff", size)
        except (OSError, ValueError):
            return self.barlow(size)

    def numeral(self, size: int) -> Any:
        """BigShoulders numerals (latin digits only, no diacritics)."""
        for candidate in (self._dir / "BigShoulders-Bold.ttf",
                          self._dir.parent.parent.parent.parent / "skills"
                          / "canvas-design" / "canvas-fonts" / "BigShoulders-Bold.ttf"):
            try:
                from PIL import ImageFont

                return ImageFont.truetype(str(candidate), size)
            except (OSError, ValueError):
                continue
        return self.barlow(size)


__all__ = ["KitFonts"]
