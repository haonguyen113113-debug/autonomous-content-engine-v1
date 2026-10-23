"""Synthetic short-form news fixture for contract-first planner checks.

The fixture is deliberately synthetic: no real clubs, players, results,
metrics, sources or dates. It exercises the channel's short-form news shape
(hook -> result -> event -> stat -> source) rather than tactical analysis.

Expected current result: hook/result/event/stat are contract beats; the source
beat resolves to C-09 in the pinned pack, but the long fixture claim fails text
fit and rendered/owner review is pending, so it is not production-ready. The
test must not "fix" that by inventing a contract card, forcing a tactical card,
deriving a claim from narration, or weakening the rights/data checks.

Visual inspection is version-scoped: an owner review record for C-09 only
clears the pack version it names. Assertions about approval are therefore
derived from `source_card_visual_approved()` for the pinned pack instead of
hard-coding a historical version.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from apps.card_selector import select_cards
from apps.measurement.render_qa import check_card_contract, check_text_fit
from apps.measurement.review_records import source_card_visual_approved
from apps.scene_graph.builder import TEMPLATE_VERSION_FALLBACK, build_clip_graphs
from apps.scene_graph.schema import validate_scene_graph

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "shortform_news_synthetic.json"


def _fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert data["synthetic"] is True
    return data


def _select(segments: list[dict]) -> dict:
    return select_cards(copy.deepcopy(segments), content_type="short")


def _c09_visually_approved() -> bool:
    """Whether an owner review record clears C-09/source_card for the pin."""
    return source_card_visual_approved(
        "C-09", "source_card", TEMPLATE_VERSION_FALLBACK
    )


def _expected_inspection() -> str:
    return "approved" if _c09_visually_approved() else "pending"


def test_synthetic_shortform_news_planner_table() -> None:
    fixture = _fixture()
    out = _select(fixture["segments"])
    decisions = out["decisions"]

    assert [d["segment_id"] for d in decisions] == [
        "beat-hook",
        "beat-result",
        "beat-event",
        "beat-stat",
        "beat-source",
    ]
    assert [d["grammar"]["role"] for d in decisions] == [
        "hook",
        "result",
        "result",
        "stat",
        "source",
    ]
    assert [d["visual_mode"] for d in decisions] == [
        "hook_card",
        "score_card",
        "score_card",
        "stat_leader",
        "source_card",
    ]
    assert [d["starter_id"] for d in decisions] == [
        "MR-01",
        "MR-02",
        "MR-02",
        "BP-16",
        "C-09",
    ]
    assert [d["card_execution"] for d in decisions] == [
        "contract",
        "contract",
        "contract",
        "contract",
        "contract",
    ]
    assert [d["production_ready"] for d in decisions] == [
        True,
        True,
        True,
        True,
        False,
    ]

    # The news fixture must never be converted into tactical analysis.
    assert all(d["visual_mode"] != "tactical_explainer" for d in decisions)
    assert all(d["card_execution"] != "partial" for d in decisions)

    # The event beat is a contract score card: goal_card is a partial legacy
    # hint and is replaced by the contract score grammar, with the scorer and
    # minute kept in the authored `context` slot rather than a new card.
    event = decisions[2]
    assert event["grammar"]["declared_mode"] == "goal_card"
    assert event["graphic_data"]["context"] == "Phút 78 • Synthetic 09 ghi bàn"
    assert any("goal_card" in warning for warning in event["warnings"])

    # The fixture provides complete source/date/claim data. C-09 is
    # graph-level executable in 12.1.0, but the 82-character claim overflows
    # its box at the shrink floor and there is no claim/source/date
    # verification gate, so the source beat remains non-ready even though the
    # scoped owner review record clears the static visual inspection.
    source = decisions[4]
    assert source["graphic_data"]["source"] == "Synthetic Sports Desk (fixture)"
    assert source["graphic_data"]["date"] == "20/10/2026 20:00 (synthetic)"
    assert source["graphic_data"]["claim"]
    assert source["production_ready"] is False
    assert source["media_status"] == "not_applicable"
    assert source["readiness"]["text_fit"] == "FAIL"
    # Version-scoped: the shipped record covers 12.1.0 only, so on the pinned
    # pack (12.2.0) inspection is pending until the owner reviews that pack.
    assert source["readiness"]["rendered_inspection"] == _expected_inspection()
    assert source["readiness"]["owner_approved"] is _c09_visually_approved()
    # Even where visual approval exists, content review is missing: no
    # claim/source/date verification gate exists.
    assert source["readiness"]["content_review"] == "missing"
    assert any("text fit FAIL" in warning for warning in source["warnings"])
    assert any(
        "no claim/source/date verification" in warning
        for warning in source["warnings"]
    )
    # The pending visual-approval warning appears exactly when no record
    # covers the pinned pack.
    has_pending_warning = any(
        "visual approval are pending" in warning for warning in source["warnings"]
    )
    assert has_pending_warning is not _c09_visually_approved()

    plan = out["plan"]
    assert plan["production_ready"] is False
    assert plan["non_ready_beats"] == ["beat-source"]
    assert plan["non_ready_roles"] == ["source"]
    assert plan["contract_beats"] == 5
    assert plan["partial_beats"] == 0
    assert plan["legacy_beats"] == 0
    assert plan["max_mode_repeat"] == 2
    assert plan["grammar_variety_ok"] is True
    assert plan["over_repeated_modes"] == {}
    assert plan["mode_counts"]["score_card"] == 2
    assert plan["source_text_fit"] == {"beat-source": "FAIL"}
    # Review-pending tracks the pinned pack: the shipped record covers 12.1.0
    # only, so on 12.2.0 the beat is awaiting a fresh visual review.
    assert plan["rendered_review_pending"] == (
        [] if _c09_visually_approved() else ["beat-source"])
    assert "C-09" in plan["contract_starters"]
    assert "BP-16" in plan["contract_starters"]
    assert plan["legacy_starters"] == []


def test_synthetic_shortform_news_freeze_and_determinism() -> None:
    fixture = _fixture()
    segments = fixture["segments"]
    decisions = _select(segments)["decisions"]
    segments_by_id = {str(segment["id"]): segment for segment in segments}

    graphs = build_clip_graphs(
        copy.deepcopy(decisions), copy.deepcopy(segments_by_id), "short"
    )
    for graph in graphs:
        validate_scene_graph(graph)

    assert [graph["kind"] for graph in graphs] == ["starter"] * 5
    assert [
        graph["provenance"]["card_contract"]["status"] for graph in graphs
    ] == ["contract"] * 5
    # BP-16 support maps stats[1].summary, not a synthesized value+label.
    # The authored transform (upper) is still applied by the freeze step.
    stat_bindings = {
        binding["slot_id"]: binding for binding in graphs[3]["data_bindings"]
    }
    assert stat_bindings["support"]["visible"] is True
    assert stat_bindings["support"]["value"] == "SYNTHETIC SPORTS DESK (FIXTURE)"

    # These are graph-level contract/text-fit checks, not rendered media QA.
    for graph in graphs[:4]:
        assert check_card_contract(graph)["status"] == "PASS"
        assert check_text_fit(graph)["status"] == "PASS"

    source_graph = graphs[-1]
    assert source_graph["starter_id"] == "C-09"
    assert source_graph["mode"] == "source_card"
    assert source_graph["design"] is not None
    assert source_graph["slots"]["src-title"] == "NGUỒN"
    source_bindings = {
        binding["slot_id"]: binding for binding in source_graph["data_bindings"]
    }
    assert source_bindings["src-body"]["sources"] == ["claim"]
    assert source_bindings["src-body"]["value"] == fixture["segments"][-1][
        "graphic_data"]["claim"]
    assert source_bindings["src-body"]["value"] != source_bindings["credit"][
        "value"]
    assert source_bindings["credit"]["sources"] == ["source", "date"]
    assert source_bindings["credit"]["value"] == (
        "Synthetic Sports Desk (fixture) \u2022 20/10/2026 20:00 (synthetic)")
    text_layers = [
        child for child in source_graph["design"]["pages"][0]["children"]
        if child.get("type") == "text"
    ]
    assert [child["id"] for child in text_layers] == ["val-5", "val-6", "val-9"]
    assert source_graph["media_bindings"] == []
    # This starter graph executed the contract with visible claim + credit. The
    # card-contract verdict still depends on the version-scoped visual review:
    # PASS when a record covers the pinned pack, NEEDS_REVIEW while it does not.
    assert check_card_contract(source_graph)["status"] == (
        "PASS" if _c09_visually_approved() else "NEEDS_REVIEW")
    assert check_text_fit(source_graph)["status"] == "FAIL"
    assert "src-body" in check_text_fit(source_graph)["detail"]

    # Same reviewed inputs -> same decisions and graph hashes. No clock,
    # randomness, network or runtime/ state is allowed on this path.
    second = _select(fixture["segments"])
    assert decisions == second["decisions"]
    second_graphs = build_clip_graphs(
        copy.deepcopy(second["decisions"]), copy.deepcopy(segments_by_id), "short"
    )
    assert [graph["provenance"]["graph_hash"] for graph in graphs] == [
        graph["provenance"]["graph_hash"] for graph in second_graphs
    ]


def test_synthetic_source_short_claim_fits_but_content_review_missing_not_ready() -> None:
    """Short claim passes text fit AND the scoped C-09 review record matches,
    but production readiness is still False: the review record covers the
    static visual inspection only and does not verify claim/source/date.
    No content/source verification gate exists yet."""
    fixture = _fixture()
    fixture["segments"][-1]["graphic_data"]["claim"] = (
        "Dữ liệu minh họa, không phải kết quả thật.")
    out = _select(fixture["segments"])
    source = out["decisions"][-1]
    assert source["starter_id"] == "C-09"
    assert source["card_execution"] == "contract"
    assert source["readiness"]["text_fit"] == "PASS"
    assert source["readiness"]["rendered_inspection"] == _expected_inspection()
    assert source["readiness"]["owner_approved"] is _c09_visually_approved()
    # Visual approval + text fit do NOT imply production readiness:
    # claim/source/date verification is missing.
    assert source["readiness"]["content_review"] == "missing"
    assert source["readiness"]["production_ready"] is False
    assert out["plan"]["source_text_fit"] == {"beat-source": "PASS"}
    assert out["plan"]["rendered_review_pending"] == (
        [] if _c09_visually_approved() else ["beat-source"])
    assert out["plan"]["production_ready"] is False
    assert any(
        "no claim/source/date verification" in warning
        for warning in source["warnings"]
    )

    segments_by_id = {str(segment["id"]): segment for segment in fixture["segments"]}
    graphs = build_clip_graphs(
        copy.deepcopy(out["decisions"]), copy.deepcopy(segments_by_id), "short")
    source_graph = graphs[-1]
    validate_scene_graph(source_graph)
    assert check_text_fit(source_graph)["status"] == "PASS"
    # check_card_contract can PASS on the contract/visual gate even though
    # planner production readiness stays False -- but only when a version-
    # scoped owner record covers the pinned pack.
    contract_check = check_card_contract(source_graph)
    if _c09_visually_approved():
        assert contract_check["status"] == "PASS"
        assert "approval recorded" in contract_check["detail"]
    else:
        assert contract_check["status"] == "NEEDS_REVIEW"
        assert "still pending" in contract_check["detail"]


def test_source_claim_over_word_limit_needs_review_and_blocks_ready() -> None:
    fixture = _fixture()
    fixture["segments"][-1]["graphic_data"]["claim"] = (
        "a b c d e f g h i j k l m n o p q r s")
    out = _select(fixture["segments"])
    source = out["decisions"][-1]
    assert source["starter_id"] == "C-09"
    assert source["readiness"]["text_fit"] == "NEEDS_REVIEW"
    assert any(
        item["slot_id"] == "src-body" and item["status"] == "NEEDS_REVIEW"
        for item in source["readiness"]["text_slots"]
    )
    assert source["production_ready"] is False
    assert out["plan"]["production_ready"] is False
    assert any(
        "NEEDS_REVIEW" in warning and "beat-source" in warning
        for warning in out["plan"]["warnings"]
    )

    segments_by_id = {str(item["id"]): item for item in fixture["segments"]}
    graph = build_clip_graphs(
        copy.deepcopy(out["decisions"]), copy.deepcopy(segments_by_id), "short"
    )[-1]
    validate_scene_graph(graph)
    assert check_text_fit(graph)["status"] == "NEEDS_REVIEW"


def test_source_claim_is_never_derived_from_narration() -> None:
    fixture = _fixture()
    segment = fixture["segments"][-1]
    segment["graphic_data"].pop("claim")
    out = _select(fixture["segments"])
    source = out["decisions"][-1]
    assert source["starter_id"] == "C-09"
    assert "claim" not in source["graphic_data"]
    assert source["production_ready"] is False
    assert source["grammar"]["source"] != "contract"

    segments_by_id = {str(item["id"]): item for item in fixture["segments"]}
    graph = build_clip_graphs(
        copy.deepcopy(out["decisions"]), copy.deepcopy(segments_by_id), "short"
    )[-1]
    validate_scene_graph(graph)
    assert graph["kind"] == "primitive"
    assert graph["provenance"]["card_contract"]["status"] == "fallback"
    assert "src-body" in graph["provenance"]["card_contract"]["reason"]
    assert "claim" not in str(graph.get("slots") or {})
    assert check_card_contract(graph)["status"] == "NEEDS_REVIEW"


def test_source_requires_both_source_and_date_for_visible_credit() -> None:
    for field in ("source", "date"):
        fixture = _fixture()
        fixture["segments"][-1]["graphic_data"].pop(field)
        out = _select(fixture["segments"])
        segments_by_id = {
            str(item["id"]): item for item in fixture["segments"]
        }
        graph = build_clip_graphs(
            copy.deepcopy(out["decisions"]), copy.deepcopy(segments_by_id), "short"
        )[-1]
        validate_scene_graph(graph)
        assert graph["kind"] == "primitive"
        assert graph["provenance"]["card_contract"]["status"] == "fallback"
        assert "credit" in graph["provenance"]["card_contract"]["reason"]
        assert out["decisions"][-1]["production_ready"] is False


def test_fact_check_and_correction_are_not_silently_c09() -> None:
    fixture = _fixture()
    base = fixture["segments"][-1]
    fact_check = copy.deepcopy(base)
    fact_check["id"] = "beat-fact-check"
    fact_check["narration"] = "Kiểm chứng nguồn dữ liệu"
    correction = copy.deepcopy(base)
    correction["id"] = "beat-correction"
    correction["narration"] = "Đính chính thông tin"

    hook = copy.deepcopy(fixture["segments"][0])
    fact = select_cards(
        [copy.deepcopy(hook), fact_check], content_type="short"
    )["decisions"][1]
    fix = select_cards(
        [copy.deepcopy(hook), correction], content_type="short"
    )["decisions"][1]
    assert fact["starter_id"] == "BP-20"
    assert fact["card_execution"] == "legacy_non_ready"
    assert fact["production_ready"] is False
    assert any("C-09" in warning and "fact_check" in warning
               for warning in fact["warnings"])
    assert fix["starter_id"] == "U-08"
    assert fix["card_execution"] == "legacy_non_ready"
    assert fix["production_ready"] is False
    assert any("C-09" in warning and "correction" in warning
               for warning in fix["warnings"])


def test_source_credit_overflow_blocks_plan_readiness() -> None:
    fixture = _fixture()
    source = fixture["segments"][-1]
    source["graphic_data"]["claim"] = "Dữ liệu minh họa."
    source["graphic_data"]["source"] = "Synthetic Sports Desk " + "X" * 80
    out = _select(fixture["segments"])
    decision = out["decisions"][-1]
    assert decision["starter_id"] == "C-09"
    assert decision["readiness"]["text_fit"] == "FAIL"
    assert any(
        item["slot_id"] == "credit" and item["status"] == "FAIL"
        for item in decision["readiness"]["text_slots"]
    )
    assert decision["production_ready"] is False
    assert out["plan"]["production_ready"] is False
    # Visual review is version-scoped and the credit text-fit FAIL is a
    # separate gate that no visual approval clears.
    assert decision["readiness"]["rendered_inspection"] == _expected_inspection()
    assert decision["readiness"]["owner_approved"] is _c09_visually_approved()
    assert decision["production_ready"] is False

    segments_by_id = {str(item["id"]): item for item in fixture["segments"]}
    graph = build_clip_graphs(
        copy.deepcopy(out["decisions"]), copy.deepcopy(segments_by_id), "short"
    )[-1]
    validate_scene_graph(graph)
    assert check_text_fit(graph)["status"] == "FAIL"


def test_match_source_uses_c09_only_with_explicit_replacement_warning() -> None:
    fixture = _fixture()
    source = fixture["segments"][-1]
    source["narration"] = "Nguồn dữ liệu trận đấu"
    source["graphic_data"]["claim"] = "Dữ liệu minh họa."
    out = _select(fixture["segments"])
    decision = out["decisions"][-1]
    assert decision["grammar"]["source_semantics"] == "match_source"
    assert decision["starter_id"] == "C-09"
    assert decision["card_execution"] == "contract"
    assert any("MR-12" in warning for warning in decision["warnings"])
    # Short claim passes text fit and the scoped C-09 review record matches,
    # but production readiness is still False: no claim/source/date
    # verification gate exists. It still uses C-09's attribution grammar,
    # not MR-12's legacy source grammar.
    assert decision["production_ready"] is False
    assert decision["readiness"]["content_review"] == "missing"


def test_old_graph_stays_pinned_to_12_0_0_legacy_source() -> None:
    fixture = _fixture()
    segment = fixture["segments"][-1]
    from apps.scene_graph.builder import build_scene_graph

    old = build_scene_graph(
        segment_id="source-old",
        visual_mode="source_card",
        starter_id="C-09",
        graphic_data=copy.deepcopy(segment["graphic_data"]),
        evidence=[],
        content_type="short",
        start_seconds=0.0,
        end_seconds=4.0,
        index=0,
        template_version="12.0.0",
    )
    new = build_scene_graph(
        segment_id="source-new",
        visual_mode="source_card",
        starter_id="C-09",
        graphic_data=copy.deepcopy(segment["graphic_data"]),
        evidence=[],
        content_type="short",
        start_seconds=0.0,
        end_seconds=4.0,
        index=0,
    )
    validate_scene_graph(old)
    validate_scene_graph(new)
    assert old["provenance"]["template_version"] == "12.0.0"
    assert old["kind"] == "primitive"
    assert old["provenance"]["card_contract"]["status"] == "legacy_non_ready"
    assert new["provenance"]["template_version"] == TEMPLATE_VERSION_FALLBACK
    assert new["kind"] == "starter"
    assert new["provenance"]["card_contract"]["status"] == "contract"
    assert old["provenance"]["graph_hash"] != new["provenance"]["graph_hash"]
