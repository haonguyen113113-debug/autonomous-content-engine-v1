# Inventory research — Sprint 1 mapping (Oct 2026, chưa build)

Nguồn: `Allen_Knows_Ball_Template_Card_Inventory.md` (35 card Sprint 1),
polotno-sdk + design skill references, schema đã verify.

## Card đã có nền (starter/plate hiện tại dùng được)

| Nhóm | Card | Nền có sẵn |
|---|---|---|
| Core | C-07 Two-way Comparison | duel_columns starter (proof-pass) |
| Core | C-06 Number Highlight | stat_leader plate |
| Core | C-04 Spotlight | player posters |
| Core | C-03 Full-screen Statement | goal/hook plates |
| Core | C-09 Source, C-10 End Card | source card + end-card renderer |
| MR | MR-01 Breaking, MR-02 Score, MR-04 Goal | hook/score/goal plates |
| MR | MR-12 Sources | source card |
| BP | BP-14 Comparison | duel_columns |
| Utility | U-02 Lower Third | overlay renderer (có `ignoreBackground` cho nền trong suốt) |

## Card cần grammar mới (research đã chốt kỹ thuật)

- **TA tactical (TA-03/05/06/11/12/14)**: pitch SVG nền + token cầu thủ
  (`figure circle` + text số, group) + vector (`line` endHead arrow/triangle,
  dash cho run/press). Không vẽ pitch bằng tay từng video.
- **Tables (MR-07, BP-16, TA-16)**: dựng bằng text-rows + figure bars
  (đúng Kit grammar); `table` element tồn tại nhưng props chưa verify → fallback.
- **Timeline/sequence (TA-12, MR-05, BP-17, BP-04)**: ordered-rows + line nối.
- **Money (BP-08)**: numerals lớn + bars figure scale theo giá trị.
- **Myth vs Reality (BP-13)**: split 2 zones (kế thừa duel grammar).
- **Verdict/Takeaway/Thesis (MR-10, TA-18/19, BP-18/19)**: statement lockups.
- **Labels (U-03, U-05, MR-12, BP-20)**: micro lockups, xuất PNG trong suốt.

## DNA chung áp cho cả 35 (ĐÃ CHỐT với owner, Oct 2026 — sửa style)

- **Style = futuristic theo ảnh mẫu owner (Oct 2026): hiện đại, hơi tối,
  sống động bằng mảng màu phụ SÁNG chiếm diện tích lớn.** Palette khóa:
  ink navy #161B2C (nâng sáng, không đen đặc), coral #E0705F (accent chính,
  được chiếm mảng lớn), trắng giấy #F4F2EC (chữ + monogram), slate #5A6B8C
  (hình phụ + chữ thứ cấp). Chi tiết tech-line mảnh, sọc chéo, tick nhỏ.
  **Tuyệt đối tránh màu sặc sỡ** (không lime/cyan/magenta neon chói) —
  số thắng dùng trắng đậm, số thua slate. Tương phản chữ/nền ≥ 4.5.
- Barlow Condensed display, Be Vietnam Pro body/micro, PermanentMarker latin-only.
- **Ảnh = khung thay được:** starters dùng image-frame placeholder đúng hình học
  + trạng thái fallback typographic; nội dung video quyết định ai vào frame.
- **Sân chiến thuật = neon mới** (lưới tối + line neon, team cyan/magenta),
  không dùng sân ink/chalk cũ hay sân đỏ.
- **Ngôn ngữ:** giữ tiếng Anh CHỈ cho viết tắt mất nghĩa khi dịch
  (MOTM, GOAT...); còn lại tiếng Việt hết.
- **Sprint 1 = tĩnh:** 35 plates PNG đúng pixel + proof; motion sau duyệt thẩm mỹ.
- Lock decor, mở value; `custom.slot` mọi ô động; overflow co-chữ.
