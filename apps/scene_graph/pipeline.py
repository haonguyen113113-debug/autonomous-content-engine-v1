"""Run-level Scene Graph freeze adapter (post-merge production path).

Builds one frozen Scene Graph per segment of a run after
``apply_card_plan()`` and attaches them to ``run["draft"]["scene_graphs"]``.

Orchestrates only:
- ``apps.asset_library.registry`` (read-only asset rights lookups; never
  creates or mutates anything under ``runtime/``), and
- ``apps.scene_graph.builder`` (deterministic freeze).

Zero composition choice, zero runtime writes. Asset records flow straight
through to the builder: a record whose persisted ``rights_scope_json`` is a
valid human-granted scope emits an ``approved`` ref; deny-default or
missing/invalid scopes emit explicit ``pending`` placeholders the renderer/QA
gate on. ``rights_state``/``lifecycle_state`` alone never imply clearance.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from apps.asset_library.registry import connect as _registry_connect
from apps.scene_graph.builder import build_clip_graphs
from apps.scene_graph.schema import validate_scene_graph

_ENGINE_DB = Path("runtime") / "engine.db"


def _fetch_asset_infos(root: Path, media_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Read-only rights rows for the given (de-duplicated) media asset ids.

    Mirrors the read-only registry pattern used by
    ``apps.measurement.render_qa._registry_row`` / ``apps.card_selector.
    _fetch_verified_images``: connect to ``root / runtime / engine.db``,
    select the asset row, return it as a plain dict.

    Missing/unreadable registry or missing row -> no entry for that id
    (graph gets a ``pending`` placeholder; renderer/QA gate). Never creates
    or mutates anything under ``runtime/``.
    """
    infos: dict[str, dict[str, Any]] = {}
    db_path = root / _ENGINE_DB
    if not db_path.is_file():
        return infos
    seen: set[str] = set()
    try:
        conn = _registry_connect(db_path)
    except (OSError, sqlite3.Error):
        return infos
    try:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(assets)").fetchall()
        }
        wanted = [
            "asset_id", "asset_type", "rights_state", "lifecycle_state",
            "license_type", "purpose_code",
        ]
        if "rights_scope_json" in columns:
            wanted.append("rights_scope_json")
        select = ", ".join(wanted)
        for media_id in media_ids:
            if not media_id or media_id in seen:
                continue
            seen.add(media_id)
            try:
                row = conn.execute(
                    f"SELECT {select} FROM assets WHERE asset_id = ?",
                    (media_id,),
                ).fetchone()
            except sqlite3.Error:
                continue
            if row is None:
                continue
            infos[media_id] = {key: row[key] for key in row.keys()}
    finally:
        conn.close()
    return infos


def build_run_scene_graphs(root: Path, run: dict[str, Any]) -> list[dict[str, Any]]:
    """Xây dựng 1 Scene Graph đóng băng cho mỗi segment của run sau
    apply_card_plan(); gắn vào run["draft"]["scene_graphs"] và trả danh sách đó.

    Raises ValueError (rõ ràng) khi run chưa có draft/segments hoặc card_plan/
    decisions (chưa gọi apply_card_plan), và khi builder xuất graph không
    hợp lệ (fail fast: graph invalid không được gắn vào run).
    """
    if not isinstance(run, dict):
        raise ValueError("scene graph pipeline: run must be an object")

    draft = run.get("draft")
    if not isinstance(draft, dict):
        raise ValueError(
            "scene graph pipeline: run has no script draft (run['draft']) — "
            "build the script draft before freezing scene graphs"
        )

    segments = draft.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError(
            "scene graph pipeline: draft['segments'] must be a non-empty list "
            "— no segments to freeze into scene graphs"
        )

    card_plan = run.get("card_plan")
    if not isinstance(card_plan, dict):
        raise ValueError(
            "scene graph pipeline: run has no card plan (run['card_plan']) — "
            "call apply_card_plan(root, run) before building scene graphs"
        )

    decisions = card_plan.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        raise ValueError(
            "scene graph pipeline: card_plan['decisions'] must be a non-empty "
            "list — call apply_card_plan(root, run) before building scene graphs"
        )

    content_type = str(draft.get("content_type", "short"))
    template_version = draft.get("template_version")

    segments_by_id = {
        str(s.get("id")): s for s in segments if isinstance(s, dict)
    }

    media_ids: list[str] = []
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        media_id = decision.get("media_asset_id")
        if isinstance(media_id, str) and media_id and media_id not in media_ids:
            media_ids.append(media_id)
    asset_map = _fetch_asset_infos(root, media_ids)

    graphs = build_clip_graphs(
        decisions,
        segments_by_id=segments_by_id,
        content_type=content_type,
        template_version=template_version,
        asset_map=asset_map,
    )

    validated: list[dict[str, Any]] = []
    for graph in graphs:
        if not isinstance(graph, dict):
            raise ValueError(
                "scene graph pipeline: builder emitted a non-object graph"
            )
        validate_scene_graph(graph)  # fail fast: invalid graph is not attached
        validated.append(graph)

    draft["scene_graphs"] = validated
    return validated


__all__ = ["build_run_scene_graphs"]
