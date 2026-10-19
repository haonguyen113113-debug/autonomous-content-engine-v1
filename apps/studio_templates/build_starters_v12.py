"""Build 21 planned long-form starters (TA-20..24, LC-01..16) for v12.

Reuses the locked v11 builder vocabulary (imported, not duplicated):
locked cyber palette, Tektur/BeVietnam faces, slot-bound dynamic text,
real Vietnamese samples (no placeholders), detailing on dead zones only.
Run: python apps/studio_templates/build_starters_v12.py
Next: render_starters.py, check_starters.py, pytest.
"""
from __future__ import annotations

import json
from pathlib import Path

from apps.studio_templates.build_starters_v11 import (
    AMBER, BODY, CYAN, DISP, MAGENTA, NUM, PANEL, PAPER, SLATE, VOID,
    arrow, badge, ball, corner_marks, credit, doc, guide_line, kick,
    l_bars, l_pitch, l_statement, locked_circle, locked_rect, perforation,
    ring, token, val_text,
)

OUT = Path(__file__).parent
ROOT = Path(__file__).resolve().parent.parent.parent
W = 1920

LONG_BEDS = {"cyber-grid", "floodlight", "grid-deep", "inkstorm", "neon-bokeh", "pitch-void"}

PACK_LONG = ROOT / "template_foundation" / "templates" / "allen-knows-ball" / "longform-12.0.0" / "resources" / "pack"


def bed(slug: str) -> dict:
    raise AssertionError("beds removed in v12; use bed_pack")


def bed_pack(stem: str) -> dict:
    for ext in (".jpg", ".png", ".jpeg"):
        if (PACK_LONG / f"{stem}{ext}").is_file():
            filename = f"{stem}{ext}"
            break
    else:
        raise AssertionError(stem)
    return {"id": "bed-1", "type": "image", "x": 0, "y": 0, "width": 1920, "height": 1080,
            "src": f"/template-foundation/resources/pack/{filename}",
            "selectable": False, "draggable": False, "resizable": False, "removable": False}


# ---------------- tactical+ (starter path, diagrams carry the point) ----------------

def ta_setpiece_attack():
    els = [*token(700, 560, "9", "r-9"), *token(900, 640, "7", "r-7"), *token(1100, 560, "10", "r-10"),
           arrow(760, 620, 300, MAGENTA), arrow(960, 700, 300, MAGENTA),
           *ball(1290, 690)]
    return l_pitch(els, "PHẠT GÓC TẤN CÔNG")


def ta_setpiece_defense():
    els = [*token(700, 560, "4", "r-4"), *token(900, 560, "5", "r-5"), *token(1100, 560, "6", "r-6"), *token(900, 700, "1", "r-1"),
           guide_line(640, 640, 620, SLATE)]
    return l_pitch(els, "PHẠT GÓC PHÒNG NGỰ")


def ta_transitions():
    els = [*token(600, 500, "8", "r-8"), *token(1250, 500, "11", "r-11"),
           arrow(660, 560, 420, CYAN), arrow(1230, 640, -420, MAGENTA),
           *ball(1050, 600)]
    return l_pitch(els, "CHUYỂN TRẠNG THÁI HAI CHIỀU")


def ta_rest_defense():
    els = [*token(760, 620, "6", "r-6"), *token(960, 660, "4", "r-4"), *token(1160, 620, "2", "r-2"), guide_line(700, 720, 520, CYAN)]
    return l_pitch(els, "PHÒNG NGỰ KHI MẤT BÓNG")


def ta_gk_buildup():
    els = [*token(420, 620, "1", "r-1"), *token(640, 560, "4", "r-4"), *token(640, 700, "3", "r-3"),
           arrow(480, 640, 220, CYAN), arrow(700, 580, 220, CYAN),
           *ball(480, 640)]
    return l_pitch(els, "THỦ MÔN TRIỂN KHAI BÓNG")


# ---------------- narrative long builders (v12-local, no filler) ----------------

