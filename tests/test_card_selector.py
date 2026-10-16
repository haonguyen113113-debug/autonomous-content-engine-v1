"""Card selector: script beats -> render-ready card decisions."""

import json
from pathlib import Path

from apps.card_selector import (
    REQUIRED_SLOTS,
    SUPPORTED_MODES,
    select_cards,
)
from apps.content_workflow import VISUAL_MODES

ROOT = Path(__file__).resolve().parent.parent


def _seg(narration, mode="tactical_explainer", data=None, **extra):
    segment = {"id": extra.pop("id", "beat-x"), "narration": narration,
               "visual": extra.pop("visual", ""), "visual_mode": mode,
               "graphic_data": data or {}, "duration_seconds": 6}
    segment.update(extra)
    return segment


def _assets():
    return [
        {"asset_id": "a-portrait", "asset_type": "image",
         "rights_state": "verified", "lifecycle_state": "active",
         "original_name": "Nguyen Van A portrait",
         "subjects": ["Nguyen Van A"],
         "metadata": {"visual_context_note": "striker portrait"}},
        {"asset_id": "a-unverified", "asset_type": "image",
         "rights_state": "unverified", "lifecycle_state": "ingested",
         "original_name": "stadium night"},
        {"asset_id": "a-video", "asset_type": "video",
         "rights_state": "verified", "lifecycle_state": "active",
         "original_name": "match clip"},
    ]


def test_beat_zero_opens_on_hook_with_derived_text():
    out = select_cards([_seg("Hang thu sap do toi nay truoc suc ep khung khiep",
                             mode="statline_scorecard",
                             data={"metrics": []}, id="beat-1")])
    first = out["decisions"][0]
    assert first["visual_mode"] == "hook_card"
    assert first["starter_id"] == "C-03"
    assert 5 <= len(first["graphic_data"]["hook_text"].split()) <= 8
    assert any("beat-0" in r for r in first["reasons"])
    assert any("8-word cap" in w for w in first["warnings"])


def test_short_hook_derives_cleanly_without_warning():
    out = select_cards([_seg("Hang thu sap do toi nay",
                             mode="hook_card", id="beat-1")])
    first = out["decisions"][0]
    assert first["graphic_data"]["hook_text"] == "Hang thu sap do toi nay"
    assert not any("cap" in w or "minimum" in w for w in first["warnings"])


def test_unknown_mode_falls_back_with_warning():
    out = select_cards([_seg("Mo dau", mode="nope-missing", id="beat-9")])
    # beat-0 rule still applies; the unknown-mode warning must survive it
    assert any("unknown visual_mode" in w for w in out["decisions"][0]["warnings"])


def test_duel_signals_pick_duel_columns_and_starter():
    out = select_cards([
        _seg("Mo dau tran dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Bang doi dau suc manh hai doi",
             mode="comparison_duel",
             data={"metrics": [{"label": "Ban", "home": "45", "away": "38"}],
                   "source": "Demo", "date": "Demo"}, id="beat-2"),
    ])
    second = out["decisions"][1]
    assert second["visual_mode"] == "comparison_duel"
    assert second["starter_id"] == "C-07"
    assert second["score"] >= 70


def test_portrait_without_verified_asset_warns_and_penalizes():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Tien dao Nguyen Van A toa sang", mode="player_poster_side",
             data={"player_name": "Nguyen Van A",
                   "stats": [{"label": "Ban", "value": "19"}]}, id="beat-2"),
    ], assets=[])
    second = out["decisions"][1]
    assert any("portrait" in s
               for s in second["warnings"] + second["reasons"])
    assert second["media_asset_id"] is None


def test_portrait_auto_attaches_verified_asset():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Tien dao Nguyen Van A toa sang", mode="player_poster_side",
             data={"player_name": "Nguyen Van A",
                   "stats": [{"label": "Ban", "value": "19"}]}, id="beat-2"),
    ], assets=_assets())
    second = out["decisions"][1]
    # Owner standing order 16/10: verified/active portraits auto-attach.
    assert second["media_asset_id"] == "a-portrait"
    assert second["suggested_asset_id"] is None
    assert any("auto-attached" in w for w in second["warnings"])


def test_unverified_binding_is_dropped():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Khung canh san van dong", mode="score_card",
             data={"home": "A", "away": "B", "score": "2 - 0",
                   "source": "D", "date": "D"},
             media_asset_id="a-unverified", id="beat-2"),
    ], assets=_assets())
    second = out["decisions"][1]
    assert second["media_asset_id"] is None
    assert any("binding dropped" in w for w in second["warnings"])


