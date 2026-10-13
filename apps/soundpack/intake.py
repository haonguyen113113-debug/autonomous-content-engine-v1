"""Owner drop importer: audited files + register.csv into locked tracks.

Pixabay serves downloads behind a bot wall, so the engine never downloads
sounds itself. The owner auditions, downloads, and drops files plus a
register.csv into soundpacks/drop/; this importer validates every row
against the catalog's provenance checklist and installs only clean files:

* slot must exist in the pack manifest (beds, stingers, reserve)
* drop filename must match the manifest's locked filename for that slot
* file must decode (ffprobe) within the slot's duration cap and 20 MiB
* license allowlisted, commercial_ok=yes, page_url recorded
* Content-ID-risk rows rejected (HOLD policy from the owner catalog)
* BY licenses require credit_text (Pixabay Content License does not)

Unlisted files are ignored. Nothing is fetched from the network.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = {"slot", "file", "title", "creator", "license", "page_url", "commercial_ok"}
ALLOWED_LICENSES = {"CC0", "BY 4.0", "BY-SA 4.0", "Pixabay Content License"}
AUDIO_SUFFIXES = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}
MAX_BYTES = 20 * 1024 * 1024
DURATION_CAPS = {"bed": 600.0, "sting": 15.0, "reserve": 90.0}


def _probe_duration(path: Path) -> float:
    """Decode-checked duration in seconds; raises ValueError when unreadable."""
    try:
        process = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError(f"ffprobe is unavailable: {error}") from error
    if process.returncode:
        raise ValueError(f"File does not decode as audio: {path.name}.")
    try:
        duration = float((process.stdout or "").strip().splitlines()[0])
    except (ValueError, IndexError) as error:
        raise ValueError(f"File has no readable duration: {path.name}.") from error
    if duration <= 0:
        raise ValueError(f"File has no audio content: {path.name}.")
    return duration


def _slot_table(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    table: dict[str, dict[str, Any]] = {}
    for bed in manifest.get("beds", []) or []:
        if isinstance(bed, dict) and bed.get("bed_id"):
            table[str(bed["bed_id"])] = {"kind": "bed", "file": bed.get("file", "")}
    for sting in manifest.get("stingers", []) or []:
        if isinstance(sting, dict) and sting.get("sting_id"):
            table[str(sting["sting_id"])] = {"kind": "sting", "file": sting.get("file", "")}
    for item in manifest.get("reserve", []) or []:
        if isinstance(item, dict) and item.get("sting_id"):
            table[str(item["sting_id"])] = {"kind": "reserve", "file": item.get("file", "")}
    return table


def import_pack(root: Path | str, drop_dir: Path | str | None = None) -> dict[str, Any]:
    """Validate a drop folder and install clean files. Returns a report dict."""
    from apps.soundpack.pack import PACK_DIRNAME

    root = Path(root)
    pack_dir = Path(root) / "soundpacks" / PACK_DIRNAME
    manifest_path = pack_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Soundpack manifest is missing.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    slots = _slot_table(manifest)
    drop = Path(drop_dir) if drop_dir is not None else pack_dir / "drop"
    register = drop / "register.csv"
    if not register.is_file():
        raise ValueError("Drop folder needs register.csv next to the audio files.")
    report: dict[str, Any] = {"imported": [], "skipped": [], "failed": []}
    with register.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("register.csv has no rows.")
    missing = REQUIRED_COLUMNS - set(rows[0].keys() or [])
    if missing:
        raise ValueError(f"register.csv misses columns: {sorted(missing)}.")
    tracks_dir = pack_dir / "tracks"
    tracks_dir.mkdir(parents=True, exist_ok=True)
    for index, row in enumerate(rows, start=2):
        slot = (row.get("slot") or "").strip()
        problems: list[str] = []

        def fail(reason: str) -> None:
            report["failed"].append({"row": index, "slot": slot or "?", "reason": reason})

        if slot not in slots:
            fail(f"Unknown slot (locked slots: {', '.join(sorted(slots))}).")
            continue
        expected = Path(str(slots[slot]["file"])).name
        filename = (row.get("file") or "").strip()
        if Path(filename).name != expected:
            fail(f"File must be named exactly {expected} for slot {slot}.")
            continue
        source = drop / filename
        if not source.is_file():
            fail(f"File not found in drop folder: {filename}.")
            continue
        if source.suffix.lower() not in AUDIO_SUFFIXES:
            fail(f"Not an audio file: {filename}.")
            continue
        if source.stat().st_size > MAX_BYTES:
            fail(f"File exceeds 20 MiB: {filename}.")
            continue
        license_name = (row.get("license") or "").strip()
        if license_name not in ALLOWED_LICENSES:
            shown = license_name or "? (blank)"
            fail(f"License not allowlisted: {shown}.")
            continue
        if (row.get("commercial_ok") or "").strip().lower() not in {"yes", "true", "1"}:
            fail("commercial_ok must be yes for monetized use.")
            continue
        if (row.get("content_id_risk") or "").strip().lower() in {"yes", "true", "1", "hold"}:
            fail("Content-ID-risk HOLD rows are rejected by catalog policy.")
            continue
        if not (row.get("page_url") or "").strip().startswith("http"):
            fail("Asset page URL is required for provenance.")
            continue
        if license_name.startswith("BY") and not (row.get("credit_text") or "").strip():
            fail("BY licenses require credit_text for the video description.")
            continue
        try:
            duration = _probe_duration(source)
        except ValueError as error:
            fail(str(error))
            continue
        cap = DURATION_CAPS["bed" if slots[slot]["kind"] == "bed"
                            else "reserve" if slots[slot]["kind"] == "reserve" else "sting"]
        if duration > cap:
            fail(f"Duration {duration:.1f}s exceeds the {cap:.0f}s cap for this slot.")
            continue
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        target = tracks_dir / expected
        shutil.copyfile(source, target)
        sidecar = {
            "slot": slot,
            "catalog_id": (row.get("catalog_id") or "").strip() or None,
            "file": expected,
            "title": (row.get("title") or "").strip(),
            "creator": (row.get("creator") or "").strip(),
            "license": license_name,
            "license_url": (row.get("license_url") or "").strip() or None,
            "page_url": (row.get("page_url") or "").strip(),
            "source_url": (row.get("source_url") or "").strip() or None,
            "platforms": (row.get("platforms") or "").strip() or "YouTube (verify per platform)",
            "credit_text": (row.get("credit_text") or "").strip() or None,
            "commercial_use": "allowed (%s, owner-verified)" % license_name,
            "duration_s": round(duration, 2),
            "sha256": digest,
            "imported_at": date.today().isoformat(),
        }
        (tracks_dir / f"{slot}.json").write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        report["imported"].append({"row": index, "slot": slot, "file": expected,
                                  "duration_s": round(duration, 2),
                                  "activated": slots[slot]["kind"] != "reserve"})
    return report
