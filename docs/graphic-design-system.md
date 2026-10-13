# Graphic design system — layout trước, effect sau

Từ: School of Motion (10 tiny type decisions), Butterick (practical typography),
broadcast lower-third craft. Chẩn đoán plates cũ: không boss, không room,
breaks ngẫu nhiên, contrast vô nhiệm vụ, spacing magic numbers, type rời frame.

## System (áp cho mọi plate, 2 aspect)

- **Unit:** u = 12px @960w (scale theo panel). Mọi margin/gap là bội số của u.
  Không số lẻ tùy hứng.
- **Type roles (tối đa 3/frame):** BOSS (claim/numeral, 1 cỡ), SUPPORT (label,
  ~0.28x BOSS), WHISPER (credit/source, ~0.16x BOSS). 1 family display +
  1 family body, không thêm.
- **Boss rule:** 1 frame = 1 boss duy nhất. Mọi thứ khác lui (nhỏ hơn, mờ hơn,
  ít hơn).
- **Room:** quanh BOSS để trống ≥ 1 dòng chữ mỗi phía; chật thì bớt chi tiết,
  không thu chữ trước.
- **Semantic breaks:** ngắt theo cụm nghĩa. Model/reviewer đánh dấu `/` trong
  text (`"Hàng thủ sập đổ / tối nay"`); renderer không bao giờ ngắt giữa cụm,
  không bỏ từ 1–2 ký tự một mình một dòng.
- **Contrast có nhiệm vụ:** đo luminance text-vs-bg dưới bbox chữ, ratio < 4.5
  → tự động lót scrim tối sau chữ (pill 0.45). Không phó mặc cho may rủi.
- **Frame:** safe margin 7% mọi cạnh; kiểm tra ở 350px; không chi tiết nhỏ hơn
  11px-equivalent.
- **Motion từ design:** reveal theo dòng (stagger), endure theo nhịp đọc
  (1–2s/cụm), không animate chữ đang bay.

## Audit list trước khi ship plate mới

1. Squint test: nhắm mắt còn thấy boss không.
2. Đếm cỡ chữ khác nhau ≤ 3.
3. Mọi gap đều là bội số u.
4. Breaks theo nghĩa, đọc to không vấp.
5. Contrast đo được, không đoán.
