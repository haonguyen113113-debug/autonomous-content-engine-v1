from __future__ import annotations

"""Local FFmpeg renderer for a template motion preview and reviewed production runs."""

import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone
import textwrap
from typing import Any

from template_foundation import resolve_template


def _ffmpeg(root: Path) -> str:
    configured = os.environ.get("FFMPEG_PATH")
    if not configured:
        env_file = root / ".env"
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8-sig").splitlines():
                key, separator, value = line.partition("=")
                if separator and key.strip() == "FFMPEG_PATH":
                    configured = value.strip().strip("\"'")
                    break
    found = configured or shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg or set FFMPEG_PATH.")
    if not shutil.which(found) and not Path(found).is_file():
        raise RuntimeError(f"FFmpeg executable does not exist: {found}")
    return found


def _ffprobe(ffmpeg: str) -> str:
    configured = os.environ.get("FFPROBE_PATH")
    found = configured or shutil.which("ffprobe")
    if not found:
        sibling = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        found = str(sibling) if sibling.is_file() else None
    if not found:
        raise RuntimeError("FFprobe was not found. Install it with FFmpeg or set FFPROBE_PATH.")
    resolved = shutil.which(found) or (found if Path(found).is_file() else None)
    if not resolved:
        raise RuntimeError(f"FFprobe executable does not exist: {found}")
    return resolved


def _safe_run_id(value: str) -> bool:
    return len(value) == 12 and all(ch in "0123456789abcdef" for ch in value)


