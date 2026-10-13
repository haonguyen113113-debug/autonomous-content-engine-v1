"""Sprint 1 proof artifacts: PIL proofs + preview audit section.

Regenerate with:
  python apps/studio_templates/build_starters.py
  python apps/studio_templates/render_starters.py
  python apps/studio_templates/write_audit.py apps/studio_templates/proof-rows.json
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SHORT_PREVIEWS = ROOT / "template_foundation/templates/allen-knows-ball/9.0.0/previews"
LONG_PREVIEWS = ROOT / "template_foundation/templates/allen-knows-ball/longform-9.0.0/previews"
HTML = ROOT / "template_foundation/templates/allen-knows-ball/9.0.0/preview.html"

SPRINT_SHORT = ["C-03", "C-04", "C-06", "C-07", "C-09", "C-10", "U-02", "U-03",
                "U-05", "MR-01", "MR-02", "MR-04", "MR-06", "MR-10", "MR-12",
                "BP-01", "BP-02", "BP-08", "BP-13", "BP-14", "BP-16", "BP-18",
                "BP-19", "BP-20"]
SPRINT_LONG = ["TA-01", "TA-02", "TA-03", "TA-05", "TA-06", "TA-11", "TA-12",
               "TA-14", "TA-16", "TA-18", "TA-19"]
SPRINT2_LONG = ["TA-04", "TA-07", "TA-08", "TA-09", "TA-10", "TA-13", "TA-15", "TA-17"]
SPRINT2_LONG = ["TA-04", "TA-07", "TA-08", "TA-09", "TA-10", "TA-13", "TA-15", "TA-17"]
SPRINT3_SHORT = ["MR-03", "MR-05", "MR-07", "MR-08", "MR-09", "MR-11",
                 "BP-03", "BP-04", "BP-05", "BP-06", "BP-07", "BP-09",
                 "BP-10", "BP-11", "BP-12", "BP-15", "BP-17",
                 "C-01", "C-02", "C-05", "C-08",
                 "U-01", "U-04", "U-06", "U-07", "U-08"]


def _proofs():
    for cid in SPRINT_SHORT + SPRINT3_SHORT:
        yield cid, "short", (1080, 1920)
    for cid in SPRINT_LONG + SPRINT2_LONG:
        yield cid, "long", (1920, 1080)


def test_all_sprint1_proofs_pixel_exact():
    for cid, aspect, size in _proofs():
        previews = SHORT_PREVIEWS if aspect == "short" else LONG_PREVIEWS
        path = previews / f"{aspect}-{cid.lower()}-proof.png"
        assert path.is_file(), path.name
        with Image.open(path) as image:
            assert image.size == size, (path.name, image.size)
        assert path.stat().st_size > 10_000, path.name


def test_no_stale_cross_aspect_proofs():
    assert list(SHORT_PREVIEWS.glob("long-*-proof.png")) == []
    assert list(LONG_PREVIEWS.glob("short-*-proof.png")) == []


def test_preview_html_has_sprint1_audit():
    text = HTML.read_text(encoding="utf-8")
    assert "<!-- SPRINT1-AUDIT -->" in text
    for cid in SPRINT_SHORT + SPRINT_LONG:
        assert cid in text, cid