def l_statement2(kicker_en, claim, support):
    W = 1920
    return [
        locked_rect(1116, 0, W - 1116, 1080, PANEL),
        locked_rect(1113, 0, 6, 1080, CYAN),
        ring(936, 397, 286, SLATE, 5),
        kick(kicker_en, 140, W, "kicker"),
        locked_rect(140, 220, 120, 10, MAGENTA),
        val_text(140, 320, 1100, 200, claim, 100, DISP, PAPER, "claim", align="left"),
        locked_rect(140, 540, 110, 10, CYAN),
        locked_rect(250, 540, 110, 10, MAGENTA),
        val_text(140, 630, 900, 110, support, 40, BODY, PAPER, "support", align="left", weight="normal"),
        val_text(1230, 300, 550, 200, "60", 200, NUM, PAPER, "numeral"),
        val_text(1230, 560, 550, 80, "Diễn giải", 44, BODY, PAPER, "sub", weight="normal"),
        credit("", W, 990),
    ]


def l_bars2(rows):
    W = 1920
    els = [
        locked_rect(1116, 0, W - 1116, 1080, PANEL),
        locked_rect(1113, 0, 6, 1080, CYAN),
        val_text(140, 120, 900, 100, "Bằng chứng số", 72, DISP, PAPER, "kicker", align="left"),
        locked_rect(140, 230, 100, 10, CYAN),
        locked_rect(240, 230, 100, 10, MAGENTA)]
    y = 320
    for i, (label, frac) in enumerate(rows):
        els.append(val_text(140, y, 500, 70, label, 48, BODY, PAPER, f"l-{i}", align="left", weight="normal"))
        els.append(locked_rect(140, y + 90, int(900 * frac), 56, CYAN))
        els.append(val_text(140 + int(900 * frac) + 30, y + 80, 300, 80,
                            str(int(round(frac * 40))), 56, NUM, PAPER, f"v-{i}", align="left"))
        y += 200
    els.append(credit("Nguồn + ngày", W, 990))
    return els


def l_moments4(items):
    els = [locked_rect(140, 120, 1640, 8, CYAN),
           val_text(140, 160, 900, 80, "Dòng thời gian", 64, DISP, PAPER, "title", align="left")]
    x = 150
    for i, (when, what) in enumerate(items):
        els.append(locked_circle(x + 133, 240, 34, 34, MAGENTA))
        els.append(val_text(x, 300, 300, 60, when, 52, NUM, PAPER, f"t-{i}"))
        els.append(val_text(x, 380, 300, 140, what, 36, BODY, PAPER, f"e-{i}", align="left", weight="normal"))
        x += 410
    els.append(credit("", W, 990))
    return els


def l_duel(home, away, rows):
    els = [val_text(140, 120, 700, 90, home, 84, DISP, PAPER, "home", align="left"),
           val_text(1080, 120, 700, 90, away, 84, DISP, PAPER, "away", align="left"),
           locked_rect(140, 230, 100, 10, CYAN), locked_rect(1080, 230, 100, 10, MAGENTA)]
    y = 300
    for i, (label, hv, av) in enumerate(rows):
        els.append(val_text(140, y, 700, 60, label, 40, BODY, SLATE, f"l-{i}", align="left", weight="normal"))
        els.append(val_text(140, y + 70, 330, 90, hv, 72, NUM, PAPER, f"h-{i}", align="left"))
        els.append(val_text(1080, y + 70, 330, 90, av, 72, NUM, PAPER, f"a-{i}", align="left"))
        y += 210
    els += badge(1560, 700, 150, home[:1], "crest-home")
    els += badge(1560, 880, 130, away[:1], "crest-away")
    els.append(credit("", W, 990))
    return els


