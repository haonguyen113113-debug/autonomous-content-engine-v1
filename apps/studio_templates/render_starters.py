"""Render Sprint 1 Polotno starters to pixel-exact proof PNGs (no browser needed).

Starters are flat vector designs (rect/circle/line/text) authored at exact
canvas sizes, so PIL reproduces the Polotno export faithfully at pixelRatio 1.
Elements with showInExport:false (guides) are skipped, matching Polotno
export semantics. Fonts are the locked brand set from the 9.0.0 package.

Run: python apps/studio_templates/render_starters.py
Writes:
  template_foundation/templates/allen-knows-ball/9.0.0/previews/<prefix>-<id>-proof.png
  apps/studio_templates/proof-rows.json  (palette stats for write_audit.py)

Next: python apps/studio_templates/write_audit.py apps/studio_templates/proof-rows.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent.parent
TPL = ROOT / "apps" / "studio_templates"
FONTS = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "9.0.0" / "resources" / "fonts"
# Proofs live next to the package that serves them: the engine resolves
# short-* from 9.0.0 and long-* from longform-9.0.0 (see server.py).
PREVIEWS_SHORT = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "9.0.0" / "previews"
PREVIEWS_LONG = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "longform-9.0.0" / "previews"
ROWS = TPL / "proof-rows.json"

SPRINT_SHORT = ["C-03", "C-04", "C-06", "C-07", "C-09", "C-10", "U-02", "U-03",
                "U-05", "MR-01", "MR-02", "MR-04", "MR-06", "MR-10", "MR-12",
                "BP-01", "BP-02", "BP-08", "BP-13", "BP-14", "BP-16", "BP-18",
                "BP-19", "BP-20"]
SPRINT_LONG = ["TA-01", "TA-02", "TA-03", "TA-05", "TA-06", "TA-11", "TA-12",
               "TA-14", "TA-16", "TA-18", "TA-19"]
# Sprint 2 (inventory §6): tactical P1 long cards.
SPRINT2_LONG = ["TA-04", "TA-07", "TA-08", "TA-09", "TA-10", "TA-13", "TA-15", "TA-17"]
# Sprint 3 (inventory §6: P1/P2 short cards; TA longs are all done).
SPRINT3_SHORT = ["MR-03", "MR-05", "MR-07", "MR-08", "MR-09", "MR-11",
                 "BP-03", "BP-04", "BP-05", "BP-06", "BP-07", "BP-09",
                 "BP-10", "BP-11", "BP-12", "BP-15", "BP-17",
                 "C-01", "C-02", "C-05", "C-08",
                 "U-01", "U-04", "U-06", "U-07", "U-08"]

PALETTE = {
    "ink": "#161B2C", "ink2": "#20263C", "coral": "#E0705F",
    "paper": "#F4F2EC", "slate": "#5A6B8C", "mist": "#8B96B0",
}
PALETTE_RGB = [tuple(int(PALETTE[k][i:i + 2], 16) for i in (1, 3, 5)) for k in PALETTE]
TOLERANCE = 90  # per-channel box, per docs/build-audit-protocol.md (AA blends)


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def font_for(family: str, weight: str, size: int) -> ImageFont.FreeTypeFont:
    size = max(11, int(size))
    if family == "Barlow Condensed":
        name = "BarlowCondensed-Bold.ttf" if weight == "bold" else "BarlowCondensed-SemiBold.ttf"
    elif family == "Be Vietnam Pro":
        name = "BeVietnamPro-Bold.ttf" if weight == "bold" else "BeVietnamPro-Regular.ttf"
    else:  # Permanent Marker (latin-only per v9 brief); fallback keeps proof running
        name = "PermanentMarker-Regular.woff"
    try:
        return ImageFont.truetype(str(FONTS / name), size)
    except OSError:
        return ImageFont.load_default()


def composite(base: Image.Image, draw_fn, opacity: float) -> None:
    """Draw with opacity by compositing a transparent layer (Polotno semantics)."""
    if opacity >= 1.0:
        draw_fn(ImageDraw.Draw(base, "RGBA"))
        return
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer, "RGBA"))
    alpha = layer.split()[3].point(lambda v: int(v * opacity))
    layer.putalpha(alpha)
    base.alpha_composite(layer)


def render_design(data: dict) -> Image.Image:
    width, height = int(data["width"]), int(data["height"])
    page = data["pages"][0]
    base = Image.new("RGBA", (width, height), hex_rgb(page.get("background", "#161B2C")) + (255,))
    for child in page.get("children", []):
        if child.get("showInExport") is False:
            continue  # guides never export; exempt everywhere (gates + proof)
        kind = child.get("type")
        opacity = float(child.get("opacity", 1.0))
        x, y, w, h = (float(child.get(k, 0)) for k in ("x", "y", "width", "height"))
        if kind == "figure":
            fill = hex_rgb(child.get("fill", "#000000"))
            stroke = child.get("stroke")
            stroke_w = int(child.get("strokeWidth", 4))

            def draw_shape(d: ImageDraw.ImageDraw) -> None:
                box = [x, y, x + w, y + h]
                if child.get("subType") == "circle":
                    d.ellipse(box, fill=fill + (255,))
                    if stroke:
                        d.ellipse(box, outline=hex_rgb(stroke) + (255,), width=stroke_w)
                else:
                    d.rectangle(box, fill=fill + (255,))
                    if stroke:
                        d.rectangle(box, outline=hex_rgb(stroke) + (255,), width=stroke_w)

            composite(base, draw_shape, opacity)
        elif kind == "line":
            color = hex_rgb(child.get("color", "#E0705F"))
            thickness = max(4, round(h * 0.3))
            cy = y + h / 2
            dash = child.get("dash")

            def draw_line(d: ImageDraw.ImageDraw) -> None:
                x0, x1 = x, x + w
                if dash:
                    seg, gap = float(dash[0]), float(dash[1])
                    pos = x0
                    flip = True
                    while pos < x1:
                        end = min(pos + (seg if flip else gap), x1)
                        if flip:
                            d.line([pos, cy, end, cy], fill=color + (255,), width=thickness)
                        pos, flip = end, not flip
                else:
                    d.line([x0, cy, x1, cy], fill=color + (255,), width=thickness)
                if child.get("endHead") in ("triangle", "arrow"):
                    s = thickness * 3
                    d.polygon([(x1 + s, cy), (x1, cy - s * 0.6), (x1, cy + s * 0.6)], fill=color + (255,))

            composite(base, draw_line, opacity)
        elif kind == "text":
            font = font_for(child.get("fontFamily", "Be Vietnam Pro"),
                            child.get("fontWeight", "normal"),
                            int(child.get("fontSize", 40)))
            fill = hex_rgb(child.get("fill", "#F4F2EC"))
            align = child.get("align", "center")
            anchor = {"left": "lt", "center": "mt", "right": "rt"}.get(align, "mt")
            tx = x if align == "left" else (x + w / 2 if align == "center" else x + w)
            text = str(child.get("text", ""))

            def draw_text(d: ImageDraw.ImageDraw) -> None:
                d.text((tx, y), text, font=font, fill=fill + (255,), anchor=anchor)

            composite(base, draw_text, opacity)
        # image/svg/video/gif/table/group: not used by Sprint 1 starters;
        # check_starters.py rejects unknown types, known-unused ones warn here.
    return base.convert("RGB")


def palette_stats(image: Image.Image) -> tuple[int, list[str]]:
    """Count pixels outside the locked palette box (+-TOLERANCE per channel)."""
    colors = image.getcolors(maxcolors=1 << 24) or []
    bad = 0
    offenders: dict[str, int] = {}
    for count, rgb in colors:
        if any(all(abs(a - b) <= TOLERANCE for a, b in zip(rgb, pal)) for pal in PALETTE_RGB):
            continue
        bad += count
        offenders["#%02X%02X%02X" % rgb] = offenders.get("#%02X%02X%02X" % rgb, 0) + count
    top = sorted(offenders, key=offenders.get, reverse=True)[:5]
    return bad, top


def main() -> int:
    jobs = [(cid, "short") for cid in SPRINT_SHORT + SPRINT3_SHORT] + [(cid, "long") for cid in SPRINT_LONG + SPRINT2_LONG]
    rows = []
    for cid, aspect in jobs:
        path = TPL / f"{cid}.{aspect}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        image = render_design(data)
        assert image.size == ((1080, 1920) if aspect == "short" else (1920, 1080)), cid
        previews = PREVIEWS_SHORT if aspect == "short" else PREVIEWS_LONG
        out = previews / f"{aspect}-{cid.lower()}-proof.png"
        image.save(out)
        bad, top = palette_stats(image)
        rows.append({"name": cid, "aspect": aspect, "size": list(image.size),
                     "bad": bad, "badTop": top, "visual": "todo",
                     "note": "PIL proof of Polotno starter; static gates pass; needs owner eyeball."})
        print(f"ok {out.name} {image.size[0]}x{image.size[1]} {out.stat().st_size // 1024}KB off-palette={bad}")
    # stale proofs from before the per-package split (long-* lived in 9.0.0)
    for stale in PREVIEWS_SHORT.glob("long-*-proof.png"):
        stale.unlink()
        print(f"removed stale {stale.name}")
    ROWS.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} proofs + {ROWS.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
