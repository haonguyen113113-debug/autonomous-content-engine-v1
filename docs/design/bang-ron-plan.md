# Băng Rôn — plan (frontend-design pass 1) + review + sketch log

Subject: Allen Knows Ball cards cho khán giả bóng đá Việt trên điện thoại.
Job mỗi card: trả lời 1 câu hỏi trong <2s (ai thắng/bao nhiêu/trận nào;
cầu thủ nào/con số nào; pressing ra sao).

## Research ground (visual-taste-research + sport-design-research)

- Bệnh đồ cũ: type-only vô hồn, không marker Việt, không rủi ro/quan điểm,
  không vết người (grain, mép cắt, texture in). Băng Rôn trị bằng: vé in +
  răng cưa perforation + grain giấy + motif sân (hoarding/pitch lines).
- Giữ từ anatomy cũ: 1 frame = 1 boss, ≤3 cỡ chữ, zones mang nghĩa + winner
  không chỉ bằng màu, provenance luôn whisper, đọc header→boss→support→whisper.
- Bỏ: ticker chéo, marquee lặp, SaaS-kit boxes, ALL-CAPS eyebrow, numbered
  markers khi không phải sequence, single-word accent.

## Token system (khóa cho proof)

- Color (5, daylight print): vé giấy `#F6F1E3` dominant; mực cuốn vé
  `#171A26`; cam LED `#F07862` (band thắng/seal/bar, chữ ink trên cam);
  slate `#5A6B8C` (context sentence-case trên giấy); giấy đậm `#E4DCC8`
  (stub zone, dải phân cách). Cam KHÔNG BAO GIỜ là chữ trên giấy (~2.8).
- Type: Barlow Condensed Bold = tên/headers/claims tiếng Việt (đủ dấu);
  Be Vietnam Pro = context/micro/provenance; BigShoulders Bold = numerals
  latin only (tỷ số, stats, phút); PermanentMarker = họ latin poster only.
- Layout: dải full-bleed edge-to-edge (LED band đầu, stub cuối, perforation
  ngăn cách, notch bán nguyệt ở mép dải); left-anchored broadcast stack;
  margins 76 (7%), top ≥173 (9%), credit whisper 1820 (ngoại lệ 97%).
- Principles: màu đến bằng kiến trúc (dải/box), không bao giờ là strip trôi;
  1 memorable element/frame; vết người = grain + perforation + notch;
  stub boxes có viền vì giữ identity, không viền trang trí.

```
DUEL 1080x1920 (white field + LED band + stub):
+------------------------------------------------+
| LED INK BAND: Đanging... comp • round (paper)  | 0-260
|~~~~perforation dots~~~~~~~~~~~~~~~~~~~~~~~~~~~~|
| HÀ NỘI [HN box]  vs  NAM ĐỊNH [NĐ box]         | stub boxes bordered
|------------------------------------------------| ink hairline
| Bàn thắng                                      |
|  45  ___orange bar___  |  38                   | columns w/ center rule
|------------------------------------------------|
| Kiến tạo  30 | 30 (tie: no bars)                 |
|~~~~perforation~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|
| STUB: Nguồn + ngày • Vòng 12                   | 1720-1920
+------------------------------------------------+
STATEMENT: LED band (kicker) + claim Barlow khổng lồ 3 dòng + orange rule
  full-width + support micro + stub. Không void: chữ lấp đầy.
PITCH 1920x1080: LED band top (title) + white pitch ink lines + tokens
  bordered + trap zone + arrows + tag stub + credit. (Kế thừa TA-06 tốt.)
```

## Review against the brief (trước khi vẽ)

- Generic default check: dải ngang full-bleed có phải SaaS-card không? Không —
  nó là ngôn ngữ hoarding/stub đặc thù subject (sân đấu/vé), không phải box
  bo góc xám đổ bóng. Perforation/notch có phải decoration không? Không — là
  motif vé, phi-data, liều như proof MR-02.
- Brief thắng: palette/type/tiếng Việt/safe-area/slot-contract giữ; skill chỉ
  quyết phần brief để trống (bố cục dải, motif vé, mật độ).
- Risk có chủ đích: chữ khổng lồ tràn gần lề + dải ink nặng đầu. Justified:
  hoarding lettering ngoài sân thật to và dày; mật độ cao trị bệnh void.

## Critique sau sketch (Chanel: cắt 1 accessory)

- Cắt marquee/ticker (đã cắt từ v10). Cắt circle motif khổng lồ giữa card
  (gây rối với số) — chỉ giữ pitch lines cho pitch cards. Cắt ghost backdrop
  nếu đè lên boss. Giữ: perforation + notch + grain (vết người) + 1 bar cam.