def _write_text(path: Path, text: str) -> str:
    # FFmpeg reads UTF-8 text files directly; this also avoids filter escaping issues.
    path.write_text(text, encoding="utf-8")
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _render(
    root: Path,
    run: dict[str, Any],
    *,
    preview: bool,
    output_name: str,
) -> dict[str, Any]:
    ffmpeg = _ffmpeg(root)
    draft = run.get("draft", {})
    content_type = draft.get("content_type", "short")
    template_id = (
        "allen-knows-ball.longform-analyst"
        if content_type == "long"
        else "allen-knows-ball.shortform-analyst"
    )
    package = resolve_template(root, template_id, allow_draft=True)
    palette = package.design_tokens.get("palette", {})

    def color_token(name: str) -> str:
        raw = str(palette.get(name, "#101814")).lstrip("#")
        return "0x" + raw.upper()

    ink = color_token("ink")
    deep_pitch = color_token("deep_pitch")
    pitch_line = color_token("pitch_line")
    chalk = color_token("chalk")
    muted = color_token("muted")
    signal_lime = color_token("signal_lime")
    is_long = content_type == "long"
    output_profile = package.manifest.get("output", {})
    width = int(output_profile.get("width", 1920 if is_long else 1080))
    height = int(output_profile.get("height", 1080 if is_long else 1920))
    fps = int(output_profile.get("frame_rate", 30))
    title = str(draft.get("topic") or "Allen Knows Ball")
    if preview:
        duration = 18
        phase_ranges = [(0, 4), (4, 14), (14, 18)]
        phase_labels = ["OPENING", "TACTICAL READ", "ALLEN'S TAKE"]
        title_text = title[:150]
    else:
        duration = int(draft.get("duration_target_seconds", 0))
        if duration < (480 if is_long else 20) or duration > (1200 if is_long else 90):
            raise ValueError("The script duration is outside the selected template range.")
        segments = draft.get("segments", [])
        if not segments:
            raise ValueError("The reviewed script has no production segments.")
        phase_ranges = [
            (max(0, int(item.get("start_seconds", 0))), min(duration, int(item.get("end_seconds", 0))))
            for item in segments
        ]
        phase_labels = [str(item.get("chapter_id", item.get("id", "ANALYSIS"))).replace("_", " ").upper() for item in segments]
        title_text = title[:150]

    render_dir = root / "runtime/renders" / str(run["run_id"])
    render_dir.mkdir(parents=True, exist_ok=True)
    work_dir = render_dir / "work"
    work_dir.mkdir(exist_ok=True)
    output_path = render_dir / output_name
    font = package.root / "resources/fonts/BeVietnamPro-Bold.ttf"
    if not font.is_file():
        raise RuntimeError("The template's Vietnamese font file is missing.")
    latin_font = package.root / "resources/fonts/BarlowCondensed-Bold.ttf"
    if not latin_font.is_file():
        raise RuntimeError("The template's Latin display font file is missing.")
    font_path = str(font).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    latin_font_path = str(latin_font).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")

    # Fixed template language: pitch-board geometry, quiet wordmark, restrained lime accents.
    filters = [
        f"drawbox=x=iw*0.08:y=ih*0.13:w=iw*0.84:h=ih*0.72:color={pitch_line}@0.65:t=2",
        f"drawbox=x=iw*0.50:y=ih*0.13:w=0:h=ih*0.72:color={pitch_line}@0.55:t=2",
        f"drawbox=x=iw*0.08:y=ih*0.32:w=iw*0.84:h=ih*0.34:color={pitch_line}@0.40:t=2",
        f"drawbox=x=iw*0.28:y=ih*0.33:w=iw*0.44:h=ih*0.32:color={pitch_line}@0.45:t=2",
        f"drawbox=x=iw*0.40:y=ih*0.13:w=iw*0.20:h=ih*0.15:color={pitch_line}@0.45:t=2",
        f"drawbox=x=iw*0.40:y=ih*0.57:w=iw*0.20:h=ih*0.15:color={pitch_line}@0.45:t=2",
    ]
    label_path = _write_text(work_dir / "wordmark.txt", "ALLEN KNOWS BALL")
    title_wrap = 29 if is_long else 27
    wrapped_title = "\n".join(textwrap.wrap(title_text, width=title_wrap, break_long_words=False, break_on_hyphens=False))
    title_path = _write_text(work_dir / "title.txt", wrapped_title)
    filters.append(
        f"drawtext=fontfile='{latin_font_path}':textfile='{label_path}':fontcolor={signal_lime}:"
        f"fontsize=h*0.026:x=w*0.08:y=h*0.075:shadowcolor=black@0.6:shadowx=1:shadowy=2"
    )
    filters.append(
        f"drawtext=fontfile='{font_path}':textfile='{title_path}':fontcolor={chalk}:"
        f"fontsize=h*{0.050 if is_long else 0.032:.3f}:line_spacing=8:text_align=center:x=(w-text_w)/2:y=h*0.25:"
        f"box=1:boxcolor=0x101814@0.78:boxborderw=30:shadowcolor=black@0.6:shadowx=2:shadowy=3"
    )
    for index, ((start, end), label) in enumerate(zip(phase_ranges, phase_labels)):
        if end <= start:
            continue
        start = min(max(0, start), duration - 1)
        end = min(max(start + 1, end), duration)
        phase_path = _write_text(work_dir / f"phase-{index}.txt", label[:100])
        filters.append(
            f"drawtext=fontfile='{latin_font_path}':textfile='{phase_path}':fontcolor={signal_lime}:"
            f"fontsize=h*0.024:x=(w-text_w)/2:y=h*0.80:"
            f"box=1:boxcolor=0x101814@0.86:boxborderw=16:enable='between(t,{start},{end})'"
        )
        if preview:
            # A quiet lime board accent gives the visual check one restrained motion cue.
            filters.append(
                f"drawbox=x=iw*0.28:y=ih*0.49:w=iw*0.44:h=4:color={signal_lime}@0.95:t=fill:"
                f"enable='between(t,{start},{min(end, start + 0.45)})'"
            )
    filters.append(
        f"drawtext=fontfile='{font_path}':text='BÓNG ĐÁ, NHÌN THÊM MỘT NHỊP':"
        f"fontcolor={muted}:fontsize=h*0.017:x=(w-text_w)/2:y=h*0.88"
    )
    filter_complex = ",".join(filters)
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c={deep_pitch}:s={width}x{height}:r={fps}:d={duration}",
    ]
    audio_path = None
    if not preview:
        voice_name = str(run.get("voice_preview", {}).get("path", ""))
        voice_root = (root / "runtime/voice").resolve()
        audio_path = (voice_root / voice_name).resolve()
        if audio_path.parent != voice_root or not audio_path.is_file():
            raise ValueError("Generate and audit the local voice preview before rendering the full run.")
        command += ["-i", str(audio_path)]
    command += ["-vf", filter_complex, "-t", str(duration), "-r", str(fps), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]
    if preview:
        command += ["-an"]
    else:
        command += ["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    command += ["-movflags", "+faststart", str(output_path)]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=7200)
    if result.returncode:
        raise RuntimeError((result.stderr or "FFmpeg render failed.")[-2500:])

    checks = [
        {"criterion": "Video file created and playable", "status": "PASS", "detail": "FFmpeg produced an H.264 MP4 and ffprobe confirms its stream metadata."},
        {"criterion": "Target aspect ratio", "status": "PASS", "detail": f"{width}×{height} ({'16:9' if is_long else '9:16'})."},
        {"criterion": "Vietnamese font and diacritics", "status": "PASS", "detail": "Template bundled Be Vietnam Pro Bold is used for Vietnamese text."},
        {"criterion": "Template palette and pitch board", "status": "PASS", "detail": "Deep-pitch background, lime accents, and authored pitch geometry are present."},
        {"criterion": "Opening / body / ending rhythm", "status": "PASS" if preview else "PARTIAL", "detail": "Preview presents the three template beats; full-run segment cards are timed from the reviewed script."},
        {"criterion": "Personal voice and speech pacing", "status": "NOT ASSESSED" if preview else "PARTIAL", "detail": "This is a silent visual preview." if preview else "Voice is muxed as one continuous narration track; phrase-level caption alignment and speech timing are not yet implemented."},
        {"criterion": "Approved real football media", "status": "NOT ASSESSED", "detail": "No approved campaign footage or images are inserted by this first renderer slice."},
        {"criterion": "Script-specific transitions and effects", "status": "PARTIAL", "detail": "Current renderer uses clean static compositions and restrained accents; timeline transition/effect execution remains to be implemented."},
    ]
    probe = _ffprobe(ffmpeg)
    probe_result = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration,size:stream=codec_name,width,height,codec_type", "-of", "json", str(output_path)],
        capture_output=True, text=True, timeout=30,
    )
    if probe_result.returncode:
        raise RuntimeError("FFprobe could not inspect the rendered MP4.")
    metadata = json.loads(probe_result.stdout)
    actual_duration = float(metadata.get("format", {}).get("duration", 0) or 0)
    duration_ok = abs(actual_duration - duration) <= max(1.0, duration * 0.01)
    checks.append({
        "criterion": "Output duration matches target",
        "status": "PASS" if duration_ok else "FAIL",
        "detail": f"Target {duration}s; rendered {actual_duration:.2f}s.",
    })
    video_streams = [item for item in metadata.get("streams", []) if item.get("codec_type") == "video"]
    audio_streams = [item for item in metadata.get("streams", []) if item.get("codec_type") == "audio"]
    audio_ok = preview or bool(audio_streams)
    checks.append({
        "criterion": "Expected audio stream",
        "status": "PASS" if audio_ok else "FAIL",
        "detail": "Silent preview is intentional." if preview else ("Narration audio stream is present." if audio_ok else "No audio stream was found."),
    })
    if not video_streams:
        raise RuntimeError("The rendered MP4 has no video stream.")
    report = {
        "run_id": run["run_id"],
        "rendered_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "renderer": "ace-ffmpeg-0.1.0",
        "template_id": template_id,
        "template_version": package.manifest["version"],
        "mode": "template_visual_preview" if preview else "full_script_render",
        "output": output_path.name,
        "quality_checks": checks,
        "ffprobe": metadata,
        "limitations": [
            "The output is a functional rendering proof, not a production-ready soccer video.",
            "No selected Asset Library media, host footage, motion graphics animation, or custom sound cue is included.",
            "Full-run narration is muxed as one continuous voice track; timing alignment is not yet tied to phrase-level scene boundaries.",
        ],
    }
    (render_dir / "render-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "video_url": f"/api/render/{run['run_id']}/{output_path.name}",
        "report": report,
        "rendered": True,
    }


