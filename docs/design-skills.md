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

## Demo: MR-02 Final Score redesign

- Gốc: `template_foundation/.../9.0.0/previews/short-mr-02-proof.png`
  (stack giữa, void nửa dưới, tỷ số treo không gắn đội thắng).
- Mới: `docs/design/mr02-redesign-proof.png` — split pitch (coral winner /
  ink loser), numeral BigShoulders monumental, tên gắn với số, circle motif,
  context 1 dòng. So sánh: `docs/design/mr02-compare.png`.
- Script: `apps/studio_templates/redesign_mr02_skill.py` (PIL, không đụng
  locked starters/proofs). Khóa bằng `tests/test_design_skills.py`
  (install intact, canvas 1080×1920, winner/away/draw branches, palette lock).
- Philosophy: `docs/design/mr02-philosophy.md`. Plan + review + critique:
  `docs/design/mr02-plan.md`.
