"""Card selector: script beats -> render-ready card decisions."""

import json
from pathlib import Path

from apps.asset_library.rights_scope import build_rights_scope
from apps.card_selector import (
    REQUIRED_SLOTS,
    SUPPORTED_MODES,
    _eligible_asset,
    normalize_upload_purpose,
    select_cards,
)
from apps.content_workflow import LAYOUT_MODES, VISUAL_MODES

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
         "rights_scope": build_rights_scope(
             platforms=["youtube"], territories=["VN"],
             commercial=True, monetization=True),
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
                             data={"hook_text": "Hang thu sap do toi nay truoc suc ep khung khiep", "metrics": []}, id="beat-1")])
    first = out["decisions"][0]
    assert first["visual_mode"] == "hook_card"
    assert first["starter_id"] == "C-11"
    assert 5 <= len(first["graphic_data"]["hook_text"].split()) <= 8
    assert any("beat-0" in r for r in first["reasons"])
    assert any("capped" in w or "8 words" in w for w in first["warnings"])
    assert not any("derived from narration" in w for w in first["warnings"])


def test_short_hook_derives_cleanly_without_warning():
    out = select_cards([_seg("Hang thu sap do toi nay",
                             mode="hook_card",
                             data={"hook_text": "Hang thu sap do toi nay"},
                             id="beat-1")])
    first = out["decisions"][0]
    assert first["graphic_data"]["hook_text"] == "Hang thu sap do toi nay"
    assert not any("cap" in w or "minimum" in w for w in first["warnings"])


def test_short_hook_without_text_returns_empty_not_fabricated():
    out = select_cards([_seg("Co noi dung nhung khong co hook",
                             mode="hook_card", id="beat-1")])
    first = out["decisions"][0]
    assert first["graphic_data"].get("hook_text", "") == ""
    # No fabricated placeholder hook text
    assert "CAU HOI TRAN DAU" not in str(first["graphic_data"])


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


def test_portrait_auto_attaches_purpose_cleared_portrait():
    cleared = {
        "asset_id": "a-portrait", "asset_type": "image",
        "rights_state": "verified", "lifecycle_state": "active",
        "original_name": "Nguyen Van A portrait", "subjects": ["Nguyen Van A"],
        "rights_scope": build_rights_scope(
            platforms=["youtube"], territories=["VN"],
            commercial=True, monetization=True),
    }
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Tien dao Nguyen Van A toa sang", mode="player_poster_side",
             data={"player_name": "Nguyen Van A",
                   "stats": [{"label": "Ban", "value": "19"}]}, id="beat-2"),
    ], assets=[cleared], purpose=PURPOSE)
    second = out["decisions"][1]
    # purpose given + is_usable_for clears the asset: auto-attach applies.
    assert second["media_asset_id"] == "a-portrait"
    assert second["suggested_asset_id"] is None
    assert any("auto-attached" in w for w in second["warnings"])


def test_portrait_not_attached_without_purpose_even_when_verified():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Tien dao Nguyen Van A toa sang", mode="player_poster_side",
             data={"player_name": "Nguyen Van A",
                   "stats": [{"label": "Ban", "value": "19"}]}, id="beat-2"),
    ], assets=[{
        "asset_id": "a-portrait", "asset_type": "image",
        "rights_state": "verified", "lifecycle_state": "active",
        "original_name": "Nguyen Van A portrait", "subjects": ["Nguyen Van A"],
        "rights_scope": build_rights_scope(
            platforms=["youtube"], territories=["VN"],
            commercial=True, monetization=True),
    }])  # purpose omitted
    second = out["decisions"][1]
    # Fail-closed: verified/active without a purpose never attaches.
    assert second["media_asset_id"] is None
    assert any("no purpose/scope" in w for w in second["warnings"])
    assert any("purpose missing" in w for w in out["plan"]["warnings"])


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
    assert any("no purpose/scope" in w for w in second["warnings"])


def test_bound_asset_forces_broll_outside_portrait_modes():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Nhin lai dien bien", mode="stat_leader",
             data={"stats": [{"label": "Ban", "value": "19"}],
                   "source": "D", "date": "D"},
             media_asset_id="a-portrait", id="beat-2"),
    ], assets=_assets(), purpose=PURPOSE)
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
    assert "C-11" in out["plan"]["starters"]


