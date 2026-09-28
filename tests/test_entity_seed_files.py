import json
from pathlib import Path


def test_seed_manifests_have_sources_and_no_invented_external_ids():
    root = Path(__file__).parents[1] / 'data/entities'
    for filename in ['competitions.json', 'clubs.json', 'national_teams.json', 'relationships.json']:
        data = json.loads((root / filename).read_text(encoding='utf-8'))
        assert data['source']['name']
        assert data['source']['retrieved_at'] == '2026-09-28'
        for record in data['records']:
            if 'entity_id' in record:
                assert 'source' not in record or record['source']
                assert 'external_refs' not in record
