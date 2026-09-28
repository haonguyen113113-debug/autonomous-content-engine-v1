from pathlib import Path

from apps.asset_library.catalog import add_alias, add_external_ref, add_relationship, link_asset_entity, upsert_entity
from apps.asset_library.entities import EntityRecord
from apps.asset_library.registry import connect


def test_entity_identity_alias_external_ref_and_temporal_relationship(tmp_path: Path):
    conn = connect(tmp_path / 'engine.db')
    upsert_entity(conn, EntityRecord('ent_player_0001', 'player', 'Nguyen Van A', 'nguyen-van-a', 'VN'))
    upsert_entity(conn, EntityRecord('ent_club_0001', 'club', 'Example FC', 'example-fc', 'VN'))
    add_alias(conn, 'ent_player_0001', 'Nguyễn Văn A', 'vi')
    add_alias(conn, 'ent_player_0001', 'NVA', 'vi', 'short')
    add_external_ref(conn, 'ent_player_0001', 'provider_x', 'player-77', 'https://example.invalid/player-77')
    add_relationship(conn, 'ent_player_0001', 'member_of', 'ent_club_0001', '2026-01-01', None)
    conn.commit()

    assert conn.execute("SELECT count(*) FROM entities").fetchone()[0] == 2
    assert conn.execute("SELECT count(*) FROM entity_aliases").fetchone()[0] == 2
    assert conn.execute("SELECT entity_id FROM entity_external_refs WHERE provider='provider_x'").fetchone()[0] == 'ent_player_0001'
    rel = conn.execute("SELECT relation_type, valid_from FROM entity_relationships").fetchone()
    assert rel['relation_type'] == 'member_of'
    assert rel['valid_from'] == '2026-01-01'
    conn.close()


def test_asset_can_have_multiple_entity_subjects(tmp_path: Path):
    conn = connect(tmp_path / 'engine.db')
    conn.execute("INSERT INTO assets(asset_id, original_name, stored_path, asset_type, size_bytes, sha256, source_type, rights_state, lifecycle_state, metadata_json) VALUES ('asset1','x.jpg','library/x.jpg','image',1,'sha1','self_created','verified_commercial','approved','{}')")
    upsert_entity(conn, EntityRecord('ent_player_0001', 'player', 'Player A', 'player-a'))
    upsert_entity(conn, EntityRecord('ent_club_0001', 'club', 'Club A', 'club-a'))
    link_asset_entity(conn, 'asset1', 'ent_player_0001', 'primary_subject', 1.0, 'manual')
    link_asset_entity(conn, 'asset1', 'ent_club_0001', 'secondary_subject', 0.95, 'manual')
    conn.commit()

    rows = conn.execute("SELECT entity_id, role FROM asset_entities ORDER BY role").fetchall()
    assert [(r['entity_id'], r['role']) for r in rows] == [
        ('ent_player_0001', 'primary_subject'),
        ('ent_club_0001', 'secondary_subject'),
    ]
    conn.close()
