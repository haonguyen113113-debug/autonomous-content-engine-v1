"""Scene Graph boundary: planner picks composition, renderer only executes.

Placeholder-free package doc. The deterministic composition decision lives in
``apps.card_selector`` (planner). ``apps.scene_graph.builder`` freezes one
beat into an absolute Scene Graph (no selection). ``apps.scene_graph.executor``
renders a validated graph with Pillow/FFmpeg primitives only.

Renderer/QA entry points (lazy to keep this package import-light)::

    from apps.scene_graph import build_scene_graph, validate, graph_hash

``build_scene_graph`` / ``build_from_decision`` / ``build_clip_graphs``
freeze planner decisions; ``validate`` (alias of
``schema.validate_scene_graph``) is the gate the renderer must call before
executing; ``graph_hash`` recomputes the deterministic freeze digest.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "SCENE_GRAPH_VERSION",
    "build_scene_graph",
    "build_from_decision",
    "build_clip_graphs",
    "validate",
    "graph_hash",
]

SCENE_GRAPH_VERSION = "1.0.0"

_LAZY = {
    "build_scene_graph": ("apps.scene_graph.builder", "build_scene_graph"),
    "build_from_decision": ("apps.scene_graph.builder", "build_from_decision"),
    "build_clip_graphs": ("apps.scene_graph.builder", "build_clip_graphs"),
    "validate": ("apps.scene_graph.schema", "validate_scene_graph"),
    "graph_hash": ("apps.scene_graph.schema", "graph_hash"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY:
        module_name, attr = _LAZY[name]
        import importlib

        return getattr(importlib.import_module(module_name), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
