"""Server wiring for distribution/measurement (additive routes)."""

import json
from pathlib import Path

from apps.web_ui.server import (
    _distribution_detail,
    _plan_distribution_for_run,
    _publish_distribution_for_run,
    _stats,
)

RUN_ID = "abcdef123456"


def _root_with_channel(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / "runtime/runs").mkdir(parents=True)
    (root / "template_foundation/channels/allen-knows-ball").mkdir(parents=True)
    (root / "template_foundation/channels/allen-knows-ball/channel.json").write_text(
        json.dumps({"channel_id": "allen-knows-ball", "market": "VN",
                    "language": "vi-VN", "audience": "Vietnamese football",
                    "brand_promise": "Clear view", "category": "soccer"}),
        encoding="utf-8",
    )
    run = {
        "run_id": RUN_ID,
        "status": "SCRIPT_APPROVED",
        "script_owner_approved": True,
        "evidence_verified_by_owner": True,
        "voice_preview": {"path": "x.wav"},
        "voice_preview_audited": True,
        "llm_cost_usd": 0.02,
        "draft": {
            "topic": "Pressing tầm cao",
            "story_form": "tactical-explainer",
            "content_type": "short",
            "locale": "vi-VN",
            "segments": [
                {"id": "beat-1", "narration": "Mở đầu rõ ràng."},
                {"id": "beat-2", "narration": "Kết luận rõ ràng."},
            ],
        },
    }
    (root / "runtime/runs" / f"{RUN_ID}.json").write_text(
        json.dumps(run, ensure_ascii=False), encoding="utf-8")
    return root


def test_plan_publish_detail_cycle(tmp_path):
    root = _root_with_channel(tmp_path)
    plan = _plan_distribution_for_run(root, {
        "run_id": RUN_ID,
        "destinations": [{"platform": "local_file", "account_ref": "local"}],
    })
    assert plan["status"] == "STAGED"
    assert plan["channel_id"] == "allen-knows-ball"

    result = _publish_distribution_for_run(root, {"run_id": RUN_ID})
    assert result["status"] == "PUBLISHED"

    detail = _distribution_detail(root, RUN_ID)
    assert detail["plan"]["status"] == "PUBLISHED"
    assert detail["lifecycle"]["state"] == "PUBLISHED"
    assert detail["records"][0]["remote_id"].startswith("file:")


def test_stats_still_reports_runs(tmp_path):
    root = _root_with_channel(tmp_path)
    stats = _stats(root, root / "runtime/engine.db")
    assert stats["run_count"] == 1
    assert stats["runs_by_status"] == {"SCRIPT_APPROVED": 1}
