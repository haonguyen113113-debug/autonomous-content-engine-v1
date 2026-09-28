from __future__ import annotations

from pathlib import Path

from .registry import connect
from .taxonomy import (
    CATEGORIES,
    COMPETITIONS,
    MARKETS,
    ensure_taxonomy_schema,
)


def seed_taxonomy(db_path: Path) -> None:
    conn = connect(db_path)
    try:
        ensure_taxonomy_schema(conn)
        conn.executemany(
            """
            INSERT OR IGNORE INTO markets (
                market_code, name, language_code, priority
            )
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    x["market_code"],
                    x["name"],
                    x["language_code"],
                    x["priority"],
                )
                for x in MARKETS
            ],
        )
        conn.executemany(
            """
            INSERT OR IGNORE INTO categories (
                category_code, market_code, name,
                parent_category_code, priority
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    x["category_code"],
                    x["market_code"],
                    x["name"],
                    x["parent_category_code"],
                    x["priority"],
                )
                for x in CATEGORIES
            ],
        )
        conn.executemany(
            """
            INSERT OR IGNORE INTO competitions (
                competition_code, category_code, name,
                scope, region, tier, priority, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    x["code"],
                    x["category"],
                    x["name"],
                    x["scope"],
                    x["region"],
                    x["tier"],
                    x["priority"],
                    None,
                )
                for x in COMPETITIONS
            ],
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    seed_taxonomy(Path("runtime/engine.db"))
    print("taxonomy seeded")