def render_template_preview(root: Path, run_id: str) -> dict[str, Any]:
    if not _safe_run_id(run_id):
        raise ValueError("Production run ID is invalid.")
    path = root / "runtime/runs" / f"{run_id}.json"
    if not path.is_file():
        raise ValueError("Production run was not found.")
    run = json.loads(path.read_text(encoding="utf-8"))
    return _render(root, run, preview=True, output_name="template-preview.mp4")


def render_full_run(root: Path, run_id: str) -> dict[str, Any]:
    if not _safe_run_id(run_id):
        raise ValueError("Production run ID is invalid.")
    path = root / "runtime/runs" / f"{run_id}.json"
    if not path.is_file():
        raise ValueError("Production run was not found.")
    run = json.loads(path.read_text(encoding="utf-8"))
    if not run.get("script_owner_approved"):
        raise ValueError("Approve and verify the script before full rendering.")
    if not run.get("voice_preview_audited"):
        raise ValueError("Listen to and approve the generated voice preview before full rendering.")
    result = _render(root, run, preview=False, output_name="full-render.mp4")
    run["render"] = {
        "path": "full-render.mp4",
        "rendered_at": result["report"]["rendered_at"],
        "report": "render-report.json",
    }
    run["status"] = "WAITING_FOR_RENDER_AUDIT"
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
