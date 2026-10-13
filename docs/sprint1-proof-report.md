# Sprint proof report — 47 starters (Sprint 1 CHỐT v1 ngày 2026-10-13 + Wave 2
P1 + Sprint 2; mọi thay đổi visual Sprint 1 phải lên version mới theo
change_policy; nguồn: `docs/card-inventory.md` — 69 cards)

Xem tại: `/template-foundation/preview.html`, section “SPRINT 1 PROOF AUDIT”.
File lẻ: `9.0.0/previews/<short|long>-<id>-proof.png`. Tái tạo:
`build_starters.py` → `render_starters.py` → `write_audit.py proof-rows.json`
(`write_audit` chạy lại nhiều lần không trùng lặp).

## Gates tự động (pass 35/35)

- Schema/ids/fonts/slots/safe-area/no-clip/element-types: `test_studio_starters.py`
- Contrast WCAG + overlap + decor-che-chữ (3 điểm mẫu dọc mỗi slot,
  bắt cả trường hợp chữ vắt ngang biên 2 nền): `audit_cards.py` → **0 issues**
  (`test_contrast_overlap_audit_clean` khóa lại).
- Pixel-exact + audit section: `test_studio_proofs.py`. Palette ±90: **0 px lạ**.

## Quy tắc độ nổi đang áp dụng (giữ theme ink/coral)

- Boss đủ opacity ≥ 4.5; chữ dim cố ý (số thua) ≥ 3.0 theo chuẩn chữ lớn WCAG.
- Chữ PAPER trên coral chỉ 2.8 → lót scrim INK (duel labels) hoặc đổi chữ INK
  (claim long, seal AKB, teams score) = 5.4.
- Loser duel 0.55 → 0.8 (≈4.1, vẫn chìm hơn winner PAPER + gạch chân).

## Lỗi bố cục bắt được từ proof (đã sửa + verify mắt)

| Card | Lỗi | Sửa |
|---|---|---|
| C-07, BP-14 | team khách INK trên nền INK → tàng hình | team-away → PAPER |
| MR-01, MR-10, BP-01… | claim 210 tràn box/phải (9 cards `statement`) | claim → 168; band ôm support (940/320); BP-01 rút placeholder |
| C-03, MR-01, MR-10, BP-18 | claim vẫn tràn box 7–155px (đo PIL, mắt thường suýt sót) | rút placeholder (C-03 “Câu then chốt”, MR-01 “Kết quả mới”, MR-10 “Điểm mấu chốt”, BP-18 “Nhìn rộng hơn”) + gate đo tràn chữ bằng fonts khóa |
| C-09, MR-12, BP-20 | slip treo cao, void dưới 620px | card hạ 100px, seal INK |
| C-10 | band rỗng 230px dưới tên kênh | band ôm khít (780/310) |
| MR-02, MR-04 | band rỗng 410px dưới tên đội | band ôm (790/180) |
| BP-08 | dòng giải thích kẹp biên band; bars lạc lõng; note MIST/chìm | dựng lại money quanh band 580/1120, bars INK2/INK, note INK, decor chân |
| TA-01, TA-19 | claim INK vắt biên band (nửa tàng hình) | band phủ từ 220; claim lùi vào 320 (trừ hao diacritics Việt tràn đỉnh box trong proof PIL) |
| TA-02 | box kicker/score chồng 5% | kicker 110 → 90 |
| U-02/03/05 | chip lơ lửng giữa void (đúng bản chất overlay lower-third) | giữ nguyên + ghi chú |

## Lỗi hạ tầng audit (không xem được long-form)

- Nguyên nhân: proof `long-*` nằm ở package short (`9.0.0/previews`) nhưng
  server resolve `long-*` từ package `longform-9.0.0` → 404 cả 11 cards long.
- Sửa: `render_starters.py` render proof theo đúng package phục vụ
  (short → `9.0.0/previews`, long → `longform-9.0.0/previews`), tự dọn file
  stale khác-aspect; `test_no_stale_cross_aspect_proofs` khóa lại. Đã verify
  HTTP 200 cho `long-ta-01`, `long-ta-18`, `short-c-03`.

## Vòng 5 — Sprint 2: 8 cards tactical P1 (từ file inventory gốc)

- Đối chiếu inventory đủ 69 cards: Sprint 1 (35, đã chốt) + Wave 2 lẻ P1
  (MR-05/07, BP-04/17, đã xong) + **Sprint 2 (8 TA)** + Sprint 3 (30 cards
  P1/P2 còn lại — theo file gốc, chỉ build khi video thực tế cần).
- Sprint 2 theo ngữ pháp analyst (Tifo/MNF/DrawTactics/FIFA): XI full 4-3-3
  (TA-04), buildup shading + chuỗi tịnh tiến (TA-07), bẫy biên pincer + vùng
  bẫy (TA-08), túi half-space + chạy vào (TA-09), overlap (TA-10), đấu 1v1
  trong vùng shaded (TA-13), mini-pitch trước/sau (TA-15), cụm chạm bóng
  + hướng đá (TA-17). Token 2 màu, ball marker, markings đủ, tag giải thích.
- Filter chọn card (`card_selector.py`) mở rộng `_tactical_starter`: lineup,
  buildup, trap, space, movement, map, before/after, adjustment → đúng TA;
  test `test_long_tactical_signals_map_to_sprint2` khóa 9 signals.
- Audit 0 issues / 47 proofs; full suite 251 passed; audit page 47 cards.

## Vòng 4 — nâng cấp 4 cards pitch theo ngữ pháp analyst

- Đối chiếu Tifo (token 2 màu + số áo), MNF/Carragher (freeze + timestamp),
  DrawTactics (liền = chuyền, đứt = chạy; play trái→phải), FIFA/UEFA
  (vùng shading, line khối đội hình): pitch cũ thua ở 6 điểm — 1 màu token,
  không bóng, thiếu markings, không vùng/line, focus không halo.
- Sửa 4 cards (`build_starters.py`, không đụng validator/renderer ngoài
  stroke outline cho vòng tròn giữa/6-yard/vòng focus):
  - Markings đủ: vòng tròn giữa, chấm pen, 6-yard, gôn.
  - TA-03: trắng 4-8-10 cầm bóng + số 6 coral pressing, mũi tên chuyền liền
    (trắng) + chạy đứt (coral), tag giải thích màu.
  - TA-05: chuỗi tịnh tiến 6→8→10 + chạy cánh đứt vào túi half-space shaded.
  - TA-06: 3 mũi pressing đồng bộ + line cao đứt + nhãn BẪY + vùng bẫy shaded,
    số 6 trắng kẹt bóng trong vùng.
  - TA-11: focus số 9 vòng reticle coral + bóng ở chân + vệ tinh dim 0.75
    (0.55 làm số INK chìm dưới chuẩn nên nâng) + stamp 67:00.
  - Ball marker kéo được trong Studio; tag pitch lùi khỏi biên (165).
- Khóa bằng `test_pitch_team_split_and_ball`,
  `test_pressing_markers_and_freeze_ring`; audit 0 issues; full suite 233 passed.

## Còn lại cho owner

1. Duyệt mắt từng proof, đổi `visual: todo → pass/block` trong `proof-rows.json`,
   chạy lại `write_audit.py` (idempotent).
2. Mở `/studio` (cần mạng + `POLOTNO_API_KEY`), xuất PNG vào `pack-drop/10.0.0`,
   `python -m apps.pack_import.build pack-drop/10.0.0`.
3. Khác biệt PIL proof vs browser đã biết: browser co chữ tràn box
   (`change-font-size`); slot nào sát biên thì kiểm kỹ trên Studio.
