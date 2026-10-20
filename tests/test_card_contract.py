"""Unified card contract v2.0: coverage, drift, binding, fallback, tamper.

``12.0.0`` remains the frozen historical contract (19 contract / 7 partial /
63 legacy cards). ``12.1.0`` adds exactly one execution promotion: C-09
``source_card``. These tests pin both the immutable old artifact and the
per-card-only new promotion, plus the planner/renderer boundaries:

* exactly one record per registry card (89 cards; media-less cards included);
* every data/media box, fit limit and execution route is authored, not
  inferred at render time;
* the builder freezes card/text/media values and the contract hash;
* missing required data or a legacy card/mode becomes an explicit non-ready
  fallback, never a silent authored render;
* a frozen graph tampered after planning is rejected against the original
  contract (including a recomputed graph hash);
* QA measures frozen text fit and never PASSes a legacy path.

No ffmpeg, no network, no user runtime data.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_FILE = (
    ROOT
    / "template_foundation"
    / "templates"
    / "allen-knows-ball"
    / "12.0.0"
    / "card-contract.json"
)
NEW_CONTRACT_FILE = (
    ROOT
    / "template_foundation"
    / "templates"
    / "allen-knows-ball"
    / "12.1.0"
    / "card-contract.json"
)
PORTRAIT_CARDS = {"C-04", "MR-08", "BP-03"}
SOURCE_CARDS = {"BP-20", "C-09", "MR-12", "U-08"}
OLD_CONTRACT_HASH = (
    "cad623bd30050dd300f27a8eb9e39408e99f2d181703917db19282f08e4e499b"
)
NEW_CONTRACT_HASH = (
    "8ceb621132f47f3fcc77b2a2a634f85cd4f85e7c6c328cce59b1ed0d928f0d0d"
)


def _contract(version: str = "12.0.0") -> dict:
    from apps.studio_templates.card_media import load_contract

    contract = load_contract(version)
    assert contract is not None
    return contract


def _build(
    card_id: str,
    mode: str,
    data: dict,
    *,
    media_asset_id: str | None = None,
    asset_info: dict | None = None,
):
    from apps.scene_graph.builder import build_scene_graph

    return build_scene_graph(
        segment_id="beat-1",
        visual_mode=mode,
        starter_id=card_id,
        graphic_data=data,
        evidence=["ESPN 14/10/2026"],
        content_type="short",
        start_seconds=0.0,
        end_seconds=5.0,
        index=0,
        media_asset_id=media_asset_id,
        asset_info=asset_info,
    )


def _duel_data() -> dict:
    return {
        "home": "HA NOI",
        "away": "NAM DINH",
        "metrics": [
            {"label": "Bàn thắng", "home": "2", "away": "1"},
            {"label": "Kiểm soát", "home": "55", "away": "45"},
            {"label": "Sút", "home": "12", "away": "8"},
        ],
        "source": "VPF",
        "date": "12/10/2026",
    }


def _stat_data() -> dict:
    return {
        "stats": [
            {"label": "Bàn thắng", "value": "19"},
            {"label": "Trận", "value": "24"},
            {"label": "Kiến tạo", "value": "7"},
        ],
        "source": "ESPN",
        "date": "14/10/2026",
    }


def _portrait_data() -> dict:
    return {
        "player_name": "Erling Haaland",
        "stats": [
            {"label": "Bàn thắng", "value": "2"},
            {"label": "Trận", "value": "7"},
        ],
    }


# --- coverage and drift ------------------------------------------------------


def test_contract_covers_every_built_card_exactly_once():
    from apps.studio_templates.card_registry import CARDS

    contract = _contract()
    card_ids = [card["card_id"] for card in contract["cards"]]
    assert len(card_ids) == len(set(card_ids)) == 89
    assert set(card_ids) == {str(card["id"]) for card in CARDS}
    assert contract["schema_version"] == "2.0"
    assert contract["contract_id"] == "card-contract"
    assert contract["template_version"] == "12.0.0"
    for card in contract["cards"]:
        assert card["starter_id"] == card["card_id"]
        assert card["template_version"] == contract["template_version"]


def test_contract_execution_partitions_are_explicit():
    statuses = Counter(
        card["execution"]["status"] for card in _contract()["cards"]
    )
    assert statuses == {
        "contract": 19,
        "partial": 7,
        "legacy_non_ready": 63,
    }
    for card in _contract()["cards"]:
        execution = card["execution"]
        if execution["status"] in ("contract", "partial"):
            assert execution["route"] == "starter_design"
            assert card["aspect"] == "short"
            assert execution["modes"]
            assert not execution["legacy_modes"] or execution["status"] == "partial"
        else:
            assert execution["route"] != "starter_design"
            assert execution["modes"] == []
            assert execution["legacy_modes"]
            assert execution["reason"]


def test_12_0_0_contract_is_byte_hash_frozen():
    on_disk = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
    assert on_disk["template_version"] == "12.0.0"
    assert on_disk["contract_hash"] == OLD_CONTRACT_HASH


def test_12_1_0_promotes_only_c09_source_card():
    old = _contract("12.0.0")
    new = _contract("12.1.0")
    assert new["template_version"] == "12.1.0"
    assert new["contract_hash"] == NEW_CONTRACT_HASH != old["contract_hash"]
    assert Counter(
        card["execution"]["status"] for card in new["cards"]
    ) == {
        "contract": 20,
        "partial": 7,
        "legacy_non_ready": 62,
    }
    old_by_id = {card["card_id"]: card for card in old["cards"]}
    new_by_id = {card["card_id"]: card for card in new["cards"]}

    def _shape(execution: dict) -> tuple:
        return (
            execution["route"], execution["status"],
            tuple(execution["modes"]), tuple(execution["legacy_modes"]),
        )

    changed = {
        card_id for card_id in old_by_id
        if _shape(old_by_id[card_id]["execution"])
        != _shape(new_by_id[card_id]["execution"])
    }
    assert changed == {"C-09"}
    c09 = new_by_id["C-09"]
    assert c09["execution"] == {
        "route": "starter_design",
        "status": "contract",
        "modes": ["source_card"],
        "legacy_modes": [],
        "reason": None,
    }
    assert c09["media_slots"] == []
    old_c09 = old_by_id["C-09"]
    old_slots = {slot["slot_id"]: slot for slot in old_c09["data_slots"]}
    slots = {slot["slot_id"]: slot for slot in c09["data_slots"]}
    assert set(slots) == set(old_slots) == {"src-title", "src-body", "credit"}
    for slot_id in slots:
        assert slots[slot_id]["box_px"] == old_slots[slot_id]["box_px"]
        assert slots[slot_id]["font"] == old_slots[slot_id]["font"]
        assert slots[slot_id]["active_modes"] == old_slots[slot_id]["active_modes"]
    assert c09["static_text_layers"] == old_c09["static_text_layers"]
    assert slots["src-title"]["sources"] == []
    assert slots["src-title"]["fallback"] == "authored_text"
    assert slots["src-body"]["sources"] == ["claim"]
    assert slots["src-body"]["required_for_modes"] == ["source_card"]
    assert slots["credit"]["sources"] == ["source", "date"]
    assert slots["credit"]["join"] == " \u2022 "
    assert slots["credit"]["required_for_modes"] == ["source_card"]


def test_12_1_0_reuses_12_0_0_resources_and_keeps_c09_starter_bytes():
    old_root = (
        ROOT / "template_foundation" / "templates" / "allen-knows-ball"
        / "12.0.0"
    )
    new_root = (
        ROOT / "template_foundation" / "templates" / "allen-knows-ball"
        / "12.1.0"
    )
    old_resources = {
        path.relative_to(old_root / "resources").as_posix(): hashlib.sha256(
            path.read_bytes()).hexdigest()
        for path in (old_root / "resources").rglob("*") if path.is_file()
    }
    new_resources = {
        path.relative_to(new_root / "resources").as_posix(): hashlib.sha256(
            path.read_bytes()).hexdigest()
        for path in (new_root / "resources").rglob("*") if path.is_file()
    }
    assert old_resources == new_resources
    starter = ROOT / "apps" / "studio_templates" / "C-09.short.json"
    assert hashlib.sha256(starter.read_bytes()).hexdigest() == (
        "877543db73fa5383efd67da93e99622493eb512c168a4710cb141da3a379c99c"
    )


def test_12_1_0_leaves_other_source_and_longform_cards_non_ready():
    by_id = {card["card_id"]: card for card in _contract("12.1.0")["cards"]}
    for card_id in SOURCE_CARDS - {"C-09"}:
        execution = by_id[card_id]["execution"]
        assert execution["status"] == "legacy_non_ready"
        assert execution["modes"] == []
        assert execution["legacy_modes"] == ["source_card"]
        assert "C-09" in execution["reason"]
    for card_id in ("LC-11", "LC-13", "LC-16"):
        card = by_id[card_id]
        assert card["aspect"] == "long"
        assert card["execution"]["status"] == "legacy_non_ready"
        assert card["execution"]["route"] == "legacy_long"
        assert card["execution"]["modes"] == []
        assert card["execution"]["legacy_modes"]


def test_contract_media_regions_are_only_the_three_portrait_cards():
    from apps.studio_templates.card_media import slot_box_px

    contract = _contract()
    media_cards = {
        card["card_id"] for card in contract["cards"] if card["media_slots"]
    }
    assert media_cards == PORTRAIT_CARDS
    for card in contract["cards"]:
        if card["card_id"] not in PORTRAIT_CARDS:
            assert card["media_slots"] == []
            continue
        assert len(card["media_slots"]) == 1
        slot = card["media_slots"][0]
        assert slot["slot_id"] == "player_portrait"
        assert slot["asset_type"] == "image"
        assert slot["z_after_layer_id"] == "bed-60"
        assert slot_box_px(slot, (1080, 1920)) == [0, 282, 424, 1240]
        assert slot["rights"] == {
            "requires_verified": True,
            "requires_active": True,
            "requires_persisted_human_grant": True,
            "purpose_specific": True,
            "human_review_required": True,
        }


def test_contract_boxes_fit_inside_declared_canvas():
    for card in _contract()["cards"]:
        width = card["canvas"]["width"]
        height = card["canvas"]["height"]
        for slot in card["data_slots"]:
            assert slot["type"] == "text"
            x, y, w, h = slot["box_px"]
            assert x >= 0 and y >= 0
            assert x + w <= width and y + h <= height
            assert w > 0 and h > 0
            assert slot["max_lines"] >= 1
            assert slot["max_words"] >= 1
            assert slot["max_chars"] >= 1
            assert slot["fit"]["min_size_px"] <= slot["font"]["size_px"]
        for layer in card["static_text_layers"]:
            x, y, w, h = layer["box_px"]
            assert x >= 0 and y >= 0
            assert x + w <= width and y + h <= height


def test_generator_output_matches_the_runtime_contract():
    spec = importlib.util.spec_from_file_location(
        "build_card_contract", ROOT / "tools" / "build_card_contract.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generated = module.build("12.0.0")
    on_disk = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
    assert generated == on_disk

    generated_new = module.build("12.1.0")
    on_disk_new = json.loads(NEW_CONTRACT_FILE.read_text(encoding="utf-8"))
    assert generated_new == on_disk_new
    assert module.build("12.0.0") == generated


def test_contract_hash_tamper_is_rejected():
    from apps.studio_templates.card_media import validate_contract

    tampered = copy.deepcopy(_contract())
    tampered["cards"][0]["data_slots"][0]["max_chars"] += 1
    with pytest.raises(ValueError, match="contract_hash"):
        validate_contract(tampered, check_drift=False)


def test_starter_drift_is_rejected_even_with_a_recomputed_hash():
    from apps.studio_templates.card_media import _canonical_hash, validate_contract

    tampered = copy.deepcopy(_contract())
    card = next(item for item in tampered["cards"] if item["card_id"] == "C-03")
    claim = next(slot for slot in card["data_slots"] if slot["slot_id"] == "claim")
    claim["box_px"][0] += 1
    tampered["contract_hash"] = _canonical_hash(tampered)
    with pytest.raises(ValueError, match="box drifted"):
        validate_contract(tampered)


# --- planner binding --------------------------------------------------------


def test_builder_binds_contract_text_and_preserves_authored_title():
    from apps.scene_graph.schema import validate_scene_graph

    graph = _build("C-07", "duel_columns", _duel_data())
    validate_scene_graph(graph)
    assert graph["kind"] == "starter"
    assert graph["provenance"]["card_contract"]["status"] == "contract"
    assert graph["slots"]["title"] == "ĐỐI ĐẦU"
    assert graph["slots"]["label-0"] == "Bàn thắng"
    assert graph["slots"]["m-0-home"] == "2"
    assert graph["slots"]["m-0-away"] == "1"
    bindings = {item["slot_id"]: item for item in graph["data_bindings"]}
    assert bindings["title"]["visible"] is True
    assert bindings["title"]["fallback"] == "authored_text"
    assert bindings["label-0"]["visible"] is True
    assert bindings["label-0"]["sources"] == ["metrics[0].label"]
    assert bindings["label-0"]["required"] is True


def test_builder_binds_stat_rows_and_money_card():
    from apps.scene_graph.schema import validate_scene_graph

    stats = _build("MR-07", "stat_leader", _stat_data())
    validate_scene_graph(stats)
    assert stats["provenance"]["card_contract"]["status"] == "contract"
    assert stats["slots"]["l-0"] == "Bàn thắng"
    assert stats["slots"]["v-0"] == "19"
    assert stats["data_bindings"][1]["slot_id"] == "l-0"

    money = _build(
        "BP-08",
        "stat_leader",
        {
            "stats": [
                {"label": "Phí chuyển nhượng", "value": "120 triệu"},
                {"label": "Mùa", "value": "2026"},
            ],
            "context": "Kỷ lục",
            "source": "ESPN",
            "date": "14/10/2026",
        },
    )
    validate_scene_graph(money)
    assert money["provenance"]["card_contract"]["status"] == "contract"
    assert money["slots"]["amount"] == "120 triệu"
    assert money["slots"]["line"] == "Kỷ lục"


def test_c09_source_card_binds_claim_and_source_date_without_new_layers():
    from apps.measurement.render_qa import (
        check_card_contract,
        check_text_fit,
    )
    from apps.scene_graph.schema import validate_scene_graph

    graph = _build(
        "C-09",
        "source_card",
        {
            "source": "Synthetic Sports Desk (fixture)",
            "date": "20/10/2026 (synthetic)",
            "claim": "Dữ liệu minh họa, không phải kết quả thật.",
        },
    )
    validate_scene_graph(graph)
    assert graph["kind"] == "starter"
    assert graph["provenance"]["card_contract"]["status"] == "contract"
    assert graph["provenance"]["card_contract"]["sha256"] == NEW_CONTRACT_HASH
    assert graph["media_bindings"] == []
    assert graph["slots"]["src-title"] == "NGUỒN"
    assert graph["slots"]["src-body"] == "Dữ liệu minh họa, không phải kết quả thật."
    assert graph["slots"]["credit"] == (
        "Synthetic Sports Desk (fixture) \u2022 20/10/2026 (synthetic)")
    bindings = {item["slot_id"]: item for item in graph["data_bindings"]}
    assert bindings["src-body"]["sources"] == ["claim"]
    assert bindings["credit"]["sources"] == ["source", "date"]
    assert bindings["credit"]["required"] is True
    assert bindings["credit"]["visible"] is True
    text_layers = [
        child for child in graph["design"]["pages"][0]["children"]
        if child.get("type") == "text"
    ]
    assert [child["id"] for child in text_layers] == ["val-5", "val-6", "val-9"]
    assert check_text_fit(graph)["status"] == "PASS"
    assert check_card_contract(graph)["status"] == "NEEDS_REVIEW"


@pytest.mark.parametrize("missing", ["claim", "source", "date"])
def test_c09_source_card_missing_required_data_falls_back(missing):
    from apps.measurement.render_qa import check_card_contract
    from apps.scene_graph.schema import validate_scene_graph

    data = {
        "source": "Synthetic Sports Desk (fixture)",
        "date": "20/10/2026 (synthetic)",
        "claim": "Dữ liệu minh họa.",
    }
    data.pop(missing)
    graph = _build("C-09", "source_card", data)
    validate_scene_graph(graph)
    assert graph["kind"] == "primitive"
    meta = graph["provenance"]["card_contract"]
    assert meta["status"] == "fallback"
    assert ("src-body" if missing == "claim" else "credit") in meta["reason"]
    assert graph["design"] is None
    assert check_card_contract(graph)["status"] == "NEEDS_REVIEW"


def test_c09_credit_overflow_is_failed_by_text_fit():
    from apps.measurement.render_qa import check_text_fit
    from apps.scene_graph.schema import validate_scene_graph

    graph = _build(
        "C-09",
        "source_card",
        {
            "source": "Synthetic Sports Desk " + "X" * 80,
            "date": "20/10/2026 (synthetic)",
            "claim": "Dữ liệu minh họa.",
        },
    )
    validate_scene_graph(graph)
    assert graph["kind"] == "starter"
    check = check_text_fit(graph)
    assert check is not None
    assert check["status"] == "FAIL"
    assert "credit" in check["detail"]


def test_c09_qa_blocks_hidden_or_missing_credit():
    from apps.measurement.render_qa import check_card_contract

    graph = _build(
        "C-09",
        "source_card",
        {
            "source": "Synthetic Sports Desk (fixture)",
            "date": "20/10/2026 (synthetic)",
            "claim": "Dữ liệu minh họa.",
        },
    )
    hidden = copy.deepcopy(graph)
    credit = next(
        item for item in hidden["data_bindings"]
        if item["slot_id"] == "credit"
    )
    credit["visible"] = False
    assert check_card_contract(hidden)["status"] == "FAIL"

    partial = copy.deepcopy(graph)
    credit = next(
        item for item in partial["data_bindings"]
        if item["slot_id"] == "credit"
    )
    credit["value"] = "Synthetic Sports Desk (fixture)"
    assert check_card_contract(partial)["status"] == "FAIL"

    missing = copy.deepcopy(graph)
    missing["data_bindings"] = [
        item for item in missing["data_bindings"]
        if item["slot_id"] != "credit"
    ]
    assert check_card_contract(missing)["status"] == "FAIL"


def test_builder_freezes_media_only_on_a_declared_region():
    from apps.scene_graph.schema import validate_scene_graph

    no_media = _build("C-03", "hook_card", {"hook_text": "Một trận cầu"})
    validate_scene_graph(no_media)
    assert no_media["media_bindings"] == []

    portrait = _build("C-04", "player_poster_side", _portrait_data())
    validate_scene_graph(portrait)
    assert portrait["provenance"]["card_contract"]["status"] == "contract"
    assert len(portrait["media_bindings"]) == 1
    binding = portrait["media_bindings"][0]
    assert binding["slot_id"] == "player_portrait"
    assert binding["status"] == "fallback"
    assert [layer["id"] for layer in portrait["design"]["pages"][0]["children"]
            if layer.get("type") == "media_slot"] == ["media-player_portrait"]


# --- fallback and legacy ----------------------------------------------------


def test_missing_required_data_freezes_an_explicit_fallback():
    from apps.measurement.render_qa import check_card_contract

    graph = _build("C-03", "hook_card", {})
    assert graph["kind"] == "primitive"
    assert graph["provenance"]["card_contract"]["status"] == "fallback"
    assert "claim" in graph["provenance"]["card_contract"]["reason"]
    check = check_card_contract(graph)
    assert check["status"] == "NEEDS_REVIEW"
    assert "fallback" in check["detail"]


def test_legacy_card_mode_is_marked_not_ready():
    from apps.measurement.render_qa import check_card_contract

    graph = _build("C-05", "quote_card", {"claim": "Một câu nói"})
    assert graph["kind"] == "primitive"
    meta = graph["provenance"]["card_contract"]
    assert meta["status"] == "legacy_non_ready"
    assert meta["route"] == "legacy_generic"
    check = check_card_contract(graph)
    assert check["status"] == "NEEDS_REVIEW"
    assert "legacy" in check["detail"]


def test_selector_marks_a_legacy_card_path():
    from apps.card_selector import select_cards

    result = select_cards(
        [
            {
                "id": "b1",
                "narration": "Mở đầu",
                "visual_mode": "hook_card",
                "graphic_data": {"hook_text": "Mở đầu"},
            },
            {
                "id": "b2",
                "narration": "Diễn biến trận đấu qua các cột mốc",
                "visual": "timeline",
                "visual_mode": "chart_timeline",
                "graphic_data": {
                    "title": "Cột mốc",
                    "moments": [{"time": "10'", "text": "Bàn thắng"}],
                },
            },
        ],
        content_type="short",
    )
    decision = result["decisions"][1]
    assert decision["starter_id"] == "BP-04"
    assert decision["card_execution"] == "legacy_non_ready"
    assert "legacy/non-ready" in " ".join(decision["warnings"])
    assert result["plan"]["legacy_starters"] == ["BP-04"]
    assert any("legacy/non-ready" in warning
               for warning in result["plan"]["warnings"])


# --- rendered text fit and tamper ------------------------------------------


def test_text_fit_measures_the_frozen_box_and_catches_overflow():
    from apps.measurement.render_qa import check_text_fit

    normal = _build("C-03", "hook_card", {"hook_text": "Một trận cầu đáng xem"})
    check = check_text_fit(normal)
    assert check is not None and check["status"] == "PASS"

    long_value = _build("C-03", "hook_card", {"hook_text": "X" * 400})
    check = check_text_fit(long_value)
    assert check is not None
    assert check["status"] == "FAIL"
    assert "overflow" in check["detail"]

    many_lines = _build(
        "C-03", "hook_card", {"hook_text": "A\nB\nC\nD\nE\nF\nG"}
    )
    check = check_text_fit(many_lines)
    assert check is not None
    assert check["status"] == "FAIL"
    assert "height" in check["detail"]


def test_frozen_graph_rejects_an_extra_text_layer():
    from apps.scene_graph.schema import graph_hash, validate_scene_graph

    graph = _build("C-07", "duel_columns", _duel_data())
    graph["design"]["pages"][0]["children"].append({
        "id": "extra-headline",
        "type": "text",
        "x": 100,
        "y": 100,
        "width": 600,
        "height": 100,
        "text": "HEADLINE",
        "fontFamily": "Be Vietnam Pro",
        "fontWeight": "normal",
        "fontSize": 40,
        "align": "left",
    })
    graph["provenance"]["graph_hash"] = graph_hash(graph)
    with pytest.raises(ValueError, match="undeclared"):
        validate_scene_graph(graph)


def test_frozen_graph_rejects_changed_binding_text():
    from apps.scene_graph.schema import graph_hash, validate_scene_graph

    graph = _build("C-07", "duel_columns", _duel_data())
    for child in graph["design"]["pages"][0]["children"]:
        if child.get("id") == "val-12":
            child["text"] = "HACKED"
    graph["provenance"]["graph_hash"] = graph_hash(graph)
    with pytest.raises(ValueError, match="disagrees with its binding"):
        validate_scene_graph(graph)


def test_frozen_graph_rejects_changed_media_geometry():
    from apps.scene_graph.schema import graph_hash, validate_scene_graph

    graph = _build("C-04", "player_poster_side", _portrait_data())
    graph["media_bindings"][0]["role"] = "hero_image"
    for child in graph["design"]["pages"][0]["children"]:
        if child.get("id") == "media-player_portrait":
            child["custom"]["role"] = "hero_image"
    graph["provenance"]["graph_hash"] = graph_hash(graph)
    with pytest.raises(ValueError, match="changed role"):
        validate_scene_graph(graph)


def test_frozen_graph_rejects_a_contract_hash_swap():
    from apps.scene_graph.schema import graph_hash, validate_scene_graph

    graph = _build("C-07", "duel_columns", _duel_data())
    graph["provenance"]["card_contract"]["sha256"] = "0" * 64
    graph["provenance"]["graph_hash"] = graph_hash(graph)
    with pytest.raises(ValueError, match="contract hash"):
        validate_scene_graph(graph)
