"""Sprint 1 starters: static gates (schema, ids, brand fonts, safe areas, slots)."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "studio_templates"))

from check_starters import check_file

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "apps" / "studio_templates"

SPRINT_SHORT = ["C-03", "C-04", "C-06", "C-07", "C-09", "C-10", "U-02", "U-03",
                "U-05", "MR-01", "MR-02", "MR-04", "MR-06", "MR-10", "MR-12",
                "BP-01", "BP-02", "BP-08", "BP-13", "BP-14", "BP-16", "BP-18",
                "BP-19", "BP-20"]
SPRINT_LONG = ["TA-01", "TA-02", "TA-03", "TA-05", "TA-06", "TA-11", "TA-12",
               "TA-14", "TA-16", "TA-18", "TA-19"]
# Sprint 3 (inventory §6): P1/P2 short cards.
SPRINT3_SHORT = ["MR-03", "MR-05", "MR-07", "MR-08", "MR-09", "MR-11",
                 "BP-03", "BP-04", "BP-05", "BP-06", "BP-07", "BP-09",
                 "BP-10", "BP-11", "BP-15", "BP-17",
                 "C-01", "C-02", "C-05", "C-08",
                 "U-01", "U-04", "U-06", "U-07", "U-08"]
# Sprint 2 (inventory §6): tactical P1 long cards.
SPRINT2_LONG = ["TA-04", "TA-07", "TA-08", "TA-09", "TA-10", "TA-13", "TA-15", "TA-17"]


def test_sprint1_inventory_complete():
    for cid in SPRINT_SHORT:
        assert (TPL / f"{cid}.short.json").is_file(), cid
    for cid in SPRINT_LONG:
        assert (TPL / f"{cid}.long.json").is_file(), cid


def test_wave2_inventory_complete():
    for cid in SPRINT3_SHORT:
        assert (TPL / f"{cid}.short.json").is_file(), cid


def test_sprint2_inventory_complete():
    for cid in SPRINT2_LONG:
        assert (TPL / f"{cid}.long.json").is_file(), cid


def test_wave2_static_gates():
    from check_starters import check_file

    failures = []
    for cid in SPRINT3_SHORT:
        failures += check_file(TPL / f"{cid}.short.json")
    for cid in SPRINT2_LONG:
        failures += check_file(TPL / f"{cid}.long.json")
    assert failures == [], "\n".join(failures[:20])


def test_sprint1_static_gates():
    failures = []
    for cid in SPRINT_SHORT + SPRINT3_SHORT:
        failures += check_file(TPL / f"{cid}.short.json")
    for cid in SPRINT_LONG + SPRINT2_LONG:
        failures += check_file(TPL / f"{cid}.long.json")
    assert failures == [], "\n".join(failures[:20])


def test_starter_endpoint_serves_sprint1():
    from apps.web_ui.server import _studio_starter

    design = _studio_starter("C-07", "short")
    assert (design["width"], design["height"]) == (1080, 1920)
    design = _studio_starter("TA-03", "long")
    assert (design["width"], design["height"]) == (1920, 1080)


def test_studio_html_lists_all_starters():
    import re

    from apps.web_ui.server import _studio_starter

    html = (ROOT / "apps" / "web_ui" / "static" / "studio.html").read_text(encoding="utf-8")
    options = re.findall(r'<option value="([A-Za-z0-9_-]+):(short|long)"', html)
    found = {(name, aspect) for name, aspect in options}
    for cid in SPRINT_SHORT:
        assert (cid, "short") in found, cid
        design = _studio_starter(cid, "short")
        assert (design["width"], design["height"]) == (1080, 1920)
    for cid in SPRINT_LONG:
        assert (cid, "long") in found, cid
        design = _studio_starter(cid, "long")
        assert (design["width"], design["height"]) == (1920, 1080)


def test_rejects_unknown_element_type(tmp_path):
    import json

    from check_starters import check_file

    bad = {
        "schemaVersion": 4, "width": 1080, "height": 1920, "fonts": [],
        "pages": [{"id": "p1", "background": "#161B2C", "children": [
            {"id": "val-1", "type": "txt", "x": 76, "y": 180,
             "width": 928, "height": 100, "text": "X",
             "fontFamily": "Barlow Condensed",
             "custom": {"slot": "title"}},
        ]}],
        "audios": [],
    }
    path = tmp_path / "BAD.short.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    errors = check_file(path)
    assert any("not a Polotno element type" in e for e in errors), errors


def test_contrast_overlap_audit_clean():
    import sys

    sys.path.insert(0, str(TPL))
    from audit_cards import SPRINT_LONG, SPRINT_SHORT, SPRINT2_LONG, SPRINT3_SHORT, audit

    failures = []
    for cid in SPRINT_SHORT + SPRINT3_SHORT:
        failures += [f"{cid}: {e}" for e in audit(TPL / f"{cid}.short.json")]
    for cid in SPRINT_LONG + SPRINT2_LONG:
        failures += [f"{cid}: {e}" for e in audit(TPL / f"{cid}.long.json")]
    assert failures == [], "\n".join(failures[:20])


def _pitch_children(cid):
    import json

    data = json.loads((TPL / f"{cid}.long.json").read_text(encoding="utf-8"))
    return data["pages"][0]["children"]


def test_pitch_team_split_and_ball():
    for cid in ("TA-03", "TA-05", "TA-06"):
        children = _pitch_children(cid)
        circles = [c for c in children
                   if c.get("type") == "figure" and c.get("subType") == "circle"]
        assert any(c.get("width") == 44 and not c.get("custom") for c in circles), cid  # ball
    for cid in ("TA-03", "TA-06"):  # two teams on the board
        children = _pitch_children(cid)
        fills = {c.get("fill") for c in children
                 if c.get("type") == "figure" and c.get("subType") == "circle"}
        assert "#F2F6FF" in fills and "#FF3D81" in fills, cid


def test_pressing_markers_and_freeze_ring():
    children = _pitch_children("TA-06")
    assert any(c.get("type") == "line" and "endHead" not in c
               and c.get("dash") for c in children)  # headless block line
    assert any((c.get("custom") or {}).get("slot") == "dline" for c in children)
    children = _pitch_children("TA-11")
    assert any(c.get("type") == "figure" and c.get("stroke") == "#FF3D81"
               for c in children)  # focus ring, not a blob
    assert any((c.get("custom") or {}).get("slot") == "focus" for c in children)