def test_deterministic():
    segments = [_seg("So sanh phong do doi dau", mode="duel_columns",
                     data={"metrics": [{"label": "X", "home": "1", "away": "0"}],
                           "source": "D", "date": "D"}, id="beat-1")]
    assert select_cards(segments) == select_cards(segments)


def test_supported_modes_mirror_workflow():
    # card_selector.SUPPORTED_MODES is computed at import time from VISUAL_MODES.
    # create_script_draft must never mutate VISUAL_MODES (template layout ids go
    # to LAYOUT_MODES), so this mirror holds regardless of import/test order.
    assert SUPPORTED_MODES == set(VISUAL_MODES) | {"media_b_roll"}
    assert "media_b_roll" in SUPPORTED_MODES
    assert "media_b_roll" not in VISUAL_MODES


def test_supported_modes_immune_to_layout_modes_mutation():
    """Regression: create_script_draft registers template layout ids
    (opening, ending, myth, takes, ...) into LAYOUT_MODES. That must never
    leak into VISUAL_MODES or change card_selector.SUPPORTED_MODES, whatever
    the order tests run in."""
    from apps.content_workflow import LAYOUT_MODES

    before_visual = set(VISUAL_MODES)
    before_supported = set(SUPPORTED_MODES)
    snapshot = set(LAYOUT_MODES)

    # Simulate create_script_draft populating LAYOUT_MODES from the template
    # package layouts.
    fake_layout_ids = {"opening", "ending", "myth", "takes", "layout_hero"}
    LAYOUT_MODES.clear()
    LAYOUT_MODES.update(fake_layout_ids)
    try:
        assert VISUAL_MODES == before_visual
        assert SUPPORTED_MODES == before_supported
        assert SUPPORTED_MODES == set(VISUAL_MODES) | {"media_b_roll"}
        assert fake_layout_ids <= (VISUAL_MODES | LAYOUT_MODES)
    finally:
        LAYOUT_MODES.clear()
        LAYOUT_MODES.update(snapshot)


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


def _feed_run(*segments, content_type="short", purpose=None, exact_terms=None):
    run = {"run_id": "a" * 12,
           "draft": {"content_type": content_type,
                     "segments": [dict(s) for s in segments]}}
    if purpose is not None:
        run["purpose"] = purpose
    if exact_terms is not None:
        run["exact_terms"] = exact_terms
    return run


PURPOSE = {"platform": "youtube", "territory": "VN", "commercial": True, "monetization": True}


def _portrait_segment():
    return _seg("Tien dao Nguyen Van A toa sang", mode="player_poster_side",
                data={"player_name": "Nguyen Van A",
                      "stats": [{"label": "Ban", "value": "19"}]}, id="beat-2")


def _portrait_assets():
    """One verified image cleared for youtube/VN/commercial, one verified
    image cleared only for tiktok/non-commercial (purpose-denied)."""
    denied_scope = build_rights_scope(
        platforms=["tiktok"], territories=["VN"],
        commercial=False, monetization=False,
    )
    cleared_scope = build_rights_scope(
        platforms=["youtube"], territories=["VN"],
        commercial=True, monetization=True,
    )
    return [
        {"asset_id": "a-scoped-denied", "asset_type": "image",
         "rights_state": "verified", "lifecycle_state": "active",
         "original_name": "Nguyen Van A warmup", "subjects": ["Nguyen Van A"],
         "rights_scope": denied_scope},
        {"asset_id": "a-cleared", "asset_type": "image",
         "rights_state": "verified", "lifecycle_state": "active",
         "original_name": "Nguyen Van A portrait", "subjects": ["Nguyen Van A"],
         "rights_scope": cleared_scope},
    ]


