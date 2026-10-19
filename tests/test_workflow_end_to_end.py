"""End-to-end proof of the completed workflow on a synthetic approved run.

Chain: quality_gate -> route -> plan_distribution -> stage_plan ->
publish_plan(local_file) -> record_observation -> record_payout ->
classify_lifecycle == PAID. No network, no keys, no template/renderer touch.
"""

import json
from pathlib import Path

from apps.distribution import ChannelDestination, default_registry, plan_distribution, publish_plan
from apps.distribution.service import stage_plan
from apps.measurement import (
    classify_lifecycle,
    record_observation,
    record_payout,
    summarize_by_run,
)

RUN_ID = "abcdef123456"


def _approved_run():
    return {
        "run_id": RUN_ID,
        "status": "SCRIPT_APPROVED",
        "script_owner_approved": True,
        "evidence_verified_by_owner": True,
        "voice_preview": {"path": "x.wav"},
        "voice_preview_audited": True,
        "llm_cost_usd": 0.03,
        "draft": {
            "topic": "Vì sao pressing tầm cao của Allen Knows Ball hiệu quả?",
            "story_form": "tactical-explainer",
            "content_type": "short",
            "locale": "vi-VN",
            "segments": [
                {"id": "beat-1", "narration": "Mở đầu rõ ràng về pressing tầm cao."},
                {"id": "beat-2", "narration": "Kết luận có giới hạn rõ ràng."},
            ],
        },
    }


def test_workflow_completes_to_paid(tmp_path: Path):
    root = tmp_path / "project"
    (root / "template_foundation/channels/allen-knows-ball").mkdir(parents=True)
    (root / "template_foundation/channels/allen-knows-ball/channel.json").write_text(
        json.dumps({"channel_id": "allen-knows-ball", "category": "soccer",
                    "market": "VN", "language": "vi-VN",
                    "audience": "Vietnamese football pressing analysis",
                    "brand_promise": "Góc nhìn bóng đá rõ ràng"}),
        encoding="utf-8",
    )
    run = _approved_run()

    plan = plan_distribution(root, run, {"allen-knows-ball": [
        ChannelDestination(platform="local_file", account_ref="local", market="VN"),
    ]})
    assert plan["status"] == "DRAFT"

    staged = stage_plan(root, plan)
    assert staged["status"] == "STAGED"

    published = publish_plan(root, run, staged, registry=default_registry())
    assert published["status"] == "PUBLISHED"
    remote_id = published["records"][0]["remote_id"]
    assert remote_id.startswith("file:")

    record_observation(root, run_id=RUN_ID, remote_id=remote_id,
                       channel_id="allen-knows-ball", platform="local_file",
                       day="2026-10-09", views=500, likes=20,
                       conversions=2, earnings_estimated_usd=5.0)
    record_payout(root, run_id=RUN_ID, channel_id="allen-knows-ball",
                  amount_usd=4.0, kind="platform_payout",
                  verified_cash_received=True, method="bank")

    obs_path = root / "runtime/measurement/observations.jsonl"
    pay_path = root / "runtime/measurement/payouts.jsonl"
    observations = [json.loads(line) for line in obs_path.read_text(encoding="utf-8").splitlines()]
    payouts = [json.loads(line) for line in pay_path.read_text(encoding="utf-8").splitlines()]
    records = published["stored_records"]

    state = classify_lifecycle(run, staged, records, observations, payouts)
    assert state["state"] == "PAID"

    rows = summarize_by_run(root, production_costs={RUN_ID: 0.03})
    assert rows[0]["profit_attributable_usd"] == round(4.0 - 0.03, 2)