def l_quote(kicker, text, speaker, source):
    return [
        locked_rect(140, 120, 8, 700, MAGENTA),
        kick(kicker, 140, W, "kicker"),
        val_text(200, 280, 1300, 320, text, 72, BODY, PAPER, "quote", align="left", weight="normal"),
        locked_rect(200, 640, 220, 10, CYAN),
        val_text(200, 680, 900, 80, speaker, 48, DISP, PAPER, "speaker", align="left"),
        val_text(200, 780, 900, 60, source, 36, BODY, SLATE, "source", align="left", weight="normal"),
        credit("", W, 990),
    ]


def l_money(amount, line, note):
    return [
        kick("TIỀN BẠC", 140, W, "kicker"),
        val_text(140, 240, 1200, 220, amount, 190, NUM, PAPER, "amount", align="left"),
        locked_rect(140, 500, 700, 60, MAGENTA, 0.5),
        val_text(140, 600, 1100, 120, line, 48, BODY, PAPER, "line", align="left", weight="normal"),
        locked_rect(1230, 240, 550, 400, PANEL, 1.0, extra={"stroke": CYAN, "strokeWidth": 4}),
        val_text(1270, 300, 470, 120, note, 40, BODY, PAPER, "note", align="left", weight="normal"),
        credit("", W, 990),
    ]


def l_history(year, meaning):
    return [
        val_text(140, 220, 900, 260, year, 240, NUM, PAPER, "year", align="left"),
        locked_rect(140, 500, 220, 10, MAGENTA),
        val_text(140, 560, 1100, 200, meaning, 56, BODY, PAPER, "meaning", align="left", weight="normal"),
        ring(1450, 350, 300, SLATE, 5),
        credit("", W, 990),
    ]


def l_myth(myth_text, fact_text):
    return [
        locked_rect(0, 180, 1920, 360, MAGENTA),
        val_text(140, 220, 900, 80, "Ngộ nhận", 64, DISP, VOID, "myth-k", align="left"),
        val_text(140, 320, 1300, 180, myth_text, 52, BODY, VOID, "myth", align="left", weight="normal"),
        locked_rect(0, 546, 1920, 6, CYAN),
        val_text(140, 600, 900, 80, "Sự thật", 64, DISP, PAPER, "fact-k", align="left"),
        val_text(140, 700, 1300, 180, fact_text, 52, BODY, PAPER, "fact", align="left", weight="normal"),
        credit("", W, 990),
    ]


def l_poster(name, role, rows):
    els = [locked_circle(200, 290, 300, 300, PANEL, extra={"stroke": CYAN, "strokeWidth": 5}),
           val_text(880, 280, 880, 110, name, 84, DISP, PAPER, "name", align="left"),
           val_text(880, 410, 880, 70, role, 44, BODY, SLATE, "role", align="left", weight="normal"),
           locked_rect(880, 500, 220, 10, MAGENTA)]
    y = 580
    for i, (label, value) in enumerate(rows):
        els.append(val_text(880, y, 440, 60, label, 40, BODY, SLATE, f"l-{i}", align="left", weight="normal"))
        els.append(val_text(1380, y - 10, 380, 80, value, 64, NUM, PAPER, f"v-{i}", align="left"))
        y += 120
    els.append(credit("", W, 990))
    return els


def l_versus(comp, home, away, when):
    els = [val_text(140, 120, 900, 80, comp, 60, DISP, CYAN, "comp", align="left"),
           val_text(140, 300, 700, 130, home, 96, DISP, PAPER, "home", align="left"),
           val_text(140, 470, 700, 80, when, 44, BODY, SLATE, "when", align="left", weight="normal"),
           val_text(1080, 300, 700, 130, away, 96, DISP, PAPER, "away", align="left"),
           locked_rect(940, 280, 6, 300, CYAN)]
    els += badge(1560, 700, 150, home[:1], "crest-home")
    els += badge(1560, 880, 130, away[:1], "crest-away")
    els.append(credit("", W, 990))
    return els


