"""Template v12.0.0 Cyber Pitch: owner neon plates plus engine boxes (89 cards)."""

from pathlib import Path

from template_foundation import resolve_template

ROOT = Path(__file__).resolve().parent.parent
SHORT_PREVIEWS = ROOT / "template_foundation/templates/allen-knows-ball/12.0.0/previews"
LONG_PREVIEWS = ROOT / "template_foundation/templates/allen-knows-ball/longform-12.0.0/previews"

CYBER = {"void": "#060913", "panel": "#0D1424", "neon_cyan": "#00E5FF",
         "pulse_magenta": "#FF3D81", "amber": "#FFB03A", "paper": "#F2F6FF",
         "slate": "#8296BE"}


def test_drafts_resolve_cyber_by_default():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                             version="12.0.0", allow_draft=True)
    assert short.manifest["version"] == "12.0.0"
    assert short.manifest["status"] == "released"
    assert "Cyber" in short.manifest["description"]
    long = resolve_template(ROOT, "allen-knows-ball.longform-analyst",
                            version="12.0.0", allow_draft=True)
    assert long.manifest["version"] == "12.0.0"


def test_released_v12_stays_pinned():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                             version="12.0.0", allow_draft=True)
    assert short.manifest["status"] == "released"


def test_cyber_palette_locked():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                             version="12.0.0", allow_draft=True)
    palette = short.design_tokens["palette"]
    for key, value in CYBER.items():
        assert palette[key] == value, key
    assert short.design_tokens["typography"]["display"]["family"] == "Tektur"
    assert any(str(f).endswith("Tektur-Medium.ttf") for f in short.manifest["font_resources"])
    assert (short.root / "resources" / "fonts" / "Tektur-Medium.ttf").is_file()
    assert {c["id"] for c in short.color_systems["colorways"]} == {"cyber-pitch"}


def test_cyber_contrast_pairs():
    from apps.studio_templates.audit_cards import contrast, hex_rgb

    assert contrast(hex_rgb("#F2F6FF"), hex_rgb("#060913")) >= 7.0
    assert contrast(hex_rgb("#00E5FF"), hex_rgb("#060913")) >= 7.0
    assert contrast(hex_rgb("#FFB03A"), hex_rgb("#060913")) >= 7.0
    assert contrast(hex_rgb("#8296BE"), hex_rgb("#060913")) >= 4.5
    assert contrast(hex_rgb("#FF3D81"), hex_rgb("#060913")) >= 4.5


def test_cyber_layouts_cover_planning_modes():
    short = resolve_template(ROOT, "allen-knows-ball.shortform-analyst",
                             version="12.0.0", allow_draft=True)
    layout_ids = [item["id"] for item in short.graphic_templates["layouts"]]
    for mode in ("duel_columns", "stat_leader", "player_poster_side", "player_poster_top",
                 "goal_card", "fixture_card", "fixture_list", "score_card", "quote_card",
                 "potm_card", "discipline_card", "welcome_card", "hook_card"):
        assert mode in layout_ids, mode
    slots = [s["slot_id"] for s in short.slots["slots"]]
    for slot in ("crest-home", "crest-away", "team-wide", "player-portrait"):
        assert slot in slots, slot


def test_cyber_registry_slots_match_package():
    import json

    from apps.card_selector import REQUIRED_SLOTS

    from template_foundation import resolve_template

    # Compare against the pack the engine actually pins, not a hard-coded
    # historical version: a new released pack is the new source of truth.
    resolved = resolve_template(
        ROOT, "allen-knows-ball.shortform-analyst", allow_draft=True
    )
    package = json.loads(
        (resolved.root / "graphic-templates.json").read_text(encoding="utf-8")
    )
    package_required = {}
    for layout in package["layouts"]:
        keys = [r.split("graphic_data.", 1)[1] for r in layout.get("required_data", [])
                if r.startswith("graphic_data.")]
        package_required[layout["id"]] = keys
    for mode, keys in REQUIRED_SLOTS.items():
        if mode in package_required:
            assert set(keys) <= set(package_required[mode]), mode


def test_cyber_proofs_pixel_exact_and_blend_clean():
    import json

    from PIL import Image

    from apps.studio_templates.render_starters import audit_blends

    short_ids = ["C-03", "C-04", "C-06", "C-07", "C-09", "C-10", "U-02", "U-03",
                 "U-05", "MR-01", "MR-02", "MR-04", "MR-06", "MR-10", "MR-12",
                 "BP-01", "BP-02", "BP-08", "BP-13", "BP-14", "BP-16", "BP-18",
                 "BP-19", "BP-20", "MR-03", "MR-05", "MR-07", "MR-08", "MR-09",
                 "MR-11", "BP-03", "BP-04", "BP-05", "BP-06", "BP-07", "BP-09",
                 "BP-10", "BP-11", "BP-15", "BP-17",
                 "C-01", "C-02", "C-05", "C-08",
                 "U-01", "U-04", "U-06", "U-07", "U-08"]
    long_ids = ["TA-01", "TA-02", "TA-03", "TA-05", "TA-06", "TA-11", "TA-12",
                "TA-14", "TA-16", "TA-18", "TA-19", "TA-04", "TA-07", "TA-08",
                "TA-09", "TA-10", "TA-13", "TA-15", "TA-17",
                "TA-20", "TA-21", "TA-22", "TA-23", "TA-24",
                "LC-01", "LC-02", "LC-03", "LC-04", "LC-05", "LC-06", "LC-07",
                "LC-08", "LC-09", "LC-10", "LC-11", "LC-12", "LC-13", "LC-14",
                "LC-15", "LC-16"]
    palette = [(6, 9, 19), (13, 20, 36), (0, 229, 255), (255, 61, 129),
               (255, 176, 58), (242, 246, 255), (130, 150, 190)]
    for cid in short_ids:
        path = SHORT_PREVIEWS / f"short-{cid.lower()}-proof.png"
        assert path.is_file(), path.name
        with Image.open(path) as image:
            assert image.size == (1080, 1920), (path.name, image.size)
    for cid in long_ids:
        path = LONG_PREVIEWS / f"long-{cid.lower()}-proof.png"
        assert path.is_file(), path.name
        with Image.open(path) as image:
            assert image.size == (1920, 1080), (path.name, image.size)
    # Blend gate on authored pixels only: owner photo plates are exempt
    # (palette binds non-image pixels), so audit bedless renders.
    from apps.studio_templates.render_starters import render_design
    tpl = ROOT / "apps" / "studio_templates"
    for cid, aspect in ([(c, "short") for c in short_ids]
                        + [(c, "long") for c in long_ids]):
        data = json.loads((tpl / f"{cid}.{aspect}.json").read_text(encoding="utf-8"))
        data["pages"][0]["children"] = [
            c for c in data["pages"][0]["children"]
            if not (isinstance(c, dict) and c.get("type") == "image")]
        bad, _ = audit_blends(render_design(data).convert("RGB"), palette)
        assert bad == 0, (cid, bad)


def test_cyber_preview_html_has_audit():
    for root in (ROOT / "template_foundation/templates/allen-knows-ball/12.0.0",
                 ROOT / "template_foundation/templates/allen-knows-ball/longform-12.0.0"):
        text = (root / "preview.html").read_text(encoding="utf-8")
        assert "<!-- SPRINT1-AUDIT -->" in text
        assert "12.0.0" in text
