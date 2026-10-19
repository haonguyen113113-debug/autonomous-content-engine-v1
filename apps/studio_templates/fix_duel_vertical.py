"""Surgical fix: duel family vertical rhythm (BP-07, BP-10, BP-14, C-07).

Disease: header crowded (ring bottom touches label-0, label-number gap
6px), bottom half empty (550-690px void), winbars on wrong/draw sides,
Tektur broken Vietnamese diacritics, placeholder samples/credit.
Cure: even row pitch, breathing room top/middle/bottom, bars only under
row winners (draw rows lose their bar), Be Vietnam Pro for Vietnamese
text (Tektur kept for latin digits/monograms), real samples + credit.

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
CREDIT = "VPF \u2022 12/10/2026"
HOME_BAR_X, AWAY_BAR_X = 155, 665  # under column centers 285 / 795

# cid -> (texts, n_rows, label_ys, number_ys, bar_xs or None=remove)
CFG = {
    "BP-07": {
        "texts": {"val-3": "CHUY\u1ec2N NH\u01af\u1ee2NG",
                  "val-4": "VIETTEL", "val-5": "NAM \u0110\u1ecaNH",
                  "val-7": "VT", "val-9": "N\u0110",
                  "val-12": "Ph\u00ed chuy\u1ec3n nh\u01b0\u1ee3ng",
                  "val-17": "B\u00e0n th\u1eafng"},
        "labels": ["val-12", "val-17"], "label_ys": [700, 1150],
        "numbers": [["val-13", "val-14"], ["val-18", "val-19"]],
        "number_ys": [760, 1210], "bars": [AWAY_BAR_X, HOME_BAR_X],
    },
    "BP-10": {
        "texts": {"val-3": "\u0110\u1ed0I \u0110\u1ea6U",
                  "val-12": "\u0110\u1ed1i \u0111\u1ea7u",
                  "val-17": "Danh hi\u1ec7u"},
        "labels": ["val-12", "val-17"], "label_ys": [700, 1150],
        "numbers": [["val-13", "val-14"], ["val-18", "val-19"]],
        "number_ys": [760, 1210], "bars": [HOME_BAR_X, None],
    },
    "BP-14": {
        "texts": {"val-3": "\u0110\u1ed0I \u0110\u1ea6U",
                  "val-4": "H\u00c0 N\u1ed8I",
                  "val-5": "B\u00ccNH \u0110\u1ecaNH",
                  "val-7": "HN", "val-9": "B\u0110",
                  "val-12": "B\u00e0n th\u1eafng",
                  "val-17": "Ki\u1ebfn t\u1ea1o"},
        "labels": ["val-12", "val-17"], "label_ys": [700, 1150],
        "numbers": [["val-13", "val-14"], ["val-18", "val-19"]],
        "number_ys": [760, 1210], "bars": [HOME_BAR_X, None],
    },
    "C-07": {
        "texts": {"val-3": "\u0110\u1ed0I \u0110\u1ea6U",
                  "val-12": "B\u00e0n th\u1eafng",
                  "val-17": "Ki\u1ebfn t\u1ea1o",
                  "val-21": "S\u00fat tr\u00fang \u0111\u00edch"},
        "labels": ["val-12", "val-17", "val-21"],
        "label_ys": [660, 930, 1190],
        "numbers": [["val-13", "val-14"], ["val-18", "val-19"],
                    ["val-22", "val-23"]],
        "number_ys": [730, 1000, 1260],
        "bars": [None, None, None],
        # Winner emphasis WITHOUT tone difference (owner 16/10: both
        # columns stay PAPER 1.0): an AMBER winner dot under each winning
        # number. Draw rows get none. Replaces bars/scrims/tone-encoding.
        "dots": ["val-13", "val-22"],
        # Labels stay PAPER 0.7 (approved brighter than SLATE).
        "opacity": {"val-12": 0.7, "val-17": 0.7, "val-21": 0.7},
        "label_fill": "#F2F6FF",
    },
}
BAR_Y_2ROW = [934, 1384]
BAR_Y_3ROW = [914, 0, 1419]
VI_TEXT = {"val-3", "val-4", "val-5", "val-12", "val-17", "val-21"}


def fix_card(cid: str) -> dict:
    cfg = CFG[cid]
    path = TPL / f"{cid}.short.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    kids = data["pages"][0]["children"]

    # Header: title / teams / rings with breathing room.
    title = by_id(kids, "val-3")
    title.update({"fontFamily": "Be Vietnam Pro", "fontSize": 80})
    if "val-3" in cfg["texts"]:
        title["text"] = cfg["texts"]["val-3"]
    fit_font(title)
    for eid in ("val-4", "val-5"):
        team = by_id(kids, eid)
        team.update({"fontFamily": "Be Vietnam Pro", "y": 390})
        if eid in cfg["texts"]:
            team["text"] = cfg["texts"][eid]
        fit_font(team)
    for rid in ("ring-290-550", "ring-790-550"):
        by_id(kids, rid).update({"y": 490})
    for eid in ("val-7", "val-9"):
        crest = by_id(kids, eid)
        crest.update({"y": 525})
        if eid in cfg["texts"]:
            crest["text"] = cfg["texts"][eid]
        fit_font(crest)

    # Rows: even pitch, label above its numbers.
    for lid, y in zip(cfg["labels"], cfg["label_ys"]):
        label = by_id(kids, lid)
        label.update({"fontFamily": "Be Vietnam Pro", "fontSize": 34,
                      "y": y, "height": 44})
        if lid in cfg["texts"]:
            label["text"] = cfg["texts"][lid]
        if "label_fill" in cfg:
            label["fill"] = cfg["label_fill"]
        fit_font(label)
    for (home_id, away_id), y in zip(cfg["numbers"], cfg["number_ys"]):
        by_id(kids, home_id).update({"y": y})
        by_id(kids, away_id).update({"y": y})
    for eid, op in cfg.get("opacity", {}).items():
        el = by_id(kids, eid)
        if abs(float(el.get("opacity", 1.0)) - op) > 1e-9:
            el["opacity"] = op
    # C-07 only: loser numbers back to full PAPER (both columns same
    # color; winner encoding moves to the dots). BP trio keeps its
    # original 0.8 dimming (out of scope for this change).
    if cid == "C-07":
        for lid in ("val-14", "val-23"):
            loser = by_id(kids, lid)
            if "opacity" in loser:
                del loser["opacity"]
    # Winner dots v2 (research-backed, stronger): solid AMBER core d34 +
    # AMBER halo d44 at 0.25 (glow presence, deterministic, palette-only).
    # Halo clears the number box above by 5px and the next label below,
    # so the decor-cover gate stays mute by construction.
    # Precedent: FotMob-style W/D/L outcome dots + broadcast gold accent
    # for winners; weight/hue parity kept per BBC/ESPN winner convention
    # (both columns PAPER, no wash on losers).
    for ref_id in cfg.get("dots", []):
        ref = by_id(kids, ref_id)
        did = f"dot-{ref_id}"
        hid = f"halo-{ref_id}"
        for old in [c for c in kids
                    if c.get("id") in (did, hid)]:
            kids.remove(old)  # recreate to current spec (idempotent)
        cx = float(ref["x"]) + float(ref["width"]) / 2
        top = float(ref["y"]) + float(ref["height"]) + 10
        kids.insert(kids.index(ref) + 1,
                    {"id": did, "type": "figure", "subType": "circle",
                     "x": cx - 17, "y": top, "width": 34, "height": 34,
                     "fill": "#FFB03A",
                     "selectable": False, "draggable": False,
                     "resizable": False, "removable": False})
        kids.insert(kids.index(ref) + 1,
                    {"id": hid, "type": "figure", "subType": "circle",
                     "x": cx - 22, "y": top - 5, "width": 44, "height": 44,
                     "fill": "#FFB03A", "opacity": 0.25,
                     "selectable": False, "draggable": False,
                     "resizable": False, "removable": False})

    # Winner bars under the winning column; draw rows lose their bar.
    bar_ys = BAR_Y_3ROW if len(cfg["bars"]) == 3 else BAR_Y_2ROW
    for i, (bx, by) in enumerate(zip(cfg["bars"], bar_ys)):
        found = [c for c in kids if c.get("id") == f"winbar-{i}"]
        if bx is None:
            for c in found:
                kids.remove(c)  # draw rows: no winner bar (idempotent)
        elif not found:
            raise KeyError(f"{cid} winbar-{i} missing but required")
        else:
            found[0].update({"x": bx, "y": by})

    # Scrim pills behind labels that fail contrast on the bright lower bed
    # (row-1 labels of 2-row cards, row-2 label of C-07). VOID 0.45 with
    # padding, inserted BEFORE the text (paint order keeps cover-gate mute;
    # VOID == page bg so the decor gate exempts it too).
    # Owner 16/10: REMOVE all bottom scrims (aesthetic call — owner is the
    # final standard). Cleanup is idempotent: delete any scrim-* elements.
    for c in [c for c in kids if c.get("id", "").startswith("scrim-")]:
        kids.remove(c)

    # Real credit sample.
    for c in kids:
        if (c.get("type") == "text"
                and (c.get("custom") or {}).get("slot") == "credit"):
            c["text"] = CREDIT
            fit_font(c)

    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    return data


def main() -> int:
    datas = {cid: fix_card(cid) for cid in CFG}
    bad = 0
    for cid in CFG:
        issues = geo_audit(TPL / f"{cid}.short.json")
        issues += audit_text_zones(TPL / f"{cid}.short.json")
        print(f"{cid}: {'PASS' if not issues else issues}")
        bad += len(issues)
    for cid, data in datas.items():
        img = render_design(data)
        assert img.size == (1080, 1920), cid
        out = PREVIEWS / f"short-{cid.lower()}-proof.png"
        img.save(out)
        print(f"wrote {out.name} {out.stat().st_size // 1024}KB")

    # Needs follow the enforced audit_cards floors (4.5 for full-opacity
    # type >= 48, else 3.0) — the legacy file's inverted small-text needs
    # match no enforced gate, so recomputed entries use the real floors.
    audit = json.loads(BLEND_AUDIT.read_text(encoding="utf-8"))
    audit["checks"] = [e for e in audit.get("checks", [])
                       if e.get("card") not in CFG]
    fails = [f for f in audit.get("fails", [])
             if f.get("card") not in CFG]
    for cid, data in datas.items():
        by_slot = {((t.get("custom") or {}).get("slot", t.get("id"))): t
                   for t in data["pages"][0]["children"]
                   if t.get("type") == "text"}
        for slot, ratio in sorted(probe_ratios(data).items()):
            t = by_slot[slot]
            size = int(t.get("fontSize", 0))
            # zone: rings carry the crests, everything else sits on plate.
            ringed = any(c.get("type") == "figure"
                         and c.get("subType") == "circle"
                         and c.get("x", 0) <= float(t["x"]) <= c.get("x", 0)
                         for c in data["pages"][0]["children"])
            zone = "backing:#060913" if ("crest" in slot or ringed) else "plate"
            nd = (4.5 if size >= 48 and float(t.get("opacity", 1.0)) >= 1.0
                  else 3.0)
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
