from __future__ import annotations

import json
from pathlib import Path

from apps.asset_library.ingest import ingest_inbox
from apps.asset_library.registry import connect


def test_ingest_and_duplicate_detection(tmp_path: Path) -> None:
    root = tmp_path
    inbox = root / "runtime/assets/inbox"
    inbox.mkdir(parents=True)
    (inbox / "sample.txt").write_text("hello", encoding="utf-8")
    (inbox / "sample.txt.json").write_text(
        json.dumps({
            "source_type": "self_created",
            "source_url": None,
            "creator": "project_owner",
            "license_type": "owned",
            "rights_state": "verified_commercial",
            "market_code": "VN",
            "category_code": "SOCCER_VIETNAM",
            "purpose_code": "background",
        }),
        encoding="utf-8",
    )

    # Taxonomy is intentionally seeded before ingest in normal operation.
    conn = connect(root / "runtime/engine.db")
    conn.execute("INSERT INTO markets VALUES ('VN','Vietnam','vi',10,'active')")
    conn.execute("INSERT INTO categories VALUES ('SOCCER_VIETNAM','VN','Vietnamese Football',NULL,5,'active')")
    conn.commit()
    conn.close()

    first = ingest_inbox(root)
    second = ingest_inbox(root)

    assert first[0].startswith("ingested:")
    assert second[0].startswith("duplicate:")

    conn = connect(root / "runtime/engine.db")
    row = conn.execute("SELECT * FROM assets").fetchone()
    conn.close()

    assert row["rights_state"] == "verified_commercial"
    assert row["lifecycle_state"] == "ingested"
    assert row["market_code"] == "VN"
    assert row["category_code"] == "SOCCER_VIETNAM"