def test_bound_asset_forces_broll_outside_portrait_modes():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Nhin lai dien bien", mode="stat_leader",
             data={"stats": [{"label": "Ban", "value": "19"}],
                   "source": "D", "date": "D"},
             media_asset_id="a-portrait", id="beat-2"),
    ], assets=_assets())
    second = out["decisions"][1]
    assert second["visual_mode"] == "media_b_roll"
    assert second["media_asset_id"] == "a-portrait"


def test_broll_without_asset_falls_back_to_pitch():
    out = select_cards([_seg("Mo dau tran", mode="media_b_roll", id="beat-1")])
    # beat-0 hook rule wins, but the fallback reason must be recorded
    assert any("pitch plate" in r for r in out["decisions"][0]["reasons"])


def test_immediate_repeat_prefers_declared_but_triple_flips():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("So sanh so do suc manh", mode="duel_columns",
             data={"metrics": [{"label": "X", "home": "1", "away": "0"}],
                   "source": "D", "date": "D"}, id="beat-2"),
        _seg("So sanh so do kha nang", mode="duel_columns",
             data={"metrics": [{"label": "Y", "home": "2", "away": "2"}],
                   "source": "D", "date": "D"}, id="beat-3"),
        _seg("So sanh so do hieu qua", mode="duel_columns",
             data={"metrics": [{"label": "Z", "home": "3", "away": "1"}],
                   "source": "D", "date": "D"}, id="beat-4"),
    ])
    got = [d["visual_mode"] for d in out["decisions"]]
    assert got[1] == "duel_columns" and got[2] == "duel_columns"
    assert got[3] != "duel_columns"  # third in a row flips for variety


def test_fixture_maps_to_mr11():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Tran dau sap toi"}, id="beat-1"),
        _seg("Lich thi dau vong toi gap doi thu manh", mode="fixture_card",
             data={"home": "HÀ NỘI", "away": "NAM ĐỊNH"}, id="beat-2"),
    ])
    second = out["decisions"][1]
    assert second["visual_mode"] == "fixture_card"
    assert second["starter_id"] == "MR-11"


def test_long_pressing_maps_to_ta06():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Cau hoi chien thuat"}, id="beat-1"),
        _seg("Doi hinh pressing tam cao", mode="tactical_explainer", id="beat-2"),
    ], content_type="long")
    assert out["decisions"][1]["starter_id"] == "TA-06"


def test_long_tactical_signals_map_to_sprint2():
    cases = [
        ("Doi hinh xuat phat voi so do 4-3-3", "TA-04"),
        ("Trien khai bong tu tuyen duoi", "TA-07"),
        ("Bay pressing ep doi thu ra bien", "TA-08"),
        ("Khoang trong sau lung hau ve", "TA-09"),
        ("Hau ve chong bien vuot qua", "TA-10"),
        ("Cuoc doi dau 1v1 o canh phai", "TA-13"),
        ("Cau truc truoc va sau khi thay doi", "TA-15"),
        ("Ban do nhiet vung hoat dong", "TA-17"),
        ("Pha dieu chinh chien thuat", "TA-14"),
    ]
    for narration, starter in cases:
        out = select_cards([
            _seg("Mo dau", mode="hook_card",
                 data={"hook_text": "Cau hoi chien thuat"}, id="beat-1"),
            _seg(narration, mode="tactical_explainer", id="beat-2"),
        ], content_type="long")
        assert out["decisions"][1]["starter_id"] == starter, narration


def test_plan_aggregates_warnings_and_counts():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Con so an tuong", mode="stat_leader",
             data={"stats": [{"label": "Ban", "value": "19"}]}, id="beat-2"),
    ])
    assert out["plan"]["beats"] == 2
    assert out["plan"]["mode_counts"]["hook_card"] == 1
    assert any("source+date" in w for w in out["plan"]["warnings"])
    assert "C-03" in out["plan"]["starters"]


def test_deterministic():
    segments = [_seg("So sanh phong do doi dau", mode="duel_columns",
                     data={"metrics": [{"label": "X", "home": "1", "away": "0"}],
                           "source": "D", "date": "D"}, id="beat-1")]
    assert select_cards(segments) == select_cards(segments)


def test_supported_modes_mirror_workflow():
    assert SUPPORTED_MODES == set(VISUAL_MODES) | {"media_b_roll"}


