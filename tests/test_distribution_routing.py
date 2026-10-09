import json
from pathlib import Path

from apps.distribution import (
    ChannelDestination,
    default_registry,
    plan_distribution,
    publish_plan,
    quality_gate,
    route_artifact,
)
from apps.distribution.service import stage_plan


RUN_ID = "abcdef123456"


def _approved_run(**overrides):
    run = {
        "run_id": RUN_ID,
        "status": "SCRIPT_APPROVED",
        "script_owner_approved": True,
        "evidence_verified_by_owner": True,
        "voice_preview": {"path": "x.wav"},
        "voice_preview_audited": True,
        "llm_cost_usd": 0.04,
        "draft": {
            "topic": "Chien thuat pressing cua Allen Knows Ball",
            "story_form": "tactical-explainer",
            "content_type": "short",
            "locale": "vi-VN",
            "segments": [
                {"id": "beat-1", "narration": "Mo dau ro rang ve pressing."},
                {"id": "beat-2", "narration": "Ket luan co gioi han ro rang."},
            ],
        },
    }
    run.update(overrides)
    return run


def _channels():
    return [
        {"channel_id": "allen-knows-ball", "category": "soccer", "market": "VN",
         "language": "vi-VN", "audience": "Vietnamese football pressing analysis",
         "brand_promise": "Goc nhin bong da ro rang", "coverage_priorities": ["Premier League"],
         "personality": ["direct"]},
        {"channel_id": "other-channel", "category": "soccer", "market": "VN",
         "language": "vi-VN", "audience": "cooking recipes", "brand_promise": "mon ngon",
         "coverage_priorities": [], "personality": []},
    ]


def test_quality_gate_blocks_unapproved_and_markers():
    ok, blockers = quality_gate(_approved_run())
    assert ok and blockers == []

    bad = _approved_run(script_owner_approved=False)
    ok, blockers = quality_gate(bad)
    assert not ok and any("owner-approved" in b for b in blockers)

    marked = _approved_run()
    marked["draft"]["segments"][0]["narration"] = "Doan nay [CẦN NGUỒN] chua co."
    ok, blockers = quality_gate(marked)
    assert not ok and any("research marker" in b for b in blockers)

    ok, blockers = quality_gate(_approved_run(voice_preview_audited=False), for_publish=True)
    assert not ok and any("audited" in b for b in blockers)


def test_routing_never_broadcasts_and_keeps_evidence():
    plan = route_artifact(_approved_run(), _channels())
    assert plan.channel_id == "allen-knows-ball"
    assert plan.status == "DRAFT"
    assert plan.fit_scores["picked"]["combined"] >= plan.fit_scores["scores"][1]["combined"]
    assert any("did not broadcast" in line for line in plan.rationale)
    assert "audience_fit" in plan.fit_scores["picked"]


def test_plan_distribution_writes_sidecar_only(tmp_path):
    root = tmp_path / "project"
    (root / "template_foundation/channels/allen-knows-ball").mkdir(parents=True)
    (root / "template_foundation/channels/allen-knows-ball/channel.json").write_text(
        json.dumps({"channel_id": "allen-knows-ball", "market": "VN", "language": "vi-VN"}),
        encoding="utf-8",
    )
    run = _approved_run()
    plan = plan_distribution(root, run, {"allen-knows-ball": [
        ChannelDestination(platform="local_file", account_ref="local", market="VN"),
    ]})
    assert plan["channel_id"] == "allen-knows-ball"
    sidecar = root / "runtime/distribution" / f"{RUN_ID}.json"
    assert sidecar.is_file()
    # Original run file is untouched by routing.
    assert not (root / "runtime/runs" / f"{RUN_ID}.json").exists()


def test_stubs_stage_but_local_file_publishes(tmp_path):
    root = tmp_path / "project"
    run = _approved_run()
    plan = route_artifact(run, _channels(), {
        "allen-knows-ball": [ChannelDestination(platform="youtube", account_ref="yt-main")],
    })
    staged = stage_plan(root, plan.as_dict())
    assert staged["status"] == "DRAFT" or staged["status"] in {"STAGED", "BLOCKED"}

    result = publish_plan(root, run, {
        **plan.as_dict(),
        "destinations": [{"platform": "youtube", "account_ref": "yt-main", "market": "VN", "format_note": ""}],
    }, registry=default_registry())
    assert result["status"] == "STAGED"
    assert result["records"][0]["error"] is not None
    assert "adapter_not_configured" in result["records"][0]["error"]

    local = publish_plan(root, run, {
        **plan.as_dict(),
        "destinations": [{"platform": "local_file", "account_ref": "local", "market": "VN", "format_note": ""}],
    }, registry=default_registry())
    assert local["status"] == "PUBLISHED"
    assert local["records"][0]["remote_id"].startswith("file:")
    manifest = root / "runtime/publish" / RUN_ID / "local_file.json"
    assert manifest.is_file()


def test_publish_blocked_without_voice_audit(tmp_path):
    root = tmp_path / "project"
    run = _approved_run(voice_preview_audited=False)
    del run["voice_preview_audited"]
    result = publish_plan(root, run, {
        "plan_id": "plan-x", "run_id": RUN_ID, "channel_id": "allen-knows-ball",
        "market": "VN", "language": "vi-VN", "status": "STAGED",
        "destinations": [{"platform": "local_file", "account_ref": "local", "market": "VN", "format_note": ""}],
    }, registry=default_registry())
    assert result["status"] == "BLOCKED"


def test_registry_is_replaceable():
    registry = default_registry()
    assert set(registry.platforms()) >= {"local_file", "youtube", "tiktok", "facebook"}
    try:
        registry.get("unknown-platform")
    except ValueError as error:
        assert "No adapter registered" in str(error)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")
