"""Card selector: beat_intent as a soft deterministic tie-break for visual_mode.

Covers:
- intent can select a contract grammar but never a legacy card,
- hard constraints (beat-0 hook, player lock) still outrank intent,
- missing/invalid intent leaves scoring unchanged and never crashes,
- same input yields same output (deterministic).

beat_intent is the 4-field semantic intent normalized by
apps.scene_graph.intent.normalize_beat_intent; it is advisory only and never
drives layout, coordinates, font, color, motion or transition.
"""

from apps.card_selector import select_cards

FULL_INTENT = {
    "image_goal": "show_evidence",
    "focus_subject": "",
    "evidence_type": "sourced_stat",
    "emphasis_level": "standard",
}


def _seg(narration, mode=None, data=None, id="beat-1", beat_intent=None, visual=""):
    segment = {
        "id": id,
        "narration": narration,
        "visual": visual,
        "visual_mode": mode,
        "graphic_data": data or {},
        "duration_seconds": 6,
    }
    if beat_intent is not None:
        segment["beat_intent"] = beat_intent
    return segment


def test_legacy_goal_intent_does_not_override_contract_score():
    # "ban thang" used to trigger the legacy goal_card route. C7 12.0.0 has no
    # contract goal card (MR-04 is partial and executes only score_card), so
    # the planner must keep the contract score_card even when the semantic
    # intent hints goal_card. Intent is advisory; contract eligibility and
    # reviewed data are hard constraints.
    seg0 = _seg("mo dau", mode="hook_card", data={"hook_text": "X"}, id="beat-0")
    with_intent = _seg("ban thang ti so", mode=None,
                       data={"home": "A", "away": "B", "score": "1-0",
                             "hook_text": "Ti so tran dau"},
                       id="beat-1", beat_intent=FULL_INTENT)
    without_intent = _seg("ban thang ti so", mode=None,
                          data={"home": "A", "away": "B", "score": "1-0",
                                "hook_text": "Ti so tran dau"},
                          id="beat-1")
    out_with = select_cards([seg0, with_intent])
    out_without = select_cards([seg0, without_intent])
    assert out_with["decisions"][1]["visual_mode"] == "score_card"
    assert out_without["decisions"][1]["visual_mode"] == "score_card"
    assert out_with["decisions"][1]["card_execution"] == "contract"
    assert out_with["decisions"][1]["production_ready"] is True


def test_intent_compare_numbers_consistent_with_signal_order():
    # compare_numbers hints score_card (not goal_card). score_card is already
    # first in signal order, so intent does not flip the result — no crash,
    # no surprising override.
    seg0 = _seg("mo dau", mode="hook_card", data={"hook_text": "X"}, id="beat-0")
    seg = _seg("ban thang ti so", mode=None,
               data={"home": "A", "away": "B", "score": "1-0"},
               id="beat-1",
               beat_intent={"image_goal": "compare_numbers", "focus_subject": "",
                            "evidence_type": "sourced_stat", "emphasis_level": "standard"})
    out = select_cards([seg0, seg])
    assert out["decisions"][1]["visual_mode"] == "score_card"


def test_beat0_hook_outranks_intent():
    # Beat-0 always opens on hook_card even when intent hints another mode.
    seg = _seg("ban thang ti so", mode=None,
               data={"home": "A", "away": "B", "score": "1-0"},
               id="beat-1",
               beat_intent={"image_goal": "compare_numbers", "focus_subject": "",
                            "evidence_type": "sourced_stat", "emphasis_level": "standard"})
    out = select_cards([seg])  # single segment -> index 0 -> beat-0 rule
    assert out["decisions"][0]["visual_mode"] == "hook_card"


def test_intent_missing_invalid_does_not_crash():
    data = {"home": "A", "away": "B", "score": "1-0"}
    seg0 = _seg("mo dau", mode="hook_card", data={"hook_text": "X"}, id="beat-0")
    variants = [
        _seg("ban thang ti so", mode=None, data=dict(data), id="beat-1"),  # no intent key
        _seg("ban thang ti so", mode=None, data=dict(data), id="beat-1", beat_intent={}),
        _seg("ban thang ti so", mode=None, data=dict(data), id="beat-1",
             beat_intent={"image_goal": "not_a_goal", "focus_subject": "",
                          "evidence_type": "none", "emphasis_level": "standard"}),
    ]
    for seg in variants:
        out = select_cards([seg0, seg])
        # No usable intent -> base scoring tie -> score_card (signal order)
        assert out["decisions"][1]["visual_mode"] == "score_card"


def test_deterministic_same_input_same_output():
    seg0 = _seg("mo dau", mode="hook_card", data={"hook_text": "X"}, id="beat-0")
    seg1 = _seg("ban thang ti so", mode=None,
                data={"home": "A", "away": "B", "score": "1-0"},
                id="beat-1", beat_intent=FULL_INTENT)
    out1 = select_cards([seg0, seg1])
    out2 = select_cards([seg0, seg1])
    assert out1 == out2
