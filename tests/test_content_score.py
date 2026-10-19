"""Script Score: deterministic rule-based draft scoring."""

from apps.content_score import SCORE_VERSION, score_script

ALIASES = ["Manchester United", "Bruno Fernandes", "Premier League", "Hanoi FC"]


def _seg(narration, **extra):
    segment = {"id": "beat-x", "narration": narration,
               "evidence_refs": [], "duration_seconds": 8}
    segment.update(extra)
    return segment


def test_sourced_specific_beat_scores_high():
    out = score_script([
        _seg("Bruno Fernandes ghi 2 ban cho Manchester United o Premier League tran toi",
             evidence_refs=["opta match report 2026-10-10"], duration_seconds=8),
        _seg("Hanoi FC choi pressing tam cao va thang tran nay", duration_seconds=8),
    ], entity_aliases=ALIASES)
    assert out["version"] == SCORE_VERSION
    assert out["score"] >= 70
    assert out["components"]["entity"] == 100


def test_unresolved_marker_fails_grounding():
    out = score_script([_seg("[CẦN NGUỒN] Thêm một quan sát cụ thể về trận đấu")],
                       entity_aliases=ALIASES)
    assert out["components"]["grounding"] == 0
    assert any("unresolved" in f["message"] for f in out["findings"])


def test_numbers_without_evidence_penalized():
    bare = score_script([_seg("Cau thu ghi 25 ban sau 30 tran mua nay")],
                        entity_aliases=ALIASES)
    sourced = score_script([_seg("Cau thu ghi 25 ban sau 30 tran mua nay",
                                 evidence_refs=["club season review"])],
                           entity_aliases=ALIASES)
    assert bare["components"]["grounding"] < sourced["components"]["grounding"]


def test_generic_talk_lowers_entity():
    out = score_script([_seg("Hang thu can choi tap trung hon trong hiep hai")],
                       entity_aliases=ALIASES)
    assert out["components"]["entity"] == 0


def test_overlong_narration_lowers_speech():
    out = score_script([_seg("x" * 400, duration_seconds=6)], entity_aliases=ALIASES)
    assert out["components"]["speech"] < 100
    assert any("overruns" in f["message"] for f in out["findings"])


def test_repeated_beats_lower_variety():
    narration = "Doi bong choi pressing tam cao va gianh lai bong rat nhanh chong"
    out = score_script([_seg(narration), _seg(narration)], entity_aliases=ALIASES)
    assert out["components"]["variety"] < 100


def test_filler_lowers_readability():
    clean = score_script([_seg("Doi bong van hanh tot o hanh lang trai toi nay")],
                         entity_aliases=ALIASES)
    spammy = score_script([_seg("Dang ky kenh ngay vi tran nay khong the bo lo nhe ban")],
                          entity_aliases=ALIASES)
    assert spammy["components"]["readability"] < clean["components"]["readability"]


def test_bad_input_never_raises():
    assert score_script(None, entity_aliases=ALIASES)["score"] == 0
    assert score_script([], entity_aliases=ALIASES)["score"] == 0
    assert score_script(["nope", 42], entity_aliases=ALIASES)["score"] >= 0


def test_deterministic():
    segments = [_seg("Bruno Fernandes toa sang o tran derby toi qua",
                     evidence_refs=["match report"], duration_seconds=8)]
    assert score_script(segments, entity_aliases=ALIASES) == \
        score_script(segments, entity_aliases=ALIASES)


def test_default_aliases_load_from_repo():
    out = score_script([_seg("Manchester United thang tran derby toi qua")])
    assert out["components"]["entity"] == 100
