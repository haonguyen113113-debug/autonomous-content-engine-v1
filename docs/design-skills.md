# Design skills: frontend-design + canvas-design

Nguồn: `anthropics/skills` (official, Apache 2.0). Cài verbatim vào
`skills/<name>/` theo đúng quy ước `polotno-sdk` của repo (source header +
LICENSE.txt). `canvas-fonts/` vendor đủ 81 files OFL đã verify size.

## Mỗi skill giúp gì cho việc thiết kế của engine

**frontend-design** — principles + process cho UI/layout mới:
- Ground designs vào subject matter (bóng đá broadcast vernacular chứ không
  generic SaaS-card kit), hero-first, typography mang personality, structure
  là information (màu/size encode ai thắng — không label thừa).
- Process 2 passes bắt buộc: plan tokens (color/type/layout/principles) →
  review uniqueness vs brief → build → self-critique + cắt 1 accessory.
  Khớp quy trình proof/audit của engine (plan trong `docs/design/`, proof
  PNG, critique trước commit).
- Brief luôn thắng: palette/fonts/tiếng Việt/safe-area/slot-contract của
  template giữ nguyên; skill chỉ được quyết trong phần brief để trống.

**canvas-design** — philosophy-first cho static art:
- Viết manifesto movement trước (docs/design/mr02-philosophy.md), rồi mới
  express lên canvas; 90% visual + 10% essential text; subtle reference;
  craftsmanship lặp đi lặp lại; refine pass chỉ gọt, không thêm đồ.
- Quy tắc fonts của skill ("dùng fonts khác cho text, tìm trong
  ./canvas-fonts") được áp dụng CÓ ĐIỀU KIỆN: chỉ numerals latin (không dấu)
  mới đổi face; toàn bộ tiếng Việt giữ Barlow/BeVietnam vì brand + diacritics.
- 81 fonts OFL là công cụ cho numerals/display latin sau này, không thay
  brand faces.

## Demo: MR-02 Final Score redesign (2 skills → 4 skills)

- Gốc: `template_foundation/.../9.0.0/previews/short-mr-02-proof.png`
  (stack giữa, void nửa dưới, tỷ số treo không gắn đội thắng).
- Redesign: `docs/design/mr02-redesign-proof.png` — split pitch (coral winner /
  ink loser), numeral BigShoulders monumental, tên gắn với số, circle motif,
  context 1 dòng. So sánh 3 panels: `docs/design/mr02-compare.png`.
- Depth pass (`skills/broadcast-depth`, custom): `docs/design/mr02-depth-proof.png`
  — top-light gradient, hero glow (paper, blur 18), grain seeded deterministic
  (trừ microcopy), 2 haze bands. Cùng data slots, cùng palette audit.
- Script: `apps/studio_templates/redesign_mr02_skill.py` (PIL, không đụng
  locked starters/proofs). Khóa bằng `tests/test_design_skills.py`
  (install intact, canvas 1080×1920, winner/away/draw branches, palette lock,
  depth deterministic + visible).
- Philosophy: `docs/design/mr02-philosophy.md`. Plan + review + critique:
  `docs/design/mr02-plan.md`.

## Hướng detailing: thư viện primitives tái dùng (`detailing.py`)

Theo emil-design-eng (unseen details compound) nhưng luật sắt của engine:
**details không bao giờ mang data** — ticks không numerals, không labels bịa
(trên MR-02 mọi slot thật đã hiển thị nên micro-label bị loại có chủ đích).

Primitives (seeded, CPU-only, palette-locked): hairline_rule (notch cuts),
tick_ruler (texture, cấm numerals), corner_marks (framing kỹ thuật),
perforation (vé xem bóng), pinstripes (air trong dead zones),
stitch_line, micro_label (sentence-case whisper). Catalog máy đọc được qua
`detail_report()`.

Demo: `apply_mr02_detailing()` trên bản lite — corner marks khung winner,
notched trim, perforation trên provenance, ticks biên trái, pinstripes void
phải. Compare panel 4 là bản detail. Khóa bằng tests (deterministic, spot
pixels, palette lock, catalog toàn non-data).

## Skill thứ 5: emil-design-eng + depth-lite (trả lời feedback v3<v2)

- `skills/emil-design-eng/` (emilkowalski/skills, single-file, 27KB): detailing
  thuần craft, zero dependency — animation decision framework, review checklist
  Before/After/Why, unseen-details-compound. Motion engine đã đúng skill sẵn
  (ease_out_cubic/back toàn bộ sportskit) nên không sửa motion.
- Áp restraint của skill vào depth pass: bản full (grain mạnh + haze bands)
  thua bản flat → thêm mode `depth="lite"` (giữ top-light + hero glow, grain
  một nửa, bỏ haze). Compare panel 3 giờ là gốc/flat/lite.
- Đánh giá thẳng thắn 4 skills đã xem mà KHÔNG cài (tránh dead weight):
  | Skill | Vì sao không cài |
  |---|---|
  | theme-factory | 10 preset themes đè lên palette lock của channel |
  | brand-guidelines | Brand của Anthropic + pptx — sai subject, sai medium |
  | high-end-visual-design | Web Tailwind/bento; variance mandate (không lặp layout) conflict trực diện locked packs |
  | web-design-guidelines | Meta-skill fetch rules ngoài mỗi lần review (cần network) — audit protocol của engine đã cover |

## Skill thứ 3 + 4: algorithmic-art + broadcast-depth (vượt 2D)

- `skills/algorithmic-art/` (official, Apache 2.0, SKILL + templates/viewer).
  p5.js/browser không chạy được trong renderer offline — chỉ port triết lý +
  parametric craft (seeded randomness, flow fields, parametric variation)
  sang PIL. Ghi rõ trong source header để không ai depend nhầm vào browser.
- `skills/broadcast-depth/` (custom của engine): faux-3D cho PIL CPU-only —
  top-light, hero glow, seeded grain, atmosphere bands, extruded edge — thay
  cho Blender (vi phạm portability spec §15: không GPU, không binary nặng,
  chạy được trên replacement PC).
- Vì sao không Blender/three.js thật: spec portability cấm dependency nặng;
  faux-3D đạt ~80% cảm quan broadcast với 1% chi phí, deterministic và audit
  được bằng palette test có sẵn.
