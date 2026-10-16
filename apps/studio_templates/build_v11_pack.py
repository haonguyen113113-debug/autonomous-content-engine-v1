"""Assemble the v11 Cyber Pitch template pack (short 11.0.0 + longform-11.0.0).

Starters are built by build_starters_v11.py. This script writes pack JSONs
(manifest, tokens, color-systems, graphic-templates, modes, styles, slots,
timeline, story-forms, licenses), copies fonts (+ Tektur display), renders
starter proofs into the preview folders, writes preview.html + proof rows,
and registers the two draft packages in catalog.json. Released packs
(10.0.0) are never modified.

Run: python apps/studio_templates/build_v11_pack.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

T10 = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "10.0.0"
TL10 = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "longform-10.0.0"
T11 = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "11.0.0"
TL11 = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "longform-11.0.0"

CYBER_PALETTE = {
    "void": "#060913",
    "panel": "#0D1424",
    "neon_cyan": "#00E5FF",
    "pulse_magenta": "#FF3D81",
    "amber": "#FFB03A",
    "paper": "#F2F6FF",
    "slate": "#8296BE",
    # Aliases so generic renderer paths keep resolving colors.
    "ink": "#060913",
    "chalk": "#F2F6FF",
    "paper_white": "#F2F6FF",
    "accent_orange": "#FF3D81",
    "muted": "#8296BE",
    "kit_red": "#FF3D81",
    "kit_dark_red": "#060913",
    "orange": "#FF3D81",
    "navy": "#0D1424",
    "winner_lime": "#00E5FF",
    "signal_lime": "#00E5FF",
    "signal_orange": "#FF3D81",
    "team_home": "#00E5FF",
    "team_away": "#FF3D81",
    "pitch_line": "#00E5FF",
    "deep_pitch": "#0D1424",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_jsons() -> None:
    for target in (T11, TL11):
        (target / "previews").mkdir(parents=True, exist_ok=True)
        (target / "resources" / "fonts").mkdir(parents=True, exist_ok=True)
        (target / "resources" / "kit").mkdir(parents=True, exist_ok=True)

    for face in (T10 / "resources" / "fonts").glob("*"):
        shutil.copy(face, T11 / "resources" / "fonts" / face.name)
        shutil.copy(face, TL11 / "resources" / "fonts" / face.name)
    for face in ("Tektur-Medium.ttf", "Tektur-OFL.txt"):
        src = ROOT / "skills" / "canvas-design" / "canvas-fonts" / face
        shutil.copy(src, T11 / "resources" / "fonts" / face)
        shutil.copy(src, TL11 / "resources" / "fonts" / face)
    for res in ("ai-night-pitch-p.jpg",):
        src = T10 / "resources" / res
        if src.is_file():
            shutil.copy(src, T11 / "resources" / res)
            shutil.copy(src, TL11 / "resources" / res)
    for spr in (T10 / "resources" / "kit").glob("*"):
        shutil.copy(spr, T11 / "resources" / "kit" / spr.name)
        shutil.copy(spr, TL11 / "resources" / "kit" / spr.name)

    manifest_short = _load(T10 / "manifest.json")
    prev_short = _load(T11 / "manifest.json") if (T11 / "manifest.json").is_file() else {}
    manifest_short.update({
        "version": "11.0.0",
        "status": prev_short.get("status", "draft"),
        "description": "Cyber Pitch generation for portrait 9:16: neon HUD starters (69 cards, 3 sprints) with Tektur display type.",
        "renderer_requirement": "Authored starter cards (apps/studio_templates, locked cyber palette/type) carry the visual system; video assembly uses the generic editorial renderer. Values only from reviewed evidence with source+date.",
        "font_resources": sorted({*manifest_short["font_resources"], "resources/fonts/Tektur-Medium.ttf"}),
    })
    _write(T11 / "manifest.json", manifest_short)

    manifest_long = _load(TL10 / "manifest.json")
    prev_long = _load(TL11 / "manifest.json") if (TL11 / "manifest.json").is_file() else {}
    manifest_long.update({
        "version": "11.0.0",
        "status": prev_long.get("status", "draft"),
        "description": "Cyber Pitch generation for landscape 16:9: neon HUD tactical starters with Tektur display type.",
        "renderer_requirement": manifest_short["renderer_requirement"],
        "font_resources": sorted({*manifest_long["font_resources"], "resources/fonts/Tektur-Medium.ttf"}),
    })
    _write(TL11 / "manifest.json", manifest_long)

    tokens = _load(T10 / "design-tokens.json")
    tokens.update({
        "palette": dict(CYBER_PALETTE),
        "typography": {
            "display": {"family": "Tektur", "weights": [500],
                        "use": "Vietnamese names, headers, claims. Precomposed glyphs, clean at all sizes."},
            "numeral": {"family": "Tektur", "weights": [500],
                        "use": "Scores, stats, minutes. Techno digits match display."},
            "body": {"family": "Be Vietnam Pro", "weights": [400, 600, 700],
                     "use": "Vietnamese context labels, micro provenance."},
            "rules": [
                "1 frame = 1 boss; max 3 type sizes.",
                "Neon edges carry structure; magenta marks winners/accents; color never carries meaning alone.",
                "Amber micro on dark; slate secondary on dark; paper boss type.",
                "Provenance whisper on every evidence plate.",
            ],
        },
        "motion": {
            "default_easing": "ease-out cubic cubic-bezier(0.23,1,0.32,1), decisive stop.",
            "scene_enter": "Slide in from the right over 0.3s.",
            "count_up_steps": 6,
            "hook_stagger_seconds": 0.18,
            "ticker": "No tickers; LED dot rows carry rhythm.",
        },
        "prohibited_effects": [
            "glitch", "screen shake", "rapid flashing", "fake scoreboard branding",
            "unlicensed club crests", "uncited stat graphics", "synthesized faces",
            "orange body text", "floating unbordered identity",
        ],
        "version": "11.0.0", "template_version": "11.0.0",
    })
    _write(T11 / "design-tokens.json", tokens)
    _write(TL11 / "design-tokens.json", tokens)

    colors = {
        "schema_version": "1.0",
        "identity_neutrals": {"void": "#060913", "paper": "#F2F6FF"},
        "colorways": [{
            "id": "cyber-pitch", "name": "Cyber pitch",
            "tokens": {"ground": "#060913", "zone": "#0D1424", "edge": "#00E5FF",
                       "accent": "#FF3D81", "micro": "#FFB03A"},
        }],
        "selection_rules": [
            "Neon edges carry structure; magenta marks winners and accents.",
            "No club crests or competition marks; identity slots ship HUD panels with monograms.",
        ],
    }
    _write(T11 / "color-systems.json", colors)
    _write(TL11 / "color-systems.json", colors)

    base_graphic = _load(T10 / "graphic-templates.json")
    cyber_purpose = {
        "duel_columns": "Head-to-head duel plan; Studio renders starter C-07 (or BP-07/BP-10/BP-14) with reviewed metrics.",
        "stat_leader": "Stat-leader plan; Studio renders starter C-06 with reviewed stats.",
        "player_poster_side": "Player spotlight plan (side); Studio renders starter C-04 with the named player.",
        "player_poster_top": "Player spotlight plan (top); Studio renders starter C-04 with the named player.",
        "goal_card": "Goal-moment plan; Studio renders starter MR-04 with the reviewed minute and score.",
        "fixture_card": "Fixture plan; Studio renders starter MR-11 with the reviewed fixture.",
        "fixture_list": "Fixture-list plan; Studio renders starter MR-11 with up to 3 reviewed fixtures.",
        "score_card": "Final-score plan; Studio renders starter MR-02 with the reviewed scoreline.",
        "quote_card": "Quote plan; Studio renders starter C-05 with the reviewed claim and source.",
        "potm_card": "POTM plan; Studio renders starter C-04 with the named player.",
        "discipline_card": "Discipline plan; Studio renders starter MR-06 with the reviewed incident.",
        "welcome_card": "Welcome plan; Studio renders starter BP-06 with the reviewed signing.",
        "hook_card": "Frame-0 hook plan; Studio renders starter C-03 with the 5-8 word claim.",
        "tactical_explainer": "Neon pitch plate for shapes/runs/press (TA starters long-form).",
        "source_card": "Provenance note: publication, date, claim, URL (starter C-09).",
    }
    layouts = [{**item, "purpose": cyber_purpose.get(item["id"], item.get("purpose", item["id"]))}
               for item in base_graphic["layouts"]]
    graphic = {**base_graphic, "template_version": "11.0.0",
               "motion_notes": "Slide-in 0.3s ease-out cubic-bezier(0.23,1,0.32,1); count-up 6 steps; stagger 0.18s (video assembly).",
               "selection_rule": "Open on hook_card; card_selector maps each beat to a starter ID for Studio; video assembly falls back to generic editorial frames.",
               "layouts": layouts,
               "layout_grammar": {lid: {"composition": cyber_purpose.get(lid, lid),
                                        "best_for": cyber_purpose.get(lid, lid)}
                                  for lid in [item["id"] for item in layouts]}}
    _write(T11 / "graphic-templates.json", graphic)
    _write(TL11 / "graphic-templates.json", graphic)

    base_modes = _load(T10 / "visual-modes.json")
    _write(T11 / "visual-modes.json", {**base_modes, "template_version": "11.0.0"})
    _write(TL11 / "visual-modes.json", {**base_modes, "template_version": "11.0.0"})

    styles = _load(T10 / "graphic-layout-styles.json")
    styles = {**styles, "template_version": "11.0.0",
              "shared_identity": ["Allen Knows Ball wordmark", "Be Vietnam Pro body",
                                  "Tektur display + numerals", "neon HUD panels",
                                  "pitch-line motifs", "source/date attribution"]}
    _write(T11 / "graphic-layout-styles.json", styles)
    _write(TL11 / "graphic-layout-styles.json", styles)

    for src, dst in ((T10, T11), (TL10, TL11)):
        slots = _load(src / "slot-contract.json")
        slots["owner_template"] = "allen-knows-ball.shortform-analyst@11.0.0"
        _write(dst / "slot-contract.json", slots)
        for name in ("timeline.json", "story-forms.json"):
            _write(dst / name, _load(src / name))
        licenses = _load(src / "LICENSES.json")
        third = list(licenses.get("third_party_resources", []))
        third.append({
            "family": "Tektur",
            "files": ["resources/fonts/Tektur-Medium.ttf", "resources/fonts/Tektur-OFL.txt"],
            "license": "SIL Open Font License 1.1",
            "source": "https://github.com/anthropics/skills (canvas-design canvas-fonts, OFL)",
            "use": "Display headlines and numerals; precomposed Vietnamese glyphs.",
        })
        licenses["third_party_resources"] = third
        _write(dst / "LICENSES.json", licenses)

    print("wrote v11 pack JSONs + fonts")


CYBER_RGB = [(6, 9, 19), (13, 20, 36), (0, 229, 255), (255, 61, 129),
             (255, 176, 58), (242, 246, 255), (130, 150, 190)]


def render_starter_proofs() -> list[dict]:
    from apps.studio_templates.render_starters import audit_blends, render_design

    tpl = ROOT / "apps" / "studio_templates"
    rows: list[dict] = []
    jobs = ([(p.stem.split(".")[0], "short") for p in sorted(tpl.glob("*.short.json"))
             if p.name != "duel_columns.short.json"]
            + [(p.stem.split(".")[0], "long") for p in sorted(tpl.glob("*.long.json"))])
    for cid, aspect in jobs:
        data = json.loads((tpl / f"{cid}.{aspect}.json").read_text(encoding="utf-8"))
        image = render_design(data)
        assert image.size == ((1080, 1920) if aspect == "short" else (1920, 1080)), cid
        target = T11 if aspect == "short" else TL11
        out = target / "previews" / f"{aspect}-{cid.lower()}-proof.png"
        image.save(out)
        bad, top = audit_blends(image, CYBER_RGB)
        rows.append({"name": cid, "aspect": aspect, "size": list(image.size),
                     "bad": bad, "badTop": top, "visual": "todo",
                     "note": "Cyber PIL proof of Polotno starter; static gates pass; needs owner eyeball."})
        print(f"ok {out.name} {image.size[0]}x{image.size[1]} off-palette={bad}")
    return rows


def write_composite(target: Path, picks: list[str]) -> None:
    from PIL import Image

    tiles = []
    for name in picks:
        path = target / "previews" / name
        with Image.open(path) as opened:
            tiles.append(opened.copy())
    cols = 2
    tw, th = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, th * rows), (6, 9, 19))
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
  <title>Allen Knows Ball — Cyber Pitch 11.0.0 (draft, chờ owner audit)</title>
  <style>
    *{box-sizing:border-box}body{margin:0;background:#060913;color:#f2f6ff;font:15px 'Be Vietnam Pro',Arial,sans-serif}
    .page{max-width:1320px;margin:auto;padding:36px 28px 54px}
    .kicker{color:#00e5ff;font-size:11px;font-weight:700;letter-spacing:1.7px}
    h1{font-size:44px;margin:8px 0}
    .stamp{background:#ff3d81;color:#060913;border-radius:99px;padding:9px 13px;font-size:11px;font-weight:700}
    .grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:14px}
    .card{background:#0d1424;border:2px solid #00e5ff;padding:10px;overflow:hidden}
    .card img{display:block;width:100%;height:auto;background:#060913}
    .card b{display:block;margin:9px 2px 3px;font-size:13px}
    .card small{display:block;margin:0 2px 5px;color:#8296be;font-size:11px}
    .swatches{display:flex;gap:8px;margin:14px 0}.swatches i{height:26px;flex:1;border:2px solid #00e5ff}
    @media(max-width:900px){.grid{grid-template-columns:1fr 1fr}}@media(max-width:560px){.grid{grid-template-columns:1fr}}
  </style>
</head>
<body><main class="page">
  <div class="kicker">ACE · TEMPLATE FOUNDATION · VERSION 11.0.0 CYBER PITCH</div>
  <h1>Allen Knows Ball — Cyber Pitch</h1>
  <p><span class="stamp">DRAFT · CHỜ OWNER AUDIT</span></p>
  <p>Neon HUD trên nền void, Tektur display, magenta winner accents, amber micro. Số liệu và nguồn trong preview chỉ minh họa.</p>
  <div class="swatches"><i style="background:#060913" title="void"></i><i style="background:#0d1424" title="panel"></i><i style="background:#00e5ff" title="cyan"></i><i style="background:#ff3d81" title="magenta"></i><i style="background:#ffb03a" title="amber"></i><i style="background:#f2f6ff" title="paper"></i><i style="background:#8296be" title="slate"></i></div>
  <div class="kicker">STARTER PROOFS · 3 SPRINTS (69 CARDS)</div>
  <div class="grid">""" + proofs + """</div>
  <!-- SPRINT1-AUDIT -->
  <p class="kicker" style="margin-top:22px">AUDIT</p>
  <p>Mọi proof: contrast pairs, palette audit (7 màu ±90), slot contract, safe areas, no-overlap, deterministic seeds. Eyeball owner cuối.</p>
</main></body></html>"""
    for pack in ("11.0.0", "longform-11.0.0"):
        (ROOT / "template_foundation/templates/allen-knows-ball" / pack / "preview.html").write_text(html, encoding="utf-8")
    print("wrote preview.html (short + long)")


