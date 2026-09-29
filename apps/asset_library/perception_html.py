from __future__ import annotations

from html.parser import HTMLParser

from apps.asset_library.input_characterization import (
    InputCharacteristics,
)
from apps.asset_library.raw_source import RawSource
from apps.asset_library.semantic_evidence import SemanticEvidence


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self._parts.append(text)

    @property
    def text(self) -> str:
        return " ".join(self._parts)


class HTMLTextExtractor:
    name = "html-text"

    def can_handle(
        self,
        characteristics: InputCharacteristics,
    ) -> bool:
        return (
            characteristics.representation == "document"
            and characteristics.media_type == "text/html"
        )

    def extract(
        self,
        source: RawSource,
        characteristics: InputCharacteristics,
    ) -> list[SemanticEvidence]:
        parser = _TextCollector()

        parser.feed(
            source.data.decode(
                characteristics.encoding or "utf-8",
                errors="replace",
            )
        )

        if not parser.text:
            return []

        return [
            SemanticEvidence(
                kind="text",
                value=parser.text,
                context=None,
                source_locator=source.locator,
                provenance={
                    "extraction_method": self.name,
                },
            )
        ]