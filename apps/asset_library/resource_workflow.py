from __future__ import annotations

import json
import sqlite3

from .asset_intelligence import (
    ResourceEvaluation,
    ResourceRequirement,
    evaluate_requirement,
)


def evaluate_library_requirement(
    conn: sqlite3.Connection,
    requirement: ResourceRequirement,
) -> ResourceEvaluation:
    """Evaluate a resource request against the library's persisted inventory.

    This is the integration seam between upstream workflows and the Asset
    Library. It is read-only: an unsatisfied result signals that a caller may
    offer external discovery, but this function never searches, downloads,
    stores, or authorizes an asset.
    """

    cursor = conn.execute(
        """
        SELECT asset_id, asset_type, subject_id, purpose_code,
               rights_state, lifecycle_state, metadata_json
        FROM assets
        ORDER BY created_at, asset_id
        """
    )
    columns = [description[0] for description in cursor.description or ()]

    candidates = []
    for row in cursor.fetchall():
        candidate = dict(zip(columns, row))
        metadata_json = candidate.pop("metadata_json", "{}")
        candidate["metadata"] = json.loads(metadata_json or "{}")
        candidates.append(candidate)

    return evaluate_requirement(requirement, candidates)
