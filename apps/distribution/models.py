from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


LIFECYCLE_STATES = (
    "GENERATED",
    "VERIFIED",
    "STAGED",
    "PUBLISHED",
    "MEASURED",
    "PAID",
)

PLAN_STATUSES = ("DRAFT", "BLOCKED", "STAGED", "PUBLISHED", "FAILED")

PUBLISH_STATUSES = ("STAGED", "PUBLISHED", "FAILED")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class ChannelDestination:
    """One authorized publishing target. Portable plain data."""

    platform: str
    account_ref: str
    market: str = "VN"
    format_note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class DistributionPlan:
    """Routing decision for one run. Never a broadcast list."""

    plan_id: str
    run_id: str
    channel_id: str
    market: str
    language: str
    destinations: list[ChannelDestination] = field(default_factory=list)
    fit_scores: dict = field(default_factory=dict)
    rationale: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    status: str = "DRAFT"
    created_at: str = field(default_factory=utc_now)

    def as_dict(self) -> dict:
        data = asdict(self)
        return data


@dataclass
class PublishRecord:
    """One adapter attempt. A STAGED record is not proof of publishing."""

    record_id: str
    plan_id: str
    run_id: str
    platform: str
    account_ref: str
    status: str
    remote_id: str | None = None
    error: str | None = None
    dry_run: bool = False
    attempted_at: str = field(default_factory=utc_now)

    def as_dict(self) -> dict:
        return asdict(self)