def l_end():
    # Baked channel badge on the ending plate is the emblem; add only the
    # wordmark beneath it (opaque rings would cover the badge).
    return [
        locked_rect(760, 620, 400, 10, CYAN),
        val_text(560, 700, 800, 110, "ALLEN KNOWS BALL", 72, DISP, PAPER, "mark"),
    ]


CARDS = {
    "TA-20": (ta_setpiece_attack, "long-tactical_explainer"),
    "TA-21": (ta_setpiece_defense, "long-tactical_explainer"),
    "TA-22": (ta_transitions, "long-tactical_explainer"),
    "TA-23": (ta_rest_defense, "long-tactical_explainer"),
    "TA-24": (ta_gk_buildup, "long-tactical_explainer"),
    "LC-01": (lambda: l_statement2("CHƯƠNG MỞ ĐẦU", "Câu hỏi của chương này là gì?", "Mở đầu mỗi chương mới"), "long-hook_card"),
    "LC-02": (lambda: l_statement2("CÂU HỎI LỚN", "Điều cả video đi tìm", "Đặt ra trước khi phân tích"), "long-hook_card"),
    "LC-03": (lambda: l_moments4([["2019", "Mầm mống"], ["2021", "Bước ngoặt"],
                                  ["2023", "Đỉnh cao"], ["2026", "Di sản"]]), "long-chart_timeline"),
    "LC-04": (lambda: l_duel("HÀ NỘI", "NAM ĐỊNH", [("BÀN THẮNG", "45", "38"),
                                                   ("KIẾN TẠO", "30", "30")]), "long-duel_columns"),
    "LC-05": (lambda: l_bars2([["Bàn thắng kỳ vọng", 0.82], ["Cơ hội rõ rệt", 0.64], ["Cú sút", 0.91]]), "long-stat_leader"),
    "LC-06": (lambda: l_quote("TRÍCH DẪN", "Chúng tôi đến đây để thắng.", "Huấn luyện viên", "Họp báo trước trận"), "long-quote_card"),
    "LC-07": (lambda: l_money("€85TR", "Thương vụ của mùa hè", "Bên mua • Bên bán"), "long-stat_leader"),
    "LC-08": (lambda: l_history("2018", "Năm bóng đá Việt Nam đổi đời"), "long-chart_timeline"),
    "LC-09": (lambda: l_myth("Tiền mua được mọi danh hiệu", "Bằng chứng từ 5 mùa gần nhất"), "long-quote_card"),
    "LC-10": (lambda: l_bars2([["Điểm số", 0.95], ["Hiệu số", 0.71], ["Phong độ", 0.83]]), "long-duel_columns"),
    "LC-11": (lambda: l_poster("NGUYỄN TIẾN LINH", "Tiền đạo • Đội tuyển", [("Bàn thắng", "19"), ("Kiến tạo", "7")]), "long-player_poster_side"),
    "LC-12": (lambda: l_statement2("NHẬN ĐỊNH", "Kết luận của Allen", "Khép lại video"), "long-hook_card"),
    "LC-13": (lambda: l_quote("NGUỒN", "Tuyên bố được kiểm chứng", "Ban tổ chức giải", "Thông cáo • Hôm nay"), "long-source_card"),
    "LC-14": (l_end, "long-ending"),
    "LC-15": (lambda: l_versus("VÒNG TIẾP THEO", "HÀ NỘI", "NAM ĐỊNH", "Cuối tuần • Sân khách"), "long-fixture_card"),
    "LC-16": (lambda: l_quote("ĐÍNH CHÍNH", "Thông tin cập nhật chính xác", "Ban biên tập", "Nguồn + giờ cập nhật"), "long-source_card"),
}


def main():
    made = []
    for cid, (fn, plate) in CARDS.items():
        els = [bed_pack(plate)] + fn()
        OUT.joinpath(f"{cid}.long.json").write_text(
            json.dumps(doc(1920, 1080, els), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        made.append(cid)
    print(f"wrote {len(made)} v12 long starters: {', '.join(made)}")


if __name__ == "__main__":
    main()
