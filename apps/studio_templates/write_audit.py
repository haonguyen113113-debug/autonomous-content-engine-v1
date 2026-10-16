"""Append Sprint proof-audit section to 10.0.0 preview.html.

Usage: python apps/studio_templates/write_audit.py rows.json
rows.json: [{name, aspect, size:[w,h], bad:int, badTop:[...], visual:'pass'|'block'|'todo', note:''}]
Proof PNGs must already sit at 10.0.0/previews/<prefix>-<id>-proof.png (lowercased id).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HTML = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "10.0.0" / "preview.html"


def main() -> int:
    rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    cards = []
    for row in rows:
        slug = f"{row['aspect']}-{row['name'].lower()}-proof.png"
        visual = row.get("visual", "todo")
        color = {"pass": "#8CFF00", "block": "#FF6B6B"}.get(visual, "#9AA3A8")
        cards.append(
            f"<div class='rendered-card'><b>{row['name']} {row['aspect']} "
            f"· <span style='color:{color}'>{visual.upper()}</span></b>"
            f"<img src='/template-foundation/previews/{slug}' alt='{row['name']}'>"
            f"<small>export {row['size'][0]}×{row['size'][1]} · off-palette px: {row['bad']} "
            f"{(row.get('badTop') or [])} · {row.get('note', '')}</small></div>")
    section = (
        "<section class='panel' style='margin-top:18px'>"
        "<div class='kicker'>SPRINT PROOF AUDIT (STARTERS)</div>"
        f"<h2 style='margin-top:8px'>{len(rows)} starters — gates + proof, khắt khe</h2>"
        "<p>Palette khóa trắng/ink/cam/slate. Số ink monumental + bar cam, thua ink trên cam. "
        "Credit ink. Xem kỹ từng proof trước khi duyệt.</p>"
        "<div class='rendered-grid'>" + "".join(cards) + "</div></section>")
    text = HTML.read_text(encoding="utf-8")
    marker = "<!-- SPRINT1-AUDIT -->"
    end = "<!-- /SPRINT1-AUDIT -->"
    section += end
    if marker not in text:
        text = text.replace("</main>", marker + end + "</main>")
    start = text.index(marker) + len(marker)
    if end in text[start:]:
        stop = text.index(end, start) + len(end)
    else:
        # one-time migration: first-generation section runs marker..</main>
        stop = text.index("</main>", start)
    text = text[:start] + section + text[stop:]
    HTML.write_text(text, encoding="utf-8")
    print(f"audit updated: {len(rows)} cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
