# Express full-pack plan: 3 sprints + long-form mở rộng (v12)

Mục tiêu: backgrounds do image model vẽ (one-shot), engine vẽ toàn bộ chữ/
số/slots + gates + lock. Quy tắc sắt giữ nguyên: **không một chữ tiếng Việt
nào trong ảnh export** (AI vẽ dấu rất dễ vỡ — engine vẽ bằng Tektur/BeVietnam
đã verify), không crest/logo/footage/mặt người thật, đúng pixel tuyệt đối.

## 1. Inventory mở rộng long-form (19 → 40 cards)

Long-form hiện chỉ có phân tích chiến thuật. Thêm 21 cards:

**Tactical+ (TA-20..TA-24)** — slots: sơ đồ/runners/nhãn + source/date:

| ID | Card | Nền cần |
|---|---|---|
| TA-20 | Set-piece attack | F4 pitch quiet |
| TA-21 | Set-piece defense | F4 pitch quiet |
| TA-22 | Transitions | F4 pitch quiet |
| TA-23 | Rest defense | F4 pitch quiet |
| TA-24 | Goalkeeper build-up | F4 pitch quiet |

**Long Narrative (LC-01..LC-16)** — video 8-20 phút cần kể chuyện, không chỉ
chiến thuật:

| ID | Card | Slots chính | Nền cần |
|---|---|---|---|
| LC-01 | Chapter opener | kicker + title chương | F2 statement |
| LC-02 | Key question | câu hỏi + context | F2 statement |
| LC-03 | Timeline | mốc + sự kiện (≤4) | F9 moments |
| LC-04 | Duel comparison | 2 đối tượng + chỉ số | F1 duel |
| LC-05 | Stat evidence | stats + source/date | F5 evidence |
| LC-06 | Quote | trích dẫn + người nói | F6 quote |
| LC-07 | Money | số tiền + diễn giải | F7 money |
| LC-08 | History | mốc lịch sử + ý nghĩa | F10 history |
| LC-09 | Myth vs reality | ngộ nhận + sự thật | F8 myth |
| LC-10 | Ranking | bảng xếp hạng + tiêu chí | F5 evidence |
| LC-11 | Player focus | tên + portrait slot + stats | F3 portrait |
| LC-12 | Verdict | nhận định + luận cứ | F2 statement |
| LC-13 | Source check | nguồn + ngày + claim | F6 quote |
| LC-14 | End card | channel (tagline TBD) | F11 end |
| LC-15 | Next up | trận/tập tiếp theo + date | F14 versus |
| LC-16 | Correction | đính chính + giờ cập nhật | F6 quote |

Short-form giữ nguyên 50 cards (đã đủ money/story/history).

## 2. 14 background families (generate theo family, không theo card)

Mỗi family = 1 prompt base + 2-3 variations (sáng/tối, density). 69 cards cũ
+ 21 cards mới map vào families (bảng map ở mục 4). Tổng ~20 ảnh/short +
~16 ảnh/long thay vì 90 ảnh rời — vừa coherence vừa khả thi.

**Shared style (dán nguyên vào mọi prompt):**

```
Unified sports broadcast background system, flat vector key-art, night cyber
stadium mood: deep navy-black void #060913, neon cyan #00E5FF edge lines and
grid floors, magenta #FF3D81 horizon glow accents, warm amber #FFB03A micro
lights, fine film grain, subtle vignette. No people, no faces, no logos, no
crests, no text in any Asian script, minimal latin micro-labels only.
Clean geometric composition, high contrast, no photorealism, no watermark.
```

**Negative (dán nguyên vào mọi prompt):**

```
No Vietnamese text, no Asian characters, no club crests, no competition
logos, no real players, no faces, no watermark, no photorealistic crowd.
Keep the specified empty zones completely empty and dark.
```

**Composition + empty zones từng family:**

- **F1 score/duel** — `monumental empty dark center, faint giant pitch
  circle behind, glowing horizon low`. Trống: giữa khung cho số khổng lồ.
- **F2 statement/hook** — `dramatic dark field, light rising from bottom,
  calm dark top band for kicker`. Trống: 2/3 giữa cho claim lớn.
- **F3 portrait** — `dark portrait void left third with soft cyan rim light
  from the left edge (empty, no person), textured dark field right`. Trống:
  1/3 trái cho ảnh, 2/3 phải cho tên.
- **F4 pitch quiet** — `near-black backdrop, faint perspective grid floor
  only, very calm center` (sơ đồ engine vẽ đè lên). Trống: toàn bộ giữa.
- **F5 evidence/bars** — `dark dossier field, faint vertical gridlines,
  low amber glow`. Trống: giữa cho bars/số.
- **F6 quote/source** — `quiet dark paper, single neon edge line, one soft
  light pool center-left`. Trống: giữa-trái cho box trích dẫn.
