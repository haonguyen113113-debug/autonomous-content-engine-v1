# Template v1.0.0 "Impact" — design brief

## Đối thủ đã research (10/2026)

- **Tifo Football (EN):** minh họa phẳng + data viz + voiceover điềm tĩnh, long-form.
  Thắng ở biến phức tạp thành đơn giản. Không có footage vẫn xem được.
- **Football Made Simple (EN, video 805K subs):** footage + telestration vẽ tay +
  graph + host nói nhanh. Nhịp dồn dập, số liệu dẫn chuyện.
- **Copa90 (EN):** comic illustration + character motion + personality host.
- **BLV Anh Quân (VN, 1.46M):** talk-show personality, video dài, thắng bằng con người.
- **@chienthuatbongda (VN):** tactical VN trực tiếp — đối thủ gần nhất của Allen.
- **Premier League official Shorts:** highlight nhanh, nhịp cắt dựng tốc độ cao.

## Kết luận: Allen thắng bằng gì khi không có footage, không quay host

Đối thủ VN hoặc talking-head, hoặc slideshow tĩnh. Allen vượt bằng **mật độ
chuyển động trên đồ họa authored**: không frame nào đứng yên, số nhảy sống,
chữ xuất hiện theo nhịp nói, chuyển cảnh trượt thay vì cắt khô.

## Có mới trong v1.0.0 (so với Nova 0.9.0)

1. **Slide-in scenes:** beat mới trượt vào từ phải trong 0.3s (thực thi
   `chalk_line_wipe` vốn khai báo mà chưa chạy). Đây là nâng cấp motion lớn nhất.
2. **Count-up numerals:** số hero/statline đếm từ 0 lên giá trị thật theo nhịp
   beat (6 bước, textfile theo cửa sổ thời gian). Không bịa số — chỉ animate
   số đã duyệt.
3. **Staggered hook lines:** 3 dòng hook card hiện so le 0.18s thay vì cùng lúc.
4. Giữ nguyên identity, palette, fonts, layout ids (tương thích runs cũ),
   giữ cam kết no-footage, no-rebrand.

## Non-goals

- Không thêm layout mới; không draw/wipe phức tạp ngoài slide-in;
  freeze/pitch_grid vẫn khai báo-chưa-chạy và báo trung thực.
- Loop-aware ending và muted captions là việc của script (prompt đã dặn),
  template chỉ cung cấp overlay + end-card cùng palette.

## Acceptance

- 18s preview + 24s overlay proof trên 1.0.0, applicable checks PASS.
- Slide filter có mặt trong filter_complex của proof; count-up textfiles đủ 6 bước.
- Draft mới resolve 1.0.0 mặc định; runs cũ pin version cũ.
