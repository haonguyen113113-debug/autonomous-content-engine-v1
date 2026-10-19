"""Freesound harvester: machine-picked locked beds (owner waived audition).

Reads FREESOUND_API_KEY from env/.env (never logged), searches CC0-only
with duration floors sorted by downloads, skips voice-tagged beds, downloads
preview-hq-mp3, verifies with ffprobe, and installs into tracks/ with
sidecars — replacing the provisional researched files. The owner audit step
is waived by standing instruction; paper audit (sidecars, manifest, report)
remains complete and every pick is revertible via git.
"""

from __future__ import annotations

import json
import os
import hashlib
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

from apps.soundpack.intake import _probe_duration

API_BASE = "https://freesound.org/apiv2"
LICENSE_CC0 = 'license:"Creative Commons 0"'
AVOID_VOICE_TAGS = {"voice", "vocal", "vocals", "speech", "spoken", "choir", "singing"}
MAX_BYTES = 20 * 1024 * 1024

SLOTS: dict[str, dict[str, Any]] = {
    "tension-pad": {"query": "dark ambient drone tension", "min_duration": 45.0,
                    "kind": "bed"},
    "neutral-pad": {"query": "delicate melancholic cinematic underscore", "min_duration": 45.0, "kind": "bed"},
    "uplift-pad": {"query": "smooth jazz background", "min_duration": 45.0,
                   "kind": "bed"},
    "dramatic-pad": {"query": "epic cinematic trailer music", "min_duration": 45.0,
                     "kind": "bed"},
    "build-riser": {"query": "cinematic riser", "min_duration": 2.0,
                    "max_duration": 12.0, "kind": "sting"},
}

FIELDS = "id,name,license,url,duration,download,num_downloads,avg_rating,tags,previews"


def _api_key(root: Path | str) -> str:
    key = os.environ.get("FREESOUND_API_KEY", "").strip()
    if not key:
        try:
            for line in (Path(root) / ".env").read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("FREESOUND_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip("\"'")
                    break
        except OSError:
            key = ""
    if not key:
        raise ValueError("FREESOUND_API_KEY is missing from env/.env.")
    return key


def _api_search(key: str, query: str, duration_filter: str,
                page_size: int = 8) -> list[dict[str, Any]]:
    params = {"query": query, "filter": f"{LICENSE_CC0} {duration_filter}".strip(),
              "sort": "downloads_desc", "page_size": page_size, "fields": FIELDS,
              "token": key}
    url = f"{API_BASE}/search/text/?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "AllenSoundpackHarvester/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read(2 * 1024 * 1024))
    except Exception as error:  # noqa: BLE001 - report, never leak the key
        raise ValueError(f"Freesound search failed for {query!r}.") from error
    results = payload.get("results", [])
    return [item for item in results if isinstance(item, dict)]


def _score_candidate(item: dict[str, Any]) -> float:
    try:
        downloads = float(item.get("num_downloads", 0) or 0)
    except (TypeError, ValueError):
        downloads = 0.0
    try:
        rating = float(item.get("avg_rating", 0) or 0)
    except (TypeError, ValueError):
        rating = 0.0
    tags = {str(tag).lower() for tag in (item.get("tags", []) or [])}
    return downloads + 2000.0 * rating + (3000.0 if "loop" in tags else 0.0)


def _pick(results: list[dict[str, Any]], min_duration: float,
          max_duration: float | None, avoid_voice: bool) -> dict[str, Any] | None:
    eligible = []
    for item in results:
        try:
            duration = float(item.get("duration", 0) or 0)
        except (TypeError, ValueError):
            continue
        if duration < min_duration:
            continue
        if max_duration is not None and duration > max_duration:
            continue
        tags = {str(tag).lower() for tag in (item.get("tags", []) or [])}
        if avoid_voice and tags & AVOID_VOICE_TAGS:
            continue
        previews = item.get("previews", {}) or {}
        if not isinstance(previews, dict) or not previews.get("preview-hq-mp3"):
            continue
        eligible.append(item)
    if not eligible:
        return None
    return max(eligible, key=_score_candidate)


