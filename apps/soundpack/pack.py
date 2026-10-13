"""Locked soundpack: fixed sounds for fixed stories (no discovery).

The pack (soundpacks/v1/) works like a template pack: a versioned manifest
maps each story form to one bed, stingers sit at fixed timeline slots, and
runs pin the pack version. The engine never searches for music; the owner
curates files once with recorded licenses. Missing pack, unknown override,
or missing file degrades to voice-only rendering with a report note — music
must never block a video.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PACK_VERSION = "1.0.0"
PACK_DIRNAME = "v1"


def _env_flag(root: Path | str, key: str, default_on: bool = True) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        try:
            for line in (Path(root) / ".env").read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(key + "="):
                    raw = line.split("=", 1)[1].strip().strip("\"'")
                    break
        except OSError:
            raw = None
    if raw is None or not str(raw).strip():
        return default_on
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def sound_enabled(root: Path | str) -> bool:
    """Global kill-switch; default on. SOUNDPACK_ENABLED=false renders voice-only."""
    return _env_flag(root, "SOUNDPACK_ENABLED", default_on=True)


def pack_root(root: Path | str) -> Path:
    return Path(root) / "soundpacks" / PACK_DIRNAME


def load_manifest(root: Path | str) -> dict[str, Any]:
    path = pack_root(root) / "manifest.json"
    if not path.is_file():
        raise ValueError("Soundpack v1 manifest is missing.")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not manifest.get("beds"):
        raise ValueError("Soundpack v1 manifest is corrupt.")
    return manifest


def bed_ids(root: Path | str) -> list[str]:
    try:
        manifest = load_manifest(root)
    except ValueError:
        return []
    return [str(bed.get("bed_id")) for bed in manifest.get("beds", [])
            if isinstance(bed, dict) and bed.get("bed_id")]


def resolve_sound(
    root: Path | str,
    story_form: str,
    content_type: str,
    override: str | None = None,
) -> dict[str, Any]:
    """Resolve the locked sound for a story. Raises ValueError when off/locked-out.

    override None → manifest mapping; "none" → disabled by owner;
    a bed_id → that bed (validated). Unknown bed_id raises ValueError so
    the summary fix endpoint can reject it before it reaches rendering.
    """
    del content_type
    manifest = load_manifest(root)
    if override is not None and str(override).strip().lower() == "none":
        return {"enabled": False, "reason": "disabled by owner override"}
    beds = {str(bed.get("bed_id")): bed for bed in manifest.get("beds", [])
            if isinstance(bed, dict)}
    if override is not None:
        bed_id = str(override).strip()
        if bed_id not in beds:
            raise ValueError(f"Unknown soundpack bed: {bed_id}. "
                             f"Choose one of {', '.join(sorted(beds))} or none.")
    else:
        mapping = manifest.get("mapping", {}) if isinstance(
            manifest.get("mapping"), dict) else {}
        bed_id = str(mapping.get(story_form, mapping.get("default", "")))
        if bed_id not in beds:
            raise ValueError(f"No locked bed for story form: {story_form}.")
    bed = beds[bed_id]
    bed_file = (pack_root(root) / str(bed.get("file", ""))).resolve()
    if pack_root(root).resolve() not in bed_file.parents or not bed_file.is_file():
        raise ValueError(f"Locked bed file is missing from the pack: {bed_id}.")
    return {
        "enabled": True,
        "pack_version": PACK_VERSION,
        "bed_id": bed_id,
        "bed_file": str(bed_file),
        "mood": bed.get("mood", ""),
        "license": bed.get("license", ""),
        "mix_volume": float(bed.get("mix_volume", 0.1) or 0.1),
        "stingers": [dict(s) for s in manifest.get("stingers", [])
                     if isinstance(s, dict)],
        "sidechain": dict(manifest.get("mix", {}).get("sidechain", {})),
    }


def plan_stingers(
    stingers: list[dict[str, Any]],
    chapter_starts: list[float],
    duration: float,
    tracks_dir: Path | str,
) -> list[dict[str, Any]]:
    """Place stingers on the timeline: hook@0, chapters, endcard-2s.

    Only existing files are planned. Chapter starts under 0.5s are skipped
    (the hook hit already owns the opening).
    """
    tracks_dir = Path(tracks_dir)
    pack_base = tracks_dir.parent.resolve()
    planned: list[dict[str, Any]] = []
    for sting in stingers:
        path = (tracks_dir / str(sting.get("file", "")).replace("tracks/", "")).resolve()
        base = (pack_base / "tracks").resolve()
        if base not in path.parents or not path.is_file():
            continue
        place = str(sting.get("place", ""))
        volume = float(sting.get("volume", sting.get("mix_volume", 0.5)) or 0.5)
        if place == "hook":
            planned.append({"sting_id": sting.get("sting_id"), "file": str(path),
                            "at": 0.0, "volume": volume})
        elif place == "chapter":
            for start in sorted(set(float(s) for s in chapter_starts)):
                if start >= 0.5 and start < max(1.0, duration - 1.0):
                    planned.append({"sting_id": sting.get("sting_id"), "file": str(path),
                                    "at": round(start, 3), "volume": volume})
        elif place == "endcard":
            at = max(0.0, duration + float(sting.get("at_seconds", -2.0) or -2.0))
            planned.append({"sting_id": sting.get("sting_id"), "file": str(path),
                            "at": round(at, 3), "volume": volume})
    return planned


def audio_filter(
    voice_index: int,
    bed_index: int,
    sting_indices: list[int],
    planned_stings: list[dict[str, Any]],
    duration: float,
    bed_volume: float,
    sidechain: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Build the voice-primary mix filter. Returns (filter, out_label).

    Bed loops under everything; stingers sit at fixed slots; the bed ducks
    under speech (template spec: music ducks under speech); the mix is
    loudness-normalized for Shorts. Pure string building — no I/O.
    """
    sidechain = sidechain or {}
    threshold = sidechain.get("threshold", 0.02)
    ratio = sidechain.get("ratio", 8)
    attack = sidechain.get("attack_ms", 20)
    release = sidechain.get("release_ms", 400)
    parts = [f"[{bed_index}:a]aresample=48000,volume={bed_volume},"
             f"atrim=0:{duration:.3f}[bed]"]
    mix_inputs = ["[bed]"]
    for position, (input_index, sting) in enumerate(zip(sting_indices, planned_stings)):
        label = f"st{position}"
        ms = int(round(float(sting.get("at", 0.0)) * 1000))
        parts.append(f"[{input_index}:a]aresample=48000,volume={float(sting.get('volume', 0.5))},"
                     f"adelay={ms}|{ms}[{label}]")
        mix_inputs.append(f"[{label}]")
    if len(mix_inputs) > 1:
        parts.append(f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:"
                     "duration=longest:dropout_transition=0[mx]")
        music = "[mx]"
    else:
        music = "[bed]"
    parts.append(f"[{voice_index}:a]aresample=48000,asplit=2[vox][voxsc]")
    parts.append(f"{music}[voxsc]sidechaincompress=threshold={threshold}:ratio={ratio}:"
                 f"attack={attack}:release={release}:makeup=1[duck]")
    parts.append("[vox][duck]amix=inputs=2:duration=first:dropout_transition=0,"
                 "loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    return ";".join(parts), "[aout]"