def test_apply_feeds_segments_and_stores_plan(tmp_path):
    from apps.card_selector import apply_card_plan

    run = _feed_run(
        _seg("Hang thu sap do toi nay", mode="statline_scorecard",
             data={"hook_text": "Hang thu sap do toi nay", "metrics": []}, id="beat-1"),
        _seg("Bang doi dau", mode="duel_columns",
             data={"metrics": [{"label": "X", "home": "1", "away": "0"}],
                   "source": "D", "date": "D"}, id="beat-2"))
    plan = apply_card_plan(tmp_path, run)
    assert run["draft"]["segments"][0]["visual_mode"] == "hook_card"
    assert run["draft"]["segments"][0]["graphic_data"]["hook_text"] == "Hang thu sap do toi nay"
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

    cleared_scope = build_rights_scope(
        platforms=["youtube"], territories=["VN"],
        commercial=True, monetization=True,
    )
    conn = connect(tmp_path / "runtime/engine.db")
    conn.execute(
        "INSERT INTO assets (asset_id, original_name, stored_path, asset_type,"
        " size_bytes, sha256, source_type, rights_state, lifecycle_state,"
        " metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("enzo-por", "Enzo Fernandes portrait", "runtime/assets/library/x.png",
         "image", 10, "sha256-" + "e" * 58, "test", "verified", "active",
         json.dumps({"rights_scope": cleared_scope})))
    conn.commit()
    conn.close()
    run = _feed_run(
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Tien dao Enzo Fernandes toa sang", mode="player_poster_side",
             data={"player_name": "Enzo Fernandes",
                   "stats": [{"label": "Ban", "value": "19"}]}, id="beat-2"),
        purpose=PURPOSE,
    )
    plan = apply_card_plan(tmp_path, run)
    plan_purpose = plan["plan"]["purpose"]
    assert {k: plan_purpose[k] for k in PURPOSE} == PURPOSE
    second = run["draft"]["segments"][1]
    assert second.get("media_asset_id") == "enzo-por"  # owner standing order: auto-attach
    assert plan["decisions"][1]["suggested_asset_id"] is None


def test_apply_auto_picks_broll_pool_for_closing_hook(tmp_path):
    import sqlite3

    from apps.asset_library.registry import connect
    from apps.card_selector import apply_card_plan

    cleared_scope = build_rights_scope(
        platforms=["youtube"], territories=["VN"],
        commercial=True, monetization=True,
    )
    conn = connect(tmp_path / "runtime/engine.db")
    conn.execute(
        "INSERT INTO assets (asset_id, original_name, stored_path, asset_type,"
        " size_bytes, sha256, source_type, rights_state, lifecycle_state,"
        " purpose_code, metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ("stad-pool", "Night stadium wide", "runtime/assets/library/x.png",
         "image", 10, "sha256-" + "f" * 58, "test", "verified", "active",
         "broll-generic", json.dumps({"rights_scope": cleared_scope})))
    conn.commit()
    conn.close()
    run = _feed_run(
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Dem nay"}, id="beat-1"),
        _seg("Ket luan", mode="hook_card",
             data={"hook_text": "Het gio"}, id="beat-2"),
        purpose=PURPOSE,
    )
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


def test_eligible_asset_verified_not_sufficient_with_purpose():
    denied, cleared = _portrait_assets()
    # purpose omitted: verified/active is NOT sufficient — fail closed, no
    # library asset is treated as cleared for use.
    for asset in (denied, cleared):
        assert _eligible_asset(asset) is False
        assert _eligible_asset(asset, None) is False
    # purpose given: verified alone is not sufficient.
    assert _eligible_asset(cleared, PURPOSE) is True
    assert _eligible_asset(denied, PURPOSE) is False  # tiktok-only, non-commercial
    assert _eligible_asset(
        {"asset_type": "video", "rights_state": "verified", "lifecycle_state": "active"},
        PURPOSE) is False


def test_select_cards_purpose_blocks_uncleared_portrait():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _portrait_segment(),
    ], assets=_portrait_assets(), purpose=PURPOSE)
    second = out["decisions"][1]
    # a-scoped-denied matches the name but fails is_usable_for for this purpose.
    assert second["media_asset_id"] == "a-cleared"
    assert any("auto-attached" in w for w in second["warnings"])


