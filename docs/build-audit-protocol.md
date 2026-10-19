# Sprint 1 strict build + audit protocol (khắt khe, bắt buộc)

Áp dụng cho mọi starter trước khi trình owner. Dừng ngay khi 1 gate fail.

## Gates tự động (chạy cho all 35, 0 ngoại lệ)

1. **Schema**: schemaVersion 4, id duy nhất, không placeholder, fonts chỉ
   thuộc {Barlow Condensed, Be Vietnam Pro, Permanent Marker, Big Shoulders}.
2. **Pixel-exact**: export đúng 1080×1920 (short) / 1920×1080 (long).
3. **Palette discipline**: mọi pixel (ngoài vùng ảnh) thuộc palette khóa
   của pack active ±90 — v10 Sân Trắng {trắng #FFFFFF, ink #161B2C, cam
   #F07862, slate #5A6B8C, mist #8B96B0}. Màu sặc sỡ = BLOCK.
4. **Contrast**: chữ boss ≥ 4.5 (đo luminance text-vs-bg tại bbox). Cấm chữ
   cam/mist trên trắng (ratio ~2.8-2.9 < floor 3.0): cam chỉ làm field/fill/
   bar với chữ ink; mist chỉ làm motif non-data.
5. **Safe area**: không ink chữ ngoài 9/13/7/7% (ngoại lệ duy nhất: credit
   whisper xuống 97% — chữ thừa kế provenance run, không mang nội dung;
   guides showInExport:false miễn kiểm).
6. **No-clip**: bbox mọi text nằm trong canvas; overflow mode co-chữ.
7. **Slots**: mọi ô động có `custom.slot`; decor khóa full flags.
   Horizontals của corner marks dùng `line` (audit miễn cover); verticals
   là rect 4px trên x-range không textbox nào chạm.

## Proof mắt (skill proof-checks: content → clip → focus → spacing)

- Tôi xem trực tiếp tối thiểu: mỗi GRAMMAR 1 mẫu + toàn bộ P0 heroes
  (duel, leader, poster, goal, score, pitch).
- So với ảnh futuristic mẫu: khối coral lớn, tech-line mảnh, không chói.
- Report bảng pass/block + evidence + repair; sửa blockers rồi proof lại.

## Audit owner

- Trang audit: all proofs + gate results + DNA tokens, phục vụ trên server.
- Quyết định P1/P2 và inventory cuối do owner sau khi duyệt thẩm mỹ P0.
