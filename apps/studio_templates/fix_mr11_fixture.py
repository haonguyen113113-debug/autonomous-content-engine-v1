"""Surgical fix: MR-11 fixture teaser per owner-designed plate.

Owner layout (locked): 2 neon rect frames = badge slots (monograms
centered inside, no rings — rect slots, not circles); team names BELOW
badges; top caption + bottom date pushed near edges in dark low-detail
zones. Plate burst between frames is the VS — the dead invisible JSON
"VS" text is removed.
One-shot surgical script. Run once, then gates.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TPL = ROOT / "apps" / "studio_templates"
sys.path.insert(0, str(TPL))

from fix_mr_score_layout import by_id, fit_font, probe_ratios  # noqa: E402
from audit_cards import audit as geo_audit  # noqa: E402
from audit_cards import audit_text_zones  # noqa: E402
from render_starters import render_design  # noqa: E402

PREVIEWS = (ROOT / "template_foundation/templates/allen-knows-ball"
            / "12.0.0/previews")
BLEND_AUDIT = (ROOT / "template_foundation/templates/allen-knows-ball"
               / "12.0.0/blend-audit.json")
CID = "MR-11"


def main() -> int:
    path = TPL / f"{CID}.short.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    kids = data["pages"][0]["children"]

    # Drop circle rings (rect slots) and the dead invisible VS text.
    for eid in ("ring-250-910", "ring-830-910", "val-7"):
        for c in [c for c in kids if c.get("id") == eid]:
            kids.remove(c)

    # Top caption near the top edge (dark, sparse stars).
    comp = by_id(kids, "val-4")
    comp.update({"fontFamily": "Be Vietnam Pro", "fontSize": 64,
                 "x": 76, "y": 185, "width": 928, "height": 80,
                 "align": "center",
                 "text": "V\u00f2ng 13 \u2022 V.League 1"})
    fit_font(comp)

    # Monograms centered on TRUE frame centers (measured neon edges:
    # L x101-392 -> cx 246, R x626-978 -> cx 802; vertical center ~1012).
    # Box y set so INK (not box) centers on it.
    for eid, cx, txt in (("val-16", 246, "HN"), ("val-18", 810, "N\u0110")):
        crest = by_id(kids, eid)
        crest.update({"x": cx - 100, "y": 962, "width": 200, "height": 100,
                      "fontSize": 72, "align": "center", "text": txt})
        fit_font(crest)

    # True centers override: away frame inner rect x737-977/y815-1142
    # (measured, not eyeballed) -> cx 857, cy 978. NĐ ink centers on it.
    # HN stays (already centered in its grid per owner).
    by_id(kids, "val-18").update({"x": 757, "y": 933})
    for eid in ("val-16",):
        by_id(kids, eid).update({"y": 967})

    # Team names BELOW the badges, bigger (64), boxes widened to frame
    # centers (246/802). SAME baseline; optical axis by INK-MASS centers:
    # dense-ink measurement on proof: HN 1257-1319 (c1288), ND 1255-1302
    # (c1278.5) — HN's dot-below runs deeper, so equal tops read as
    # misaligned. ND sits +10 to share one optical center (c1288).
    for eid, x, y in (("val-5", 76, 1255), ("val-8", 632, 1265)):
        name = by_id(kids, eid)
        name.update({"fontFamily": "Be Vietnam Pro", "fontSize": 64,
                     "x": x, "y": y, "width": 340, "height": 70,
                     "align": "center"})
        fit_font(name)

    # Date/venue near the bottom edge (dark flat zone). Slot renamed
    # when -> date to match the registry (MR-11: home/away/date).
    when = by_id(kids, "val-9")
    when.update({"x": 130, "y": 1610, "width": 820, "height": 54,
                 "align": "center", "fontSize": 44,
                 "text": "Ch\u1ee7 nh\u1eadt \u2022 19g00 "
                         "\u2022 H\u00e0ng \u0110\u1eaby"})
    when["custom"]["slot"] = "date"
    fit_font(when)

    for c in kids:
        if (c.get("type") == "text"
                and (c.get("custom") or {}).get("slot") == "credit"):
            c["text"] = "VPF \u2022 12/10/2026"
            fit_font(c)

    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")

    issues = geo_audit(path) + audit_text_zones(path)
    print(f"{CID}: {'PASS' if not issues else issues}")

    img = render_design(data)
    assert img.size == (1080, 1920)
    out = PREVIEWS / "short-mr-11-proof.png"
    img.save(out)
    print(f"wrote {out.name} {out.stat().st_size // 1024}KB")

    audit = json.loads(BLEND_AUDIT.read_text(encoding="utf-8"))
    audit["checks"] = [e for e in audit.get("checks", [])
                       if e.get("card") != CID]
    fails = [f for f in audit.get("fails", []) if f.get("card") != CID]
    by_slot = {((t.get("custom") or {}).get("slot", t.get("id"))): t
               for t in data["pages"][0]["children"]
               if t.get("type") == "text"}
    for slot, ratio in sorted(probe_ratios(data).items()):
        t = by_slot[slot]
        size = int(t.get("fontSize", 0))
        zone = "plate"
        nd = (4.5 if size >= 48 and float(t.get("opacity", 1.0)) >= 1.0
              else 3.0)
        entry = {"card": CID, "slot": slot, "size": size, "zone": zone,
                 "contrast": ratio, "need": nd, "pass": ratio >= nd}
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
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
