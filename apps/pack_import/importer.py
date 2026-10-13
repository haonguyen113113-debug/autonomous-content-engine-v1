"""Owner-authored pack import: Canva (or any platform) backgrounds + boxes.

The owner designs every pixel; the engine only validates, versions, draws
dynamic text into declared boxes, and serves the audit page.
See docs/canva-pack-contract.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SAFE_SLUG = re.compile(r"^[A-Za-z0-9_-]{1,60}$")
SHORT_SIZE = (1080, 1920)
LONG_SIZE = (1920, 1080)
FONTS = ("display", "body", "brush")
MAX_BYTES = 2 * 1024 * 1024


class PackError(ValueError):
    """One validation failure; build() raises with the full list attached."""


def _load_pack(drop: Path) -> dict[str, Any]:
    try:
        data = json.loads((drop / "pack.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PackError(f"pack.json missing or invalid: {error}") from error
    if not isinstance(data, dict):
        raise PackError("pack.json must contain an object.")
    return data


def validate(drop: Path) -> list[str]:
    """Return a list of human-readable errors; empty means the pack is shippable."""
    from PIL import Image

    errors: list[str] = []
    drop = Path(drop)
    try:
        pack = _load_pack(drop)
    except PackError as error:
        return [str(error)]
    for field in ("channel_id", "template_id", "version", "layouts"):
        if not pack.get(field):
            errors.append(f"pack.json: missing '{field}'.")
    version = str(pack.get("version", ""))
    if version and not re.fullmatch(r"\d+\.\d+\.\d+", version):
        errors.append(f"pack.json: version '{version}' is not semver.")
    layouts = pack.get("layouts", [])
    if not isinstance(layouts, list) or not layouts:
        errors.append("pack.json: 'layouts' must be a non-empty list.")
        return errors
    seen: set[str] = set()
    for item in layouts:
        if not isinstance(item, dict):
            errors.append("pack.json: every layout must be an object.")
            continue
        lid = str(item.get("id", ""))
        if not SAFE_SLUG.match(lid):
            errors.append(f"layout id '{lid}' must match [A-Za-z0-9_-].")
            continue
        if lid in seen:
            errors.append(f"duplicate layout id '{lid}'.")
        seen.add(lid)
        for prefix, size in (("short", SHORT_SIZE), ("long", LONG_SIZE)):
            found = None
            for ext in (".png", ".jpg", ".jpeg"):
                candidate = drop / f"{prefix}-{lid}{ext}"
                if candidate.is_file():
                    found = candidate
                    break
            if found is None:
                errors.append(f"missing background: {prefix}-{lid}.png (or .jpg).")
                continue
            if found.stat().st_size > MAX_BYTES:
                errors.append(f"{found.name}: over 2MB, re-export lighter.")
            try:
                with Image.open(found) as image:
                    if image.size != size:
                        errors.append(
                            f"{found.name}: is {image.size[0]}x{image.size[1]}, "
                            f"need {size[0]}x{size[1]}.")
            except (OSError, ValueError):
                errors.append(f"{found.name}: unreadable image.")
        boxes = item.get("boxes", [])
        if not isinstance(boxes, list):
            errors.append(f"layout '{lid}': 'boxes' must be a list.")
            continue
        for box in boxes:
            if not isinstance(box, dict):
                errors.append(f"layout '{lid}': every box must be an object.")
                continue
            key = str(box.get("key", ""))
            if not key or len(key) > 80:
                errors.append(f"layout '{lid}': box needs a data key.")
            coords = box.get("box")
            if (not isinstance(coords, list) or len(coords) != 4
                    or not all(isinstance(v, (int, float)) for v in coords)
                    or not all(0.0 <= v <= 1.0 for v in coords)
                    or coords[2] <= 0 or coords[3] <= 0
                    or coords[0] + coords[2] > 1.0 or coords[1] + coords[3] > 1.0):
                errors.append(f"layout '{lid}' box '{key}': box must be [x,y,w,h] in 0-1, inside canvas.")
            if box.get("font", "body") not in FONTS:
                errors.append(f"layout '{lid}' box '{key}': font must be one of {FONTS}.")
            try:
                size_px = int(box.get("size", 0))
            except (TypeError, ValueError):
                size_px = 0
            if not 11 <= size_px <= 400:
                errors.append(f"layout '{lid}' box '{key}': size must be 11-400px.")
            color = str(box.get("color", ""))
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                errors.append(f"layout '{lid}' box '{key}': color must be #rrggbb.")
            if box.get("align", "center") not in ("left", "center", "right"):
                errors.append(f"layout '{lid}' box '{key}': align must be left/center/right.")
    return errors


def init_scaffold(drop: Path, layouts: list[str] | None = None) -> Path:
    """Create an empty drop folder with a documented pack.json starter."""
    drop = Path(drop)
    drop.mkdir(parents=True, exist_ok=True)
    (drop / "fonts").mkdir(exist_ok=True)
    layouts = layouts or ["duel_columns", "stat_leader", "player_poster",
                          "goal_card", "fixture_card", "score_card"]
    pack = {
        "channel_id": "allen-knows-ball",
        "template_id": "allen-knows-ball.shortform-analyst",
        "version": (drop.name if re.fullmatch(r"\d+\.\d+\.\d+", drop.name) else "10.0.0"),
        "layouts": [
            {"id": lid, "title": lid.replace("-", " "),
             "boxes": [
                 {"key": "headline", "box": [0.08, 0.10, 0.84, 0.10],
                  "font": "display", "size": 90, "color": "#F5F1E6", "align": "center"}
             ]}
            for lid in layouts
        ],
        "licenses": [
            {"what": "Background plates", "by": "Owner (Canva export)", "terms": "Channel-owned"}
        ],
    }
    (drop / "pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (drop / "PUT_BACKGROUNDS_HERE.txt").write_text(
        "Export Canva: short-<id>.png 1080x1920 + long-<id>.png 1920x1080 per layout id.\n"
        "See docs/canva-pack-contract.md, then: python -m apps.pack_import.build <this-folder>\n",
        encoding="utf-8")
    return drop


def _lookup(data: dict[str, Any], key: str) -> str:
    """Resolve 'metrics.0.value.home' style paths against graphic_data."""
    current: Any = data
    for part in str(key).split("."):
        if isinstance(current, dict):
            current = current.get(part, "")
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return ""
        else:
            return ""
    if isinstance(current, (dict, list)):
        return ""
    return str(current)[:120]


def render_pack_plate(bg_path: Path, boxes: list[dict[str, Any]], data: dict[str, Any],
                      fonts: Any, is_long: bool) -> Any:
    """Draw dynamic boxes over an owner background. Locked fonts only."""
    from PIL import Image as _Image, ImageDraw as _Draw, ImageFont as _Font, ImageOps as _Ops

    target = LONG_SIZE if is_long else SHORT_SIZE
    with _Image.open(bg_path) as opened:
        base = _Ops.fit(opened.convert("RGB"), target).convert("RGBA")
    draw = _Draw.Draw(base, "RGBA")
    ref_w = SHORT_SIZE[0]
    scale = target[0] / ref_w

    def face(kind: str, size: int) -> Any:
        size = max(11, round(size * scale))
        if kind == "display":
            return fonts.barlow(size)
        if kind == "brush":
            return fonts.brush(size)
        return fonts.bev_b(size)

    for box in boxes:
        value = " ".join(_lookup(data, box.get("key", "")).split())
        if not value:
            continue
        x, y, w, h = (box.get("box") or [0, 0, 0, 0])
        font = face(box.get("font", "body"), int(box.get("size", 40)))
        raw = str(box.get("color", "#FFFFFF")).lstrip("#")
        fill = (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16), 255)
        # shrink until the value fits its box
        size_px = int(box.get("size", 40))
        while size_px > 11:
            font = face(box.get("font", "body"), size_px)
            try:
                text_w = draw.textbbox((0, 0), value, font=font)[2]
            except (ValueError, TypeError):
                break
            if text_w <= w * target[0]:
                break
            size_px -= 4
        box_px = (round(x * target[0]), round(y * target[1]),
                  round(w * target[0]), round(h * target[1]))
        text_w = draw.textbbox((0, 0), value, font=font)[2]
        align = box.get("align", "center")
        if align == "center":
            tx = box_px[0] + (box_px[2] - text_w) / 2
        elif align == "right":
            tx = box_px[0] + box_px[2] - text_w
        else:
            tx = box_px[0]
        draw.text((tx, box_px[1]), value, font=font, fill=fill)
    return base


def build(root: Path, drop: Path) -> dict[str, Any]:
    """Validate and install an owner pack as a new draft template version."""
    from PIL import Image as _Image

    root, drop = Path(root), Path(drop)
    errors = validate(drop)
    if errors:
        raise PackError("pack invalid:\n- " + "\n- ".join(errors))
    pack = _load_pack(drop)
    version = str(pack["version"])
    template_id = str(pack["template_id"])
    long_id = template_id.replace("shortform", "longform")
    foundation = root / "template_foundation"
    catalog_path = foundation / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))

    for tid, variant, prefix, size, aspect, w, h in [
        (template_id, version, "short", SHORT_SIZE, "9:16", 1080, 1920),
        (long_id, f"longform-{version}", "long", LONG_SIZE, "16:9", 1920, 1080),
    ]:
        if any(t.get("template_id") == tid and t.get("version") == version
               for t in catalog.get("templates", [])):
            raise PackError(f"catalog already has {tid}@{version}; bump pack.json version.")
        package = foundation / "templates" / "allen-knows-ball" / variant
        res = package / "resources" / "pack"
        prev = package / "previews"
        res.mkdir(parents=True, exist_ok=True)
        prev.mkdir(parents=True, exist_ok=True)
        for item in pack["layouts"]:
            lid = str(item["id"])
            for ext in (".png", ".jpg", ".jpeg"):
                src = drop / f"{prefix}-{lid}{ext}"
                if src.is_file():
                    (res / f"{prefix}-{lid}{ext}").write_bytes(src.read_bytes())
                    with _Image.open(src) as opened:
                        opened.convert("RGB").save(prev / f"{prefix}-{lid}-preview.png")
                    break
        manifest = {
            "template_id": tid, "channel_id": str(pack["channel_id"]), "version": version,
            "status": "draft",
            "description": f"Owner-authored pack v{version} (Canva backgrounds + engine boxes).",
            "market": "VN", "locale": "vi-VN", "category": "soccer", "content_owner": "Allen Knows Ball",
            "output": {"media_type": "video", "aspect_ratio": aspect, "width": w, "height": h,
                       "frame_rate": 30, "color_space": "SDR Rec.709", "audio_sample_rate_hz": 48000},
            "duration_seconds": {"target": 45, "minimum": 30, "maximum": 58},
            "primary_publishing_shape": "Short-form video; platform publishing not configured.",
            "renderer_requirement": "Backgrounds are owner-authored; engine draws declared boxes with locked fonts.",
            "font_resources": ["resources/fonts/BeVietnamPro-Regular.ttf",
                               "resources/fonts/BeVietnamPro-SemiBold.ttf",
                               "resources/fonts/BeVietnamPro-Bold.ttf",
                               "resources/fonts/BarlowCondensed-SemiBold.ttf",
                               "resources/fonts/BarlowCondensed-Bold.ttf",
                               "resources/fonts/PermanentMarker-Regular.woff"],
            "required_input_slots": ["hook", "match_or_topic", "one_core_claim", "evidence",
                                     "host_analysis", "takeaway"],
            "fixed_components": ["visual_identity", "typography", "opening_behavior",
                                 "closing_behavior", "transition_set", "effect_set", "sound_cue_spec"],
            "change_policy": "Owner re-exports backgrounds; changes require a new pack version.",
            "slot_contract": "slot-contract.json",
        }
        (package / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (package / "graphic-templates.json").write_text(json.dumps({
            "schema_version": "1.0", "template_version": version, "pack": True,
            "motion_notes": "Owner backgrounds; engine boxes only.",
            "selection_rule": "Modes map 1-1 to owner layouts.",
            "layouts": [
                {"id": str(item["id"]), "purpose": str(item.get("title", item["id"])),
                 "required_data": ["graphic_data"], "pack_bg": True,
                 "boxes": item.get("boxes", [])} for item in pack["layouts"]],
            "data_integrity": ["Only reviewed values with source+date."],
            "previews": "Owner-exported backgrounds in previews/."}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for name in ("design-tokens.json", "timeline.json", "story-forms.json",
                     "slot-contract.json", "visual-modes.json", "color-systems.json"):
            src = foundation / "templates" / "allen-knows-ball" / "9.0.0" / name
            text = src.read_text(encoding="utf-8") if src.is_file() else "{}"
            (package / name).write_text(text, encoding="utf-8")
        # fonts: prefer pack fonts, else link the locked Kit set
        font_dir = package / "resources" / "fonts"
        if (drop / "fonts").is_dir() and any((drop / "fonts").glob("*.ttf")):
            font_dir.mkdir(parents=True, exist_ok=True)
            for face in (drop / "fonts").glob("*"):
                if face.suffix.lower() in (".ttf", ".otf", ".woff", ".txt"):
                    (font_dir / face.name).write_bytes(face.read_bytes())
        else:
            kit_fonts = foundation / "templates" / "allen-knows-ball" / "9.0.0" / "resources" / "fonts"
            font_dir.mkdir(parents=True, exist_ok=True)
            for face in kit_fonts.glob("*"):
                (font_dir / face.name).write_bytes(face.read_bytes())
        (package / "LICENSES.json").write_text(json.dumps({
            "schema_version": "1.0",
            "owner_resources": pack.get("licenses", []),
            "policy": "Owner-authored backgrounds; engine draws boxes with locked fonts."},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        catalog["templates"].append({
            "template_id": tid, "channel_id": str(pack["channel_id"]),
            "version": version, "status": "draft",
            "path": f"templates/allen-knows-ball/{variant}"})
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_audit(root, pack)
    return {"version": version, "layouts": [str(i["id"]) for i in pack["layouts"]]}


def _write_audit(root: Path, pack: dict[str, Any]) -> None:
    version = str(pack["version"])
    package = root / "template_foundation" / "templates" / "allen-knows-ball" / version
    cards = "\n".join(
        f'<div class="rendered-card"><b>{i["id"]}</b>'
        f'<img src="/template-foundation/previews/short-{i["id"]}-preview.png" alt="{i["id"]}">'
        f'<small>{len(i.get("boxes", []))} boxes.</small></div>'
        for i in pack["layouts"])
    (package / "pack-audit.html").write_text(
        "<!doctype html><html lang='vi'><head><meta charset='utf-8'>"
        f"<title>Pack audit {version}</title><style>"
        "body{margin:0;background:#0b0d10;color:#f5f1e6;font:15px Arial,sans-serif}"
        ".page{max-width:1200px;margin:auto;padding:28px}.grid{display:grid;"
        "grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}"
        ".rendered-card{background:#14171c;padding:10px}.rendered-card img{width:100%}"
        "</style></head><body><main class='page'>"
        f"<h1>Owner pack {version} — {len(pack['layouts'])} layouts</h1>"
        f"<p>Backgrounds: owner Canva export. Boxes: engine-drawn, locked fonts.</p>"
        f"<div class='grid'>{cards}</div></main></body></html>", encoding="utf-8")
