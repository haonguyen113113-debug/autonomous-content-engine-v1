"""R4 final-gate driver: one fresh synthetic render + contact sheet + evidence.

Writes only under ``runtime/`` (run JSON, silent voice WAV, MP4, frames,
contact sheet, ``gate-evidence.json``). No code, template or contract file is
touched.

Shape of the gate
-----------------
Five synthetic beats, one per contract card under test::

    beat-hook        hook_card          C-11
    beat-stat        stat_leader        BP-16
    beat-reading     tactical_explainer C-12   (12.2.0)
    beat-source      source_card        C-09
    beat-conclusion  conclusion         C-13   (12.2.0)

The MP4 covers three of them (hook, reading, conclusion) at 7 s each: the
planner assigns roles positionally, so a three-beat run must start with the
hook and end with the takeaway. Why
not all five: the renderer's overlay graph holds several full-canvas
1080x1920 frames in flight, and this sandbox has ~4 GB RAM with no swap and
no root. At the default thread count even three beats are OOM-killed, so the
gate runs FFmpeg single-threaded (``ACE_RENDER_FILTER_THREADS=1``); five
beats exceed the budget even then. The two remaining beats are still frozen,
validated and painted with the real executor, and appear on the contact sheet
labelled as stills. This limitation is recorded in the evidence file instead
of being hidden.

Honest limits recorded in the evidence, never silently dropped:
- the voice is a silent WAV (no speech/pronunciation grading),
- there is no owner-approved real media (S4.1 cannot clear),
- no human has looked at the frames (S2/S5 stay NEEDS_REVIEW),
- two beats are stills, not encoded frames.

Usage::

    PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tools/r4_gate.py
    .venv/bin/python tools/r4_gate.py --no-render      # grade existing output
    .venv/bin/python tools/r4_gate.py --filter-threads 2
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_RUN_ID = "4a4f0c1d2e3b"
MP4_BEATS = ("beat-hook", "beat-reading", "beat-conclusion")
SECONDS_PER_MP4_BEAT = 7  # 3 * 7 = 21 s, inside the short-form template range

SEGMENTS = [
    {
        "id": "beat-hook",
        "visual_mode": "hook_card",
        "graphic_data": {"hook_text": "MỘT PHA BÓNG ĐỔI CẢ THẾ TRẬN"},
        "beat_intent": {
            "image_goal": "establish_moment",
            "focus_subject": "opening",
            "evidence_type": "none",
            "emphasis_level": "hero",
        },
    },
    {
        "id": "beat-stat",
        "visual_mode": "stat_leader",
        "graphic_data": {
            "stats": [
                {"label": "Chạm bóng trong vòng cấm", "value": "9"},
                {"label": "Tỉ lệ thắng bóng", "value": "68%"},
            ],
            "source": "Synthetic Sports Desk (fixture)",
            "date": "20/10/2026 (synthetic)",
        },
        "beat_intent": {
            "image_goal": "show_evidence",
            "focus_subject": "data",
            "evidence_type": "sourced_stat",
            "emphasis_level": "quiet",
        },
    },
    {
        "id": "beat-reading",
        "visual_mode": "tactical_explainer",
        "graphic_data": {
            "note": "Hai biên dâng cao, lộ khoảng trống sau lưng.",
            "source": "Synthetic Sports Desk (fixture)",
            "date": "20/10/2026 (synthetic)",
        },
        "beat_intent": {
            "image_goal": "explain_why",
            "focus_subject": "tactics",
            "evidence_type": "sourced_stat",
            "emphasis_level": "quiet",
        },
    },
    {
        "id": "beat-source",
        "visual_mode": "source_card",
        "graphic_data": {
            "claim": "Dữ liệu minh họa, không phải kết quả thật.",
            "source": "Synthetic Sports Desk (fixture)",
            "date": "20/10/2026 (synthetic)",
        },
        "beat_intent": {
            "image_goal": "attribute",
            "focus_subject": "source",
            "evidence_type": "citation",
            "emphasis_level": "quiet",
        },
    },
    {
        "id": "beat-conclusion",
        "visual_mode": "conclusion",
        "graphic_data": {
            "claim": "Đọc trận trước, đừng chỉ đọc tỉ số.",
            "source": "Synthetic Sports Desk (fixture)",
            "date": "20/10/2026 (synthetic)",
        },
        "beat_intent": {
            "image_goal": "land_takeaway",
            "focus_subject": "takeaway",
            "evidence_type": "none",
            "emphasis_level": "hero",
        },
    },
]


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_silent_wav(path: Path, seconds: float, rate: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * int(rate * seconds))


def build_run(run_id: str) -> dict:
    """The 3-beat run that is actually encoded to MP4."""
    specs = [s for s in SEGMENTS if s["id"] in MP4_BEATS]
    segments = []
    for index, spec in enumerate(specs):
        segment = dict(spec)
        segment["start_seconds"] = index * SECONDS_PER_MP4_BEAT
        segment["end_seconds"] = (index + 1) * SECONDS_PER_MP4_BEAT
        segments.append(segment)
    return {
        "run_id": run_id,
        "script_owner_approved": True,
        "voice_preview_audited": True,
        "voice_preview": {"path": "preview.wav"},
        "status": "READY_TO_RENDER",
        "draft": {
            "content_type": "short",
            "duration_target_seconds": len(segments) * SECONDS_PER_MP4_BEAT,
            "segments": segments,
            "script": " ".join(s["id"] for s in segments),
        },
    }


def _prepare(root: Path, run_id: str) -> dict:
    run = build_run(run_id)
    _write_silent_wav(
        root / "runtime" / "voice" / "preview.wav",
        int(run["draft"]["duration_target_seconds"]),
    )
    runs = root / "runtime" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{run_id}.json").write_text(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return run


def _five_beat_graphs() -> tuple[list[dict], dict]:
    """Freeze all five beats in memory (no runtime writes).

    Used for planner/QA evidence and for the two stills the MP4 cannot carry.
    """
    from apps.card_selector import select_cards
    from apps.scene_graph.builder import build_clip_graphs

    segments = {}
    for spec in SEGMENTS:
        segment = dict(spec)
        segment["start_seconds"] = 0.0
        segment["end_seconds"] = float(SECONDS_PER_MP4_BEAT)
        segments[spec["id"]] = segment
    plan = select_cards([dict(s) for s in segments.values()], content_type="short")
    for decision in plan["decisions"]:
        target = segments[decision["segment_id"]]
        target["visual_mode"] = decision["visual_mode"]
        target["graphic_data"] = decision["graphic_data"]
    graphs = build_clip_graphs(
        plan["decisions"], segments, "short"
    )
    return graphs, plan


def _frames(ffmpeg: str, mp4: Path, graphs: list[dict], out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    shots = []
    for index, graph in enumerate(graphs):
        timing = graph.get("timing", {})
        midpoint = (float(timing.get("start", 0)) + float(timing.get("end", 0))) / 2
        target = out_dir / f"frame-{index + 1:02d}-{graph.get('segment_id')}.png"
        subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
             "-ss", f"{midpoint:.3f}", "-i", str(mp4),
             "-frames:v", "1", str(target)],
            check=True, capture_output=True, text=True,
        )
        shots.append({
            "segment_id": graph.get("segment_id"),
            "mode": graph.get("mode"),
            "at_seconds": round(midpoint, 3),
            "frame": str(target.relative_to(ROOT)),
            "sha256": _sha(target),
            "source": "mp4 frame",
        })
    return shots


def _stills(graphs: list[dict], out_dir: Path) -> list[dict]:
    from apps.scene_graph.executor import write_scene_png

    out_dir.mkdir(parents=True, exist_ok=True)
    shots = []
    for graph in graphs:
        target = out_dir / f"still-{graph.get('segment_id')}.png"
        write_scene_png(graph, target)
        shots.append({
            "segment_id": graph.get("segment_id"),
            "mode": graph.get("mode"),
            "frame": str(target.relative_to(ROOT)),
            "sha256": _sha(target),
            "source": "executor still",
        })
    return shots


def _still_qa(graphs: list[dict]) -> dict[str, dict]:
    """Grade the still-only beats with the same scene QA the MP4 beats get."""
    from apps.measurement.render_qa import qa_scene
    from apps.scene_graph.executor import render_scene_graph_layers

    reports: dict[str, dict] = {}
    for graph in graphs:
        bg, text = render_scene_graph_layers(graph)
        rendered = bg.convert("RGBA")
        if text is not None:
            rendered.alpha_composite(text.convert("RGBA"))
        report = qa_scene(graph, rendered, bg_image=bg)
        reports[str(graph.get("segment_id"))] = {
            "verdict": report["verdict"],
            "failing": [
                {"criterion": c["criterion"], "status": c["status"],
                 "detail": c["detail"]}
                for c in report["checks"] if c["status"] != "PASS"
            ],
        }
    return reports


def _rgb_hex(value: str) -> tuple[int, int, int]:
    text = str(value or "#F2F6FF").lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    try:
        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (242, 246, 255)


def _luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        v = value / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(int(c)) for c in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    hi, lo = max(_luminance(a), _luminance(b)), min(_luminance(a), _luminance(b))
    return (hi + 0.05) / (lo + 0.05)


def _percentile(values: list[float], frac: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(frac * (len(ordered) - 1)))))
    return ordered[index]


def _is_glyph_halo(colour: tuple[int, int, int], fill: tuple[int, int, int],
                   fill_luminance: float) -> bool:
    """True when a pixel is the glyph's own bloom rather than the plate.

    A 26 px amber line carries a warm glow a few pixels wide. Counting that
    glow as "background" reported 2.1:1 for copy sitting on near-black (it
    measures 6–8:1 once the halo is excluded). Warm fills are excluded by hue
    family; light fills by luminance, where a same-brightness plate pixel
    cannot lower legibility anyway.
    """
    if fill[0] >= fill[1] >= fill[2] and fill[0] - fill[2] > 40:
        # Warm fill: only the same hue family is bloom. A bright cyan beam or
        # a white sparkle behind amber type is exactly what must be counted,
        # so luminance is NOT a halo signal for warm fills.
        r, g, b = colour
        return r >= g >= b and (r - b) > 40 and r / max(g, 1) < 1.9
    return _luminance(colour) > 0.6 * fill_luminance


def _frame_contrast(ffmpeg: str, mp4: Path, graphs: list[dict],
                    run_id: str) -> dict[str, dict]:
    """Grade text contrast on the ENCODED frame, not on a pre-zoom still.

    Plate and type share one zoompan chain, so they move together — but they
    move: even beats ease in to 1.025x, odd beats start at 1.025x and ease to
    1.0, punch beats ramp to 1.035x. At 1080x1920 that displaces the credit by
    up to ~31 px, so a still rendered at zoom 1.0 (and the frozen text mask)
    no longer covers the rows the encoded frame paints at t=7 s+. This probe
    therefore locates the glyph rows *in the frame* by counting fill-coloured
    runs inside the authored box, then measures what those rows sit on:

    * ``ratio_p95`` — contrast of the fill against the 95th-percentile
      background luminance between the glyphs (single sparkles cannot move a
      percentile; a plate beam crossing the credit still can);
    * ``bright_fraction`` — share of that background brighter than 60 % of the
      fill's luminance.

    A beat passes only when both hold at every sampled timestamp.
    """
    from PIL import Image

    from apps.measurement.render_qa import _layer_box, visible_text_layers

    reports: dict[str, dict] = {}
    for graph in graphs:
        timing = graph.get("timing", {})
        start, end = float(timing.get("start", 0)), float(timing.get("end", 0))
        rows: list[dict] = []
        for frac in (0.15, 0.45, 0.75, 0.92):
            at = start + (end - start) * frac
            shot = ROOT / "runtime" / "renders" / run_id / "work" / (
                f"probe-{graph.get('segment_id')}-{frac:.2f}.png")
            shot.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                 "-ss", f"{at:.3f}", "-i", str(mp4),
                 "-frames:v", "1", str(shot)],
                check=True, capture_output=True, text=True,
            )
            with Image.open(shot) as opened:
                frame = opened.convert("RGB")
            pixels = frame.load()
            width, height = frame.size
            worst = None
            for layer in visible_text_layers(graph) or []:
                x, y, w, h = _layer_box(layer)
                fill = _rgb_hex(str(layer.get("fill", "#F2F6FF")))
                fill_lum = _luminance(fill)
                x0 = max(0, min(width - 1, int(x)))
                x1 = max(x0 + 1, min(width, int(x + w)))
                y0 = max(0, min(height - 1, int(y)))
                y1 = max(y0 + 1, min(height, int(y + h)))

                def is_fill(colour: tuple[int, int, int]) -> bool:
                    return all(abs(colour[i] - fill[i]) <= 60 for i in range(3))

                glyph_rows = [
                    py for py in range(y0, y1)
                    if sum(1 for px in range(x0, x1, 3) if is_fill(pixels[px, py])) >= 8
                ]
                if len(glyph_rows) < 4:
                    continue
                top, bottom = min(glyph_rows), max(glyph_rows)
                luminaires: list[tuple[float, tuple[int, int, int]]] = []
                for py in range(top, bottom + 1):
                    for px in range(x0, x1, 2):
                        colour = tuple(pixels[px, py])
                        if is_fill(colour) or _is_glyph_halo(colour, fill, fill_lum):
                            continue
                        luminaires.append((_luminance(colour), colour))
                if len(luminaires) < 200:
                    continue
                luminaires.sort(key=lambda item: item[0])
                p95 = _percentile([item[0] for item in luminaires], 0.95)
                background = min(luminaires, key=lambda item: abs(item[0] - p95))[1]
                bright = sum(1 for lum, _ in luminaires
                             if lum > 0.6 * fill_lum) / len(luminaires)
                ratio = _ratio(fill, background)
                size = int(layer.get("fontSize", 0) or 0)
                floor = 4.5 if size >= 48 else 3.0
                passes = ratio >= floor and bright <= 0.02
                candidate = {
                    "layer": layer.get("id"),
                    "at_seconds": round(at, 3),
                    "ratio": round(ratio, 2),
                    "floor": floor,
                    "fill": str(layer.get("fill")),
                    "background_p95": "#%02X%02X%02X" % background,
                    "bright_fraction": round(bright, 4),
                    "passes": passes,
                    "glyph_rows": [top, bottom],
                }
                if worst is None or (ratio / floor) < (worst["ratio"] / worst["floor"]):
                    worst = candidate
            if worst is not None:
                rows.append(worst)
        if rows:
            low = min(rows, key=lambda r: r["ratio"] / r["floor"])
            reports[str(graph.get("segment_id"))] = {
                "worst": low,
                "passes": all(r["passes"] for r in rows),
                "samples": rows,
            }
    return reports


def _contact_sheet(shots: list[dict], out_path: Path, columns: int = 3) -> None:
    from PIL import Image, ImageDraw

    width, height, label = 420, 747, 52
    rows = (len(shots) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * width, rows * (height + label)), (12, 14, 20))
    draw = ImageDraw.Draw(sheet)
    for index, shot in enumerate(shots):
        image = Image.open(ROOT / shot["frame"]).convert("RGB").resize((width, height))
        column, row = index % columns, index // columns
        x, y = column * width, row * (height + label)
        sheet.paste(image, (x, y))
        timing = f"{shot['at_seconds']}s · " if "at_seconds" in shot else ""
        draw.text(
            (x + 10, y + height + 10),
            f"{index + 1}. {shot['segment_id']}",
            fill=(235, 238, 245),
        )
        draw.text(
            (x + 10, y + height + 30),
            f"{shot['mode']} · {timing}{shot['source']}",
            fill=(150, 160, 178),
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--no-render", action="store_true",
                        help="grade the existing run/MP4 instead of rendering again")
    parser.add_argument("--filter-threads", type=int, default=None,
                        help="cap FFmpeg filter/encoder threads (low-RAM machines)")
    args = parser.parse_args(argv)

    os.environ.setdefault("SOUNDPACK_ENABLED", "false")
    if args.filter_threads is not None:
        os.environ["ACE_RENDER_FILTER_THREADS"] = str(args.filter_threads)

    run_id = args.run_id
    if len(run_id) != 12 or any(ch not in "0123456789abcdef" for ch in run_id):
        parser.error("--run-id must be 12 lowercase hex characters")

    from apps.measurement.render_qa import check_card_contract, check_text_fit
    from apps.video_renderer import render_full_run

    run_path = ROOT / "runtime" / "runs" / f"{run_id}.json"
    if not args.no_render:
        _prepare(ROOT, run_id)
        result = render_full_run(ROOT, run_id)
        if not result.get("rendered"):
            raise SystemExit("render did not complete")
        run_path = ROOT / "runtime" / "runs" / f"{run_id}.json"

    if not run_path.is_file():
        parser.error(f"no run at {run_path}")

    run = json.loads(run_path.read_text(encoding="utf-8"))
    encoded = run.get("draft", {}).get("scene_graphs") or []
    render_dir = ROOT / "runtime" / "renders" / run_id
    mp4 = render_dir / "full-render.mp4"
    report = json.loads((render_dir / "render-report.json").read_text(encoding="utf-8"))

    # All five beats, frozen in memory: planner table + QA + the extra stills.
    all_graphs, plan = _five_beat_graphs()
    decisions = {d["segment_id"]: d for d in plan["decisions"]}

    beats = []
    for graph in all_graphs:
        decision = decisions.get(graph["segment_id"], {})
        beats.append({
            "segment_id": graph["segment_id"],
            "mode": decision.get("visual_mode"),
            "starter_id": decision.get("starter_id"),
            "execution": decision.get("card_execution"),
            "production_ready": decision.get("production_ready"),
            "encoded_to_mp4": graph["segment_id"] in MP4_BEATS,
            "warnings": decision.get("warnings", []),
        })

    graph_checks = []
    for graph in all_graphs:
        contract = check_card_contract(graph)
        fit = check_text_fit(graph)
        meta = graph.get("provenance", {}).get("card_contract") or {}
        children = ((graph.get("design") or {}).get("pages") or [{}])[0].get(
            "children", []
        )
        text_layers = [c for c in children
                       if isinstance(c, dict) and c.get("type") == "text"]
        visible = [c for c in text_layers if c.get("showInExport") is not False]
        hidden = [(c.get("custom") or {}).get("slot") for c in text_layers
                  if c.get("showInExport") is False]
        graph_checks.append({
            "segment_id": graph.get("segment_id"),
            "mode": graph.get("mode"),
            "card": meta.get("card_id"),
            "card_status": meta.get("status"),
            "graph_hash": graph.get("provenance", {}).get("graph_hash"),
            "card_contract": {"status": contract.get("status"),
                              "detail": contract.get("detail")},
            "text_fit": {"status": fit.get("status"), "detail": fit.get("detail")},
            # A slot hides itself when the reviewed data is missing. An empty
            # hidden slot is not a QA failure by itself, but a card that ships
            # half-empty must be visible in the evidence, not only in pixels.
            "text_slots_visible": [
                (c.get("custom") or {}).get("slot") for c in visible
            ],
            "text_slots_hidden": hidden,
        })

    still_dir = render_dir / "stills"
    still_graphs = [g for g in all_graphs if g["segment_id"] not in MP4_BEATS]
    stills = _stills(still_graphs, still_dir)
    still_qa = _still_qa(still_graphs)
    ffmpeg = os.environ.get("FFMPEG_PATH") or "ffmpeg"
    # The gate's own graphs carry beat-LOCAL timing (0..7 s); probing the MP4
    # with those would read the first beat three times. Use the encoded
    # run's timeline for the frame probe.
    encoded_timing = {
        str(g.get("segment_id")): g.get("timing", {}) for g in encoded
    }
    frame_graphs = []
    for graph in all_graphs:
        if graph["segment_id"] not in MP4_BEATS:
            continue
        probe = dict(graph)
        probe["timing"] = encoded_timing.get(graph["segment_id"], graph.get("timing", {}))
        frame_graphs.append(probe)
    frame_contrast = _frame_contrast(ffmpeg, mp4, frame_graphs, run_id=run_id)

    shots: list[dict] = []
    if not args.no_render or mp4.is_file():
        shots.extend(_frames(ffmpeg, mp4, encoded, render_dir / "frames"))
    shots.extend(stills)

    contact = render_dir / "contact-sheet.png"
    _contact_sheet(shots, contact)

    thread_cap = os.environ.get("ACE_RENDER_FILTER_THREADS", "").strip() or None
    encoder = report.get("encoder") or {}
    evidence = {
        "schema": "ace-r4-gate/1",
        "run_id": run_id,
        "template_version": report.get("template_version"),
        "renderer": report.get("renderer"),
        "scene_graph_default_path": True,
        "render_thread_cap": thread_cap,
        "video": {
            "path": str(mp4.relative_to(ROOT)) if mp4.is_file() else None,
            "sha256": _sha(mp4) if mp4.is_file() else None,
            "bytes": mp4.stat().st_size if mp4.is_file() else 0,
            "encoded_beats": list(MP4_BEATS),
            "ffprobe": report.get("ffprobe"),
            "bitrate": encoder.get("bitrate"),
        },
        "contact_sheet": {
            "path": str(contact.relative_to(ROOT)),
            "sha256": _sha(contact),
        },
        "planner": {
            "production_ready": plan["plan"].get("production_ready"),
            "non_ready_roles": plan["plan"].get("non_ready_roles"),
            "grammar_variety_ok": plan["plan"].get("grammar_variety_ok"),
            "rendered_review_pending": plan["plan"].get("rendered_review_pending"),
        },
        "beats": beats,
        "graphs": graph_checks,
        "frames": shots,
        "still_qa": still_qa,
        "frame_contrast": frame_contrast,
        "clip_qa": report.get("scene_graph_qa"),
        "quality_checks": report.get("quality_checks"),
        "limits": [
            "Voice is a synthetic silent WAV: no speech, pacing or pronunciation "
            "was graded (S1 speech checks are NOT assessed).",
            "No owner-approved real media: S4.1 media cannot clear; every beat is "
            "card-only or an explicit pending placeholder.",
            "No human has opened the contact sheet or the MP4 yet: aesthetic "
            "verdict (S2/S5) remains NEEDS_REVIEW, never PASS.",
            "The MP4 encodes three beats (hook/reading/conclusion); stat and "
            "source beats are executor stills only, because a five-beat overlay "
            "graph exceeds this sandbox's ~4 GB RAM with no swap.",
            "The gate runs FFmpeg with a thread cap on this box; frames are "
            "extracted from the encoded MP4, not from the design source.",
        ],
    }
    evidence_path = render_dir / "gate-evidence.json"
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"run_id            {run_id}")
    print(f"mp4               {mp4.relative_to(ROOT)}  ({mp4.stat().st_size} bytes)")
    print(f"contact sheet     {contact.relative_to(ROOT)}")
    print(f"evidence          {evidence_path.relative_to(ROOT)}")
    print(f"planner ready     {evidence['planner']['production_ready']} "
          f"{evidence['planner']['non_ready_roles']}")
    for check in graph_checks:
        encoded_mark = "MP4 " if check["segment_id"] in MP4_BEATS else "still"
        extra = ""
        if check["segment_id"] in still_qa:
            extra = f" scene_qa={still_qa[check['segment_id']]['verdict']}"
        if check["segment_id"] in frame_contrast:
            probe = frame_contrast[check["segment_id"]]["worst"]
            extra = (f" scene_qa={still_qa[check['segment_id']]['verdict']}"
                     if check["segment_id"] in still_qa else "")
            extra += f" frame_contrast={probe['ratio']:.2f}{'' if probe['ratio'] >= probe['floor'] else ' FAIL'}"
        print(f"  {encoded_mark} {check['segment_id']:<16} {str(check['mode']):<20} "
              f"card={check['card']} contract={check['card_contract']['status']} "
              f"text_fit={check['text_fit']['status']}{extra}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
