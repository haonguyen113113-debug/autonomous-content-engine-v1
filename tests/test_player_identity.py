from pathlib import Path
import pytest

from apps.asset_library.catalog import add_external_ref, upsert_entity
from apps.asset_library.entities import EntityRecord
from apps.asset_library.player_identity import add_name_history, add_nationality, upsert_person_profile
from apps.asset_library.registry import connect


def test_player_identity_supports_name_history_nationality_and_profile(tmp_path: Path):
    conn = connect(tmp_path / 'engine.db')
    upsert_entity(conn, EntityRecord('player:test-1', 'player', 'Nguyen Van A', 'nguyen-van-a', 'VN'))
    add_name_history(conn, 'player:test-1', 'Nguyễn Văn A', language_code='vi', name_type='display',
                     source_name='Official profile', source_url='https://example.invalid/player/test-1', dataset_version='test-1')
    add_name_history(conn, 'player:test-1', 'Nguyen Van A', language_code='en', name_type='transliteration',
                     source_name='Official profile', source_url='https://example.invalid/player/test-1', dataset_version='test-1')
    upsert_person_profile(conn, 'player:test-1', birth_date='2000-01-02', birth_place='Hanoi')
    add_nationality(conn, 'player:test-1', 'VN', source_name='Official profile',
                    source_url='https://example.invalid/player/test-1', dataset_version='test-1')
    conn.commit()

    assert conn.execute("SELECT count(*) FROM entity_name_history WHERE entity_id='player:test-1'").fetchone()[0] == 2
    assert conn.execute("SELECT birth_place FROM person_profiles WHERE entity_id='player:test-1'").fetchone()[0] == 'Hanoi'
    assert conn.execute("SELECT country_code FROM entity_nationalities WHERE entity_id='player:test-1'").fetchone()[0] == 'VN'
    conn.close()


def test_external_reference_requires_proof_for_verified_state_and_is_unique(tmp_path: Path):
    conn = connect(tmp_path / 'engine.db')
    upsert_entity(conn, EntityRecord('player:test-1', 'player', 'Player One', 'player-one'))
    upsert_entity(conn, EntityRecord('player:test-2', 'player', 'Player Two', 'player-two'))

    with pytest.raises(ValueError):
        add_external_ref(conn, 'player:test-1', 'provider_x', '77', verification_state='verified')

    add_external_ref(conn, 'player:test-1', 'provider_x', '77', 'https://example.invalid/player/77',
                     source_name='Provider X', verification_state='verified')
    conn.commit()

    with pytest.raises(ValueError):
        add_external_ref(conn, 'player:test-2', 'provider_x', '77', 'https://example.invalid/player/other',
                         source_name='Provider X', verification_state='verified')
    conn.close()
