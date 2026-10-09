from pathlib import Path

import pytest

from apps.measurement import (
    classify_lifecycle,
    record_observation,
    record_payout,
    summarize_by_channel,
    summarize_by_run,
)


RUN_ID = "abcdef123456"


def _run(**overrides):
    run = {"run_id": RUN_ID, "script_owner_approved": True,
           "evidence_verified_by_owner": True}
    run.update(overrides)
    return run


def test_lifecycle_distinguishes_all_six_states():
    assert classify_lifecycle(None, None, None, None, None)["state"] == "GENERATED"
    assert classify_lifecycle({"run_id": RUN_ID}, None, None, None, None)["state"] == "GENERATED"
    assert classify_lifecycle(_run(script_owner_approved=False), None, None, None, None)["state"] == "GENERATED"

    verified = classify_lifecycle(_run(), None, None, None, None)
    assert verified["state"] == "VERIFIED"

    plan = {"plan_id": "plan-1", "status": "STAGED"}
    assert classify_lifecycle(_run(), plan, [], [], [])["state"] == "STAGED"

    records = [{"status": "PUBLISHED", "remote_id": "file:x"}]
    assert classify_lifecycle(_run(), plan, records, [], [])["state"] == "PUBLISHED"

    obs = [{"views": 10}]
    measured = classify_lifecycle(_run(), plan, records, obs, [])
    assert measured["state"] == "MEASURED"
    assert any("no verified cash" in r for r in measured["reasons"])

    # Estimates alone never promote to PAID.
    estimate_only = [{"amount_usd": 5.0, "verified_cash_received": False}]
    assert classify_lifecycle(_run(), plan, records, obs, estimate_only)["state"] == "MEASURED"

    paid = classify_lifecycle(_run(), plan, records, obs,
                              [{"amount_usd": 5.0, "verified_cash_received": True}])
    assert paid["state"] == "PAID"


def test_ledger_math_separates_estimates_from_cash(tmp_path: Path):
    root = tmp_path / "project"
    record_observation(root, run_id=RUN_ID, channel_id="allen-knows-ball",
                       platform="youtube", day="2026-10-09", views=1000,
                       likes=50, conversions=4, earnings_estimated_usd=12.5)
    # Unverified payout must not move profit.
    record_payout(root, run_id=RUN_ID, channel_id="allen-knows-ball",
                  amount_usd=12.5, kind="platform_payout",
                  verified_cash_received=False, note="dashboard estimate")
    rows = summarize_by_run(root, production_costs={RUN_ID: 2.5})
    assert rows[0]["earnings_estimated_usd"] == 12.5
    assert rows[0]["contribution_margin_estimated_usd"] == 10.0
    assert rows[0]["profit_attributable_usd"] == -2.5

    record_payout(root, run_id=RUN_ID, channel_id="allen-knows-ball",
                  amount_usd=9.0, kind="platform_payout",
                  verified_cash_received=True, method="bank",
                  note="verified monthly payout")
    rows = summarize_by_run(root, production_costs={RUN_ID: 2.5})
    assert rows[0]["payout_verified_usd"] == 9.0
    assert rows[0]["profit_attributable_usd"] == 6.5

    by_channel = summarize_by_channel(root)
    assert by_channel[0]["channel_id"] == "allen-knows-ball"
    assert by_channel[0]["views"] == 1000
    assert by_channel[0]["payout_verified_usd"] == 9.0


def test_ledger_validation(tmp_path: Path):
    root = tmp_path / "project"
    with pytest.raises(ValueError, match="run_id"):
        record_observation(root, run_id="bad", channel_id="c", platform="p")
    with pytest.raises(ValueError, match="amount_usd"):
        record_payout(root, run_id=RUN_ID, channel_id="c", amount_usd=0)
    with pytest.raises(ValueError, match="kind"):
        record_payout(root, run_id=RUN_ID, channel_id="c", amount_usd=1, kind="nope")
