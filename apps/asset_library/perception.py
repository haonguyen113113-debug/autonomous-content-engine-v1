from __future__ import annotations

from typing import Protocol

from apps.asset_library.input_characterization import (
    InputCharacteristics,
    characterize_input,
)
from apps.asset_library.raw_source import RawSource


class SemanticEvidenceExtractor(Protocol):
    name: str

    def can_handle(
        self,
        characteristics: InputCharacteristics,
    ) -> bool:
        ...

    def extract(
        self,
        source: RawSource,
        characteristics: InputCharacteristics,
    ) -> list[object]:
        ...


class UnsupportedSourceError(RuntimeError):
    pass


class PerceptionEngine:
    def __init__(
        self,
        extractors: list[SemanticEvidenceExtractor] | None = None,
    ) -> None:
        self._extractors = list(extractors or [])

    def extract(
        self,
        source: RawSource,
    ) -> list[object]:
        characteristics = characterize_input(source)

        for extractor in self._extractors:
            if extractor.can_handle(characteristics):
                return extractor.extract(
                    source,
                    characteristics,
                )

        raise UnsupportedSourceError(
            "No semantic evidence extractor can handle "
            f"representation={characteristics.representation!r}, "
            f"media_type={characteristics.media_type!r}, "
            f"source={source.locator}"
        )