"""Static gates for Sprint 1 starters (no browser needed)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TPL = ROOT / "apps" / "studio_templates"
FONTS = {"Barlow Condensed", "Be Vietnam Pro", "Permanent Marker", "Big Shoulders", "Tektur"}
# Element types per Polotno SDK (store → pages → elements).
# See https://polotno.com/docs/store.md and skills/polotno-sdk/SKILL.md.
ALLOWED_TYPES = {"text", "image", "svg", "figure", "line", "video", "gif", "table", "group"}


def check_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [f"{path.name}: unreadable ({e})"]
    if data.get("schemaVersion") != 4:
        errors.append(f"{path.name}: schemaVersion != 4")
    w, h = data.get("width"), data.get("height")
    aspect = "short" if path.suffixes == [".short", ".json"] else "long"
    want = (1080, 1920) if aspect == "short" else (1920, 1080)
    if (w, h) != want:
        errors.append(f"{path.name}: size {(w, h)} != {want}")
    if not data.get("fonts") == []:
        errors.append(f"{path.name}: fonts must be [] (Google auto-load)")
    pages = data.get("pages", [])
    if len(pages) != 1:
        errors.append(f"{path.name}: must have exactly 1 page")
        return errors
    children = pages[0].get("children", [])
    ids = [c.get("id") for c in children if isinstance(c, dict)]
    if len(ids) != len(set(ids)):
        errors.append(f"{path.name}: duplicate element ids")
    n_slot = 0
    for c in children:
        if not isinstance(c, dict):
            errors.append(f"{path.name}: non-object child")
            continue
        cid = c.get("id", "?")
        if c.get("type") not in ALLOWED_TYPES:
            errors.append(f"{path.name}/{cid}: type {c.get('type')!r} not a Polotno element type")
            continue
        for key in ("x", "y", "width", "height"):
            v = c.get(key)
            if not isinstance(v, (int, float)):
                errors.append(f"{path.name}/{cid}: {key} not a number")
        if c.get("type") == "text":
            if c.get("fontFamily") not in FONTS:
                errors.append(f"{path.name}/{cid}: font {c.get('fontFamily')} not brand")
            if not c.get("text", "").strip():
                errors.append(f"{path.name}/{cid}: empty text (placeholder risk)")
            if c.get("showInExport") is False:
                continue  # guides never export; exempt from safe checks
            # safe area for text: 7% sides, 9% top, 13% bottom —
            # except the credit slot (whisper, redundant with run provenance),
            # allowed down to 97% height (documented exception).
            x, y, cw, chh = c["x"], c["y"], c["width"], c["height"]
            bottom_limit = h * (0.97 if (isinstance(c.get("custom"), dict)
                                          and c["custom"].get("slot") == "credit") else 0.87)
            if x < w * 0.07 - 1 or x + cw > w * 0.93 + 1:
                errors.append(f"{path.name}/{cid}: text breaks side safe area")
            if y < h * 0.09 - 1 or y + chh > bottom_limit + 1:
                errors.append(f"{path.name}/{cid}: text breaks top/bottom safe area")
            if isinstance(c.get("custom"), dict) and c["custom"].get("slot"):
                n_slot += 1
        else:
            x, y, cw, chh = c["x"], c["y"], c["width"], c["height"]
            if x < 0 or y < 0 or x + cw > w + 1 or y + chh > h + 1:
                errors.append(f"{path.name}/{cid}: element outside canvas")
            if c.get("type") == "image":
                # Art bed: fullscreen pack resource, locked first child.
                # v12: owner pack plates; legacy generative beds also accepted.
                import re as _re

                src = str(c.get("src", ""))
                pack_m = _re.fullmatch(
                    r"/template-foundation/resources/pack/(short|long)-([A-Za-z0-9_-]+)\.(png|jpg|jpeg)", src)
                beds_m = _re.fullmatch(r"/template-foundation/resources/beds/[A-Za-z0-9_-]+\.png", src)
                if not (pack_m or beds_m):
                    errors.append(f"{path.name}/{cid}: bed src must be /template-foundation/resources/beds/<slug>.png or /template-foundation/resources/pack/<aspect>-<mode>.(png|jpg)")
                if children.index(c) != 0:
                    errors.append(f"{path.name}/{cid}: bed image must be the first child")
                if (x, y, cw, chh) != (0, 0, w, h):
                    errors.append(f"{path.name}/{cid}: bed must fill the exact canvas")
                base = (ROOT / "template_foundation/templates/allen-knows-ball"
                        / ("longform-12.0.0" if aspect == "long" else "12.0.0"))
                if pack_m:
                    bed_file = base / "resources/pack" / src.rsplit("/", 1)[-1]
                else:
                    bed_file = base / "resources/beds" / src.rsplit("/", 1)[-1]
                if not bed_file.is_file():
                    errors.append(f"{path.name}/{cid}: bed file missing: {bed_file.name}")
    if n_slot == 0:
        errors.append(f"{path.name}: no slotted value elements")
    return errors


def main() -> int:
    files = sorted(TPL.glob("*.short.json")) + sorted(TPL.glob("*.long.json"))
    files = [f for f in files if f.name != "duel_columns.short.json"]
    bad = 0
    for path in files:
        errs = check_file(path)
        for e in errs:
            print("FAIL", e)
            bad += 1
        if not errs:
            print("ok", path.name)
    print(f"{len(files)} files, {bad} errors")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
