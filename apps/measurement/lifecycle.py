from __future__ import annotations

from typing import Any

STATES = (
    "GENERATED",
    "VERIFIED",
    "STAGED",
    "PUBLISHED",
    "MEASURED",
    "PAID",
)


def classify_lifecycle(
    run: dict[str, Any] | None,
    plan: dict[str, Any] | None,
    publish_records: list[dict[str, Any]] | None,
    observations: list[dict[str, Any]] | None,
    payouts: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Distinguish generated != verified != staged != published != measured != paid."""
    reasons: list[str] = []
    if not isinstance(run, dict) or not run.get("run_id"):
        return {"state": "GENERATED", "reasons": ["no run artifact yet"]}

    state = "GENERATED"
    reasons.append("draft artifact exists")

    if run.get("script_owner_approved") and run.get("evidence_verified_by_owner"):
        state = "VERIFIED"
        reasons.append("script approved and evidence verified by owner")
    else:
        return {"state": state, "reasons": reasons + ["awaiting owner verification"]}

    if isinstance(plan, dict) and plan.get("status") in {"STAGED", "PUBLISHED"}:
        state = "STAGED"
        reasons.append(f"distribution plan {plan.get('plan_id')} is {plan.get('status')}")
    else:
        return {"state": state, "reasons": reasons + ["no staged distribution plan"]}

    records = [r for r in (publish_records or []) if isinstance(r, dict)]
    published = [r for r in records if r.get("status") == "PUBLISHED" and r.get("remote_id")]
    if published:
        state = "PUBLISHED"
        reasons.append(f"{len(published)} adapter(s) returned remote_id")
    else:
        return {"state": state, "reasons": reasons + ["no adapter publish with remote_id"]}

    obs = [o for o in (observations or []) if isinstance(o, dict)]
    if obs:
        state = "MEASURED"
        reasons.append(f"{len(obs)} audience observation(s) recorded")
    else:
        return {"state": state, "reasons": reasons + ["published but no audience measurement"]}

    verified_payouts = [
        p for p in (payouts or [])
        if isinstance(p, dict)
        and p.get("verified_cash_received") is True
        and float(p.get("amount_usd", 0.0) or 0.0) > 0
    ]
    if verified_payouts:
        state = "PAID"
        total = round(sum(float(p.get("amount_usd", 0.0)) for p in verified_payouts), 2)
        reasons.append(f"verified cash received across {len(verified_payouts)} payout(s): ${total}")
    else:
        reasons.append("estimates exist but no verified cash receipt; not PAID")

    return {"state": state, "reasons": reasons}
