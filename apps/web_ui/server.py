from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
import unicodedata
from urllib.request import urlopen
from typing import Any
from urllib.parse import urlparse

from apps.content_workflow import run_content_agent
from apps.asset_library.asset_intelligence import ResourceRequirement
from apps.asset_library.discovery import (
    DiscoveryError,
    save_commons_candidate,
    search_candidates,
)
from apps.asset_library.identity import apply_identity_filter
from apps.asset_library.registry import connect
from apps.asset_library.resource_workflow import evaluate_library_requirement
from apps.distribution import ChannelDestination, default_registry, plan_distribution
from apps.distribution.routing import read_plan
from apps.distribution.service import publish_plan, stage_plan
from apps.measurement import (
    classify_lifecycle,
    record_observation,
    record_payout,
    summarize_by_channel,
    summarize_by_run,
)
from apps.voice_tts import save_voice_reference, synthesize_voice_preview, voice_profile_status
from apps.video_renderer import render_full_run, render_template_preview, render_graphic_template_previews, render_visual_only_run
from template_foundation import resolve_template


STATIC_ROOT = Path(__file__).parent / "static"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}
MAX_REQUEST_BYTES = 64 * 1024
TEMPLATE_ID = "allen-knows-ball.shortform-analyst"
LONG_TEMPLATE_ID = "allen-knows-ball.longform-analyst"
TEMPLATE_FILES = {
    "/template-foundation/preview.html": ("preview.html", "text/html; charset=utf-8"),
    "/template-foundation/previews/portrait-composite.png": (
        "previews/composite-proof.png",
        "image/png",
    ),
    "/template-foundation/previews/landscape-composite.png": (
        "previews/composite-proof.png",
        "image/png",
    ),
    **{
        f"/template-foundation/previews/{prefix}-{name}.png": (
            f"previews/{prefix}-{name}.png", "image/png",
        )
        for prefix in ("short", "long")
        for name in (
            "statline-preview", "chart-preview", "source-preview",
            "chart-bar-preview", "chart-column-preview", "chart-pie-preview",
            "chart-donut-preview", "chart-line-preview",
            "hook-card-preview", "hero-preview",
        )
    },
    "/template-foundation/resources/identity/akb-mark.svg": (
        "resources/identity/akb-mark.svg",
        "image/svg+xml",
    ),
    **{
        f"/template-foundation/resources/fonts/{name}": (
            f"resources/fonts/{name}",
            "font/ttf",
        )
        for name in (
            "BeVietnamPro-Regular.ttf",
            "BeVietnamPro-SemiBold.ttf",
            "BeVietnamPro-Bold.ttf",
            "BarlowCondensed-SemiBold.ttf",
            "BarlowCondensed-Bold.ttf",
        )
    },
}


