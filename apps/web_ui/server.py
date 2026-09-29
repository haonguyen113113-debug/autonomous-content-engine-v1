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
    search_image_candidates,
)
from apps.asset_library.registry import connect
from apps.asset_library.resource_workflow import evaluate_library_requirement
from apps.voice_tts import save_voice_reference, synthesize_voice_preview, voice_profile_status
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
            if path == "/api/voice-preview/voice-preview.wav":
                voice_file = (db_path.parent.parent / "runtime/voice/voice-preview.wav").resolve()
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

            template_file = TEMPLATE_FILES.get(path)
            if template_file:
                package = resolve_template(
                    db_path.parent.parent,
                    TEMPLATE_ID,
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
                "/api/content/script-review",
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
                    candidates = search_image_candidates(
                        str(payload.get("query", "")),
                        limit=int(payload.get("limit", 24)),
                    )
                    self._send_json(
                        {
                            "provider": "Openverse + Wikimedia Commons",
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
                    )
                    self._send_json(result, HTTPStatus.CREATED)
                    return

                if path == "/api/content/script-review":
                    self._send_json(_approve_script(db_path.parent.parent, payload))
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
