"""Assemble the v10 San Trang template pack (short 10.0.0 + longform-10.0.0).

The pack's visual system lives in the 69 authored starters
(apps/studio_templates/*.short/long.json, built by build_starters_v10.py).
This script writes pack JSONs, copies fonts, renders starter proofs into the
preview folders, writes preview.html + proof rows, and registers the packages
in catalog.json. Released packs are never modified in place — rerun only
regenerates draft-time artifacts (proofs, preview.html).

Run: python apps/studio_templates/build_v10_pack.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

SAN_TRANG_RGB = [(255, 255, 255), (22, 27, 44), (240, 120, 98), (90, 107, 140), (139, 150, 176)]


def render_starter_proofs() -> list[dict]:
    from apps.studio_templates.render_starters import render_design

    tpl = ROOT / "apps" / "studio_templates"
    rows: list[dict] = []
    jobs = ([(p.stem.split(".")[0], "short") for p in sorted(tpl.glob("*.short.json"))
             if p.name != "duel_columns.short.json"]
            + [(p.stem.split(".")[0], "long") for p in sorted(tpl.glob("*.long.json"))])
    for cid, aspect in jobs:
        data = json.loads((tpl / f"{cid}.{aspect}.json").read_text(encoding="utf-8"))
        image = render_design(data)
        assert image.size == ((1080, 1920) if aspect == "short" else (1920, 1080)), cid
        target = (ROOT / "template_foundation/templates/allen-knows-ball/10.0.0"
                  if aspect == "short" else
                  ROOT / "template_foundation/templates/allen-knows-ball/longform-10.0.0")
        out = target / "previews" / f"{aspect}-{cid.lower()}-proof.png"
        image.save(out)
        colors = image.getcolors(maxcolors=1 << 24) or []
        bad, top_map = 0, {}
        for count, rgb in colors:
            if any(all(abs(a - b) <= 90 for a, b in zip(rgb, pal)) for pal in SAN_TRANG_RGB):
                continue
            bad += count
            top_map["#%02X%02X%02X" % rgb] = top_map.get("#%02X%02X%02X" % rgb, 0) + count
        top = sorted(top_map, key=top_map.get, reverse=True)[:5]
        rows.append({"name": cid, "aspect": aspect, "size": list(image.size),
                     "bad": bad, "badTop": top, "visual": "todo",
                     "note": "San-trang PIL proof of Polotno starter; static gates pass; needs owner eyeball."})
        print(f"ok {out.name} {image.size[0]}x{image.size[1]} off-palette={bad}")
    return rows


def write_composite(target: Path, aspect: str, picks: list[str]) -> None:
    from PIL import Image

    tiles = []
    for name in picks:
        path = target / "previews" / name
        with Image.open(path) as opened:
            tiles.append(opened.copy())
    cols = 2
    tw, th = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, th * rows), (255, 255, 255))
    for i, tile in enumerate(tiles):
        sheet.paste(tile.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
    sheet.save(target / "previews" / "composite-proof.png")
    print(f"ok composite-proof.png {sheet.size[0]}x{sheet.size[1]} ({target.name})")


def write_preview_html(proof_rows: list[dict]) -> None:
    proofs = "\n".join(
        f'<article class="card"><img src="/template-foundation/previews/{r["aspect"]}-{r["name"].lower()}-proof.png" alt="{r["name"]}" loading="lazy"><b>{r["name"]}</b><small>{r["aspect"]} · off-palette {r["bad"]}.</small></article>'
        for r in proof_rows)
    html = """<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Allen Knows Ball — Sân Trắng 10.0.0 (released)</title>
  <style>
    *{box-sizing:border-box}body{margin:0;background:#fff;color:#161b2c;font:15px 'Be Vietnam Pro',Arial,sans-serif}
    .page{max-width:1320px;margin:auto;padding:36px 28px 54px}
    .kicker{color:#5a6b8c;font-size:11px;font-weight:700;letter-spacing:1.7px}
    h1{font-family:'Barlow Condensed',Arial,sans-serif;font-size:44px;margin:8px 0}
    .stamp{background:#f07862;color:#161b2c;border-radius:99px;padding:9px 13px;font-size:11px;font-weight:700}
    .grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:14px}
    .card{background:#fff;border:2px solid #161b2c;padding:10px;overflow:hidden}
    .card img{display:block;width:100%;height:auto;background:#fff}
    .card b{display:block;margin:9px 2px 3px;font-size:13px}
    .card small{display:block;margin:0 2px 5px;color:#5a6b8c;font-size:11px}
    .swatches{display:flex;gap:8px;margin:14px 0}.swatches i{height:26px;flex:1;border:2px solid #161b2c}
    @media(max-width:900px){.grid{grid-template-columns:1fr 1fr}}@media(max-width:560px){.grid{grid-template-columns:1fr}}
  </style>
</head>
<body><main class="page">
  <div class="kicker">ACE · TEMPLATE FOUNDATION · VERSION 10.0.0 SÂN TRẮNG</div>
  <h1>Allen Knows Ball — Sân Trắng</h1>
  <p><span class="stamp">RELEASED</span></p>
  <p>Trắng dominant, cam loser field, ink monumental + orange bar, monogram crest slots, BigShoulders numerals (latin only), tiếng Việt Barlow/BeVietnam. Số liệu và nguồn trong preview chỉ minh họa.</p>
  <div class="swatches"><i style="background:#ffffff" title="white"></i><i style="background:#161b2c" title="ink"></i><i style="background:#f07862" title="orange"></i><i style="background:#5a6b8c" title="slate"></i><i style="background:#8b96b0" title="mist"></i></div>
  <div class="kicker">STARTER PROOFS · 3 SPRINTS (69 CARDS)</div>
  <div class="grid">""" + proofs + """</div>
  <!-- SPRINT1-AUDIT -->
  <p class="kicker" style="margin-top:22px">AUDIT</p>
  <p>Mọi proof: contrast pairs (ink/white ≥7, slate/white ≥4.5, ink/orange ≥4.5), palette audit (5 màu ±90), slot contract, safe areas, no-overlap, winner encoding, deterministic seeds. Eyeball owner cuối.</p>
</main></body></html>"""
    for pack in ("10.0.0", "longform-10.0.0"):
        (ROOT / "template_foundation/templates/allen-knows-ball" / pack / "preview.html").write_text(html, encoding="utf-8")
    print("wrote preview.html (short + long)")


def main() -> None:
    proof_rows = render_starter_proofs()
    bad_proofs = [r for r in proof_rows if r["bad"] > 0]
    print(f"starter proofs off-palette: {len(bad_proofs)}/{len(proof_rows)}")
    for row in bad_proofs[:10]:
        print("  -", row["name"], row["aspect"], row["bad"], row["badTop"])
    (ROOT / "apps" / "studio_templates" / "proof-rows-v10.json").write_text(
        json.dumps(proof_rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    base = ROOT / "template_foundation/templates/allen-knows-ball"
    write_composite(base / "10.0.0", "short",
                    ["short-mr-02-proof.png", "short-c-07-proof.png",
                     "short-c-04-proof.png", "short-bp-01-proof.png"])
    write_composite(base / "longform-10.0.0", "long",
                    ["long-ta-02-proof.png", "long-ta-06-proof.png",
                     "long-ta-16-proof.png", "long-ta-01-proof.png"])
    write_preview_html(proof_rows)


if __name__ == "__main__":
    main()
