from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable


def stable_slug(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    normalized = normalized.lower().strip()
    normalized = re.sub(r'[^a-z0-9]+', '-', normalized).strip('-')
    return normalized or 'entity'


@dataclass(frozen=True)
class EntityRecord:
    entity_id: str
    entity_type: str
    canonical_name: str
    slug: str
    country_code: str | None = None
    status: str = 'active'
    metadata: dict | None = None


VALID_ENTITY_TYPES = {
    'player',
    'manager',
    'club',
    'national_team',
    'competition',
    'venue',
    'federation',
    'match',
    'official',
}

VALID_RELATION_TYPES = {
    'member_of',
    'represented',
    'managed_by',
    'plays_at',
    'participates_in',
    'organized_by',
    'affiliated_with',
    'hosted_at',
    'opponent_of',
    'part_of',
}


def validate_entity(record: EntityRecord) -> None:
    if record.entity_type not in VALID_ENTITY_TYPES:
        raise ValueError(f'Unsupported entity type: {record.entity_type}')
    if not record.entity_id or not record.canonical_name:
        raise ValueError('entity_id and canonical_name are required')
    if record.status not in {'active', 'inactive', 'deprecated'}:
        raise ValueError(f'Unsupported entity status: {record.status}')


def validate_relationship(relation_type: str) -> None:
    if relation_type not in VALID_RELATION_TYPES:
        raise ValueError(f'Unsupported relationship type: {relation_type}')
