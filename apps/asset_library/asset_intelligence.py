from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ResourceRequirement:
    """Domain-agnostic request for a resource needed by an upstream workflow."""

    requirement_id: str
    resource_type: str
    entity_id: str | None = None
    purpose: str | None = None
    context: str | None = None
    rights_state: str | None = None
    lifecycle_state: str | None = None
    quality_constraints: Mapping[str, Any] = field(default_factory=dict)
    temporal_constraints: Mapping[str, Any] = field(default_factory=dict)
    market_constraints: Mapping[str, Any] = field(default_factory=dict)
    format_constraints: Mapping[str, Any] = field(default_factory=dict)
    discovery_query: str | None = None
    content_objective: str | None = None


@dataclass(frozen=True)
class ResourceEvaluation:
    requirement_id: str
    status: str
    eligible_assets: tuple[str, ...]
    recommended_asset: str | None
    context_fit: str
    recommendation: str
    reasons: tuple[str, ...]
    asset_gap: ResourceRequirement | None = None


def _metadata(asset: Mapping[str, Any]) -> Mapping[str, Any]:
    value = asset.get("metadata", {})
    return value if isinstance(value, Mapping) else {}


def _contexts(asset: Mapping[str, Any]) -> tuple[str, ...]:
    value = _metadata(asset).get("contexts", [])

    if isinstance(value, str):
        return (value,)

    if isinstance(value, (list, tuple, set)):
        return tuple(str(item) for item in value)

    return ()


def _eligible(
    requirement: ResourceRequirement,
    asset: Mapping[str, Any],
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []

    if asset.get("asset_type") != requirement.resource_type:
        return False, ("asset_type_mismatch",)

    reasons.append("asset_type_matches")

    if requirement.entity_id is not None:
        if asset.get("subject_id") != requirement.entity_id:
            return False, ("entity_mismatch",)

        reasons.append("entity_matches")

    if requirement.purpose is not None:
        if asset.get("purpose_code") != requirement.purpose:
            return False, ("purpose_mismatch",)

        reasons.append("purpose_matches")

    if requirement.rights_state is not None:
        if asset.get("rights_state") != requirement.rights_state:
            return False, ("rights_mismatch",)

        if requirement.rights_state == "verified":
            reasons.append("rights_verified")
        else:
            reasons.append("rights_match")

    if requirement.lifecycle_state is not None:
        if asset.get("lifecycle_state") != requirement.lifecycle_state:
            return False, ("lifecycle_mismatch",)

        if requirement.lifecycle_state == "active":
            reasons.append("lifecycle_active")
        else:
            reasons.append("lifecycle_match")

    return True, tuple(reasons)


def _context_fit(
    requirement: ResourceRequirement,
    asset: Mapping[str, Any],
) -> tuple[str, str]:
    if requirement.context is None:
        return "NOT_REQUIRED", "context_not_required"

    contexts = _contexts(asset)

    # Absence of context evidence is not evidence of mismatch.
    if not contexts:
        return "UNKNOWN_CONTEXT", "context_not_known"

    if requirement.context in contexts:
        return "EXACT_CONTEXT", "context_matches"

    return "NO_CONTEXT_MATCH", "context_does_not_match"


def evaluate_requirement(
    requirement: ResourceRequirement,
    candidates: Iterable[Mapping[str, Any]],
) -> ResourceEvaluation:
    """
    Evaluate reusable inventory without acquiring, mutating, or authorizing anything.

    This function is intentionally pure with respect to the asset library.
    """

    eligible: list[
        tuple[Mapping[str, Any], tuple[str, ...]]
    ] = []

    for asset in candidates:
        is_eligible, reasons = _eligible(requirement, asset)

        if is_eligible:
            eligible.append((asset, reasons))

    if not eligible:
        return ResourceEvaluation(
            requirement_id=requirement.requirement_id,
            status="UNSATISFIED",
            eligible_assets=(),
            recommended_asset=None,
            context_fit="NONE",
            recommendation="ACQUIRE",
            reasons=("no_eligible_asset",),
            asset_gap=requirement,
        )

    exact: list[
        tuple[Mapping[str, Any], tuple[str, ...]]
    ] = []

    unknown: list[
        tuple[Mapping[str, Any], tuple[str, ...]]
    ] = []

    mismatch: list[
        tuple[Mapping[str, Any], tuple[str, ...]]
    ] = []

    for asset, reasons in eligible:
        fit, _ = _context_fit(requirement, asset)

        if fit in {"EXACT_CONTEXT", "NOT_REQUIRED"}:
            exact.append((asset, reasons))
        elif fit == "UNKNOWN_CONTEXT":
            unknown.append((asset, reasons))
        else:
            mismatch.append((asset, reasons))

    eligible_asset_ids = tuple(
        str(asset.get("asset_id"))
        for asset, _ in eligible
    )

    if exact:
        asset, base_reasons = exact[0]
        fit, context_reason = _context_fit(requirement, asset)

        return ResourceEvaluation(
            requirement_id=requirement.requirement_id,
            status="SATISFIED",
            eligible_assets=eligible_asset_ids,
            recommended_asset=str(asset.get("asset_id")),
            context_fit=fit,
            recommendation="REUSE",
            reasons=base_reasons + (context_reason,),
        )

    if unknown:
        asset, base_reasons = unknown[0]

        return ResourceEvaluation(
            requirement_id=requirement.requirement_id,
            status="NEEDS_VERIFICATION",
            eligible_assets=eligible_asset_ids,
            recommended_asset=str(asset.get("asset_id")),
            context_fit="UNKNOWN_CONTEXT",
            recommendation="VERIFY",
            reasons=base_reasons + ("context_not_known",),
        )

    asset, base_reasons = mismatch[0]

    return ResourceEvaluation(
        requirement_id=requirement.requirement_id,
        status="UNSATISFIED",
        eligible_assets=eligible_asset_ids,
        recommended_asset=None,
        context_fit="NO_CONTEXT_MATCH",
        recommendation="DO_NOT_RECOMMEND",
        reasons=base_reasons + ("context_does_not_match",),
    )