- **F7 money** — `dark vault mood, rising golden bokeh dots, deep shadows`.
  Trống: giữa cho con số.
- **F8 myth** — `split energy: charged magenta top vs calm dark bottom`.
  Trống: cả hai nửa cho 2 khối text.
- **F9 moments/timeline** — `horizontal timeline energy, faint glowing
  axis line middle, dark above and below`. Trống: dọc trục giữa cho mốc.
- **F10 history** — `archival dark mood, faint giant year numerals backdrop,
  vignette mạnh`. Trống: giữa cho text (số năm nền mờ OK).
- **F11 end/sting** — `centered emblem glow, symmetric, calm`. Trống: giữa
  cho wordmark.
- **F12 chips** — `minimal dark, single thin neon frame line`. Trống: giữa
  cho chip.
- **F13 takes** — `three ascending light steps motif, dark`. Trống: dọc cho
  3 ý.
- **F14 versus** — `two glowing slots left-right, VS energy center, calm`.
  Trống: 2 ô + giữa.

Kích thước: short `1080x1920`, long `1920x1080`, đúng pixel, <2MB, PNG.

## 3. Map card → family (short)

C-01:F11, C-02:F2, C-03:F2, C-04:F3, C-05:F6, C-06:F2, C-07:F1, C-08:F13,
C-09:F6, C-10:F11, U-01..U-06,U-08:F12, U-07:F11, U-03:F12, U-05:F12,
MR-01:F2, MR-02:F1, MR-03:F1, MR-04:F1, MR-05:F9, MR-06:F9, MR-07:F5,
MR-08:F3, MR-09:F5, MR-10:F2, MR-11:F14, MR-12:F6,
BP-01:F2, BP-02:F2, BP-03:F3, BP-04:F9, BP-05:F9, BP-06:F7, BP-07:F1,
BP-08:F7, BP-09:F2, BP-10:F1, BP-11:F10, BP-12:F8, BP-13:F8, BP-14:F1,
BP-15:F5, BP-16:F2, BP-17:F9, BP-18:F2, BP-19:F2, BP-20:F6.

## 4. Map card → family (long)

TA-01:F2, TA-02:F1, TA-03..TA-11:F4, TA-12:F9, TA-13:F1, TA-14:F4, TA-15:F4,
TA-16:F5, TA-17:F4, TA-18:F13, TA-19:F2,
TA-20..TA-24:F4,
LC-01:F2, LC-02:F2, LC-03:F9, LC-04:F1, LC-05:F5, LC-06:F6, LC-07:F7,
LC-08:F10, LC-09:F8, LC-10:F5, LC-11:F3, LC-12:F2, LC-13:F6, LC-14:F11,
LC-15:F14, LC-16:F6.

## 5. Hướng dẫn thao tác Adobe Express (từng bước)

1. Mở Adobe Express → công cụ **Text to Template / Generate Template**
   (khu vực AI generation). Tạo project mới, đặt đúng khổ **trước khi
   generate**: short `1080 × 1920`, long `1920 × 1080` (custom size).
2. Prompt = 1 khối: dán **Shared style** + **Composition của family** +
   **Negative**. Bấm generate, lấy 3-6 variations.
3. Pick 1: kiểm tra bằng mắt — (a) không có chữ Việt/chữ lạ nào lọt vào,
   (b) vùng trống đúng chỗ mục 2 (chỗ chữ phải tối và thoáng),
   (c) không logo/crest/mặt người/watermark.
4. Xóa sạch text layers còn lại trong editor (chỉ giữ background thuần).
   Không thêm chữ Việt trang trí — engine vẽ sau.
5. Export PNG đúng pixel gốc (không resize, không nén quá tay — mỗi file
   <2MB), đặt tên `short-f01-score.png`… hoặc gửi thẳng cho tôi, tôi đổi tên.
6. Lặp cho 14 families × short/long (+ variations dự phòng).File quyền:
   note lại plan Adobe + ngày export, tôi ghi vào licenses khi build.

## 6. Checklist trước khi giao file

- [ ] Đúng `1080x1920` / `1920x1080` (sai 1px validate fail)
- [ ] <2MB mỗi file, PNG
- [ ] Không chữ Việt, không logo/crest/mặt người/watermark
- [ ] Vùng trống tối + thoáng đúng chỗ chữ
- [ ] Ghi ngày export + plan Adobe đang dùng

## 7. Việc tôi làm sau khi nhận file

1. Lưu vào `resources/plates/` pack v12 (draft mới, v11 released giữ nguyên).
2. Compose 21 cards long-form mới (JSON builders TA-20..24, LC-01..16) +
   rewire backgrounds toàn bộ 69 cards cũ sang art mới (bỏ beds generative).
3. Chạy gates: schema/safe/slots + probe tương phản pixel từng text zone +
   palette audit; vá veil/reposition đến khi 90/90 xanh.
4. Render proofs + audit page → bạn duyệt → promote released.
