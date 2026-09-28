from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .catalog import add_alias, add_relationship, upsert_entity
from .entities import EntityRecord
from .registry import connect
from .seed import seed_taxonomy


DATASET_ROOT = Path('data/entities')


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'Manifest must be an object: {path}')
    if not isinstance(data.get('records'), list):
        raise ValueError(f'Manifest records must be a list: {path}')
    source = data.get('source')
    if not isinstance(source, dict) or not source.get('name') or not source.get('url'):
        raise ValueError(f'Manifest source.name and source.url are required: {path}')
    return data


def record_source(conn, entity_id: str, manifest: dict[str, Any]) -> None:
    source = manifest['source']
    conn.execute(
        '''
        INSERT OR IGNORE INTO entity_sources
        (entity_id, source_name, source_url, retrieved_at, dataset_version, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (
            entity_id,
            source['name'],
            source['url'],
            source.get('retrieved_at', ''),
            manifest.get('dataset_version'),
            source.get('notes'),
        ),
    )


def seed_entity_catalog(root: Path) -> dict[str, int]:
    root = root.resolve()
    db_path = root / 'runtime/engine.db'
    data_root = root / DATASET_ROOT

    seed_taxonomy(db_path)
    conn = connect(db_path)
    try:
        entity_manifests = [
            data_root / 'competitions.json',
            data_root / 'clubs.json',
            data_root / 'national_teams.json',
        ]
        relationship_manifest = data_root / 'relationships.json'

        entities_upserted = 0
        aliases_added = 0
        sources_recorded = 0
        for path in entity_manifests:
            if not path.exists():
                continue
            manifest = load_manifest(path)
            for item in manifest['records']:
                entity = EntityRecord(
                    entity_id=item['entity_id'],
                    entity_type=item['entity_type'],
                    canonical_name=item['canonical_name'],
                    slug=item['slug'],
                    country_code=item.get('country_code'),
                    status=item.get('status', 'active'),
                    metadata=item.get('metadata', {}),
                )
                upsert_entity(conn, entity)
                entities_upserted += 1
                for alias in item.get('aliases', []):
                    add_alias(
                        conn,
                        item['entity_id'],
                        alias['alias'],
                        alias.get('language_code'),
                        alias.get('alias_type', 'common'),
                    )
                    aliases_added += 1
                record_source(conn, item['entity_id'], manifest)
                sources_recorded += 1

        relationships_added = 0
        if relationship_manifest.exists():
            manifest = load_manifest(relationship_manifest)
            for item in manifest['records']:
                add_relationship(
                    conn,
                    item['subject_entity_id'],
                    item['relation_type'],
                    item['object_entity_id'],
                    item.get('valid_from'),
                    item.get('valid_to'),
                    item.get('metadata', {}),
                )
                relationships_added += 1

        conn.commit()
        return {
            'entities_upserted': entities_upserted,
            'aliases_seen': aliases_added,
            'sources_seen': sources_recorded,
            'relationships_seen': relationships_added,
        }
    finally:
        conn.close()
