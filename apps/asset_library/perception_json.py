from __future__ import annotations

import json
from typing import Any

from apps.asset_library.input_characterization import (
    InputCharacteristics,
)
from apps.asset_library.raw_source import RawSource
from apps.asset_library.semantic_evidence import SemanticEvidence


class JSONSemanticEvidenceExtractor:
    name = "json-semantic"

    def can_handle(
        self,
        characteristics: InputCharacteristics,
    ) -> bool:
        return (
            characteristics.representation == "structured"
            and characteristics.media_type == "application/json"
        )

    def extract(
        self,
        source: RawSource,
        characteristics: InputCharacteristics,
    ) -> list[SemanticEvidence]:
        data = json.loads(
            source.data.decode(
                characteristics.encoding or "utf-8",
                errors="replace",
            )
        )

        evidence: list[SemanticEvidence] = []

        def walk(
            value: Any,
            path: str = "$",
        ) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = f"{path}.{key}"
                    walk(child, child_path)
                return

            if isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, f"{path}[{index}]")
                return

            if value is None:
                return

            evidence.append(
                SemanticEvidence(
                    kind="structured_value",
                    value=str(value),
                    context=path,
                    source_locator=source.locator,
                    provenance={
                        "extraction_method": self.name,
                        "representation": "json",
                    },
                )
            )

        walk(data)

        return evidence