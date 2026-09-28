from __future__ import annotations

import argparse
from pathlib import Path

from .ingest import ingest_inbox
from .registry import connect
from .seed import seed_taxonomy


def main() -> None:
    parser = argparse.ArgumentParser(description="Asset Library foundation")
    parser.add_argument("command", choices=["seed", "ingest", "list", "list-competitions"])
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    db_path = root / "runtime/engine.db"

    if args.command == "seed":
        seed_taxonomy(db_path)
        print("taxonomy seeded")
        return

    if args.command == "ingest":
        for result in ingest_inbox(root):
            print(result)
        return

    conn = connect(db_path)
    try:
        if args.command == "list":
            rows = conn.execute(
                """
                SELECT asset_id, original_name, asset_type, rights_state,
                       lifecycle_state, category_code, competition_code,
                       purpose_code
                FROM assets ORDER BY created_at
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT competition_code, name, category_code, scope, region, tier, priority
                FROM competitions ORDER BY category_code, priority
                """
            ).fetchall()
        for row in rows:
            print(dict(row))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
