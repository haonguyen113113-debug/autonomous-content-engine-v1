from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .models import DistributionPlan, PublishRecord, utc_now


class PlatformAdapter(ABC):
    """Replaceable publishing backend. One subclass per platform."""

    platform: str = "base"
    requires_auth: bool = True

    @abstractmethod
    def publish(
        self,
        root: Path,
        plan: DistributionPlan,
        artifact: dict[str, Any],
        account_ref: str,
        *,
        dry_run: bool = False,
    ) -> PublishRecord:
        ...  # pragma: no cover

    def fetch_status(self, root: Path, remote_id: str) -> dict[str, Any]:
        return {"remote_id": remote_id, "status": "unknown"}


class LocalFileAdapter(PlatformAdapter):
    """Local-first proof adapter. Writes a manifest, needs no network."""

    platform = "local_file"
    requires_auth = False

    def publish(self, root, plan, artifact, account_ref, *, dry_run=False) -> PublishRecord:
        record = PublishRecord(
            record_id=f"rec-{uuid.uuid4().hex[:8]}",
            plan_id=plan.plan_id,
            run_id=plan.run_id,
            platform=self.platform,
            account_ref=account_ref or "local",
            status="STAGED" if dry_run else "PUBLISHED",
            remote_id=None,
            dry_run=dry_run,
        )
        if dry_run:
            return record
        out_dir = Path(root) / "runtime" / "publish" / plan.run_id
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "remote_id": f"file:{plan.run_id}/{self.platform}",
            "plan_id": plan.plan_id,
            "run_id": plan.run_id,
            "channel_id": plan.channel_id,
            "topic": (artifact.get("draft") or {}).get("topic"),
            "published_at": utc_now(),
        }
        (out_dir / f"{self.platform}.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        record.remote_id = manifest["remote_id"]
        return record


class StubAdapter(PlatformAdapter):
    """Placeholder for real platform APIs. Never fakes a publish."""

    def __init__(self, platform: str):
        self.platform = platform

    def publish(self, root, plan, artifact, account_ref, *, dry_run=False) -> PublishRecord:
        hint = (
            f"adapter_not_configured: link the {self.platform} account "
            f"(account_ref={account_ref or 'missing'}) via machine-local .env, "
            "then replace this stub with a real adapter. Nothing was uploaded."
        )
        return PublishRecord(
            record_id=f"rec-{uuid.uuid4().hex[:8]}",
            plan_id=plan.plan_id,
            run_id=plan.run_id,
            platform=self.platform,
            account_ref=account_ref,
            status="STAGED",
            remote_id=None,
            error=hint,
            dry_run=dry_run,
        )


class AdapterRegistry:
    def __init__(self):
        self._adapters: dict[str, PlatformAdapter] = {}

    def register(self, adapter: PlatformAdapter) -> None:
        self._adapters[adapter.platform] = adapter

    def get(self, platform: str) -> PlatformAdapter:
        try:
            return self._adapters[platform]
        except KeyError as error:
            raise ValueError(f"No adapter registered for platform={platform!r}.") from error

    def platforms(self) -> list[str]:
        return sorted(self._adapters)


def default_registry() -> AdapterRegistry:
    registry = AdapterRegistry()
    registry.register(LocalFileAdapter())
    for platform in ("youtube", "tiktok", "facebook"):
        registry.register(StubAdapter(platform))
    return registry
