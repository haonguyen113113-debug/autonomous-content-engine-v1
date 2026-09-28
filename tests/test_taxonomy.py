from pathlib import Path
import sqlite3

from apps.asset_library.seed import seed_taxonomy


def test_soccer_taxonomy_seed(tmp_path: Path):
    db = tmp_path / 'engine.db'
    seed_taxonomy(db)
    conn = sqlite3.connect(db)
    assert conn.execute("select count(*) from markets where market_code='VN'").fetchone()[0] == 1
    assert conn.execute("select count(*) from categories where category_code='SOCCER_VIETNAM'").fetchone()[0] == 1
    assert conn.execute("select count(*) from competitions where competition_code='PREMIER_LEAGUE'").fetchone()[0] == 1
    assert conn.execute("select count(*) from competitions where competition_code='UEFA_CHAMPIONS_LEAGUE'").fetchone()[0] == 1
    assert conn.execute("select count(*) from competitions where competition_code='FIFA_WORLD_CUP'").fetchone()[0] == 1
    assert conn.execute("select count(*) from competitions where competition_code='V_LEAGUE_1'").fetchone()[0] == 1
    assert conn.execute("select count(*) from competitions where competition_code='ASEAN_CHAMPIONSHIP'").fetchone()[0] == 1
    conn.close()