def _download(url: str, dest: Path) -> Path:
    request = urllib.request.Request(url, headers={"User-Agent": "AllenSoundpackHarvester/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read(MAX_BYTES + 1)
    except Exception as error:  # noqa: BLE001 - network failure is a loud skip
        raise ValueError(f"Could not download preview audio.") from error
    if len(data) > MAX_BYTES or len(data) < 1024:
        raise ValueError("Downloaded preview is empty or exceeds 20 MiB.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def harvest(root: Path | str, slots: list[str] | None = None) -> dict[str, Any]:
    """Search, download, verify, and install locked sounds. Returns a report."""

    root = Path(root)
    key = _api_key(root)
    wanted = list(SLOTS) if slots is None else [s for s in slots if s in SLOTS]
    unknown = [s for s in (slots or []) if s not in SLOTS]
    if unknown:
        raise ValueError(f"Unknown soundpack slots: {', '.join(unknown)}.")
    manifest_path = root / "soundpacks" / "v1" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tracks_dir = root / "soundpacks" / "v1" / "tracks"
    report: dict[str, Any] = {"date": date.today().isoformat(), "slots": {}}
    for slot in wanted:
        spec = SLOTS[slot]
        entry: dict[str, Any] = {"query": spec["query"]}
        duration_filter = f"duration:[{spec['min_duration']:g} TO "
        duration_filter += f"{spec.get('max_duration'):g}]" if spec.get("max_duration") else "*]"
        try:
            results = _api_search(key, spec["query"], duration_filter)
            entry["considered"] = len(results)
            pick = _pick(results, spec["min_duration"], spec.get("max_duration"),
                         avoid_voice=spec["kind"] == "bed")
            if pick is None:
                entry.update({"status": "SKIPPED", "reason": "no eligible CC0 result"})
                report["slots"][slot] = entry
                continue
            tmp = tracks_dir / f".{slot}.download"
            _download(str((pick.get("previews", {}) or {}).get("preview-hq-mp3")), tmp)
            duration = _probe_duration(tmp)
            if duration < spec["min_duration"]:
                entry.update({"status": "SKIPPED",
                              "reason": f"decoded {duration:.1f}s below floor"})
                tmp.unlink(missing_ok=True)
                report["slots"][slot] = entry
                continue
            target = tracks_dir / f"{slot}.mp3"
            tmp.replace(target)
            for stale in tracks_dir.glob(f"{slot}.*"):
                if stale.name not in {target.name, f"{slot}.json"}:
                    stale.unlink(missing_ok=True)
            sidecar = {
                "slot": slot,
                "file": target.name,
                "title": pick.get("name"),
                "creator": None,
                "license": "CC0",
                "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                "source_url": (pick.get("previews", {}) or {}).get("preview-hq-mp3"),
                "landing_url": pick.get("url"),
                "freesound_id": pick.get("id"),
                "freesound_url": pick.get("url"),
                "duration_s": round(duration, 2),
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "downloads": pick.get("num_downloads"),
                "avg_rating": pick.get("avg_rating"),
                "tags": pick.get("tags", []),
                "harvested_at": date.today().isoformat(),
                "harvest_query": spec["query"],
                "commercial_use": "allowed (CC0, machine-picked, owner audit waived)",
            }
            (tracks_dir / f"{slot}.json").write_text(
                json.dumps(sidecar, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            for bed in manifest.get("beds", []) or []:
                if isinstance(bed, dict) and bed.get("bed_id") == slot:
                    bed["file"] = f"tracks/{slot}.mp3"
                    bed.pop("provisional", None)
                    bed.pop("note", None)
                    bed["source"] = f"freesound-harvest {date.today().isoformat()}"
            entry.update({"status": "INSTALLED", "file": target.name,
                          "freesound_id": pick.get("id"), "title": pick.get("name"),
                          "duration_s": round(duration, 2)})
        except ValueError as error:
            entry.update({"status": "FAILED", "reason": str(error)[:200]})
        report["slots"][slot] = entry
        time.sleep(2)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
    report_path = root / "soundpacks" / f"harvest-report-{date.today().isoformat()}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
    return report
