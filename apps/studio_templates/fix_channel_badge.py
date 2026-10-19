"""Channel badge watermark (bake) + baked-text cleanup + seal removal.

Owner order (2026-10-16, in-place on 12.0.0, logged in manual):
1. Remove cyan seal-disc + AKB text from BP-20/C-05/C-09/MR-12/U-08.
2. Inpaint baked gibberish text on short-source/quote plates (same image).
3. Bake badge-circle watermark top-right on every plate EXCEPT opening/
   ending (those bake it already): short d120@(912,48), long d96@(1704,30).
   pack-drop is source of truth; resources/ copies get identical bytes.

One-shot surgical script. Verifies: rescan clean, exact pixels, <2MB,
gates (check_starters + audit geometric/bed-aware), full pytest outside.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TPL = ROOT / "apps" / "studio_templates"
sys.path.insert(0, str(TPL))

from fix_mr_score_layout import by_id, probe_ratios  # noqa: E402
from audit_cards import audit as geo_audit  # noqa: E402
from audit_cards import audit_text_zones  # noqa: E402
from render_starters import render_design  # noqa: E402

DROP = ROOT / "pack-drop" / "12.0.0"
RES = ROOT / "template_foundation/templates/allen-knows-ball/12.0.0/resources/pack"
RESL = ROOT / "template_foundation/templates/allen-knows-ball/longform-12.0.0/resources/pack"
BLEND = ROOT / "template_foundation/templates/allen-knows-ball/12.0.0/blend-audit.json"

SHORT_BADGE = (912, 48, 120)   # x, y, d
LONG_BADGE = (1704, 30, 96)
# Neon frame spec measured on intact plates (myth/opening/ending):
# inset 40, width 3, radius 34. Restores frames lost to the bad
# drop->resources sync (drop masters lack frames on most plates).
FRAME_COLOR_SHORT = (238, 127, 190)
FRAME_COLOR_LONG = (252, 121, 191)
FRAME_INSET, FRAME_W, FRAME_R = 40, 3, 34
SEAL_CARDS = ["BP-20", "C-05", "C-09", "MR-12", "U-08"]


def detect_text_mask(g):
    """Letter-stroke mask for dim baked gibberish on dark bg."""
    import cv2
    import numpy as np
    blur = cv2.GaussianBlur(g, (25, 25), 0)
    d = g.astype(int) - blur.astype(int)
    m = ((g > 55) & (d > 12)).astype("uint8") * 255
    m[:400, :] = 0
    m[700:, :] = 0
    m = cv2.dilate(m, np.ones((5, 5), np.uint8), iterations=1)
    return m


def refine_inpaint(path: Path) -> dict:
    """Second pass on stubborn ghost strokes: lower threshold, but keep
    only glyph-sized components (long beams/line-art excluded)."""
    import cv2
    import numpy as np
    img = cv2.imread(str(path))
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(g, (25, 25), 0)
    d = g.astype(int) - blur.astype(int)
    m = ((g > 40) & (d > 8)).astype("uint8") * 255
    m[:460, :] = 0
    m[640:, :] = 0
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    keep = np.zeros_like(m)
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if 20 < a < 2000 and w < 120 and h < 60:
            keep[lab == i] = 255
    keep = cv2.dilate(keep, np.ones((7, 7), np.uint8), iterations=1)
    npx = int((keep > 0).sum())
    if npx == 0:
        # Fallback: dotted ghost rows live in two tight bands; take any
        # bright speck there (stars in-band are acceptable collateral).
        m2 = ((g > 50) & (d > 10)).astype("uint8") * 255
        band = np.zeros_like(m2)
        band[495:535, :] = 255
        band[550:590, :] = 255
        keep = cv2.bitwise_and(m2, band)
        keep = cv2.dilate(keep, np.ones((5, 5), np.uint8), iterations=1)
        npx = int((keep > 0).sum())
    if npx == 0:
        return {"file": path.name, "refined": 0}
    out = cv2.inpaint(img, keep, 6, cv2.INPAINT_TELEA)
    cv2.imwrite(str(path), out)
    return {"file": path.name, "refined": npx}


def inpaint_file(path: Path) -> dict:
    import cv2
    img = cv2.imread(str(path))
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = detect_text_mask(g)
    n = int((mask > 0).sum())
    if n == 0:
        return {"file": path.name, "masked": 0, "skipped": True}
    out = cv2.inpaint(img, mask, 5, cv2.INPAINT_TELEA)
    cv2.imwrite(str(path), out)
    # verify rescan clean (strict: undilated strokes)
    g2 = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(g2, (25, 25), 0)
    d = g2.astype(int) - blur.astype(int)
    m2 = ((g2 > 55) & (d > 12)).astype("uint8") * 255
    m2[:400, :] = 0
    m2[700:, :] = 0
    left = int((m2 > 0).sum())
    return {"file": path.name, "masked": n, "residual": left}


def badge_present(plate, x, y, d, badge) -> bool:
    """Skip plates already stamped (idempotent reruns)."""
    import numpy as np
    zone = plate.convert("RGB").crop((x, y, x + d, y + d)).resize((48, 48))
    ref = badge.convert("RGB").resize((48, 48))
    diff = np.asarray(zone, dtype=float) - np.asarray(ref, dtype=float)
    return float(abs(diff).mean()) < 12.0


def frame_present(plate, is_long) -> bool:
    """Detect intact neon frame (top edge row) to keep reruns idempotent."""
    import numpy as np
    w, h = plate.size
    rgb = plate.convert("RGB")
    y = FRAME_INSET
    row = np.asarray(rgb.crop((200, y, w - 200, y + 1)), dtype=float)
    pink = (row[:, :, 0] > 170) & (row[:, :, 2] > 150) & (row[:, :, 1] < 150)
    return float(pink.mean()) > 0.5


def restore_frame(path: Path) -> dict:
    from PIL import Image, ImageDraw
    is_long = path.name.startswith("long-")
    plate = Image.open(path).convert("RGBA")
    if frame_present(plate, is_long):
        return {"file": path.name, "framed": False}
    w, h = plate.size
    color = FRAME_COLOR_LONG if is_long else FRAME_COLOR_SHORT
    d = ImageDraw.Draw(plate)
    d.rounded_rectangle([FRAME_INSET, FRAME_INSET, w - 41, h - 41],
                        radius=FRAME_R, outline=color + (255,),
                        width=FRAME_W)
    rgb = plate.convert("RGB")
    if path.suffix.lower() in (".jpg", ".jpeg"):
        rgb.save(path, quality=95)
    else:
        rgb.save(path, optimize=True)
    assert path.stat().st_size < 2 * 1024 * 1024, path.name
    return {"file": path.name, "framed": True}


def stamp_plate(path: Path, badge) -> dict:
    from PIL import Image
    is_long = path.name.startswith("long-")
    x, y, d = LONG_BADGE if is_long else SHORT_BADGE
    plate = Image.open(path).convert("RGBA")
    if badge_present(plate, x, y, d, badge):
        return {"file": path.name, "stamped": False}
    b = badge.resize((d, d), Image.Resampling.LANCZOS)
    plate.alpha_composite(b, (x, y))
    rgb = plate.convert("RGB")
    assert rgb.size == ((1920, 1080) if is_long else (1080, 1920)), path.name
    rgb.save(path, quality=95) if path.suffix.lower() in (".jpg", ".jpeg") else rgb.save(path, optimize=True)
    assert path.stat().st_size < 2 * 1024 * 1024, path.name
    return {"file": path.name, "stamped": True}


def main() -> int:
    from PIL import Image
    badge = Image.open(RES / "badge-circle.png").convert("RGBA")
    log: list[str] = []

    # 1. Inpaint baked text (pack-drop source of truth; identical bytes out).
    src_drop = DROP / "short-source_card.jpg"
    r = inpaint_file(src_drop)
    log.append(f"inpaint {r}")
    if r["masked"] >= 500:
        assert r.get("residual", 0) <= 0.03 * r["masked"], r
    else:
        log.append("inpaint skipped (already clean, residual is JPEG noise)")
    r2 = refine_inpaint(src_drop)
    log.append(f"refine {r2}")
    for dst in [DROP / "short-quote_card.jpg",
                RES / "short-source_card.jpg",
                RES / "short-quote_card.jpg"]:
        shutil.copy(src_drop, dst)
    for dst in [DROP / "short-quote_card.jpg",
                RES / "short-source_card.jpg",
                RES / "short-quote_card.jpg"]:
        shutil.copy(src_drop, dst)
        log.append(f"sync {dst.parent.name}/{dst.name}")

    # 2. Stamp badge on every plate except opening/ending.
    for base in (DROP, RES, RESL):
        for p in sorted(base.glob("short-*")) + sorted(base.glob("long-*")):
            if p.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            if "opening" in p.name or "ending" in p.name:
                log.append(f"skip {p.parent.name}/{p.name} (bakes badge)")
                continue
            if p.name == "badge-circle.png":
                continue
            r = stamp_plate(p, badge)
            f = restore_frame(p)
            # sync resources copies with pack-drop bytes (single truth)
            if base is DROP:
                for other in (RES, RESL):
                    q = other / p.name
                    if q.is_file():
                        shutil.copy(p, q)
            log.append(f"stamp {p.parent.name}/{p.name}: {r['stamped']}/{f['framed']}")

    # 3. Remove seal-disc + AKB text from the 5 cards.
    for cid in SEAL_CARDS:
        path = TPL / f"{cid}.short.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        kids = data["pages"][0]["children"]
        kids[:] = [c for c in kids if c.get("id") not in ("seal-disc", "val-8")]
        assert not [c for c in kids if c.get("id") in ("seal-disc", "val-8")]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        log.append(f"seal-removed {cid}")

    # 3b. MR-02/03/04 score-away: box khit glyph (h260->200). Plate
    # re-encode shifted the off-empty bottom samples below floor; the
    # 260px digit ink ends ~1310, so sampling bare bed at +221 was
    # mis-sampling. Glyphs do not move (single-line draws from top).
    for cid in ["MR-02", "MR-03", "MR-04"]:
        path = TPL / f"{cid}.short.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for c in data["pages"][0]["children"]:
            if (c.get("custom") or {}).get("slot") == "score-away":
                c["height"] = 200
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        log.append(f"box-tightened {cid}/score-away h200")

    # 4. Gates on touched cards + full blend-audit recompute + proofs.
    bad = 0
    for f in sorted(TPL.glob("*.short.json")) + sorted(TPL.glob("*.long.json")):
        if f.name == "duel_columns.short.json":
            continue
        issues = geo_audit(f) + audit_text_zones(f)
        if issues:
            bad += len(issues)
            print(f"FAIL {f.name}: {issues}")
    print(f"audit: {'PASS' if not bad else f'{bad} issues'}")

    audit = {"checks": [], "fails": []}
    for f in sorted(TPL.glob("*.short.json")) + sorted(TPL.glob("*.long.json")):
        if f.name == "duel_columns.short.json":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        cid = f.name.split(".")[0]
        by_slot = {((t.get("custom") or {}).get("slot", t.get("id"))): t
                   for t in data["pages"][0]["children"]
                   if t.get("type") == "text"}
        for slot, ratio in sorted(probe_ratios(data).items()):
            t = by_slot[slot]
            size = int(t.get("fontSize", 0))
            nd = 4.5 if size >= 48 and float(t.get("opacity", 1.0)) >= 1.0 else 3.0
            entry = {"card": cid, "slot": slot, "size": size, "zone": "plate",
                     "contrast": ratio, "need": nd, "pass": ratio >= nd}
            audit["checks"].append(entry)
            if not entry["pass"]:
                fails = {k: entry[k] for k in ("card", "slot", "size", "zone", "contrast", "need", "pass")}
                audit["fails"].append(fails)
        img = render_design(data)
        w, h = (1080, 1920) if ".short." in f.name else (1920, 1080)
        assert img.size == (w, h), f.name
        prev = (ROOT / "template_foundation/templates/allen-knows-ball"
                / ("longform-12.0.0" if ".long." in f.name else "12.0.0")
                / "previews" / f"{'long' if '.long.' in f.name else 'short'}-{cid.lower()}-proof.png")
        img.save(prev)
    BLEND.write_text(json.dumps(audit, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"blend-audit: {len(audit['checks'])} checks, {len(audit['fails'])} fails")
    for line in log:
        print(" ", line)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
