from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PAYOUT_KIND = ("platform_payout", "sponsorship", "affiliate", "other")

_RUN_ID_RE = re.compile(r"[a-f0-9]{12}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class ObservationRecord:
    observation_id: str
    run_id: str
    remote_id: str | None
    channel_id: str
    platform: str
    day: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    watch_hours: float = 0.0
    ctr: float = 0.0
    conversions: int = 0
    earnings_estimated_usd: float = 0.0
    source: str = "manual_entry"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PayoutRecord:
    payout_id: str
    run_id: str | None
    channel_id: str
    amount_usd: float
    received_at: str
    verified_cash_received: bool = False
    kind: str = "platform_payout"
    method: str = ""
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ledger_paths(root: Path) -> tuple[Path, Path]:
    base = Path(root) / "runtime" / "measurement"
    return base / "observations.jsonl", base / "payouts.jsonl"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            rows.append(data)
    return rows


def record_observation(root: Path, **fields: Any) -> dict[str, Any]:
    """Record audience/earnings observation. Estimates stay estimates."""
    run_id = str(fields.get("run_id", ""))
    if not _RUN_ID_RE.fullmatch(run_id):
        raise ValueError("run_id must be a 12-hex engine run id.")
    for key in ("views", "likes", "comments", "shares", "conversions"):
        value = int(fields.get(key, 0) or 0)
        if value < 0:
            raise ValueError(f"{key} must be >= 0.")
        fields[key] = value
    fields["watch_hours"] = max(0.0, float(fields.get("watch_hours", 0.0) or 0.0))
    fields["ctr"] = max(0.0, min(1.0, float(fields.get("ctr", 0.0) or 0.0)))
    fields["earnings_estimated_usd"] = max(0.0, float(fields.get("earnings_estimated_usd", 0.0) or 0.0))
    record = ObservationRecord(
        observation_id=f"obs-{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        remote_id=fields.get("remote_id"),
        channel_id=str(fields.get("channel_id", "")),
        platform=str(fields.get("platform", "")),
        day=str(fields.get("day", _utc_now()[:10])),
        views=fields["views"],
        likes=fields["likes"],
        comments=fields["comments"],
        shares=fields["shares"],
        watch_hours=fields["watch_hours"],
        ctr=fields["ctr"],
        conversions=fields["conversions"],
        earnings_estimated_usd=fields["earnings_estimated_usd"],
        source=str(fields.get("source", "manual_entry")),
    )
    obs_path, _ = _ledger_paths(Path(root))
    _append_jsonl(obs_path, {**record.as_dict(), "recorded_at": _utc_now()})
    return record.as_dict()


def record_payout(root: Path, **fields: Any) -> dict[str, Any]:
    """Record a payout. Only verified_cash_received counts as realized."""
    amount = float(fields.get("amount_usd", 0.0) or 0.0)
    if amount <= 0:
        raise ValueError("amount_usd must be > 0.")
    kind = str(fields.get("kind", "platform_payout"))
    if kind not in PAYOUT_KIND:
        raise ValueError(f"kind must be one of {PAYOUT_KIND}.")
    record = PayoutRecord(
        payout_id=f"pay-{uuid.uuid4().hex[:8]}",
        run_id=fields.get("run_id"),
        channel_id=str(fields.get("channel_id", "")),
        amount_usd=round(amount, 2),
        received_at=str(fields.get("received_at", _utc_now()[:10])),
        verified_cash_received=bool(fields.get("verified_cash_received", False)),
        kind=kind,
        method=str(fields.get("method", "")),
        note=str(fields.get("note", ""))[:500],
    )
    _, pay_path = _ledger_paths(Path(root))
    _append_jsonl(pay_path, {**record.as_dict(), "recorded_at": _utc_now()})
    return record.as_dict()


def summarize_by_run(root: Path, production_costs: dict[str, float] | None = None) -> list[dict[str, Any]]:
    obs_path, pay_path = _ledger_paths(Path(root))
    observations = _read_jsonl(obs_path)
    payouts = _read_jsonl(pay_path)
    production_costs = production_costs or {}

    by_run: dict[str, dict[str, Any]] = {}
    for obs in observations:
        entry = by_run.setdefault(str(obs.get("run_id")), {
            "run_id": str(obs.get("run_id")),
            "views": 0, "likes": 0, "conversions": 0,
            "earnings_estimated_usd": 0.0, "payout_verified_usd": 0.0,
        })
        for key in ("views", "likes", "conversions"):
            entry[key] += int(obs.get(key, 0) or 0)
        entry["earnings_estimated_usd"] = round(
            entry["earnings_estimated_usd"] + float(obs.get("earnings_estimated_usd", 0.0) or 0.0), 2
        )
    for pay in payouts:
        if pay.get("verified_cash_received") is not True:
            continue
        run_id = str(pay.get("run_id") or "unattributed")
        entry = by_run.setdefault(run_id, {
            "run_id": run_id, "views": 0, "likes": 0, "conversions": 0,
            "earnings_estimated_usd": 0.0, "payout_verified_usd": 0.0,
        })
        entry["payout_verified_usd"] = round(
            entry["payout_verified_usd"] + float(pay.get("amount_usd", 0.0) or 0.0), 2
        )
    results = []
    for run_id, entry in sorted(by_run.items()):
        prod = round(float(production_costs.get(run_id, 0.0) or 0.0), 2)
        entry["production_cost_usd"] = prod
        # Contribution uses estimates for operations; profit uses verified cash.
        entry["contribution_margin_estimated_usd"] = round(entry["earnings_estimated_usd"] - prod, 2)
        entry["profit_attributable_usd"] = round(entry["payout_verified_usd"] - prod, 2)
        results.append(entry)
    return results


def summarize_by_channel(root: Path, production_costs: dict[str, float] | None = None) -> list[dict[str, Any]]:
    obs_path, pay_path = _ledger_paths(Path(root))
    observations = _read_jsonl(obs_path)
    payouts = _read_jsonl(pay_path)

    channels: dict[str, dict[str, Any]] = {}
    for obs in observations:
        key = str(obs.get("channel_id") or "unknown")
        entry = channels.setdefault(key, {
            "channel_id": key, "runs": set(), "views": 0,
            "earnings_estimated_usd": 0.0, "payout_verified_usd": 0.0,
        })
        entry["runs"].add(str(obs.get("run_id")))
        entry["views"] += int(obs.get("views", 0) or 0)
        entry["earnings_estimated_usd"] = round(
            entry["earnings_estimated_usd"] + float(obs.get("earnings_estimated_usd", 0.0) or 0.0), 2
        )
    for pay in payouts:
        if pay.get("verified_cash_received") is not True:
            continue
        key = str(pay.get("channel_id") or "unknown")
        entry = channels.setdefault(key, {
            "channel_id": key, "runs": set(), "views": 0,
            "earnings_estimated_usd": 0.0, "payout_verified_usd": 0.0,
        })
        if pay.get("run_id"):
            entry["runs"].add(str(pay.get("run_id")))
        entry["payout_verified_usd"] = round(
            entry["payout_verified_usd"] + float(pay.get("amount_usd", 0.0) or 0.0), 2
        )
    _ = production_costs  # per-run costs roll up in summarize_by_run; channel keeps cash truth
    results = []
    for key in sorted(channels):
        entry = channels[key]
        results.append({
            "channel_id": key,
            "run_count": len(entry["runs"]),
            "views": entry["views"],
            "earnings_estimated_usd": entry["earnings_estimated_usd"],
            "payout_verified_usd": entry["payout_verified_usd"],
        })
    return results
