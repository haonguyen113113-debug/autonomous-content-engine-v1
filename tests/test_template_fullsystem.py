"""Template v5.0.0 full system: opening ident, subtitles, loop-callback ending."""

from pathlib import Path

from template_foundation import resolve_template

ROOT = Path(__file__).resolve().parent.parent


def test_full_system_resolves_pinned():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                             version="5.0.0", allow_draft=True)
    assert short.manifest["version"] == "5.0.0"
    assert "ident" in short.timeline.get("opening", "").lower()
    assert short.timeline["motion"]["scene_enter"].startswith("slide-in")


def test_sandem_stays_pinned():
    package = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                               version="4.0.0", allow_draft=True)
    assert package.manifest["version"] == "4.0.0"


def test_renderer_writes_ident_and_takeaway():
    source = (ROOT / "apps/video_renderer.py").read_text(encoding="utf-8")
    assert "ident_end" in source
    assert "endcard-takeaway.txt" in source
    assert "0.9.0" in source or "ace-ffmpeg-0.9.0" in source
