"""Replaceable distribution layer (PROJECT_SPEC section 9).

Generation stays separate from routing and distribution::

    opportunity -> artifact -> quality gate -> theme classification
        -> channel routing -> platform adaptation -> publish -> measure

This package never broadcasts to every channel and never invents a
publish. Stub platform adapters return STAGED until a real, authorized
adapter replaces them.
"""

from .adapters import AdapterRegistry, LocalFileAdapter, PlatformAdapter, StubAdapter, default_registry
from .models import ChannelDestination, DistributionPlan, PublishRecord, utc_now
from .routing import load_channels, plan_distribution, quality_gate, route_artifact
from .service import estimate_distribution_cost, publish_plan, stage_plan

__all__ = [
    "AdapterRegistry",
    "ChannelDestination",
    "DistributionPlan",
    "LocalFileAdapter",
    "PlatformAdapter",
    "StubAdapter",
    "default_registry",
    "estimate_distribution_cost",
    "load_channels",
    "plan_distribution",
    "publish_plan",
    "quality_gate",
    "route_artifact",
    "stage_plan",
    "utc_now",
]