def _approve_script(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{12}", run_id):
        raise ValueError("Production run ID is invalid.")
    if payload.get("evidence_verified") is not True:
        raise ValueError("Confirm that you reviewed the script and its factual evidence.")
    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments or len(segments) > 12:
        raise ValueError("A reviewed script with at least one segment is required.")
    run_path = root / "runtime/runs" / f"{run_id}.json"
    if not run_path.is_file():
        raise ValueError("Production run was not found.")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    original = run.get("draft", {}).get("segments", [])
    if len(original) != len(segments):
        raise ValueError("Keep the story beats intact while reviewing the narration.")
    approved = []
    for expected, segment in zip(original, segments):
        if not isinstance(segment, dict) or segment.get("id") != expected.get("id"):
            raise ValueError("Script segment order or ID does not match the generated draft.")
        narration = unicodedata.normalize("NFC", str(segment.get("narration", ""))).strip()
        if not narration or len(narration) > 3000:
            raise ValueError("Each voiceover segment needs 1–3,000 characters.")
        if "[CẦN NGUỒN]" in narration or "[KẾT LUẬN CỦA ALLEN]" in narration:
            raise ValueError("Resolve every research or conclusion marker before approving the script.")
        approved.append({**expected, "narration": narration})
    run["draft"]["segments"] = approved
    run["draft"]["evidence"] = [
        unicodedata.normalize("NFC", line.strip())
        for line in str(payload.get("evidence", "")).splitlines()
        if line.strip()
    ][:12]
    run["script_owner_approved"] = True
    run["evidence_verified_by_owner"] = True
    run["script_approved_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    run["status"] = "SCRIPT_APPROVED"
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": run["status"], "run_id": run_id}


def _approve_voice_preview(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{12}", run_id):
        raise ValueError("Production run ID is invalid.")
    if payload.get("voice_audited") is not True:
        raise ValueError("Confirm that you listened to the generated voice preview.")
    run_path = root / "runtime/runs" / f"{run_id}.json"
    if not run_path.is_file():
        raise ValueError("Production run was not found.")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if not run.get("script_owner_approved") or not run.get("voice_preview"):
        raise ValueError("Approve the script and generate its voice preview first.")
    voice_root = (root / "runtime/voice").resolve()
    voice_file = (voice_root / str(run["voice_preview"].get("path", ""))).resolve()
    if not voice_file.is_file() or voice_file.parent != voice_root:
        raise ValueError("The local voice preview file is missing from this workspace.")
    run["voice_preview_audited"] = True
    run["voice_preview_audited_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "VOICE_PREVIEW_APPROVED", "run_id": run_id}


def _attach_segment_media(root: Path, db_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{12}", run_id):
        raise ValueError("Production run ID is invalid.")
    segment_id = payload.get("segment_id")
    if not isinstance(segment_id, str) or not segment_id.strip() or len(segment_id) > 80:
        raise ValueError("A segment ID is required.")
    segment_id = unicodedata.normalize("NFC", segment_id.strip())
    asset_id = payload.get("asset_id")
    if not isinstance(asset_id, str):
        raise ValueError("An asset ID is required.")
    asset_id = asset_id.strip()
    caption = unicodedata.normalize("NFC", str(payload.get("media_caption", ""))).strip()[:500]

    run_path = root / "runtime/runs" / f"{run_id}.json"
    if not run_path.is_file():
        raise ValueError("Production run was not found.")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    segments = run.get("draft", {}).get("segments", [])
    if not isinstance(segments, list):
        raise ValueError("Production run has no script segments.")
    segment = next((item for item in segments if isinstance(item, dict) and item.get("id") == segment_id), None)
    if segment is None:
        raise ValueError("Script segment was not found in this run.")

    if not asset_id:
        segment.pop("media_asset_id", None)
        segment.pop("media_caption", None)
        run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"status": "MEDIA_DETACHED", "run_id": run_id, "segment_id": segment_id}

    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT asset_id, asset_type, rights_state, lifecycle_state, stored_path "
            "FROM assets WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError("Asset was not found in the library.")
    if row["asset_type"] != "image":
        raise ValueError("Only verified image assets can be attached as segment media.")
    if row["rights_state"] != "verified":
        raise ValueError("Asset rights must be verified before attaching it to a segment.")
    if row["lifecycle_state"] != "active":
        raise ValueError("Only active library assets can be attached to a segment.")
    library_root = (root / "runtime/assets/library").resolve()
    image_path = (root / row["stored_path"]).resolve()
    if library_root not in image_path.parents or not image_path.is_file():
        raise ValueError("Selected library image is missing or outside the library.")

    segment["media_asset_id"] = asset_id
    if caption:
        segment["media_caption"] = caption
    else:
        segment.pop("media_caption", None)
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "MEDIA_ATTACHED", "run_id": run_id, "segment_id": segment_id, "asset_id": asset_id}


def _read_api_keys(root: Path) -> dict[str, str]:
    """Optional provider keys from the environment and the local .env file."""
    keys = dict(os.environ)
    env_file = root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                keys.setdefault(key.strip(), value.strip().strip("\"'"))
    return {name: keys[name] for name in ("PEXELS_API_KEY", "PIXABAY_API_KEY") if keys.get(name)}


def _asset_file_info(root: Path, db_path: Path, asset_id: str) -> tuple[Path, str]:
    """Resolve a library file for owner preview. Any rights state is viewable:
    the owner must see an asset to review its rights."""
    if not isinstance(asset_id, str) or not asset_id.strip() or len(asset_id) > 80:
        raise ValueError("Asset ID is required.")
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT stored_path, mime_type FROM assets WHERE asset_id = ?",
            (asset_id.strip(),),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError("Asset was not found in the library.")
    library_root = (root / "runtime/assets/library").resolve()
    file_path = (root / row["stored_path"]).resolve()
    if library_root not in file_path.parents or not file_path.is_file():
        raise ValueError("Library file is missing or outside the library.")
    mime_type = str(row["mime_type"] or "")
    if "/" not in mime_type:
        import mimetypes
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    return file_path, mime_type


def _read_run(root: Path, run_id: str) -> dict[str, Any]:
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{12}", run_id):
        raise ValueError("Production run ID is invalid.")
    run_path = root / "runtime/runs" / f"{run_id}.json"
    if not run_path.is_file():
        raise ValueError("Production run was not found.")
    try:
        run = json.loads(run_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Production run file is unreadable.") from error
    if not isinstance(run, dict):
        raise ValueError("Production run file is unreadable.")
    return run


def _overview(db_path: Path) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        verified = conn.execute(
            "SELECT COUNT(*) FROM assets WHERE rights_state = 'verified'"
        ).fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM assets WHERE lifecycle_state = 'active'"
        ).fetchone()[0]
        types = conn.execute(
            """
            SELECT asset_type, COUNT(*) AS count
            FROM assets
            GROUP BY asset_type
            ORDER BY asset_type
            """
        ).fetchall()
        return {
            "asset_count": total,
            "verified_rights_count": verified,
            "active_count": active,
            "type_counts": [dict(row) for row in types],
        }
    finally:
        conn.close()


def _assets(db_path: Path) -> list[dict[str, Any]]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT asset_id, original_name, asset_type, purpose_code,
                   rights_state, lifecycle_state, source_url, license_type,
                   created_at
            FROM assets
            ORDER BY created_at DESC, asset_id
            LIMIT 200
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _summarize_run(root: Path, path: Path) -> dict[str, Any] | None:
    try:
        run = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(run, dict):
        return None
    draft = run.get("draft", {})
    if not isinstance(draft, dict):
        draft = {}
    segments = draft.get("segments", [])
    if not isinstance(segments, list):
        segments = []
    media_count = sum(
        1 for item in segments if isinstance(item, dict) and item.get("media_asset_id")
    )
    render_dir = root / "runtime/renders" / str(run.get("run_id", ""))
    videos: dict[str, str] = {}
    has_report = False
    if render_dir.is_dir():
        for name in ("template-preview.mp4", "visual-benchmark-silent.mp4", "full-render.mp4"):
            if (render_dir / name).is_file():
                videos[name] = f"/api/render/{run.get('run_id')}/{name}"
        has_report = (render_dir / "render-report.json").is_file()
    return {
        "run_id": run.get("run_id"),
        "created_at": run.get("created_at"),
        "status": run.get("status", "unknown"),
        "topic": draft.get("topic"),
        "content_type": draft.get("content_type"),
        "generation_mode": draft.get("generation_mode"),
        "segment_count": len(segments),
        "media_count": media_count,
        "script_owner_approved": bool(run.get("script_owner_approved")),
        "voice_preview": bool(run.get("voice_preview")),
        "voice_preview_audited": bool(run.get("voice_preview_audited")),
        "videos": videos,
        "has_report": has_report,
        "current_beat": run.get("current_beat"),
        "total_beats": run.get("total_beats"),
    }


def _list_runs(root: Path, limit: int = 200) -> list[dict[str, Any]]:
    runs_dir = root / "runtime/runs"
    if not runs_dir.is_dir():
        return []
    summaries = []
    for path in runs_dir.glob("*.json"):
        if not re.fullmatch(r"[a-f0-9]{12}\.json", path.name):
            continue
        summary = _summarize_run(root, path)
        if summary is not None:
            summaries.append(summary)
    summaries.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return summaries[:limit]


def _stats(root: Path, db_path: Path) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        verified = conn.execute(
            "SELECT COUNT(*) FROM assets WHERE rights_state = 'verified'"
        ).fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM assets WHERE lifecycle_state = 'active'"
        ).fetchone()[0]

        def daily(where: str) -> list[dict[str, Any]]:
            rows = conn.execute(
                "SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS count "
                f"FROM assets WHERE {where} GROUP BY day ORDER BY day",
            ).fetchall()
            return [{"day": row["day"], "count": row["count"]} for row in rows]

        by_day = daily("1 = 1")
        verified_by_day = daily("rights_state = 'verified'")
        active_by_day = daily("lifecycle_state = 'active'")
        by_license = conn.execute(
            "SELECT COALESCE(NULLIF(license_type, ''), 'Unknown') AS license, "
            "COUNT(*) AS count FROM assets GROUP BY license "
            "ORDER BY count DESC LIMIT 6",
        ).fetchall()
    finally:
        conn.close()
    runs = _list_runs(root)
    by_status: dict[str, int] = {}
    for item in runs:
        key = str(item.get("status", "unknown"))
        by_status[key] = by_status.get(key, 0) + 1
    return {
        "asset_count": total,
        "verified_rights_count": verified,
        "active_count": active,
        "run_count": len(runs),
        "assets_by_day": by_day,
        "verified_by_day": verified_by_day,
        "active_by_day": active_by_day,
        "assets_by_license": [
            {"license": row["license"], "count": row["count"]} for row in by_license
        ],
        "runs_by_status": by_status,
    }


def _template_foundation(db_path: Path) -> dict[str, Any]:
    root = db_path.parent.parent
    packages = {}
    for content_type, template_id in (("short", TEMPLATE_ID), ("long", LONG_TEMPLATE_ID)):
        package = resolve_template(root, template_id, allow_draft=True)
        packages[content_type] = {
            "channel": package.channel,
            "manifest": package.manifest,
            "design_tokens": package.design_tokens,
            "timeline": package.timeline,
            "story_forms": package.story_forms,
            "slots": package.slots,
            "visual_modes": package.visual_modes,
            "graphic_templates": package.graphic_templates,
            "color_systems": package.color_systems,
        }
    return {"channel": packages["short"]["channel"], "templates": packages}


def _content_status(root: Path) -> dict[str, Any]:
    voice_status = voice_profile_status(root)
    env = dict(os.environ)
    env_file = root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env.setdefault(key.strip(), value.strip().strip("\"'"))
    model = env.get("LLM_MODEL", "").strip() or "qwen3.5:2b"
    base_url = env.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    ready = False
    if model:
        try:
            with urlopen(f"{base_url}/api/tags", timeout=0.35) as response:
                models = json.loads(response.read().decode("utf-8")).get("models", [])
            ready = any(item.get("name", "").split(":", 1)[0] == model.split(":", 1)[0] for item in models)
        except Exception:
            ready = False
    installed_model = None
    if ready:
        installed_model = next(
            (item.get("name") for item in models if item.get("name", "").split(":", 1)[0] == model.split(":", 1)[0]),
            None,
        )
    return {
        "script_model_ready": ready,
        "provider": env.get("LLM_PROVIDER", "ollama"),
        "model": model or None,
        "installed_model": installed_model,
        "tts_runtime_installed": voice_status["tts_runtime_installed"],
        "tts_model": "pnnbao-ump/VieNeu-TTS-v3-Turbo (CPU/ONNX)",
        "voice_reference_ready": voice_status["reference_ready"],
        "renderer": "ffmpeg",
    }


def _review_asset_rights(db_path: Path, asset_id: str) -> dict[str, str]:
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT rights_state, metadata_json FROM assets WHERE asset_id = ?",
            (asset_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Asset was not found in the library.")
        if row["rights_state"] == "verified":
            return {"status": "ALREADY_VERIFIED", "asset_id": asset_id}

        metadata = json.loads(row["metadata_json"] or "{}")
        if not isinstance(metadata, dict):
            metadata = {}
        reviewed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        metadata["rights_reviewed_by_user"] = True
        metadata["rights_reviewed_at"] = reviewed_at
        metadata["rights_review_source"] = "local_ui_confirmation"
        conn.execute(
            """
            UPDATE assets
            SET rights_state = 'verified', lifecycle_state = 'active',
                metadata_json = ?
            WHERE asset_id = ?
            """,
            (json.dumps(metadata, ensure_ascii=False, sort_keys=True), asset_id),
        )
        conn.commit()
        return {"status": "RIGHTS_VERIFIED", "asset_id": asset_id}
    finally:
        conn.close()


def _distribution_detail(root: Path, run_id: str) -> dict[str, Any]:
    """Routing plan + publish records + lifecycle for one run (read-only)."""
    run = _read_run(root, run_id)
    plan = read_plan(root, run_id)
    records: list[dict[str, Any]] = []
    records_path = root / "runtime/publish" / run_id / "publish-records.json"
    if records_path.is_file():
        try:
            loaded = json.loads(records_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                records = [r for r in loaded if isinstance(r, dict)]
        except (OSError, json.JSONDecodeError):
            records = []
    observations = [
        json.loads(line) for line in
        ((root / "runtime/measurement/observations.jsonl").read_text(encoding="utf-8").splitlines()
         if (root / "runtime/measurement/observations.jsonl").is_file() else [])
        if line.strip()
    ]
    payouts = [
        json.loads(line) for line in
        ((root / "runtime/measurement/payouts.jsonl").read_text(encoding="utf-8").splitlines()
         if (root / "runtime/measurement/payouts.jsonl").is_file() else [])
        if line.strip()
    ]
    run_obs = [o for o in observations if isinstance(o, dict) and o.get("run_id") == run_id]
    run_pay = [p for p in payouts if isinstance(p, dict) and p.get("run_id") == run_id]
    lifecycle = classify_lifecycle(run, plan, records, run_obs, run_pay)
    return {"run_id": run_id, "plan": plan, "records": records,
            "observations": run_obs, "payouts": run_pay, "lifecycle": lifecycle}


def _plan_distribution_for_run(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{12}", run_id):
        raise ValueError("Production run ID is invalid.")
    run = _read_run(root, run_id)
    raw_dests = payload.get("destinations", [{"platform": "local_file", "account_ref": "local"}])
    if not isinstance(raw_dests, list) or not raw_dests or len(raw_dests) > 4:
        raise ValueError("Provide 1-4 destinations.")
    destinations: dict[str, list[ChannelDestination]] = {}
    plan = plan_distribution(root, run, {})
    for item in raw_dests:
        if not isinstance(item, dict) or not str(item.get("platform", "")).strip():
            raise ValueError("Each destination needs a platform.")
        dest = ChannelDestination(
            platform=str(item["platform"]).strip(),
            account_ref=str(item.get("account_ref", "")).strip(),
            market=str(item.get("market", plan.get("market", "VN"))).strip() or "VN",
        )
        destinations.setdefault(plan["channel_id"], []).append(dest)
    plan = plan_distribution(root, run, destinations)
    return stage_plan(root, plan)


def _publish_distribution_for_run(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not re.fullmatch(r"[a-f0-9]{12}", run_id):
        raise ValueError("Production run ID is invalid.")
    run = _read_run(root, run_id)
    plan = read_plan(root, run_id)
    if plan is None:
        raise ValueError("Plan distribution first via /api/distribution/plan.")
    dry_run = payload.get("dry_run", False) is True
    return publish_plan(root, run, plan, registry=default_registry(), dry_run=dry_run)


def make_handler(db_path: Path) -> type[BaseHTTPRequestHandler]:
    class EngineUIHandler(BaseHTTPRequestHandler):
        server_version = "AutonomousContentEngineUI/0.1"

        def _send_json(
            self,
            payload: Any,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            body = json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/voice/status":
                self._send_json(voice_profile_status(db_path.parent.parent))
                return
            voice_match = re.fullmatch(r"/api/voice-preview/([a-f0-9]{12}-voice-preview\.wav)", path)
            if voice_match:
                voice_file = (db_path.parent.parent / "runtime/voice" / voice_match.group(1)).resolve()
                voice_root = (db_path.parent.parent / "runtime/voice").resolve()
                if voice_root not in voice_file.parents or not voice_file.is_file():
                    self._send_json({"error": "Voice preview not found."}, HTTPStatus.NOT_FOUND)
                    return
                body = voice_file.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            render_match = re.fullmatch(r"/api/render/([a-f0-9]{12})/(template-preview\.mp4|visual-benchmark-silent\.mp4|full-render\.mp4)", path)
            if render_match:
                run_id, filename = render_match.groups()
                video_file = (db_path.parent.parent / "runtime/renders" / run_id / filename).resolve()
                render_root = (db_path.parent.parent / "runtime/renders").resolve()
                if render_root not in video_file.parents or not video_file.is_file():
                    self._send_json({"error": "Rendered video not found."}, HTTPStatus.NOT_FOUND)
                    return
                size = video_file.stat().st_size
                range_header = self.headers.get("Range")
                start, end = 0, size - 1
                if range_header and re.fullmatch(r"bytes=\d*-\d*", range_header):
                    raw_start, raw_end = range_header.removeprefix("bytes=").split("-", 1)
                    if raw_start:
                        start = int(raw_start)
                    if raw_end:
                        end = min(end, int(raw_end))
                    if start > end or start >= size:
                        self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                        return
                    self.send_response(HTTPStatus.PARTIAL_CONTENT)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                else:
                    self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(end - start + 1))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with video_file.open("rb") as stream:
                    stream.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        block = stream.read(min(1024 * 1024, remaining))
                        if not block:
                            break
                        self.wfile.write(block)
                        remaining -= len(block)
                return
            asset_match = re.fullmatch(r"/api/assets/file/([A-Za-z0-9][A-Za-z0-9_-]{0,79})", path)
            if asset_match:
                try:
                    file_path, mime_type = _asset_file_info(
                        db_path.parent.parent, db_path, asset_match.group(1)
                    )
                except ValueError:
                    self._send_json({"error": "Library file not found."}, HTTPStatus.NOT_FOUND)
                    return
                body = file_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            report_match = re.fullmatch(r"/api/render/([a-f0-9]{12})/report", path)
            if report_match:
                report_path = db_path.parent.parent / "runtime/renders" / report_match.group(1) / "render-report.json"
                if not report_path.is_file():
                    self._send_json({"error": "Render report not found."}, HTTPStatus.NOT_FOUND)
                else:
                    self._send_json(json.loads(report_path.read_text(encoding="utf-8")))
                return
            if path == "/api/overview":
                try:
                    self._send_json(_overview(db_path))
                except Exception:
                    self._send_json(
                        {"error": "Could not read the Asset Library."},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                return

            if path == "/api/assets":
                try:
                    self._send_json({"assets": _assets(db_path)})
                except Exception:
                    self._send_json(
                        {"error": "Could not read the Asset Library."},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                return

            if path == "/api/runs":
                try:
                    self._send_json({"runs": _list_runs(db_path.parent.parent)})
                except Exception:
                    self._send_json(
                        {"error": "Could not read engine runs."},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                return

            run_detail_match = re.fullmatch(r"/api/runs/([a-f0-9]{12})", path)
            if run_detail_match:
                try:
                    self._send_json(_read_run(db_path.parent.parent, run_detail_match.group(1)))
                except ValueError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                except Exception:
                    self._send_json(
                        {"error": "Could not read the run."},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                return

            if path == "/api/stats":
                try:
                    self._send_json(_stats(db_path.parent.parent, db_path))
                except Exception:
                    self._send_json(
                        {"error": "Could not compute engine stats."},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                return

            if path == "/api/template-foundation":
                try:
                    self._send_json(_template_foundation(db_path))
                except Exception:
                    self._send_json(
                        {"error": "Could not read the Template Foundation package."},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                return

            if path == "/api/content/status":
                self._send_json(_content_status(db_path.parent.parent))
                return

            distribution_match = re.fullmatch(r"/api/distribution/([a-f0-9]{12})", path)
            if distribution_match:
                try:
                    self._send_json(_distribution_detail(
                        db_path.parent.parent, distribution_match.group(1)))
                except ValueError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                except Exception:
                    self._send_json(
                        {"error": "Could not read the distribution plan."},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                return

            if path == "/api/measurement/summary":
                try:
                    root = db_path.parent.parent
                    self._send_json({
                        "by_run": summarize_by_run(root),
                        "by_channel": summarize_by_channel(root),
                    })
                except Exception:
                    self._send_json(
                        {"error": "Could not compute measurement summary."},
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                    )
                return

            template_file = TEMPLATE_FILES.get(path)
            if template_file:
                template_id = (
                    LONG_TEMPLATE_ID
                    if path == "/template-foundation/previews/landscape-composite.png"
                    or path.startswith("/template-foundation/previews/long-")
                    else TEMPLATE_ID
                )
                package = resolve_template(
                    db_path.parent.parent,
                    template_id,
                    allow_draft=True,
                )
                relative_path, content_type = template_file
                resource_path = (package.root / relative_path).resolve()
                if package.root not in resource_path.parents:
                    self._send_json({"error": "Not found."}, HTTPStatus.NOT_FOUND)
                    return
                body = resource_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(body)
                return

            static_file = STATIC_FILES.get(path)
            if static_file is None:
                self._send_json(
                    {"error": "Not found."},
                    HTTPStatus.NOT_FOUND,
                )
                return

            filename, content_type = static_file
            body = (STATIC_ROOT / filename).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/voice/profile":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > 50 * 1024 * 1024:
                        raise ValueError("The recording is empty or exceeds the 50 MB limit.")
                    suffix = self.headers.get("X-Voice-Suffix", "").lower()
                    result = save_voice_reference(
                        db_path.parent.parent,
                        f"voice-reference{suffix}",
                        self.headers.get_content_type() if hasattr(self.headers, "get_content_type") else self.headers.get("Content-Type", ""),
                        self.rfile.read(length),
                    )
                    self._send_json(result, HTTPStatus.CREATED)
                except ValueError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                except Exception:
                    self._send_json({"error": "Could not store the voice reference locally."}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            if path == "/api/voice/preview":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length <= 0 or length > MAX_REQUEST_BYTES:
                        raise ValueError("Request body size is invalid.")
                    payload = json.loads(self.rfile.read(length))
                    if not isinstance(payload, dict):
                        raise ValueError("Request must be a JSON object.")
                    result = synthesize_voice_preview(db_path.parent.parent, str(payload.get("run_id", "")))
                    self._send_json(result)
                except (json.JSONDecodeError, TypeError, ValueError) as error:
                    self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                except RuntimeError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.SERVICE_UNAVAILABLE)
                except Exception:
                    self._send_json({"error": "The local voice preview could not be generated."}, HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            if path not in {
                "/api/resource-evaluations",
                "/api/discovery-search",
                "/api/assets/approve-candidate",
                "/api/assets/review-rights",
                "/api/content/agent-runs",
                "/api/content/attach-media",
                "/api/content/render-visual-benchmark",
                "/api/content/script-review",
                "/api/content/voice-review",
                "/api/content/render-preview",
                "/api/content/render-full",
                "/api/distribution/plan",
                "/api/distribution/publish",
                "/api/measurement/observations",
                "/api/measurement/payouts",
            }:
                self._send_json(
                    {"error": "Not found."},
                    HTTPStatus.NOT_FOUND,
                )
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_REQUEST_BYTES:
                    raise ValueError("Request body size is invalid.")

                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Request must be a JSON object.")

                if path == "/api/discovery-search":
                    resource_type = str(payload.get("resource_type", "image")).strip().lower()
                    if resource_type not in {"image", "video"}:
                        raise ValueError("Discovery supports image and video requests.")
                    sort = str(payload.get("sort", "relevance")).strip().lower()
                    if sort not in {"relevance", "newest"}:
                        raise ValueError("Sort must be relevance or newest.")
                    candidates, statuses = search_candidates(
                        str(payload.get("query", "")),
                        resource_type=resource_type,
                        limit=int(payload.get("limit", 24)),
                        api_keys=_read_api_keys(db_path.parent.parent),
                        sort=sort,
                    )
                    ready = sorted({item["label"] for item in statuses if item["state"] == "ready"})
                    identity = None
                    entity_id = str(payload.get("entity_id", "")).strip()
                    if entity_id:
                        candidates, identity = apply_identity_filter(
                            candidates, entity_id, db_path
                        )
                    self._send_json(
                        {
                            "provider": " + ".join(ready) if ready else "No providers available",
                            "provider_status": statuses,
                            "identity": identity,
                            "candidates": [asdict(item) for item in candidates],
                        }
                    )
                    return

                if path == "/api/content/agent-runs":
                    result = run_content_agent(
                        db_path.parent.parent,
                        db_path,
                        str(payload.get("topic", "")),
                        str(payload.get("story_form", "")),
                        str(payload.get("evidence", "")),
                        str(payload.get("content_type", "short")),
                        str(payload.get("colorway", "match-night")),
                    )
                    self._send_json(result, HTTPStatus.CREATED)
                    return

                if path == "/api/content/script-review":
                    self._send_json(_approve_script(db_path.parent.parent, payload))
                    return

                if path == "/api/content/voice-review":
                    self._send_json(_approve_voice_preview(db_path.parent.parent, payload))
                    return

                if path == "/api/content/attach-media":
                    self._send_json(_attach_segment_media(db_path.parent.parent, db_path, payload))
                    return

                if path == "/api/distribution/plan":
                    self._send_json(_plan_distribution_for_run(db_path.parent.parent, payload))
                    return

                if path == "/api/distribution/publish":
                    self._send_json(_publish_distribution_for_run(db_path.parent.parent, payload))
                    return

                if path == "/api/measurement/observations":
                    self._send_json(record_observation(
                        db_path.parent.parent,
                        run_id=str(payload.get("run_id", "")),
                        remote_id=payload.get("remote_id"),
                        channel_id=str(payload.get("channel_id", "")),
                        platform=str(payload.get("platform", "")),
                        day=str(payload.get("day", "")),
                        views=int(payload.get("views", 0) or 0),
                        likes=int(payload.get("likes", 0) or 0),
                        comments=int(payload.get("comments", 0) or 0),
                        shares=int(payload.get("shares", 0) or 0),
                        watch_hours=float(payload.get("watch_hours", 0.0) or 0.0),
                        ctr=float(payload.get("ctr", 0.0) or 0.0),
                        conversions=int(payload.get("conversions", 0) or 0),
                        earnings_estimated_usd=float(payload.get("earnings_estimated_usd", 0.0) or 0.0),
                        source=str(payload.get("source", "ui_entry")),
                    ), HTTPStatus.CREATED)
                    return

                if path == "/api/measurement/payouts":
                    self._send_json(record_payout(
                        db_path.parent.parent,
                        run_id=payload.get("run_id"),
                        channel_id=str(payload.get("channel_id", "")),
                        amount_usd=float(payload.get("amount_usd", 0.0) or 0.0),
                        kind=str(payload.get("kind", "platform_payout")),
                        verified_cash_received=payload.get("verified_cash_received") is True,
                        method=str(payload.get("method", "")),
                        note=str(payload.get("note", "")),
                    ), HTTPStatus.CREATED)
                    return

                if path == "/api/content/render-preview":
                    self._send_json(render_template_preview(db_path.parent.parent, str(payload.get("run_id", ""))))
                    return

                if path == "/api/content/render-visual-benchmark":
                    self._send_json(render_visual_only_run(db_path.parent.parent, str(payload.get("run_id", ""))))
                    return

                if path == "/api/content/render-full":
                    self._send_json(render_full_run(db_path.parent.parent, str(payload.get("run_id", ""))))
                    return

                if path == "/api/assets/approve-candidate":
                    requirement_data = payload.get("requirement")
                    if not isinstance(requirement_data, dict):
                        raise ValueError("A resource requirement is required.")
                    rights_reviewed = payload.get("rights_reviewed")
                    if not isinstance(rights_reviewed, bool):
                        raise ValueError("Rights review choice is required.")
                    result = save_commons_candidate(
                        db_path.parent.parent,
                        str(payload.get("candidate_id", "")),
                        ResourceRequirement(**requirement_data),
                        rights_reviewed=rights_reviewed,
                        api_keys=_read_api_keys(db_path.parent.parent),
                    )
                    self._send_json(result, HTTPStatus.CREATED)
                    return

                if path == "/api/assets/review-rights":
                    asset_id = payload.get("asset_id")
                    if not isinstance(asset_id, str) or not asset_id:
                        raise ValueError("Asset ID is required.")
                    result = _review_asset_rights(db_path, asset_id)
                    self._send_json(result)
                    return

                requirement = ResourceRequirement(**payload)
                conn = connect(db_path)
                try:
                    result = evaluate_library_requirement(conn, requirement)
                finally:
                    conn.close()
                self._send_json(asdict(result))
            except (json.JSONDecodeError, TypeError, ValueError) as error:
                self._send_json(
                    {"error": str(error)},
                    HTTPStatus.BAD_REQUEST,
                )
            except DiscoveryError as error:
                self._send_json(
                    {"error": str(error)},
                    HTTPStatus.BAD_GATEWAY,
                )
            except RuntimeError as error:
                self._send_json({"error": str(error)}, HTTPStatus.SERVICE_UNAVAILABLE)
            except OSError as error:
                self._send_json({"error": f"Local render I/O failed: {error}"}, HTTPStatus.SERVICE_UNAVAILABLE)
            except Exception:
                self._send_json(
                    {"error": "Could not evaluate this resource request."},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

        def log_message(self, format: str, *args: Any) -> None:
            print(f"[engine-ui] {self.address_string()} {format % args}")

    return EngineUIHandler


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the local Autonomous Content Engine UI"
    )
    parser.add_argument("--root", default=".")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    project_root = Path(args.root).resolve()
    db_path = project_root / "runtime/engine.db"
    try:
        from apps.asset_library.entity_seed import seed_entity_catalog
        seed_entity_catalog(project_root)
    except Exception as error:
        print(f"[engine-ui] entity catalog seed skipped: {error}", flush=True)
    server = ThreadingHTTPServer(
        (args.host, args.port),
        make_handler(db_path),
    )
    print(
        f"Engine UI available at http://{args.host}:{args.port} "
        f"(project root: {project_root})",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Engine UI.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
