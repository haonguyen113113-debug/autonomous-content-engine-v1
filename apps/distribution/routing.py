from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from .models import ChannelDestination, DistributionPlan, utc_now


RUN_ID_RE = re.compile(r"[a-f0-9]{12}")
RESEARCH_MARKERS = ("[CẦN NGUỒN]", "[KẾT LUẬN CỦA ALLEN]")


def load_channels(root: Path) -> list[dict[str, Any]]:
    """Read channel catalogs directly (no template-code dependency).

    Portable: only reads JSON under template_foundation/channels.
    Missing directory means zero routable channels, never an exception
    that blocks the rest of the engine.
    """
    channels_dir = Path(root) / "template_foundation" / "channels"
    channels: list[dict[str, Any]] = []
    if not channels_dir.is_dir():
        return channels
    for path in sorted(channels_dir.glob("*/channel.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("channel_id"):
            channels.append(data)
    return channels


def _segments(run: dict[str, Any]) -> list[dict[str, Any]]:
    draft = run.get("draft") or {}
    segments = draft.get("segments") or []
    return [s for s in segments if isinstance(s, dict)]


def quality_gate(run: dict[str, Any], *, for_publish: bool = False) -> tuple[bool, list[str]]:
    """Structural + approval gate. Critical failures block publishing.

    Staging requires an approved script. Publishing additionally requires
    an audited voice preview. Returns (ok, blockers).
    """
    blockers: list[str] = []
    if not isinstance(run, dict) or not run.get("run_id"):
        return False, ["run_id is missing"]
    segments = _segments(run)
    if not segments:
        blockers.append("artifact has no script segments")
    for seg in segments:
        narration = str(seg.get("narration", ""))
        for marker in RESEARCH_MARKERS:
            if marker in narration:
                blockers.append(f"unresolved research marker in {seg.get('id', 'segment')}")
                break
    if not run.get("script_owner_approved"):
        blockers.append("script is not owner-approved")
    if not run.get("evidence_verified_by_owner"):
        blockers.append("evidence is not owner-verified")
    if for_publish:
        if not run.get("voice_preview"):
            blockers.append("voice preview is missing")
        if not run.get("voice_preview_audited"):
            blockers.append("voice preview is not owner-audited")
    return (len(blockers) == 0), blockers


def _keyword_set(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def classify_theme(run: dict[str, Any], channel: dict[str, Any]) -> dict[str, Any]:
    """Explainable multi-factor fit. Components are kept, not collapsed.

    Scores are 0..1 with reasons so routing stays auditable (spec 7).
    """
    draft = run.get("draft") or {}
    topic = str(draft.get("topic", ""))
    story_form = str(draft.get("story_form", ""))
    content_type = str(draft.get("content_type", "short"))

    channel_text = " ".join([
        str(channel.get("audience", "")),
        str(channel.get("brand_promise", "")),
        " ".join(channel.get("coverage_priorities", []) or []),
        " ".join(channel.get("personality", []) or []),
    ])
    topic_keys = _keyword_set(topic)
    channel_keys = _keyword_set(channel_text)
    overlap = len(topic_keys & channel_keys)
    audience_fit = min(1.0, overlap / 4.0) if topic_keys else 0.0

    thematic_fit = 0.5
    if story_form:
        thematic_fit = 0.8 if channel.get("category", "soccer") == "soccer" else 0.5

    format_fit = 1.0 if content_type in {"short", "long"} else 0.0

    reasons = [
        f"audience keyword overlap {overlap} (topic vs channel promise/coverage)",
        f"story_form={story_form or 'unknown'} against category={channel.get('category', '?')}",
        f"content_type={content_type} fits channel formats",
    ]
    combined = round(0.5 * audience_fit + 0.3 * thematic_fit + 0.2 * format_fit, 3)
    return {
        "channel_id": channel.get("channel_id"),
        "audience_fit": round(audience_fit, 3),
        "thematic_fit": round(thematic_fit, 3),
        "format_fit": round(format_fit, 3),
        "combined": combined,
        "reasons": reasons,
    }


def route_artifact(
    run: dict[str, Any],
    channels: list[dict[str, Any]],
    destinations_by_channel: dict[str, list[ChannelDestination]] | None = None,
    *,
    max_channels: int = 1,
) -> DistributionPlan:
    """Route to the best-fit channel only. Never broadcast.

    max_channels is capped at 1 by default; callers must justify more.
    """
    run_id = str(run.get("run_id", "unknown"))
    destinations_by_channel = destinations_by_channel or {}
    ok, blockers = quality_gate(run, for_publish=False)

    scored = [classify_theme(run, ch) for ch in channels]
    scored.sort(key=lambda s: s["combined"], reverse=True)
    picked = scored[0] if scored else None
    # Hard cap: one channel per artifact unless evidence justifies more.
    max_channels = max(1, min(int(max_channels), 2))

    if picked is None:
        return DistributionPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            channel_id="unrouted",
            market="VN",
            language=str((run.get("draft") or {}).get("locale", "vi-VN")),
            destinations=[],
            fit_scores={"scores": []},
            rationale=["no channels available; artifact stays unrouted"],
            blockers=[*blockers, "no routable channel"],
            status="BLOCKED",
        )

    channel_id = str(picked["channel_id"])
    destinations = list(destinations_by_channel.get(channel_id, []))[:4]
    rationale = [
        f"selected {channel_id} with combined fit {picked['combined']} (top {max_channels} of {len(scored)})",
        *[f"{k}={picked[k]}" for k in ("audience_fit", "thematic_fit", "format_fit")],
        *picked["reasons"],
    ]
    if len(scored) > 1:
        rationale.append(
            f"did not broadcast to {len(scored) - 1} lower-fit channel(s); "
            f"next best was {scored[1]['channel_id']} at {scored[1]['combined']}"
        )
    status = "BLOCKED" if blockers else "DRAFT"
    return DistributionPlan(
        plan_id=f"plan-{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        channel_id=channel_id,
        market=str(next((c.get("market", "VN") for c in channels if c.get("channel_id") == channel_id), "VN")),
        language=str(next((c.get("language", "vi-VN") for c in channels if c.get("channel_id") == channel_id), "vi-VN")),
        destinations=destinations,
        fit_scores={"scores": scored, "picked": picked, "routed_count": max_channels},
        rationale=rationale,
        blockers=list(blockers),
        status=status,
    )


def _distribution_path(root: Path, run_id: str) -> Path:
    return Path(root) / "runtime" / "distribution" / f"{run_id}.json"


def plan_distribution(
    root: Path,
    run: dict[str, Any],
    destinations_by_channel: dict[str, list[ChannelDestination]] | None = None,
) -> dict[str, Any]:
    """Build a routing plan and persist it as a sidecar file.

    Never mutates runtime/runs/*.json so parallel builders stay safe.
    Sidecar lives under git-ignored runtime/distribution/.
    """
    channels = load_channels(root)
    plan = route_artifact(run, channels, destinations_by_channel)
    data = plan.as_dict()
    data["created_at"] = utc_now()
    path = _distribution_path(root, str(run.get("run_id", "unknown")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return data


def read_plan(root: Path, run_id: str) -> dict[str, Any] | None:
    path = _distribution_path(root, run_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
