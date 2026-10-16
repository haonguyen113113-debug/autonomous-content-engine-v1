"""Surgical fix: MR-02/03/04 score layout per owner-approved geometry.

Owner layout (locked):
  top-center winner name / left badge + right NUMBER per half /
  bottom-center loser name. Winner number hero-large, loser dimmer.
Details (allowed): scrim pill covers text box, real credit sample,
sentence-case context, MR-03 half-time cue, MR-04 scorer in context,
home/away Tektur -> Be Vietnam Pro (Tektur U+00C0 renders as macron),
badge centers aligned to number centers, numbers clear of neon lines.

One-shot surgical script (NOT rework36.py). Run once, then gates.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TPL = ROOT / "apps" / "studio_templates"
sys.path.insert(0, str(TPL))

from audit_cards import audit as geo_audit  # noqa: E402
from audit_cards import audit_text_zones  # noqa: E402
from render_starters import font_for, render_design  # noqa: E402

PREVIEWS = (ROOT / "template_foundation/templates/allen-knows-ball"
            / "12.0.0/previews")
BLEND_AUDIT = (ROOT / "template_foundation/templates/allen-knows-ball"
               / "12.0.0/blend-audit.json")

CONTEXT = {
    "MR-02": "V.League \u2022 T\u1ed1i nay \u2022 H\u00e0ng \u0110\u1eaby",
    "MR-03": "H\u1ebft hi\u1ec7p 1 \u2022 S\u00e2n H\u00e0ng \u0110\u1eaby",
    "MR-04": ("B\u00e0n th\u1eafng ph\u00fat 67 \u2022 V\u0103n Quy\u1ebft "
              "\u2022 H\u00e0ng \u0110\u1eaby"),
}
CREDIT = "VPF \u2022 12/10/2026"


def by_id(children: list[dict], eid: str) -> dict:
    for c in children:
        if c.get("id") == eid:
            return c
    raise KeyError(eid)


def fit_font(text_el: dict) -> None:
    """Step down fontSize until single-line text fits its box (min 30)."""
    content = str(text_el.get("text", ""))
    size = int(text_el.get("fontSize", 40))
    while size > 30:
        font = font_for(text_el.get("fontFamily", "Be Vietnam Pro"),
                        text_el.get("fontWeight", "normal"), size)
        box = font.getbbox(content)
        if box[2] - box[0] <= float(text_el.get("width", 0)) + 2:
            break
        size -= 2
    text_el["fontSize"] = size


def fix_card(cid: str) -> dict:
    path = TPL / f"{cid}.short.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    kids = data["pages"][0]["children"]

    # 1. Context scrim pill covers the text box with padding.
    scrim = by_id(kids, "scrim-context")
    scrim.update({"x": 110, "y": 165, "width": 860, "height": 80})
    ctx = by_id(kids, "val-context")
    ctx["text"] = CONTEXT[cid]
    fit_font(ctx)

    # 2. Team names: Tektur -> Be Vietnam Pro (Tektur grave marks broken).
    for eid in ("val-home", "val-away"):
        name = by_id(kids, eid)
        name["fontFamily"] = "Be Vietnam Pro"
        fit_font(name)
    # Winner name breathing room above the hero numeral (dot-below mark).
    by_id(kids, "val-home").update({"y": 355})

    # 3. Winner number + badge: one left-shifted group.
    # Badge x256 (owner: nudge left); number ink recentered DOWN onto the
    # badge center (measured ink center 642 vs badge 700 -> box y520->578).
    score = by_id(kids, "val-score")
    score.update({"x": 534, "y": 578, "width": 250})
    # Winner badge center (700) == winner number ink center (700).
    by_id(kids, "ring-crest-winner").update({"x": 256, "y": 605})
    by_id(kids, "val-crest-winner").update({"x": 256, "y": 653})

    # 4. Loser number + badge: same columns, ink recentered DOWN onto the
    # badge center (measured ink center 1091 vs badge 1220 -> box y1000->1129).
    by_id(kids, "val-score-away").update({"x": 534, "y": 1129, "width": 250})
    # Loser badge center (1220) == loser number ink center (1220).
    # Row symmetry kept: 700 + 1220 = 2 * 960 (mid-axis).
    by_id(kids, "ring-crest-loser").update({"x": 256, "y": 1125})
    by_id(kids, "val-crest-loser").update({"x": 256, "y": 1173})

    # 4b. Midfield bars sit exactly on the mid-axis y960.
    by_id(kids, "deco-bar1").update({"y": 954})
    by_id(kids, "deco-bar2").update({"y": 954})
    # Loser name nudged up for top/bottom symmetry around the axis.
    by_id(kids, "val-away").update({"y": 1470})

    # 5. Real credit sample (was placeholder "Ngu\u1ed3n + ng\u00e0y").
    credit = by_id(kids, "val-credit")
    credit["text"] = CREDIT
    fit_font(credit)

    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    return data


def probe_ratios(data: dict) -> dict[str, float]:
    """Bed-aware min contrast per slot (same floor logic as blend audit)."""
    import copy as _copy
    from audit_cards import blend, contrast, hex_rgb
    bg_data = _copy.deepcopy(data)
    for c in bg_data["pages"][0].get("children", []):
        if c.get("type") == "text":
            c["showInExport"] = False
    bg_img = render_design(bg_data).convert("RGB")
    px = bg_img.load()
    w, h = bg_img.size
    out: dict[str, float] = {}
    for t in data["pages"][0]["children"]:
        if t.get("type") != "text" or t.get("showInExport") is False:
            continue
        slot = (t.get("custom") or {}).get("slot", t.get("id"))
        cx = min(w - 1, max(0, int(float(t["x"]) + float(t["width"]) / 2)))
        ratios = []
        for frac in (0.15, 0.5, 0.85):
            py = min(h - 1, max(0, int(float(t["y"])
                                       + float(t["height"]) * frac)))
            bgc = px[cx, py]
            fg = blend(hex_rgb(t.get("fill", "#F2F6FF")),
                       tuple(float(v) for v in bgc),
                       float(t.get("opacity", 1.0)))
            ratios.append(contrast(fg, tuple(float(v) for v in bgc)))
        out[slot] = round(min(ratios), 2)
    return out


def main() -> int:
    cids = ["MR-02", "MR-03", "MR-04"]
    datas = {cid: fix_card(cid) for cid in cids}

    # Gates per card: geometric audit + bed-aware zones.
    bad = 0
    for cid in cids:
        issues = geo_audit(TPL / f"{cid}.short.json")
        issues += audit_text_zones(TPL / f"{cid}.short.json")
        print(f"{cid}: {'PASS' if not issues else issues}")
        bad += len(issues)

    # Re-render the 3 proofs (pixel-exact names expected by tests).
    for cid, data in datas.items():
        img = render_design(data)
        assert img.size == (1080, 1920), cid
        out = PREVIEWS / f"short-{cid.lower()}-proof.png"
        img.save(out)
        print(f"wrote {out.name} {out.stat().st_size // 1024}KB")

    # Refresh blend-audit entries for the 3 cards (keep slot need values).
    audit = json.loads(BLEND_AUDIT.read_text(encoding="utf-8"))
    need = {(e["card"], e["slot"]): (e["need"], e["zone"])
            for e in audit.get("checks", [])}
    audit["checks"] = [e for e in audit.get("checks", [])
                       if e.get("card") not in cids]
    fails = [f for f in audit.get("fails", [])
             if f.get("card") not in cids]
    for cid, data in datas.items():
        for slot, ratio in sorted(probe_ratios(data).items()):
            size = next(int(t.get("fontSize", 0))
                        for t in data["pages"][0]["children"]
                        if t.get("type") == "text"
                        and (t.get("custom") or {}).get("slot",
                                                        t.get("id")) == slot)
            nd, zone = need.get((cid, slot), (4.5, "plate"))
            entry = {"card": cid, "slot": slot, "size": size,
                     "zone": zone, "contrast": ratio, "need": nd,
                     "pass": ratio >= nd}
            audit["checks"].append(entry)
            if not entry["pass"]:
                fails.append({k: entry[k] for k in
                              ("card", "slot", "size", "zone",
                               "contrast", "need", "pass")})
    audit["fails"] = fails
    BLEND_AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=1)
                           + "\n", encoding="utf-8")
    print(f"blend-audit: {len(audit['checks'])} checks, "
          f"{len(fails)} fails")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
