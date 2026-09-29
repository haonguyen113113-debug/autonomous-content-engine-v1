from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from apps.asset_library.raw_source import RawSource


@dataclass(frozen=True)
class InputCharacteristics:
    representation: str
    media_type: str | None
    encoding: str | None
    signals: dict[str, Any]


def _looks_like_html(text: str) -> bool:
    stripped = text.lstrip().lower()

    return (
        stripped.startswith("<!doctype html")
        or stripped.startswith("<html")
        or "<html" in stripped[:2000]
    )


def _looks_like_json(text: str) -> bool:
    stripped = text.lstrip()

    if not stripped:
        return False

    if stripped[0] not in "{[":
        return False

    try:
        json.loads(stripped)
    except json.JSONDecodeError:
        return False

    return True


def characterize_input(
    source: RawSource,
) -> InputCharacteristics:
    raw = source.data

    if not raw:
        return InputCharacteristics(
            representation="empty",
            media_type=None,
            encoding=None,
            signals={
                "byte_length": 0,
            },
        )

    encoding = "utf-8"

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None
        encoding = None

    if text is not None:
        if _looks_like_html(text):
            return InputCharacteristics(
                representation="document",
                media_type="text/html",
                encoding=encoding,
                signals={
                    "byte_length": len(raw),
                    "has_html_doctype": text.lstrip()
                    .lower()
                    .startswith("<!doctype html"),
                },
            )

        if _looks_like_json(text):
            return InputCharacteristics(
                representation="structured",
                media_type="application/json",
                encoding=encoding,
                signals={
                    "byte_length": len(raw),
                },
            )

        return InputCharacteristics(
            representation="text",
            media_type="text/plain",
            encoding=encoding,
            signals={
                "byte_length": len(raw),
            },
        )

    return InputCharacteristics(
        representation="binary",
        media_type=None,
        encoding=None,
        signals={
            "byte_length": len(raw),
        },
    )