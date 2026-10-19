from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .adapters import AdapterRegistry, default_registry
from .models import DistributionPlan, PublishRecord
from .routing import _distribution_path, quality_gate, read_plan  # noqa: F401  (re-export for callers)


def estimate_distribution_cost(plan: DistributionPlan) -> float:
    """Local-first cost model. Real adapters override per platform."""
    if not plan.destinations:
        return 0.0
    cost = 0.0
    for dest in plan.destinations:
        if dest.platform == "local_file":
            cost += 0.0
        else:
            cost += 0.0  # stubs never spend; real adapters report actual fees
    return round(cost, 6)


def _records_path(root: Path, run_id: str) -> Path:
    return Path(root) / "runtime" / "publish" / run_id / "publish-records.json"


def _append_records(root: Path, run_id: str, records: list[PublishRecord]) -> list[dict[str, Any]]:
    path = _records_path(root, run_id)
    existing: list[dict[str, Any]] = []
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = loaded
        except (OSError, json.JSONDecodeError):
            existing = []
    existing.extend(r.as_dict() for r in records)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return existing


def stage_plan(root: Path, plan_data: dict[str, Any]) -> dict[str, Any]:
    """Mark a plan STAGED after its quality gate passes. Sidecar only."""
    plan_data = dict(plan_data)
    blockers = list(plan_data.get("blockers", []))
    if blockers:
        plan_data["status"] = "BLOCKED"
    else:
        plan_data["status"] = "STAGED"
    run_id = str(plan_data.get("run_id", "unknown"))
    path = _distribution_path(root, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan_data


def publish_plan(
    root: Path,
    run: dict[str, Any],
    plan_data: dict[str, Any],
    *,
    registry: AdapterRegistry | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Publish through replaceable adapters. Never mutates run files.

    Requires the publish-time quality gate (script + audited voice).
    Stub adapters yield STAGED records, never PUBLISHED.
    """
    registry = registry or default_registry()
    ok, blockers = quality_gate(run, for_publish=True)
    if not ok:
        plan_data = dict(plan_data)
        plan_data["status"] = "BLOCKED"
        plan_data["publish_blockers"] = blockers
        return {"status": "BLOCKED", "blockers": blockers, "records": []}

    plan = DistributionPlan(
        plan_id=str(plan_data.get("plan_id", "plan-unknown")),
        run_id=str(plan_data.get("run_id", run.get("run_id", "unknown"))),
        channel_id=str(plan_data.get("channel_id", "unrouted")),
        market=str(plan_data.get("market", "VN")),
        language=str(plan_data.get("language", "vi-VN")),
        status=str(plan_data.get("status", "STAGED")),
    )
    from .models import ChannelDestination

    for dest in plan_data.get("destinations", []) or []:
        if isinstance(dest, dict):
            plan.destinations.append(ChannelDestination(
                platform=str(dest.get("platform", "")),
                account_ref=str(dest.get("account_ref", "")),
                market=str(dest.get("market", plan.market)),
                format_note=str(dest.get("format_note", "")),
            ))

    records: list[PublishRecord] = []
    for dest in plan.destinations:
        adapter = registry.get(dest.platform)
        records.append(adapter.publish(Path(root), plan, run, dest.account_ref, dry_run=dry_run))

    stored = _append_records(Path(root), plan.run_id, records)
    statuses = {r.status for r in records}
    if "PUBLISHED" in statuses:
        plan_data = {**plan_data, "status": "PUBLISHED"}
    elif records and all(r.status == "STAGED" for r in records):
        plan_data = {**plan_data, "status": "STAGED"}
    else:
        plan_data = {**plan_data, "status": "FAILED"}
    path = _distribution_path(Path(root), plan.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "status": plan_data["status"],
        "records": [r.as_dict() for r in records],
        "stored_records": stored,
        "distribution_cost_usd": estimate_distribution_cost(plan),
        "production_cost_usd": float((run.get("llm_cost_usd", 0.0) or 0.0)),
    }