def test_registry_slots_match_package():
    package = json.loads(
        (ROOT / "template_foundation/templates/allen-knows-ball/12.0.0"
         / "graphic-templates.json").read_text(encoding="utf-8"))
    package_required = {}
    for layout in package["layouts"]:
        keys = [r.split("graphic_data.", 1)[1] for r in layout.get("required_data", [])
                if r.startswith("graphic_data.")]
        package_required[layout["id"]] = keys
    for mode, keys in REQUIRED_SLOTS.items():
        if mode in package_required:
            assert set(keys) <= set(package_required[mode]), mode
            extra = set(package_required[mode]) - set(keys)
            assert extra <= {"tactical_diagram"}, (mode, extra)


def _feed_run(*segments, content_type="short"):
    return {"run_id": "a" * 12,
            "draft": {"content_type": content_type,
                      "segments": [dict(s) for s in segments]}}


def test_apply_feeds_segments_and_stores_plan(tmp_path):
    from apps.card_selector import apply_card_plan

    run = _feed_run(
        _seg("Hang thu sap do toi nay", mode="statline_scorecard",
             data={"metrics": []}, id="beat-1"),
        _seg("Bang doi dau", mode="duel_columns",
             data={"metrics": [{"label": "X", "home": "1", "away": "0"}],
                   "source": "D", "date": "D"}, id="beat-2"))
    plan = apply_card_plan(tmp_path, run)
    assert run["draft"]["segments"][0]["visual_mode"] == "hook_card"
    assert "hook_text" in run["draft"]["segments"][0]["graphic_data"]
    assert run["card_plan"]["plan"]["beats"] == 2
    assert plan is run["card_plan"]


def test_apply_drops_invalid_binding(tmp_path):
    from apps.card_selector import apply_card_plan

    run = _feed_run(
        _seg("Khung canh", mode="score_card",
             data={"home": "A", "away": "B", "score": "1 - 0"},
             media_asset_id="ghost", id="beat-1"))
    apply_card_plan(tmp_path, run)
    assert "media_asset_id" not in run["draft"]["segments"][0]


def test_apply_auto_attaches_library_portrait(tmp_path):
    import sqlite3

    from apps.asset_library.registry import connect
    from apps.card_selector import apply_card_plan

    conn = connect(tmp_path / "runtime/engine.db")
    conn.execute(
        "INSERT INTO assets (asset_id, original_name, stored_path, asset_type,"
        " size_bytes, sha256, source_type, rights_state, lifecycle_state,"
        " metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("enzo-por", "Enzo Fernandes portrait", "runtime/assets/library/x.png",
         "image", 10, "sha256-" + "e" * 58, "test", "verified", "active", "{}"))
    conn.commit()
    conn.close()
    run = _feed_run(
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Tien dao Enzo Fernandes toa sang", mode="player_poster_side",
             data={"player_name": "Enzo Fernandes",
                   "stats": [{"label": "Ban", "value": "19"}]}, id="beat-2"))
    plan = apply_card_plan(tmp_path, run)
    second = run["draft"]["segments"][1]
    assert second.get("media_asset_id") == "enzo-por"  # owner standing order: auto-attach
    assert plan["decisions"][1]["suggested_asset_id"] is None


def test_apply_auto_picks_broll_pool_for_closing_hook(tmp_path):
    import sqlite3

    from apps.asset_library.registry import connect
    from apps.card_selector import apply_card_plan

    conn = connect(tmp_path / "runtime/engine.db")
    conn.execute(
        "INSERT INTO assets (asset_id, original_name, stored_path, asset_type,"
        " size_bytes, sha256, source_type, rights_state, lifecycle_state,"
        " purpose_code, metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("stad-pool", "Night stadium wide", "runtime/assets/library/x.png",
         "image", 10, "sha256-" + "f" * 58, "test", "verified", "active",
         "broll-generic", "{}"))
    conn.commit()
    conn.close()
    run = _feed_run(
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Dem nay"}, id="beat-1"),
        _seg("Ket luan", mode="hook_card",
             data={"hook_text": "Het gio"}, id="beat-2"))
    apply_card_plan(tmp_path, run)
    first, second = run["draft"]["segments"]
    assert "media_asset_id" not in first  # opener keeps branded hook
    assert second.get("media_asset_id") == "stad-pool"
    assert second["visual_mode"] == "media_b_roll"


