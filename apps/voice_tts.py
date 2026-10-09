from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import unicodedata
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


VOICE_DIR = Path("runtime/voice")
ALLOWED_SUFFIXES = {".wav", ".mp3", ".flac"}
MAX_REFERENCE_BYTES = 50 * 1024 * 1024


def _runtime_python(root: Path) -> Path | None:
    local = root / "runtime/tts-venv/Scripts/python.exe"
    if local.is_file():
        return local
    posix = root / "runtime/tts-venv/bin/python"
    if posix.is_file():
        return posix
    if importlib.util.find_spec("vieneu") is not None:
        return Path(sys.executable)
    return None


def voice_profile_status(root: Path) -> dict[str, Any]:
    profile_file = root / VOICE_DIR / "profile.json"
    profile: dict[str, Any] = {}
    if profile_file.exists():
        try:
            profile = json.loads(profile_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            profile = {}
    return {
        "reference_ready": bool(profile.get("reference_file")),
        "reference_name": profile.get("reference_name"),
        "reference_size_bytes": profile.get("size_bytes"),
        "tts_runtime_installed": _runtime_python(root) is not None,
        "tts_model": "pnnbao-ump/VieNeu-TTS-v3-Turbo (CPU/ONNX)",
        "processing": "local",
    }


def save_voice_reference(root: Path, filename: str, content_type: str, data: bytes) -> dict[str, Any]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Choose a WAV, MP3, or FLAC voice recording.")
    if not data or len(data) > MAX_REFERENCE_BYTES:
        raise ValueError("The recording is empty or exceeds the 50 MB limit.")
    if not (content_type.startswith("audio/") or content_type == "application/octet-stream"):
        raise ValueError("The uploaded file must be an audio recording.")

    voice_dir = root / VOICE_DIR
    voice_dir.mkdir(parents=True, exist_ok=True)
    reference_path = voice_dir / f"allen-reference{suffix}"
    reference_path.write_bytes(data)
    profile = {
        "reference_file": reference_path.name,
        "reference_name": "Allen voice reference",
        "content_type": content_type,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "stored_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "processing": "local_only",
    }
    (voice_dir / "profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return voice_profile_status(root)


def _clean_for_tts(text: str) -> str:
    """Make narration safe for the local TTS stack on any OS locale.

    A single stray byte (e.g. 0x81 inside a UTF-8 sequence decoded as
    cp1252) once produced a lone surrogate that crashed the Rust text
    normalizer, so belt (UTF-8 pipes) and suspenders (sanitize) both apply.
    """
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\ud800-\udfff]", "", text)
    return "".join(ch for ch in text if ch == "\n" or ch == "\t" or not unicodedata.category(ch).startswith("C"))


def _local_value(root: Path, key: str) -> str | None:
    """Read one machine-local setting from .env without touching os.environ."""
    env_file = root / ".env"
    if not env_file.exists():
        return None
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip().strip("\"'")
    return None


def synthesize_voice_preview(root: Path, run_id: str) -> dict[str, Any]:
    if not run_id.isalnum() or len(run_id) != 12:
        raise ValueError("Production run ID is invalid.")
    run_path = root / "runtime/runs" / f"{run_id}.json"
    if not run_path.is_file():
        raise ValueError("Production run was not found.")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    if not run.get("script_owner_approved"):
        raise ValueError("Approve the reviewed script before generating its voice.")
    segments = run.get("draft", {}).get("segments", [])
    text = "\n\n".join(
        item.get("narration", "") for item in segments if isinstance(item, dict)
    )
    if "[CẦN NGUỒN]" in text or "[KẾT LUẬN CỦA ALLEN]" in text:
        raise ValueError("Complete the research placeholders and edit the conclusion before TTS.")
    text = _clean_for_tts(unicodedata.normalize("NFC", text).strip())
    if len(text) < 12 or len(text) > 24000:
        raise ValueError("The voice preview needs 12–24,000 characters of reviewed script.")
    profile_status = voice_profile_status(root)
    if not profile_status["reference_ready"]:
        raise ValueError("Import your local voice reference before generating TTS.")
    runtime_python = _runtime_python(root)
    if runtime_python is None:
        raise RuntimeError("VieNeu-TTS is not installed. Install the local vieneu runtime first.")

    profile = json.loads((root / VOICE_DIR / "profile.json").read_text(encoding="utf-8"))
    reference = root / VOICE_DIR / profile["reference_file"]
    output_dir = root / VOICE_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    output_name = f"{run_id}-voice-preview.wav"
    worker = root / "apps/tts_preview_worker.py"
    child_env = dict(os.environ)
    child_env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    child_env["HF_HOME"] = str(root / "runtime/model-cache")
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    for key in ("TTS_SILENCE_P",):
        value = _local_value(root, key)
        if value is not None:
            child_env[key] = value
    process = subprocess.run(
        [str(runtime_python), str(worker), str(reference), str(output_dir / output_name)],
        input=text,
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        timeout=3600,
        cwd=root,
        env=child_env,
    )
    if process.returncode != 0:
        detail = (process.stderr or process.stdout or "Unknown local TTS error.").strip()
        raise RuntimeError(detail[-1200:])
    run["voice_preview"] = {
        "path": output_name,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "engine": profile_status["tts_model"],
        "local_only": True,
    }
    run["status"] = "WAITING_FOR_VOICE_AUDIT"
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"audio_url": f"/api/voice-preview/{output_name}", "engine": profile_status["tts_model"]}
