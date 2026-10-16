# Template v10.0.0 "Sân Trắng" — rebuild brief (thay toàn bộ pack)

Prototype khóa: `docs/design/mr02-prototype-lock.md` (MR-02 san-trang:
trắng `#FFFFFF` dominant / cam `#F07862`, split 58/42, ink monumental +
orange bar, monogram badges, lite depth + detailing).
Phạm vi: **pack starter** — toàn bộ starters 3 sprint (69 JSON: Sprint 1 + Sprint 2 +
Sprint 3) + package short/long `10.0.0`. Kit live-data plates đã loại bỏ;
video assembly dùng generic editorial renderer, Studio dùng starters.
Pack `9.0.0` đã xóa hoàn toàn; drafts mới resolve `10.0.0` (released).

## 1. Tokens (khóa, chỉ 5 màu)

| Vai trò | Hex | Dùng |
|---|---|---|
| Trắng sân | `#FFFFFF` | Winner field dominant |
| Mực ink | `#161B2C` | Chữ winner, rule, badge ring, bar text |
| Cam san hô | `#F07862` | Loser field, winner bar/glow, seal |
| Slate | `#5A6B8C` | Context 1 dòng sentence-case |
| Mist | `#8B96B0` | Motif faint non-data (không làm chữ body) |

Type: Barlow Condensed Bold (tên/headers tiếng Việt, đủ dấu) +
Be Vietnam Pro (context/provenance/body) + BigShoulders Bold
(numerals latin only, digits không dấu) + PermanentMarker
(họ latin/ký số poster only, không câu Việt).
Contrast khóa bằng test: ink/white ≥7, slate/white ≥4.5, ink/orange ≥4.5.

## 2. Layout grammar (mọi card)

- Split pitch 58/42: short ngang y1120 (winner trắng trên, loser cam dưới);
  long dọc x1116 (winner trắng trái, loser cam phải). Rule ink + faint circle.
- Left-aligned broadcast stack; margins 76 (7%), top ≥195 (9%), credit y1820
  (ngoại lệ 97%). Mỗi frame 1 boss duy nhất, ≤3 cỡ chữ.
- Winner = ink monumental + orange bar/glow; loser = ink trên cam, credit ink.
  Màu encode ai thắng, size encode quan trọng — không label "thắng" thừa.
- Identity slots hình học cố định, content swappable, không reflow khi
  thiếu ảnh: score/duel/fixture 2 crest slots (monogram ring, winner d280 @
  (800,600), loser d220 @ (800,1470), long scale tương đối); player/coach
  1 portrait slot + face-safe framing (fit center 0.5/0.35), fallback monogram;
  team picture 1 wide slot + caption. Chỉ ảnh verified/active; crest thật
  vẫn cấm — slot giữ chỗ.
- Detailing liều lượng như proof (detailing.py, non-data only): corner marks
  khung winner, notched trim dưới hero, perforation trên provenance,
  ticks biên, pinstripes void phải.
- Lite depth: top-light + hero glow + grain sáng một nửa (seed 7, mask
  microcopy), bỏ haze trên nền trắng.

## 3. Review against the brief (frontend-design: plan → review → build)

- Generic default bị loại: centered stack + "2 - 0" treo (bản gốc), SaaS-kit
  boxes đồng loạt, ALL-CAPS eyebrow (→ sentence-case context), numbered
  markers khi không phải sequence, single-word accent, ticker chéo ồn
  (→ cắt, chỉ giữ notched trim), marquee lặp (→ cắt), haze bands trên trắng.
- Giữ vì brief thắng: palette/type/tiếng Việt/safe-area/slot-contract,
  geometry badge slots, circle motif, credit vị trí.
- Risk có chủ đích: typeface thứ 3 cho numerals + split bất đối xứng.
  Justified: digits không dấu + score-bug broadcast tách số khỏi chữ.

## 4. Critique (emil-design-eng, Chanel: cắt 1 accessory)

| Before | After | Why |
|---|---|---|
| Full depth (grain mạnh + haze bands) | Lite (top-light + glow + grain nửa, bỏ haze) | Haze không đọc trên trắng, grain mạnh làm xám trắng |
| Diagonal name ticker mọi poster | Notched hairline trim | Ticker là decoration lặp, trim giữ craft không ồn |
| Winner lime + navy/orange zones (v9) | Ink monumental + orange bar | Lime/navy ngoài palette lock san-trang; bar+size đủ encode |
| Centered claim + meta dots (generic) | Left stack, sentence-case context | Structure là information, không chrome template |
| Mist provenance trên trắng | Ink provenance trên band cam | Mist/white ~2.8 fail floor 3.0; ink/orange ≥4.5 pass |

## 5. Skill mapping

- frontend-design: hero-first, structure-is-information, 2-pass plan/review,
  restraint 1 memorable element, self-critique bảng trên.
- canvas-design: philosophy Sân Chia Đôi có sẵn (territory split, color là
  information, text as rare gesture); numerals đổi face có điều kiện (latin).
- algorithmic-art: seeded parametric craft port sang PIL (grain seed 7,
  pinstripes seed 21, deterministic, không browser/GPU).
- emil-design-eng: unseen-details-compound, animation framework
  (slide-in 0.3s ease-out cubic `cubic-bezier(0.23,1,0.32,1)`, stagger 0.18s/
  30–80ms, count-up 6 bước, chỉ transform+opacity, <300ms).
- theme-factory: chỉ dùng method (curated palette + pairing), presets cấm
  trên locked channel — san-trang là custom theme theo owner brief.
- broadcast-depth: 5 moves theo thứ tự, dừng khi đọc lit; hard limits
  (brief thắng depth, contrast bind, không hue mới, deterministic).
- polotno-sdk: starters giữ schemaVersion 4 + locked set +1 face
  (Big Shoulders cho numerals), gates check_starters/audit_cards giữ.

## 6. Acceptance v10

- `pytest tests/test_template_santrang.py
  tests/test_studio_starters.py tests/test_design_skills.py
  tests/test_card_selector.py -q` xanh; drafts mới resolve 10.0.0 (released),
  pack cũ 9.0.0 đã xóa, Kit plates đã gỡ.
- 69 starters pass check_starters + audit_cards (contrast/overlap/cover/
  overflow), proofs đúng pixel 1080×1920 / 1920×1080.
- preview.html v10 có gallery + audit rows; owner eyeball cuối từng card.
