"""Build Sprint 1 Polotno starters (35 JSON) from locked DNA tokens.

No build pixels here: plates are authored as JSON, proofed in Studio.
Run: python apps/studio_templates/build_starters.py  (writes *.short/long.json)
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).parent

INK = "#161B2C"
INK2 = "#20263C"
CORAL = "#E0705F"
PAPER = "#F4F2EC"
SLATE = "#5A6B8C"
MIST = "#8B96B0"
DISP = "Barlow Condensed"
BODY = "Be Vietnam Pro"

_n = 0


def _id(prefix: str) -> str:
    global _n
    _n += 1
    return f"{prefix}-{_n}"


def locked_rect(x, y, w, h, fill, opacity=1.0, extra=None):
    d = {"id": _id("deco"), "type": "figure", "subType": "rect",
         "x": x, "y": y, "width": w, "height": h, "fill": fill,
         "opacity": opacity, "selectable": False, "draggable": False,
         "resizable": False, "removable": False}
    if extra:
        d.update(extra)
    return d


def val_text(x, y, w, h, text, size, family, fill, slot, align="center",
             weight="bold", extra=None):
    d = {"id": _id("val"), "type": "text", "x": x, "y": y,
         "width": w, "height": h, "text": text, "fontSize": size,
         "fontFamily": family, "fontWeight": weight, "fill": fill,
         "align": align, "draggable": False, "resizable": False,
         "removable": False, "styleEditable": False, "contentEditable": True,
         "custom": {"slot": slot}}
    if extra:
        d.update(extra)
    return d


def tech_rules(w, y_list, color=SLATE):
    return [locked_rect(76, y, w - 152, 3, color, 0.7) for y in y_list]


def doc(w, h, children, bg=INK):
    return {"schemaVersion": 4, "width": w, "height": h, "fonts": [],
            "pages": [{"id": "p1", "background": bg, "children": children}],
            "audios": []}


SUPPORT_SAMPLE = "Dòng phụ (sửa theo từng video)"
CREDIT_SAMPLE = "NGUỒN + NGÀY CẬP NHẬT"


def credit(text, w, bottom, slot="credit"):
    m = int(w * 0.07)
    return val_text(m, bottom, w - 2 * m, 40, (text or "").strip() or CREDIT_SAMPLE,
                    26, BODY, MIST, slot, align="center", weight="normal")


def coral_band(y, h, w):
    return locked_rect(0, y, w, h, CORAL)


def kick(text, y, w, slot):
    m = int(w * 0.07)
    return val_text(m, y, w - 2 * m, 50, text, 34, DISP, CORAL,
                    slot, align="left", weight="bold")


# ---------------- short (1080x1920) builders ----------------

def statement(kicker_en, claim, credit_txt, support=SUPPORT_SAMPLE):
    W = 1080
    return [
        coral_band(940, 320, W),
        locked_rect(76, 200, 120, 10, CORAL),
        kick(kicker_en, 240, W, "kicker"),
        val_text(76, 320, W - 152, 420, claim, 168, DISP, PAPER, "claim", align="left"),
        val_text(76, 1050, W - 152, 130, support, 48, BODY, INK, "support", align="left", weight="normal"),
        locked_rect(76, 1450, 420, 8, SLATE, 0.8),
        locked_rect(76, 1478, 260, 8, CORAL, 0.9),
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 830, "y": 1430, "width": 90, "height": 90, "fill": SLATE,
         "opacity": 0.7, "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 940, "y": 1452, "width": 46, "height": 46, "fill": CORAL,
         "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        credit(credit_txt, W, 1820),
    ] + tech_rules(W, [1700])


def duel(home, away, rows, credit_txt):
    W = 1080
    els = [
        locked_rect(0, 400, 540, 1300, INK2),
        locked_rect(540, 400, 540, 1300, CORAL),
        val_text(76, 180, 928, 100, "ĐỐI ĐẦU", 84, DISP, PAPER, "title"),
        val_text(90, 300, 400, 64, home, 56, DISP, PAPER, "team-home"),
        val_text(590, 300, 400, 64, away, 56, DISP, PAPER, "team-away"),
    ]
    y = 470
    for i, (label, hv, av, winner) in enumerate(rows):
        els.append(locked_rect(80, y, 920, 54, INK))
        els.append(val_text(80, y, 920, 54, label, 38, DISP, PAPER, f"label-{i}"))
        home_loser = winner not in ("home", "tie")
        away_loser = winner not in ("away", "tie")
        els.append(val_text(90, y + 60, 390, 190, hv, 150, DISP,
                            PAPER, f"m-{i}-home",
                            extra=None if not home_loser else {"opacity": 0.8}))
        els.append(val_text(600, y + 60, 390, 190, av, 150, DISP,
                            INK, f"m-{i}-away",
                            extra=None if not away_loser else {"opacity": 0.8}))
        if winner != "tie":
            els.append(locked_rect(150 if winner == "home" else 690, y + 250, 260, 10, CORAL))
        y += 330
    els.append(credit(credit_txt, W, 1820))
    return els


def score_card(home, away, score, comp, when):
    W = 1080
    return [
        coral_band(790, 180, W),
        val_text(76, 200, 928, 110, comp, 72, DISP, PAPER, "comp"),
        val_text(76, 330, 928, 70, when, 40, BODY, MIST, "when", weight="normal"),
        val_text(76, 480, 928, 200, score, 200, DISP, PAPER, "score"),
        val_text(76, 830, 928, 80, f"{home}  •  {away}", 52, DISP, INK, "teams"),
        locked_rect(76, 1400, 420, 8, SLATE, 0.8),
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 830, "y": 1380, "width": 90, "height": 90, "fill": SLATE,
         "opacity": 0.7, "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 940, "y": 1402, "width": 46, "height": 46, "fill": CORAL,
         "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        credit("Nguồn + ngày", W, 1820),
    ]


def poster(slot_prefix):
    W = 1080
    return [
        locked_rect(0, 0, 500, 1920, INK2),
        locked_rect(0, 0, 500, 1920, SLATE, 0.25),
        locked_rect(60, 200, 14, 300, CORAL),
        locked_rect(60, 540, 14, 300, CORAL, 0.6),
        locked_rect(60, 880, 14, 300, CORAL, 0.35),
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 330, "y": 1500, "width": 110, "height": 110, "fill": SLATE,
         "opacity": 0.6, "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 120, "y": 1620, "width": 54, "height": 54, "fill": CORAL,
         "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        val_text(60, 900, 380, 120, "KHUNG ẢNH\n(Thay theo video)", 40, BODY, MIST,
                 f"{slot_prefix}-photo-note", weight="normal",
                 extra={"showInExport": False}),
        locked_rect(500, 120, 580, 240, CORAL, 0.25),
        val_text(540, 420, 440, 300, "TÊN", 170, DISP, PAPER, f"{slot_prefix}-name", align="left"),
        val_text(540, 740, 440, 70, "#SỐ • VAI TRÒ", 44, BODY, CORAL, f"{slot_prefix}-tag", align="left"),
        val_text(540, 900, 440, 60, "THÔNG TIN", 40, DISP, MIST, f"{slot_prefix}-meta", align="left", weight="normal"),
        val_text(540, 1080, 440, 220, "19", 170, DISP, PAPER, f"{slot_prefix}-stat", align="left"),
        credit("Nguồn + ngày", W, 1820),
    ]


def source_slip(title, credit_txt):
    W = 1080
    return [
        locked_rect(76, 600, 928, 700, PAPER),
        locked_rect(76, 600, 928, 90, CORAL),
        val_text(110, 620, 860, 60, title, 44, DISP, INK, "src-title", align="left"),
        val_text(110, 740, 860, 380, "Nội dung nguồn/trích dẫn", 44, BODY, INK,
                 "src-body", align="left", weight="normal"),
        locked_rect(820, 1220, 130, 130, CORAL, extra={"subType": "circle"}),
        val_text(820, 1250, 130, 70, "AKB", 44, DISP, INK, "seal"),
        credit(credit_txt, W, 1820),
    ]


def end_card(show_tagline=True):
    W = 1080
    els = [
        coral_band(780, 310, W),
        kick("KÊNH CHÍNH THỨC", 240, W, "kicker"),
        locked_rect(380, 400, 320, 320, PAPER),
        locked_rect(380, 400, 320, 26, CORAL),
        val_text(380, 470, 320, 180, "AKB", 130, DISP, INK, "mark"),
        val_text(76, 880, 928, 110, "ALLEN KNOWS BALL", 84, DISP, INK, "channel"),
        locked_rect(76, 1330, 300, 8, INK),
        credit("", W, 1820),
    ]
    if show_tagline:
        els.insert(6, val_text(76, 1430, 928, 70, "Bóng đá, nhìn thêm một nhịp.", 44, BODY, MIST,
                               "tagline", weight="normal"))
    return els


def label_chip(big, small):
    W = 1080
    return [
        locked_rect(76, 1300, 928, 260, INK2),
        locked_rect(76, 1300, 14, 260, CORAL),
        val_text(130, 1340, 820, 120, big, 84, DISP, PAPER, "chip-main", align="left"),
        val_text(130, 1460, 820, 60, small, 40, BODY, MIST, "chip-sub", align="left", weight="normal"),
        locked_rect(76, 1220, 420, 8, SLATE, 0.8),
    ]


def moments(rows):
    W = 1080
    els = [locked_rect(76, 180, 928, 110, CORAL),
           val_text(76, 195, 928, 80, "BƯỚC NGOẶT", 64, DISP, INK, "title"),
           coral_band(360, 920, W)]
    y = 420
    for i, (minute, event) in enumerate(rows):
        els.append(val_text(76, y, 200, 70, minute, 56, DISP, INK, f"min-{i}", align="left"))
        els.append(val_text(300, y, 700, 130, event, 44, BODY, INK, f"evt-{i}", align="left", weight="normal"))
        y += 250
    els += [locked_rect(76, 1400, 420, 8, SLATE, 0.8),
            locked_rect(76, 1428, 260, 8, CORAL, 0.9)]
    els.append(credit("Nguồn + ngày", W, 1820))
    return els


def money(amount="€120TR", line="Diễn giải 1 dòng", note="Chú thích so sánh"):
    W = 1080
    return [
        locked_rect(76, 200, 120, 10, CORAL),
        kick("TIỀN BẠC", 240, W, "kicker"),
        val_text(76, 320, 928, 220, amount, 200, DISP, PAPER, "amount", align="left"),
        coral_band(580, 540, W),
        val_text(76, 620, 928, 120, line, 48, BODY, INK, "line", align="left", weight="normal"),
        locked_rect(76, 860, 700, 60, INK2),
        locked_rect(76, 950, 450, 60, INK),
        val_text(76, 1040, 928, 60, note, 38, BODY, INK, "note", align="left", weight="normal"),
        locked_rect(76, 1400, 420, 8, SLATE, 0.8),
        locked_rect(76, 1428, 260, 8, CORAL, 0.9),
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 830, "y": 1380, "width": 90, "height": 90, "fill": SLATE,
         "opacity": 0.7, "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 940, "y": 1402, "width": 46, "height": 46, "fill": CORAL,
         "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        credit("Nguồn + ngày", W, 1820),
    ]


def myth(myth_text="Điều mọi người vẫn tin", fact_text="Bằng chứng nói gì"):
    W = 1080
    return [
        locked_rect(0, 360, 1080, 620, CORAL),
        val_text(76, 200, 928, 100, "NGỘ NHẬN", 72, DISP, PAPER, "myth-k"),
        val_text(76, 420, 928, 380, myth_text, 64, BODY, INK, "myth", align="left", weight="normal"),
        val_text(76, 1060, 928, 100, "SỰ THẬT", 72, DISP, CORAL, "fact-k"),
        val_text(76, 1180, 928, 380, fact_text, 64, BODY, PAPER, "fact", align="left", weight="normal"),
        credit("Nguồn + ngày", W, 1820),
    ]


def table_card(title, rows):
    """Short data table: text-rows + figure bars (inventory grammar)."""
    W = 1080
    els = [locked_rect(76, 180, 928, 110, CORAL),
           val_text(76, 195, 928, 80, title, 64, DISP, INK, "title")]
    y = 380
    for i, (label, frac) in enumerate(rows):
        els.append(val_text(76, y, 700, 60, label, 44, BODY, PAPER, f"l-{i}", align="left", weight="normal"))
        els.append(locked_rect(76, y + 80, int(700 * frac), 54, CORAL))
        els.append(val_text(76 + int(700 * frac) + 24, y + 70, 200, 80,
                            str(int(round(frac * 40))), 56, DISP, PAPER, f"v-{i}", align="left"))
        y += 260
    els += [locked_rect(76, 1400, 420, 8, SLATE, 0.8),
            locked_rect(76, 1428, 260, 8, CORAL, 0.9),
            {"id": _id("deco"), "type": "figure", "subType": "circle",
             "x": 830, "y": 1380, "width": 90, "height": 90, "fill": SLATE,
             "opacity": 0.7, "selectable": False, "draggable": False,
             "resizable": False, "removable": False},
            {"id": _id("deco"), "type": "figure", "subType": "circle",
             "x": 940, "y": 1402, "width": 46, "height": 46, "fill": CORAL,
             "selectable": False, "draggable": False,
             "resizable": False, "removable": False}]
    els.append(credit("Nguồn + ngày", W, 1820))
    return els


# ---------------- long (1920x1080) builders ----------------

def l_statement(kicker_en, claim, support=SUPPORT_SAMPLE):
    W = 1920
    return [
        coral_band(220, 560, W),
        kick(kicker_en, 140, W, "kicker"),
        val_text(140, 320, W - 280, 200, claim, 130, DISP, INK, "claim", align="left"),
        val_text(140, 630, 900, 110, support, 40, BODY, INK, "support", align="left", weight="normal"),
        credit("", W, 990),
    ]


def l_context(home, away, score, meta):
    W = 1920
    return [
        val_text(140, 120, 1640, 90, "TRẬN ĐẤU", 72, DISP, CORAL, "kicker", align="left"),
        val_text(140, 240, 700, 130, home, 96, DISP, PAPER, "home", align="left"),
        val_text(140, 390, 700, 130, away, 96, DISP, PAPER, "away", align="left"),
        val_text(1230, 220, 550, 220, score, 200, DISP, PAPER, "score"),
        val_text(1230, 470, 550, 80, meta, 44, BODY, MIST, "meta", weight="normal"),
        locked_rect(140, 700, 1640, 8, CORAL),
        credit("", W, 990),
    ]


def l_pitch(extra_els, tag):
    W = 1920
    els = [
        locked_rect(140, 90, 1640, 820, INK2),
        locked_rect(140, 90, 1640, 10, SLATE),
        locked_rect(140, 900, 1640, 10, SLATE),
        locked_rect(140, 90, 10, 820, SLATE),
        locked_rect(1770, 90, 10, 820, SLATE),
        locked_rect(955, 90, 10, 820, SLATE),
        locked_rect(140, 420, 420, 160, SLATE, 0.5),
        locked_rect(1360, 420, 420, 160, SLATE, 0.5),
        # full markings (analyst grammar): 6-yard insets, goals, spots,
        # center circle (outline only — fill matches pitch so only ring shows)
        {"id": _id("deco"), "type": "figure", "subType": "rect",
         "x": 300, "y": 470, "width": 140, "height": 60, "fill": INK2,
         "stroke": SLATE, "strokeWidth": 4, "selectable": False,
         "draggable": False, "resizable": False, "removable": False},
        {"id": _id("deco"), "type": "figure", "subType": "rect",
         "x": 1340, "y": 470, "width": 140, "height": 60, "fill": INK2,
         "stroke": SLATE, "strokeWidth": 4, "selectable": False,
         "draggable": False, "resizable": False, "removable": False},
        locked_rect(110, 455, 30, 90, PAPER),
        locked_rect(1780, 455, 30, 90, PAPER),
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 817, "y": 390, "width": 286, "height": 220, "fill": INK2,
         "stroke": SLATE, "strokeWidth": 6, "selectable": False,
         "draggable": False, "resizable": False, "removable": False},
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 953, "y": 493, "width": 14, "height": 14, "fill": SLATE,
         "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 305, "y": 493, "width": 14, "height": 14, "fill": SLATE,
         "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 1601, "y": 493, "width": 14, "height": 14, "fill": SLATE,
         "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        val_text(165, 820, 875, 60, tag, 44, DISP, CORAL, "tag", align="left"),
    ] + extra_els
    return els


def token(x, y, num, slot, fill=PAPER, tfill=INK, opacity=1.0):
    circle = {"id": _id("deco"), "type": "figure", "subType": "circle", "x": x, "y": y,
              "width": 96, "height": 96, "fill": fill, "selectable": False,
              "draggable": False, "resizable": False, "removable": False}
    text = val_text(x, y + 8, 96, 80, num, 52, DISP, tfill, slot)
    if opacity < 1.0:
        circle["opacity"] = opacity
        text["opacity"] = opacity
    return [circle, text]


def ball(x, y):
    """Ball marker: always visible, draggable in Studio (no lock flags)."""
    return [
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": x, "y": y, "width": 44, "height": 44, "fill": PAPER},
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": x + 14, "y": y + 14, "width": 16, "height": 16, "fill": INK},
    ]


def guide_line(x, y, w, color=SLATE, dash=None):
    """Headless dashed construction line (block height, offside line...)."""
    return {"id": _id("deco"), "type": "line", "x": x, "y": y, "width": w,
            "height": 20, "color": color, "selectable": False,
            "draggable": False, "resizable": False, "removable": False,
            **({"dash": dash} if dash else {})}


def arrow(x, y, w, color=CORAL, dash=None, head="triangle"):
    d = {"id": _id("deco"), "type": "line", "x": x, "y": y, "width": w,
         "height": 20, "color": color, "endHead": head,
         "selectable": False, "draggable": False, "resizable": False, "removable": False}
    if dash:
        d["dash"] = dash
    return d


def l_takeaways(rows):
    W = 1920
    els = [val_text(140, 120, 1640, 100, "KẾT LUẬN", 72, DISP, CORAL, "kicker", align="left")]
    y = 280
    for i, text in enumerate(rows):
        els.append(val_text(140, y, 160, 110, str(i + 1), 96, DISP, CORAL, f"n-{i}", align="left"))
        els.append(val_text(330, y, 1450, 170, text, 56, BODY, PAPER, f"t-{i}", align="left", weight="normal"))
        y += 230
    els.append(credit("", W, 990))
    return els


def l_bars(rows):
    W = 1920
    els = [val_text(140, 120, 1640, 100, "BẰNG CHỨNG SỐ", 72, DISP, CORAL, "kicker", align="left")]
    y = 300
    for i, (label, frac) in enumerate(rows):
        els.append(val_text(140, y, 500, 70, label, 48, BODY, PAPER, f"l-{i}", align="left", weight="normal"))
        els.append(locked_rect(140, y + 90, int(1200 * frac), 56, CORAL))
        els.append(val_text(140 + int(1200 * frac) + 30, y + 80, 300, 80,
                            str(int(round(frac * 40))), 56, DISP, PAPER, f"v-{i}", align="left"))
        y += 200
    els.append(credit("Nguồn + ngày", W, 990))
    return els


def versus(comp, home, away, when):
    """Next fixture teaser: clubs + date on a hugging color block."""
    W = 1080
    return [
        coral_band(860, 400, W),
        locked_rect(76, 200, 120, 10, CORAL),
        val_text(76, 240, 928, 110, comp, 72, DISP, PAPER, "comp", align="left"),
        val_text(76, 400, 928, 150, home, 110, DISP, PAPER, "home", align="left"),
        val_text(76, 570, 928, 100, "VS", 84, DISP, CORAL, "vs", align="left"),
        val_text(76, 700, 928, 150, away, 110, DISP, PAPER, "away", align="left"),
        val_text(76, 900, 928, 70, when, 40, BODY, INK, "when", align="left", weight="normal"),
        locked_rect(76, 1400, 420, 8, SLATE, 0.8),
        locked_rect(76, 1428, 260, 8, CORAL, 0.9),
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 830, "y": 1380, "width": 90, "height": 90, "fill": SLATE,
         "opacity": 0.7, "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        {"id": _id("deco"), "type": "figure", "subType": "circle",
         "x": 940, "y": 1402, "width": 46, "height": 46, "fill": CORAL,
         "selectable": False, "draggable": False,
         "resizable": False, "removable": False},
        credit("Nguồn + ngày", W, 1820),
    ]


def takes_short(rows):
    """Three-point summary for portrait cards."""
    W = 1080
    els = [locked_rect(76, 200, 120, 10, CORAL),
           kick("TÓM TẮT", 240, W, "kicker")]
    y = 380
    for i, text in enumerate(rows):
        els.append(val_text(76, y, 130, 110, str(i + 1), 96, DISP, CORAL, f"n-{i}", align="left"))
        els.append(val_text(230, y, 774, 170, text, 56, BODY, PAPER, f"t-{i}", align="left", weight="normal"))
        y += 260
    els += [locked_rect(76, 1400, 420, 8, SLATE, 0.8),
            locked_rect(76, 1428, 260, 8, CORAL, 0.9),
            {"id": _id("deco"), "type": "figure", "subType": "circle",
             "x": 830, "y": 1380, "width": 90, "height": 90, "fill": SLATE,
             "opacity": 0.7, "selectable": False, "draggable": False,
             "resizable": False, "removable": False},
            {"id": _id("deco"), "type": "figure", "subType": "circle",
             "x": 940, "y": 1402, "width": 46, "height": 46, "fill": CORAL,
             "selectable": False, "draggable": False,
             "resizable": False, "removable": False}]
    els.append(credit("Nguồn + ngày", W, 1820))
    return els


def sting():
    """Transition sting: full-width brand band, nothing else to read."""
    W = 1080
    return [
        locked_rect(0, 800, 1080, 320, CORAL),
        val_text(76, 880, 928, 110, "ALLEN KNOWS BALL", 72, DISP, INK, "sting"),
    ]


SHORT = {
    "C-01": ("end", [False]),
    "C-02": ("statement", ["CHƯƠNG MỚI", "Ý tiếp theo", ""]),
    "C-03": ("statement", ["TUYÊN BỐ", "Câu then chốt", ""]),
    "C-05": ("source", ["TRÍCH DẪN", "Nguồn + ngày"]),
    "C-08": ("takes3", ["Ý chính một", "Ý chính hai", "Ý chính ba"]),
    "C-04": ("poster", ["spot"]),
    "C-06": ("statement", ["CON SỐ", "19", "Nguồn + ngày"]),
    "C-07": ("duel", ["HÀ NỘI", "NAM ĐỊNH",
                       [("BÀN THẮNG", "45", "38", "home"), ("KIẾN TẠO", "30", "30", "tie"),
                        ("SÚT TRÚNG ĐÍCH", "120", "98", "home")], "Nguồn + ngày"]),
    "C-09": ("source", ["NGUỒN", "Nguồn + ngày"]),
    "C-10": ("end", []),
    "U-02": ("chip", ["NGUYỄN VĂN A", "Tiền đạo • #19"]),
    "U-01": ("chip", ["CHƯƠNG 2", "Diễn biến chính"]),
    "U-04": ("chip", ["08.2026", "Vòng 12 • Cập nhật"]),
    "U-06": ("chip", ["LƯU Ý", "Số liệu ước tính • Chờ xác nhận"]),
    "U-07": ("sting", []),
    "U-08": ("source", ["ĐÍNH CHÍNH", "Nguồn + giờ cập nhật"]),
    "U-03": ("chip", ["V.LEAGUE 2026", "Vòng 12 • Sân Hàng Đẫy"]),
    "U-05": ("chip", ["xG 1.8", "Bàn thắng kỳ vọng • Opta"]),
    "MR-01": ("statement", ["TIN NÓNG", "Kết quả mới", "Nguồn + giờ"]),
    "MR-02": ("score", ["HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League", "Tối nay • Hàng Đẫy"]),
    "MR-04": ("score", ["HÀ NỘI", "NAM ĐỊNH", "1 - 0", "BÀN THẮNG PHÚT 67", "Sân Hàng Đẫy"]),
    "MR-06": ("moments", [[ "12'", "Bàn mở tỷ số"], ["67'", "Thẻ đỏ đổi cục diện"], ["89'", "Ấn định 2-0"]]),
    "MR-03": ("score", ["HÀ NỘI", "NAM ĐỊNH", "1 - 0", "NGHỈ GIỮA HIỆP", "Sân Hàng Đẫy"]),
    "MR-08": ("poster", ["potm"]),
    "MR-09": ("table", ["BẢNG XẾP HẠNG", [["Điểm số", 0.92], ["Hiệu số", 0.71], ["Phong độ", 0.83]]]),
    "MR-11": ("versus", ["VÒNG TIẾP THEO", "HÀ NỘI", "NAM ĐỊNH", "Cuối tuần • Sân khách"]),
    "MR-05": ("moments", [["23'", "Bị dẫn trước từ sớm"], ["61'", "Gỡ hòa sau giờ nghỉ"], ["90+3'", "Ngược dòng phút bù giờ"]]),
    "MR-07": ("table", ["BẢNG CHỈ SỐ", [["Cơ hội rõ rệt", 0.85], ["Kiểm soát bóng", 0.62], ["Hiệu suất dứt điểm", 0.73]]]),
    "MR-10": ("statement", ["NHẬN ĐỊNH", "Điểm mấu chốt", ""]),
    "MR-12": ("source", ["NGUỒN DỮ LIỆU", "Nguồn + giờ cập nhật"]),
    "BP-01": ("statement", ["CÂU HỎI", "Sự thật mở đầu", ""]),
    "BP-02": ("statement", ["DỮ KIỆN", "Điều cần nhớ", "Nguồn + ngày"]),
    "BP-03": ("poster", ["profile"]),
    "BP-05": ("moments", [["2015", "Khởi đầu sự nghiệp"], ["2020", "Đỉnh cao phong độ"], ["2024", "Tái sinh mạnh mẽ"]]),
    "BP-06": ("money", ["€85TR", "Thương vụ của mùa hè", "Bên mua • Bên bán"]),
    "BP-07": ("duel", ["ĐỘI A", "ĐỘI B", [("PHÍ CHUYỂN NHƯỢNG", "85", "120", "away"),
                                           ("BÀN THẮNG", "30", "19", "home")], "Nguồn + ngày"]),
    "BP-09": ("statement", ["BẢN SẮC", "Giá trị cốt lõi", ""]),
    "BP-10": ("duel", ["HÀ NỘI", "HẢI PHÒNG", [("ĐỐI ĐẦU", "12", "8", "home"),
                                                ("DANH HIỆU", "5", "5", "tie")], "Nguồn + ngày"]),
    "BP-11": ("moments", [["1954", "Cột mốc lịch sử"], ["1988", "Thế hệ vàng"], ["2024", "Di sản còn lại"]]),
    "BP-12": ("myth", ["Điều gây tranh cãi", "Các góc nhìn và bằng chứng"]),
    "BP-15": ("table", ["TOP GHI BÀN", [["Bàn thắng", 0.95], ["Kiến tạo", 0.68], ["Hat-trick", 0.42]]]),
    "BP-08": ("money", []),
    "BP-13": ("myth", []),
    "BP-14": ("duel", ["A", "B", [("TIÊU CHÍ 1", "9", "7", "home"),
                                   ("TIÊU CHÍ 2", "5", "5", "tie")], "Nguồn + ngày"]),
    "BP-16": ("statement", ["GÓC NHÌN MỚI", "Số liệu tiết lộ", "Nguồn + ngày"]),
    "BP-04": ("moments", [["HT'", "Dẫn trước 1 bàn"], ["60'", "Đối thủ vùng lên"], ["85'", "Khoảnh khắc định đoạt"]]),
    "BP-17": ("moments", [["01'", "Khởi đầu thận trọng"], ["45+1'", "Bàn thắng giờ nghỉ"], ["90'", "Dấu chấm hết"]]),
    "BP-18": ("statement", ["BỨC TRANH LỚN", "Nhìn rộng hơn", ""]),
    "BP-19": ("statement", ["KẾT LUẬN", "Nhìn khác đi", ""]),
    "BP-20": ("source", ["KIỂM CHỨNG", "Nguồn + ngày"]),
}

LONG = {
    "TA-01": ("lstate", ["CÂU HỎI CHIẾN THUẬT", "Vấn đề của trận đấu?"]),
    "TA-02": ("lcontext", ["HÀ NỘI", "NAM ĐỊNH", "2 - 0", "V.League • Tối nay"]),
    "TA-03": ("pitch410", []),
    "TA-04": ("lineup", []),
    "TA-05": ("pitchposs", []),
    "TA-06": ("pitchpress", []),
    "TA-07": ("buildup", []),
    "TA-08": ("trap", []),
    "TA-09": ("space", []),
    "TA-10": ("overlap", []),
    "TA-11": ("freeze", []),
    "TA-12": ("sequence", []),
    "TA-13": ("duel1v1", []),
    "TA-14": ("adjust", []),
    "TA-15": ("shift", []),
    "TA-16": ("bars", [[ "Cơ hội rõ rệt", 0.8], ["Sút trúng đích", 0.6], ["Thu hồi bóng", 0.9]]),
    "TA-17": ("amap", []),
    "TA-18": ("takes", ["Tuyến giữa thắng nhờ pressing tầm cao",
                        "Cánh trái là hướng tấn công chính",
                        "Thay người phút 60 đổi cục diện"]),
    "TA-19": ("lstate", ["LUẬN ĐIỂM", "Góc nhìn của Allen"]),
}

BUILDERS = {
    "statement": lambda a: statement(*a),
    "poster": lambda a: poster(*a),
    "duel": lambda a: duel(*a),
    "source": lambda a: source_slip(*a),
    "end": lambda a: end_card(*a),
    "chip": lambda a: label_chip(*a),
    "moments": lambda a: moments(a),
    "money": lambda a: money(*a),
    "table": lambda a: table_card(*a),
    "myth": lambda a: myth(*a),
    "versus": lambda a: versus(*a),
    "takes3": lambda a: takes_short(a),
    "sting": lambda a: sting(),
    "score": lambda a: score_card(*a),
    "lstate": lambda a: l_statement(*a),
    "lcontext": lambda a: l_context(*a),
    "bars": lambda a: l_bars(a),
    "takes": lambda a: l_takeaways(a),
}


def pitch410():
    # White midfield trio circulates; one coral presser steps to the ball.
    els = l_pitch([], "SƠ ĐỒ 4-3-3 • TRẮNG CẦM BÓNG")
    for x, n, s in [(400, "4", "p1"), (700, "8", "p2"), (1000, "10", "p3")]:
        els += token(x, 450, n, s)
    els += token(550, 620, "6", "o1", fill=CORAL, tfill=INK)
    els += ball(800, 500)
    els += [arrow(500, 490, 180, color=PAPER),
            arrow(660, 655, 140, color=CORAL, dash=[14, 10])]
    return els


def pitchposs():
    # Progression chain 6→8→10 plus wide run into shaded half-space pocket.
    els = l_pitch([], "KHI CÓ BÓNG • DÂNG CAO CÁNH")
    els += [locked_rect(1150, 250, 220, 260, SLATE, 0.35)]
    for x, n, s in [(500, "6", "p1"), (800, "8", "p2"), (1100, "10", "p3"), (1400, "11", "p4")]:
        els += token(x, 400, n, s)
    els += ball(900, 455)
    els += [arrow(600, 440, 180, color=PAPER),
            arrow(900, 440, 180, color=PAPER),
            arrow(1200, 440, 180, color=PAPER, dash=[14, 10])]
    return els


def pitchpress():
    # Front three step up together; trap pocket shaded, high line marked.
    els = l_pitch([], "PRESSING TẦM CAO • BẪY BIÊN")
    els += [locked_rect(1050, 350, 450, 300, CORAL, 0.22),
            guide_line(140, 300, 1640, color=CORAL, dash=[10, 10]),
            val_text(150, 240, 420, 50, "BẪY PRESSING", 36, DISP, CORAL,
                     "dline", align="left")]
    for x, n, s in [(700, "9", "p1"), (1000, "10", "p2"), (1300, "7", "p3")]:
        els += token(x, 350, n, s, fill=CORAL, tfill=INK)
    els += token(1100, 550, "6", "o1")
    els += ball(1200, 605)
    els += [arrow(790, 390, 180, color=CORAL, dash=[10, 10]),
            arrow(1090, 390, 180, color=CORAL, dash=[10, 10]),
            arrow(1390, 390, 180, color=CORAL, dash=[10, 10])]
    return els


def freeze():
    # Focus man isolated: coral halo + dimmed surroundings + stamp.
    els = l_pitch([], "ĐÓNG BĂNG PHÚT 67")
    els += [{"id": _id("deco"), "type": "figure", "subType": "circle",
             "x": 878, "y": 398, "width": 140, "height": 140, "fill": INK2,
             "stroke": CORAL, "strokeWidth": 8,
             "selectable": False, "draggable": False,
             "resizable": False, "removable": False}]
    els += token(900, 420, "9", "focus", fill=CORAL, tfill=INK)
    els += token(600, 550, "4", "p1", opacity=0.75) + token(1200, 550, "5", "p2", opacity=0.75)
    els += ball(962, 545)
    els.append(val_text(1400, 130, 340, 60, "67:00", 48, DISP, CORAL, "stamp", align="right"))
    return els


def lineup_xi():
    # Full 4-3-3 XI, one team: kickoff shape card, no ball yet.
    els = l_pitch([], "ĐỘI HÌNH XUẤT PHÁT • 4-3-3")
    els += token(250, 500, "1", "gk")
    for y, n, s in [(230, "2", "d1"), (390, "4", "d2"), (550, "5", "d3"), (710, "3", "d4")]:
        els += token(550, y, n, s)
    for y, n, s in [(310, "6", "m1"), (480, "8", "m2"), (650, "10", "m3")]:
        els += token(850, y, n, s)
    for y, n, s in [(260, "7", "f1"), (480, "9", "f2"), (700, "11", "f3")]:
        els += token(1200, y, n, s)
    return els


def buildup():
    # Playing out from the back: shaded build-up third + progressive chain.
    els = l_pitch([], "TRIỂN KHAI BÓNG • TỪ TUYẾN DƯỚI")
    els += [locked_rect(140, 150, 450, 650, SLATE, 0.3)]
    els += token(280, 500, "1", "gk")
    els += token(550, 350, "4", "cb1") + token(550, 650, "5", "cb2")
    els += token(850, 500, "8", "m")
    els += ball(380, 553)
    els += [arrow(380, 480, 160, color=PAPER),
            arrow(650, 420, 180, color=PAPER),
            arrow(950, 490, 160, color=PAPER, dash=[14, 10])]
    return els


def trap():
    # Wide pressing trap: pincer runs converge on the carrier by the line.
    els = l_pitch([], "BẪY PRESSING • ÉP RA BIÊN")
    els += [locked_rect(1300, 350, 350, 350, CORAL, 0.22)]
    els += token(1250, 400, "7", "p1", fill=CORAL, tfill=INK)
    els += token(1250, 700, "10", "p2", fill=CORAL, tfill=INK)
    els += token(1400, 550, "6", "o1")
    els += ball(1500, 605)
    els += [arrow(1350, 445, 130, color=CORAL, dash=[10, 10]),
            arrow(1350, 655, 130, color=CORAL, dash=[10, 10])]
    return els


def space():
    # Vacated half-space: shaded channel + run into it, marker dragged out.
    els = l_pitch([], "KHOẢNG TRỐNG • KHAI THÁC")
    els += [locked_rect(1000, 150, 300, 650, SLATE, 0.35)]
    els += token(750, 500, "10", "p1")
    els += token(950, 680, "5", "o1", fill=CORAL, tfill=INK)
    els += ball(850, 553)
    els += [arrow(840, 490, 300, color=PAPER, dash=[14, 10])]
    return els


def overlap():
    # Fullback overlap beyond the winger, beaten defender behind play.
    els = l_pitch([], "CHỒNG BIÊN • OVERLAP")
    els += token(500, 650, "2", "fb")
    els += token(900, 500, "7", "w")
    els += token(1200, 550, "3", "o1", fill=CORAL, tfill=INK)
    els += ball(1000, 553)
    els += [arrow(590, 690, 380, color=PAPER, dash=[14, 10])]
    return els


def duel1v1():
    # Isolated duel in a shaded arena, ball contested between the two.
    els = l_pitch([], "ĐỐI ĐẦU 1V1 • CÁNH PHẢI")
    els += [locked_rect(750, 300, 450, 350, SLATE, 0.3)]
    els += token(800, 475, "7", "a")
    els += token(1050, 475, "3", "d", fill=CORAL, tfill=INK)
    els += ball(962, 503)
    return els


def structure_shift():
    # Before/after team shape: same numbers, higher second block.
    els = [val_text(140, 120, 1640, 100, "THAY ĐỔI CẤU TRÚC", 72, DISP, CORAL, "kicker", align="left")]
    for i, tag in enumerate(["TRƯỚC", "SAU"]):
        x = 140 + i * 850
        els.append(locked_rect(x, 280, 790, 560, INK2))
        els.append(val_text(x + 40, 860, 710, 60, tag, 48, DISP, CORAL if i else MIST, f"tag-{i}", align="left"))
    for n, s, dx, dy in [("4", "s1", 0, 80), ("8", "s2", 200, 30), ("10", "s3", 400, 80)]:
        els += token(300 + dx, 420 + dy, n, s)
    for n, s, dx, dy in [("4", "t1", 0, 0), ("8", "t2", 200, -50), ("10", "t3", 400, 0)]:
        els += token(1150 + dx, 420 + dy, n, s)
    els.append(arrow(895, 540, 60))
    els.append(credit("", 1920, 990))
    return els


def activity_map():
    # Touch clusters down the left wing + direction of play.
    els = l_pitch([], "BẢN ĐỒ HOẠT ĐỘNG • CÁNH TRÁI")
    for x, y, r, fill in [(350, 400, 44, PAPER), (420, 520, 56, SLATE),
                          (500, 350, 32, PAPER), (560, 600, 48, SLATE),
                          (640, 450, 40, PAPER), (480, 680, 28, SLATE),
                          (700, 560, 36, PAPER), (380, 600, 24, SLATE)]:
        els.append({"id": _id("deco"), "type": "figure", "subType": "circle",
                    "x": x - r / 2, "y": y - r / 2, "width": r, "height": r,
                    "fill": fill, "opacity": 0.5, "selectable": False,
                    "draggable": False, "resizable": False, "removable": False})
    els += ball(750, 478)
    els += [arrow(450, 500, 300, color=PAPER, dash=[14, 10])]
    return els


def sequence():
    els = [val_text(140, 120, 1640, 100, "DIỄN BIẾN 3 NHỊP", 72, DISP, CORAL, "kicker", align="left")]
    for i in range(3):
        x = 140 + i * 560
        els.append(locked_rect(x, 280, 500, 420, INK2))
        els.append(val_text(x + 30, 310, 120, 100, str(i + 1), 80, DISP, CORAL, f"f-{i}", align="left"))
        els.append(val_text(x + 30, 560, 440, 110, "Mô tả nhịp", 44, BODY, PAPER, f"c-{i}", align="left", weight="normal"))
    els.append(credit("", 1920, 990))
    return els


def adjust():
    els = [val_text(140, 120, 1640, 100, "ĐIỀU CHỈNH", 72, DISP, CORAL, "kicker", align="left")]
    for i, tag in enumerate(["TRƯỚC", "SAU"]):
        x = 140 + i * 850
        els.append(locked_rect(x, 280, 790, 560, INK2))
        els.append(val_text(x + 40, 860, 710, 60, tag, 48, DISP, CORAL if i else MIST, f"tag-{i}", align="left"))
    els.append(arrow(945, 540, 60))
    els.append(credit("", 1920, 990))
    return els


BUILDERS.update({
    "pitch410": lambda a: pitch410(),
    "lineup": lambda a: lineup_xi(),
    "pitchposs": lambda a: pitchposs(),
    "pitchpress": lambda a: pitchpress(),
    "buildup": lambda a: buildup(),
    "trap": lambda a: trap(),
    "space": lambda a: space(),
    "overlap": lambda a: overlap(),
    "freeze": lambda a: freeze(),
    "duel1v1": lambda a: duel1v1(),
    "sequence": lambda a: sequence(),
    "adjust": lambda a: adjust(),
    "shift": lambda a: structure_shift(),
    "amap": lambda a: activity_map(),
})


def main():
    global _n
    made = []
    for cid, (kind, args) in SHORT.items():
        _n = 0
        OUT.joinpath(f"{cid}.short.json").write_text(
            json.dumps(doc(1080, 1920, BUILDERS[kind](args)), ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")
        made.append(cid)
    for cid, (kind, args) in LONG.items():
        _n = 0
        OUT.joinpath(f"{cid}.long.json").write_text(
            json.dumps(doc(1920, 1080, BUILDERS[kind](args)), ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")
        made.append(cid)
    print(f"wrote {len(made)} starters: {', '.join(made)}")


if __name__ == "__main__":
    main()