def test_sprint3_short_story_signals_map_to_p1():
    cases = [
        # (narration, mode, data, expected starter)
        ("Tin nóng kết quả mới nhất tối nay", "hook_card",
         {"hook_text": "Tin nóng tối nay"}, "MR-01"),
        ("Câu chuyện ngoài sân đầy bất ngờ", "hook_card",
         {"hook_text": "Câu chuyện ngoài sân"}, "BP-01"),
        ("Tỷ số nghỉ giữa hiệp một", "score_card",
         {"home": "A", "away": "B", "score": "1 - 0"}, "MR-03"),
        ("Cầu thủ xuất sắc nhất trận đấu", "player_poster_side",
         {"player_name": "Nguyen Van A",
          "stats": [{"label": "Ban", "value": "2"}]}, "MR-08"),
        ("Hồ sơ sự nghiệp chân dung cầu thủ", "player_poster_side",
         {"player_name": "Nguyen Van A",
          "stats": [{"label": "Ban", "value": "2"}]}, "BP-03"),
        ("Phí chuyển nhượng kỷ lục mùa hè", "duel_columns",
         {"metrics": [{"label": "Phi", "home": "85", "away": "120"}],
          "source": "D", "date": "D"}, "BP-07"),
        ("Derby kình địch lịch sử đối đầu", "duel_columns",
         {"metrics": [{"label": "Thang", "home": "12", "away": "8"}],
          "source": "D", "date": "D"}, "BP-10"),
        ("Top ghi bàn nhiều nhất mùa giải", "stat_leader",
         {"stats": [{"label": "Ban", "value": "19"}],
          "source": "D", "date": "D"}, "BP-15"),
        ("Điểm số hiệu số cuộc đua vô địch", "stat_leader",
         {"stats": [{"label": "Diem", "value": "45"}],
          "source": "D", "date": "D"}, "MR-09"),
        ("Kiểm soát bóng cú sút xG trận đấu", "stat_leader",
         {"stats": [{"label": "xG", "value": "1.8"}],
          "source": "D", "date": "D"}, "MR-07"),
        ("Cột mốc sự nghiệp career cầu thủ", "chart_timeline",
         {"values": [1, 2, 3]}, "BP-04"),
        ("Tái sinh sau sa sút phong độ", "chart_timeline",
         {"values": [1, 2, 3]}, "BP-05"),
        ("Di sản lịch sử bóng đá", "chart_timeline",
         {"values": [1, 2, 3]}, "BP-11"),
        ("Bước ngoặt turning point trận đấu", "chart_timeline",
         {"values": [1, 2, 3]}, "BP-17"),
        ("Timeline trình tự diễn biến trận", "chart_timeline",
         {"values": [1, 2, 3]}, "MR-05"),
        ("Cần kiểm chứng fact check xác minh", "source_card",
         {"source": "D", "date": "D", "claim": "Tin đồn"}, "BP-20"),
    ]
    for narration, mode, data, starter in cases:
        out = select_cards([
            _seg("Mo dau cau chuyen", mode="hook_card",
                 data={"hook_text": "Mo dau cau chuyen"}, id="beat-1"),
            _seg(narration, mode=mode, data=data, id="beat-2"),
        ])
        assert out["decisions"][1]["starter_id"] == starter, (narration, mode)


def test_sprint3_new_modes_have_starters():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mo dau cau chuyen"}, id="beat-1"),
        _seg("Danh sách lịch thi đấu sắp tới", mode="fixture_list",
             data={"fixtures": [{"home": "A", "away": "B"}],
                   "source": "D", "date": "D"}, id="beat-2"),
        _seg("Thẻ đỏ truất quyền thi đấu", mode="discipline_card",
             data={"player_name": "Nguyen Van A"}, id="beat-3"),
        _seg("Chào đón tân binh gia nhập", mode="welcome_card",
             data={"player_name": "Nguyen Van A"}, id="beat-4"),
        _seg("Anh ấy nói rằng đội sẽ vô địch", mode="quote_card",
             data={"claim": "Chúng tôi sẽ vô địch"}, id="beat-5"),
    ])
    starters = [d["starter_id"] for d in out["decisions"]]
    assert starters[1] == "MR-11"
    assert starters[2] == "MR-06"
    assert starters[3] == "BP-06"
    assert starters[4] == "C-05"


def test_sprint3_long_hook_and_fallbacks():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Cau hoi chien thuat"}, id="beat-1"),
        _seg("Tỷ số chung cuộc trận đấu", mode="score_card",
             data={"home": "A", "away": "B", "score": "2 - 0"}, id="beat-2"),
    ], content_type="long")
    assert out["decisions"][0]["starter_id"] == "TA-01"
    assert out["decisions"][1]["starter_id"] == "TA-02"
