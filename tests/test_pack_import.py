"""Owner pack import: validate, build, and render boxes."""

from pathlib import Path
import json

from apps.pack_import import PackError, build, init_scaffold, render_pack_plate, validate

ROOT = Path(__file__).resolve().parent.parent


def _scaffold_root(tmp_path: Path) -> Path:
    foundation = tmp_path / "template_foundation"
    (foundation / "templates" / "allen-knows-ball").mkdir(parents=True)
    (foundation / "channels" / "allen-knows-ball").mkdir(parents=True)
    (foundation / "catalog.json").write_text(json.dumps({
        "schema_version": "1.0", "foundation_id": "test",
        "channels": [{"channel_id": "allen-knows-ball",
                      "path": "channels/allen-knows-ball/channel.json"}],
        "templates": []}), encoding="utf-8")
    (foundation / "channels" / "allen-knows-ball" / "channel.json").write_text(
        json.dumps({"channel_id": "allen-knows-ball"}), encoding="utf-8")
    return tmp_path


def _make_pack(drop: Path) -> Path:
    from PIL import Image

    init_scaffold(drop, layouts=["duel_columns", "stat_leader"])
    pack = json.loads((drop / "pack.json").read_text(encoding="utf-8"))
    pack["version"] = "99.0.0"
    pack["layouts"][0]["boxes"] = [
        {"key": "metrics.0.value.home", "box": [0.08, 0.40, 0.30, 0.14],
         "font": "display", "size": 150, "color": "#F5F1E6", "align": "center"}]
    pack["layouts"][1]["boxes"] = [
        {"key": "stats.0.value", "box": [0.06, 0.10, 0.40, 0.20],
         "font": "display", "size": 200, "color": "#000000", "align": "left"}]
    (drop / "pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")
    for lid in ("duel_columns", "stat_leader"):
        Image.new("RGB", (1080, 1920), (200, 16, 46)).save(drop / f"short-{lid}.png")
        Image.new("RGB", (1920, 1080), (200, 16, 46)).save(drop / f"long-{lid}.png")
    return drop


def test_validate_accepts_good_pack(tmp_path):
    assert validate(_make_pack(tmp_path / "pack-drop" / "99.0.0")) == []


def test_validate_rejects_bad_size_and_box(tmp_path):
    from PIL import Image

    drop = _make_pack(tmp_path / "pack-drop" / "99.0.0")
    Image.new("RGB", (100, 100), (0, 0, 0)).save(drop / "short-duel_columns.png")
    pack = json.loads((drop / "pack.json").read_text(encoding="utf-8"))
    pack["layouts"][0]["boxes"] = [{"key": "", "box": [0.9, 0.9, 0.5, 0.5],
                                     "font": "nope", "size": 5, "color": "red", "align": "up"}]
    (drop / "pack.json").write_text(json.dumps(pack), encoding="utf-8")
    errors = validate(drop)
    assert any("100x100" in e or "need 1080x1920" in e for e in errors)
    assert any("box must be" in e or "inside canvas" in e for e in errors)
    assert any("font must be" in e for e in errors)


def test_build_installs_versioned_package(tmp_path):
    root = _scaffold_root(tmp_path)
    result = build(root, _make_pack(tmp_path / "pack-drop" / "99.0.0"))
    assert result["version"] == "99.0.0"
    package = root / "template_foundation" / "templates" / "allen-knows-ball" / "99.0.0"
    assert (package / "manifest.json").is_file()
    assert (package / "resources" / "pack" / "short-duel_columns.png").is_file()
    assert (package / "previews" / "short-duel_columns-preview.png").is_file()
    assert (package / "pack-audit.html").is_file()
    graphic = json.loads((package / "graphic-templates.json").read_text(encoding="utf-8"))
    duel = next(item for item in graphic["layouts"] if item["id"] == "duel_columns")
    assert duel["pack_bg"] is True and len(duel["boxes"]) == 1
    catalog = json.loads((root / "template_foundation" / "catalog.json").read_text(encoding="utf-8"))
    versions = [(t["template_id"], t["version"]) for t in catalog["templates"]]
    assert ("allen-knows-ball.shortform-analyst", "99.0.0") in versions
    assert ("allen-knows-ball.longform-analyst", "99.0.0") in versions
    # reinstalling the same version is rejected
    try:
        build(root, tmp_path / "pack-drop" / "99.0.0")
    except PackError:
        pass
    else:
        raise AssertionError("duplicate version should be rejected")


def test_render_pack_plate_draws_boxes(tmp_path):
    from apps.sportskit import KitFonts

    fonts = KitFonts(ROOT / "template_foundation/templates/allen-knows-ball/12.0.0/resources/fonts")
    bg = tmp_path / "bg.png"
    from PIL import Image
    Image.new("RGB", (1080, 1920), (200, 16, 46)).save(bg)
    img = render_pack_plate(bg, [
        {"key": "metrics.0.value.home", "box": [0.08, 0.40, 0.30, 0.14],
         "font": "display", "size": 150, "color": "#F5F1E6", "align": "center"},
        {"key": "missing.key", "box": [0.08, 0.60, 0.30, 0.14],
         "font": "body", "size": 40, "color": "#FFFFFF", "align": "left"}],
        {"metrics": [{"value": {"home": "45"}}]}, fonts, False)
    assert img.size == (1080, 1920)
