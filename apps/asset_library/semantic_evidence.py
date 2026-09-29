from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SemanticEvidence:
    """
    Canonical representation of information extracted from real-world data.

    Perception produces SemanticEvidence.
    Downstream reasoning layers evaluate it.

    This contract intentionally does not contain domain-specific identity
    fields or a confidence score. Evidence quality and identity confidence
    belong to downstream reasoning.
    """

    kind: str
    value: str
    context: str | None
    source_locator: str
    provenance: dict[str, Any]