def test_select_cards_without_purpose_is_fail_closed():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _portrait_segment(),
    ], assets=_portrait_assets())  # purpose omitted
    second = out["decisions"][1]
    # Fail-closed: no purpose → no library asset attached, even when a
    # name-matched portrait exists and verified/active images are available.
    assert second["media_asset_id"] is None
    assert any("no purpose/scope" in w for w in second["warnings"])
    assert any("purpose missing" in w for w in out["plan"]["warnings"])
    assert out["plan"]["purpose"] is None
    assert out["plan"]["exact_terms"] is None


def test_select_cards_carries_purpose_and_exact_terms():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
    ], assets=_portrait_assets(), purpose=PURPOSE,
       exact_terms=["Nguyen Van A", "U23"])
    assert out["plan"]["purpose"] == PURPOSE
    assert out["plan"]["exact_terms"] == ["Nguyen Van A", "U23"]

    out_plain = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
    ])
    assert out_plain["plan"]["purpose"] is None
    assert out_plain["plan"]["exact_terms"] is None


def test_apply_card_plan_derives_purpose_and_blocks_uncleared_portrait(tmp_path):
    import json

    from apps.asset_library.registry import connect
    from apps.card_selector import apply_card_plan

    denied_scope = build_rights_scope(
        platforms=["tiktok"], territories=["VN"],
        commercial=False, monetization=False,
    )
    conn = connect(tmp_path / "runtime/engine.db")
    conn.execute(
        "INSERT INTO assets (asset_id, original_name, stored_path, asset_type,"
        " size_bytes, sha256, source_type, rights_state, lifecycle_state, metadata_json)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("enzo-por", "Enzo Fernandes portrait", "runtime/assets/library/x.png",
         "image", 10, "sha256-" + "e" * 58, "test", "verified", "active",
         json.dumps({"rights_scope": denied_scope})),
    )
    conn.commit()
    conn.close()

    run = _feed_run(
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Tien dao Enzo Fernandes toa sang", mode="player_poster_side",
             data={"player_name": "Enzo Fernandes",
                   "stats": [{"label": "Ban", "value": "19"}]}, id="beat-2"),
        purpose=PURPOSE,
    )
    plan = apply_card_plan(tmp_path, run)
    plan_purpose = plan["plan"]["purpose"]
    assert {k: plan_purpose[k] for k in PURPOSE} == PURPOSE
    # verified/active but not cleared for youtube + commercial: no auto-attach.
    assert run["draft"]["segments"][1].get("media_asset_id") is None
    assert any("typographic fallback" in r
               for r in plan["decisions"][1]["reasons"])

    # draft-level purpose is the fallback when run has none.
    run2 = _feed_run(
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        _seg("Tien dao Enzo Fernandes toa sang", mode="player_poster_side",
             data={"player_name": "Enzo Fernandes",
                   "stats": [{"label": "Ban", "value": "19"}]}, id="beat-2"),
    )
    run2["draft"]["purpose"] = PURPOSE
    plan2 = apply_card_plan(tmp_path, run2)
    plan2_purpose = plan2["plan"]["purpose"]
    assert {k: plan2_purpose[k] for k in PURPOSE} == PURPOSE
    assert run2["draft"]["segments"][1].get("media_asset_id") is None


def test_normalize_upload_purpose_flat_destinations_and_none():
    # Flat purpose: run-level wins over draft-level.
    got = normalize_upload_purpose(
        {"purpose": {"platform": "youtube", "territory": "VN",
                     "commercial": True, "monetization": True}},
        {"purpose": {"platform": "tiktok", "territory": "VN",
                     "commercial": False, "monetization": False}},
    )
    assert {k: got[k] for k in PURPOSE} == PURPOSE
    assert got["edit"] is False
    assert got["credit_planned"] is False
    assert got["credit_text"] is None
    assert got["use_count"] == 0

    # destinations/distribution: {platform, market/territory, commercial, monetization}.
    got = normalize_upload_purpose(
        {},
        {"distribution": {"destinations": [
            {"platform": "local_file"},
            {"platform": "tiktok", "market": "VN",
             "commercial": False, "monetization": False},
        ]}},
    )
    assert got["platform"] == "tiktok"
    assert got["territory"] == "VN"
    assert got["commercial"] is False
    assert got["monetization"] is False

    # No usable intent -> None (fail closed).
    assert normalize_upload_purpose({}, {}) is None
    assert normalize_upload_purpose(
        {"destinations": [{"platform": "local_file"}]}, {}) is None
    assert normalize_upload_purpose(
        {"purpose": {"commercial": True}}, {}) is None  # no platform/territory


