from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .asset_intelligence import ResourceRequirement
from .entity_seed import seed_entity_catalog
from .ingest import ingest_inbox
from .registry import connect
from .resource_workflow import evaluate_library_requirement
from .seed import seed_taxonomy
from .taxonomy import ensure_taxonomy_schema


def main() -> None:
    parser = argparse.ArgumentParser(description="Asset Library foundation")
    parser.add_argument(
        "command",
        choices=[
            "seed",
            "seed-entities",
            "ingest",
            "list",
            "list-competitions",
            "list-entities",
            "evaluate-requirement",
        ],
    )
    parser.add_argument("--root", default=".")
    parser.add_argument(
        "--requirement-file",
        help="JSON file containing a ResourceRequirement",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    db_path = root / "runtime/engine.db"

    if args.command == "seed":
        seed_taxonomy(db_path)
        print("taxonomy seeded")
        return

    if args.command == "seed-entities":
        result = seed_entity_catalog(root)
        print(result)
        return

    if args.command == "ingest":
        for result in ingest_inbox(root):
            print(result)
        return

    if args.command == "evaluate-requirement":
        if not args.requirement_file:
            parser.error(
                "evaluate-requirement requires --requirement-file"
            )
        requirement_data = json.loads(
            Path(args.requirement_file).read_text(encoding="utf-8")
        )
        requirement = ResourceRequirement(**requirement_data)
        conn = connect(db_path)
        try:
            result = evaluate_library_requirement(conn, requirement)
            print(
                json.dumps(
                    asdict(result),
                    ensure_ascii=False,
                    indent=2,
                )
            )
        finally:
            conn.close()
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
        elif args.command == "list-competitions":
            ensure_taxonomy_schema(conn)
            rows = conn.execute(
                """
                SELECT competition_code, name, category_code,
                       scope, region, tier, priority
                FROM competitions
                ORDER BY category_code, priority
                """
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT entity_id, entity_type, canonical_name, slug,
                       country_code, status
                FROM entities
                ORDER BY entity_type, canonical_name
                """
            ).fetchall()
        for row in rows:
            print(dict(row))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
