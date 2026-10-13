"""Audit Sprint 1 starters: contrast (WCAG) + text overlap + decor-covering-text.

Geometry-based (no browser): background color at each text slot is resolved by
walking the paint order with alpha blending, then contrast vs the text fill.
Run: python apps/studio_templates/audit_cards.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TPL = ROOT / "apps" / "studio_templates"

SPRINT_SHORT = ["C-03", "C-04", "C-06", "C-07", "C-09", "C-10", "U-02", "U-03",
                "U-05", "MR-01", "MR-02", "MR-04", "MR-06", "MR-10", "MR-12",
                "BP-01", "BP-02", "BP-08", "BP-13", "BP-14", "BP-16", "BP-18",
                "BP-19", "BP-20"]
SPRINT_LONG = ["TA-01", "TA-02", "TA-03", "TA-05", "TA-06", "TA-11", "TA-12",
               "TA-14", "TA-16", "TA-18", "TA-19"]
# Sprint 2 (inventory §6): tactical P1 long cards.
SPRINT2_LONG = ["TA-04", "TA-07", "TA-08", "TA-09", "TA-10", "TA-13", "TA-15", "TA-17"]
# Sprint 3 (inventory §6): P1/P2 short cards.
SPRINT3_SHORT = ["MR-03", "MR-05", "MR-07", "MR-08", "MR-09", "MR-11",
                 "BP-03", "BP-04", "BP-05", "BP-06", "BP-07", "BP-09",
                 "BP-10", "BP-11", "BP-12", "BP-15", "BP-17",
                 "C-01", "C-02", "C-05", "C-08",
                 "U-01", "U-04", "U-06", "U-07", "U-08"]


def hex_rgb(value: str) -> tuple[float, float, float]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def blend(fg: tuple[float, float, float], bg: tuple[float, float, float], alpha: float):
    return tuple(f * alpha + b * (1 - alpha) for f, b in zip(fg, bg))


def luminance(rgb: tuple[float, float, float]) -> float:
    def channel(v: float) -> float:
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    la, lb = luminance(a), luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def covers(child: dict, px: float, py: float) -> bool:
    if child.get("type") == "line":
        return False
    x, y, w, h = (float(child.get(k, 0)) for k in ("x", "y", "width", "height"))
    if child.get("type") == "figure" and child.get("subType") == "circle":
        cx, cy, rx, ry = x + w / 2, y + h / 2, w / 2, h / 2
        return ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1 if rx and ry else False
    return x <= px <= x + w and y <= py <= y + h


def bbox_overlap(a: dict, b: dict) -> float:
    ax, ay, aw, ah = (float(a.get(k, 0)) for k in ("x", "y", "width", "height"))
    bx, by, bw, bh = (float(b.get(k, 0)) for k in ("x", "y", "width", "height"))
    ix = min(ax + aw, bx + bw) - max(ax, bx)
    iy = min(ay + ah, by + bh) - max(ay, by)
    if ix <= 0 or iy <= 0:
        return 0.0
    return (ix * iy) / min(aw * ah, bw * bh)


def audit(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    page = data["pages"][0]
    bg = hex_rgb(page.get("background", "#161B2C"))
    children = [c for c in page.get("children", []) if c.get("showInExport") is not False]
    issues: list[str] = []
    texts = [c for c in children if c.get("type") == "text"]
    # 1. contrast per text slot (worst of 3 vertical samples: glyphs may
    # straddle a background boundary even when the box center is safe)
    for text in texts:
        slot = (text.get("custom") or {}).get("slot", text.get("id"))
        cx = float(text["x"]) + float(text["width"]) / 2
        ratios = []
        for frac in (0.15, 0.5, 0.85):
            px = cx
            py = float(text["y"]) + float(text["height"]) * frac
            color = bg
            for child in children:
                if child is text:
                    break
                if child.get("type") == "figure" and covers(child, px, py):
                    color = blend(hex_rgb(child.get("fill", "#000000")),
                                  color, float(child.get("opacity", 1.0)))
            fg = blend(hex_rgb(text.get("fill", "#F4F2EC")), color,
                       float(text.get("opacity", 1.0)))
            ratios.append(contrast(fg, color))
        ratio = min(ratios)
        size = int(text.get("fontSize", 0))
        # Boss = full-opacity large type (protocol floor 4.5). Dimmed values
        # (opacity < 1) are deliberate de-emphasis; WCAG large-type floor 3.0.
        floor = 4.5 if size >= 48 and float(text.get("opacity", 1.0)) >= 1.0 else 3.0
        if ratio < floor:
            issues.append(f"contrast {slot}: {ratio:.2f} < {floor} "
                          f"(size {size}, fg {text.get('fill')})")
    # 2. text-text overlap
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            overlap = bbox_overlap(texts[i], texts[j])
            if overlap > 0.02:
                si = (texts[i].get("custom") or {}).get("slot", texts[i].get("id"))
                sj = (texts[j].get("custom") or {}).get("slot", texts[j].get("id"))
                issues.append(f"overlap {si} x {sj}: {overlap:.0%} of smaller box")
    # 3. decor painted over text (outline-only figures — anything with a
    # stroke key: center circle, 6-yard insets, focus ring — never cover text)
    page_bg = hex_rgb(page.get("background", "#161B2C"))
    for idx, child in enumerate(children):
        if child.get("type") != "figure":
            continue
        if "stroke" in child:
            continue
        if hex_rgb(child.get("fill", "#000000")) == page_bg:
            continue
        for text in texts:
            if children.index(text) < idx:
                overlap = bbox_overlap(child, text)
                if overlap > 0.05:
                    slot = (text.get("custom") or {}).get("slot", text.get("id"))
                    issues.append(f"cover {child.get('id')} over text {slot}: {overlap:.0%}")
    # 4. single-line text wider than its box (would shrink on Polotno export;
    # placeholders must demo the fitted look). Measured with the locked fonts.
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent))
    from render_starters import font_for
    for text in texts:
        content = str(text.get("text", ""))
        if "\n" in content or not content.strip():
            continue
        font = font_for(text.get("fontFamily", "Be Vietnam Pro"),
                        text.get("fontWeight", "normal"),
                        int(text.get("fontSize", 40)))
        box = font.getbbox(content)
        width = box[2] - box[0]
        if width > float(text.get("width", 0)) + 2:
            slot = (text.get("custom") or {}).get("slot", text.get("id"))
            issues.append(f"overflow {slot}: text {width}px > box {text.get('width')}px")
    return issues


def main() -> int:
    total = 0
    for cid in SPRINT_SHORT + SPRINT3_SHORT:
        issues = audit(TPL / f"{cid}.short.json")
        total += len(issues)
        print(f"{cid}: {'PASS' if not issues else ''}")
        for issue in issues:
            print(f"  - {issue}")
    for cid in SPRINT_LONG + SPRINT2_LONG:
        issues = audit(TPL / f"{cid}.long.json")
        total += len(issues)
        print(f"{cid}: {'PASS' if not issues else ''}")
        for issue in issues:
            print(f"  - {issue}")
    print(f"{total} issues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