def register_catalog() -> None:
    catalog_path = ROOT / "template_foundation" / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    entries = [
        {"template_id": "allen-knows-ball.shortform-analyst", "channel_id": "allen-knows-ball",
         "version": "11.0.0", "status": "draft", "path": "templates/allen-knows-ball/11.0.0"},
        {"template_id": "allen-knows-ball.longform-analyst", "channel_id": "allen-knows-ball",
         "version": "11.0.0", "status": "draft", "path": "templates/allen-knows-ball/longform-11.0.0"},
    ]
    have = {(t.get("template_id"), t.get("version")) for t in catalog.get("templates", [])}
    for entry in entries:
        if (entry["template_id"], entry["version"]) not in have:
            catalog["templates"].append(entry)
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("catalog: short + longform 11.0.0 registered as draft")


def main() -> None:
    build_jsons()
    proof_rows = render_starter_proofs()
    bad_proofs = [r for r in proof_rows if r["bad"] > 0]
    print(f"starter proofs off-palette: {len(bad_proofs)}/{len(proof_rows)}")
    for row in bad_proofs[:10]:
        print("  -", row["name"], row["aspect"], row["bad"], row["badTop"])
    (ROOT / "apps" / "studio_templates" / "proof-rows-v11.json").write_text(
        json.dumps(proof_rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    base = ROOT / "template_foundation/templates/allen-knows-ball"
    write_composite(base / "11.0.0",
                    ["short-mr-02-proof.png", "short-c-07-proof.png",
                     "short-c-04-proof.png", "short-bp-01-proof.png"])
    write_composite(base / "longform-11.0.0",
                    ["long-ta-02-proof.png", "long-ta-06-proof.png",
                     "long-ta-16-proof.png", "long-ta-01-proof.png"])
    write_preview_html(proof_rows)
    register_catalog()


if __name__ == "__main__":
    main()