def test_normalize_upload_purpose_matches_renderer():
    from apps.video_renderer import _render_purpose

    run = {
        "run_id": "a" * 12,
        "purpose": {"platform": "youtube", "territory": "VN",
                    "commercial": True, "monetization": True},
    }
    draft = {"destinations": [{"platform": "tiktok", "market": "VN",
                               "commercial": False, "monetization": False}]}
    selector = normalize_upload_purpose(run, draft)
    renderer = _render_purpose(run, draft)
    # Selector and renderer share the normalizer -> identical purpose shape.
    assert selector == renderer
    assert selector["platform"] == "youtube"
    assert selector["territory"] == "VN"
    assert selector["commercial"] is True
    assert selector["monetization"] is True

    # Empty intent -> None on both sides.
    assert normalize_upload_purpose({}, {}) is None
    assert _render_purpose({}, {}) is None


def test_missing_visual_mode_warns_and_falls_back_to_tactical():
    out = select_cards([
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
        # Segment thuần khong co khoa visual_mode (khong qua helper _seg, vi
        # helper mac dinh visual_mode = tactical_explainer).
        {"id": "beat-2", "narration": "Nhin lai dien bien tran dau",
         "visual": "", "graphic_data": {}, "duration_seconds": 6},
    ])
    second = out["decisions"][1]
    # Not silently defaulted: declared fallback with an explicit warning.
    assert second["visual_mode"] == "tactical_explainer"
    assert any(
        "no visual_mode declared; deterministic pitch-plate fallback" in w
        for w in second["warnings"])


def test_apply_card_plan_normalizes_destinations_purpose(tmp_path):
    from apps.card_selector import apply_card_plan

    run = _feed_run(
        _seg("Mo dau", mode="hook_card",
             data={"hook_text": "Mot tran cau dinh doat"}, id="beat-1"),
    )
    run["draft"]["destinations"] = [
        {"platform": "tiktok", "market": "VN",
         "commercial": False, "monetization": False}]
    plan = apply_card_plan(tmp_path, run)
    plan_purpose = plan["plan"]["purpose"]
    assert plan_purpose is not None
    assert plan_purpose["platform"] == "tiktok"
    assert plan_purpose["territory"] == "VN"
    assert plan_purpose["commercial"] is False
    assert plan_purpose["monetization"] is False


def test_hook_text_never_derived_from_narration():
    # Narration dài nhưng graphic_data KHÔNG có hook_text: slot phải để trống,
    # không được suy diễn hook từ narration (fail-closed).
    out = select_cards([_seg("Co noi dung dai dai dai dai dai dai dai dai dai",
                             mode="hook_card", id="beat-1")])
    first = out["decisions"][0]
    assert first["graphic_data"].get("hook_text", "") == ""
    assert not any("hook_text" in w and "narration" in w
                   for w in first["warnings"] + first["reasons"])


def test_hook_text_normalized_from_graphic_data_not_narration():
    # graphic_data có hook_text dài; narration hoàn toàn khác. Hook_text phải
    # được cắt từ graphic_data, KHÔNG được lấy từ đầu narration.
    narration = "Toan bo noi dung noi dung dai dai dai dai dai dai dai dai dai dai"
    data = {"hook_text": "Mot cau hook dai dai dai dai dai dai dai dai dai dai dai"}
    out = select_cards([_seg(narration, mode="hook_card",
                             data=data, id="beat-1")])
    first = out["decisions"][0]
    # Cắt từ graphic_data.hook_text (8 từ đầu), không phải từ narration.
    expected = " ".join(data["hook_text"].split()[:8])
    assert first["graphic_data"]["hook_text"] == expected
    assert first["graphic_data"]["hook_text"] != " ".join(narration.split()[:8])
    assert any("capped" in w or "8 words" in w for w in first["warnings"])
    assert not any("derived from narration" in w
                   for w in first["warnings"] + first["reasons"])
