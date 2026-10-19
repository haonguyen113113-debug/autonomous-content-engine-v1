# TEMPLATE BUILD INSTRUCTION (bắt buộc đọc trước khi build/sửa pack)

File này là contract hướng build template trong repo. Build sai hướng = vỡ
tests + vỡ runtime. Mọi model làm template pack đều tuân thủ.

## 1. Kiến trúc bất biến

- `template_foundation/catalog.json` là source of truth. `registry.resolve_template`
  mặc định resolve package **mới nhất** (draft cần `allow_draft=True`).
- **Released packs bất biến**: đã release thì không sửa file trong đó. Sửa =
  version mới. Draft sửa tại chỗ được.
- Mọi thay đổi default pack (version/colorway/mode mới) BẮT BUỘC cập nhật
  ripple list ở mục 6 — đây là lỗi hay gặp nhất (vụ 12.0.0).

## 2. Pack anatomy (mỗi version short + longform)

`manifest.json` (id/version/status/market/locale/renderer_requirement/
font_resources/required_input_slots/slot_contract), `design-tokens.json`
(palette + aliases cho generic renderer + typography + motion), 
`color-systems.json` (colorway ids — TÊN colorway là contract),
`graphic-templates.json` (layouts = planning vocabulary, `required_data`
phải cover `apps/card_selector.py REQUIRED_SLOTS` — có test khóa),
`visual-modes.json`, `graphic-layout-styles.json`, `slot-contract.json`
(+ identity slots: crest-home/away, team-wide, player-portrait),
`timeline.json`, `story-forms.json`, `LICENSES.json` (mọi asset ngoài),
`resources/fonts/` (bắt buộc có BigShoulders + Tektur + BeVietnam),
`resources/beds/` hoặc `resources/plates/` (art), `previews/` (proofs đúng
pixel + `composite-proof.png` + `preview.html` có marker `<!-- SPRINT1-AUDIT -->`).

## 3. Starters (`apps/studio_templates/*.short/long.json`, 69 cards + mở rộng)

- `schemaVersion: 4`, đúng `1080x1920` / `1920x1080`, `fonts: []`, 1 page,
  id duy nhất, mọi ô động có `custom.slot`.
- Font whitelist (xem `check_starters.py FONTS`): Tektur, Be Vietnam Pro,
  Permanent Marker, Big Shoulders. **CẤM Barlow cho chữ Việt cỡ lớn**:
  Pillow ở đây không có raqm nên marks vỡ (đã verify bằng render test).
  Tiếng Việt cỡ display chỉ dùng Tektur/BeVietnam (glyphs đúc sẵn).
- Safe area text 7%/9%/13% (credit whisper xuống 97%). Decor đặc (figure
  không stroke) đứng TRƯỚC text; outline-only (`stroke`) và `line` exempt.
- Contrast: boss ≥4.5, còn lại ≥3.0. Cấm chữ cam/mist trên nền sáng.
- Beds: element `image` đầu tiên, full-bleed đúng canvas, src
  `/template-foundation/resources/beds/<slug>.png`, file phải tồn tại.
  Text trên beds do `audit_text_zones` (pixel-level) quyết định, không phải
  audit hình học.
- **Tagline: TBD — cấm mọi placeholder text trong card/UI/doc.**

## 4. Art ngoài (AI/Express/Pippit)

- Không chữ Việt/chữ lạ baked trong ảnh, không logo/crest/mặt người/watermark.
- Đúng pixel tuyệt đối (`1080x1920` / `1920x1080`, sai 1px fail), <2MB.
- Gốc lưu ở `assets/originals/` + `manifest.json` (nguồn, ngày, quyền).
- Watermark: xóa bằng inpaint có kiểm tra before/after, không ăn line art
  (mask theo saturation gate, verify compare từng file nghi ngờ).

## 5. Gates (dừng ngay khi 1 gate đỏ)

```powershell
python apps/studio_templates/check_starters.py
python -m pytest tests/test_studio_starters.py tests/test_studio_proofs.py -q
python -m pytest tests/test_template_cyber.py tests/test_template_santrang.py tests/test_card_selector.py -q
python -m pytest tests/ -q   # xanh toàn bộ mới commit
```

## 6. Ripple list (đổi default pack là phải đụng — kiểm tra từng dòng)

- `apps/content_workflow.py`: default `colorway` phải tồn tại trong
  color-systems của default pack.
- `apps/web_ui/static/index.html`: options `colorway` phải khớp packs.
- `apps/worker/{runner,queue_store}.py`, `apps/web_ui/server.py`: defaults.
- Tests pin version: `test_template_cyber.py`, `test_template_santrang.py`,
  `test_script_decomposition.py` (colorway), `test_worker_*`,
  `test_ai_backdrops.py`, `test_kit_sprites.py`, `test_pack_import.py`,
  `test_card_selector.py` (đường dẫn pack).
- `apps/studio_templates/render_starters.py`: FONTS/PREVIEWS/PALETTE theo pack.
- `apps/web_ui/static/studio.html`: `packVersion` default.

## 7. Definition of done

Gates xanh hết + proofs đúng pixel + audit page hiển thị đủ ảnh qua server
(`/template-foundation/preview.html`, KHÔNG mở file local) + owner eyeball.

## 8. Card registry (chống lẫn lộn + renderer gọi đúng card)

`apps/studio_templates/card_registry.py` là single source of truth cho cả
90 cards (69 built + 21 planned): mỗi entry khóa ID ↔ aspect ↔ family ↔
purpose ↔ required slots ↔ renderer path (`starter`/`generic:<mode>`/`frame`).
- Thêm card MỚI: khai báo entry `status: "planned"` ở đây TRƯỚC, rồi mới
  build JSON theo đúng purpose/slots/aspect đã khai.
- `tests/test_card_registry.py` khóa: đủ 90 entries, built nào cũng có JSON,
  mọi `STARTERS_*` trong `card_selector.py` phải nằm trong registry, mọi
  fallback mode đều render được (test render thật từng path).
- Renderer gọi card qua 2 đường duy nhất: `tactical_card` → starter scene
  (long TA), còn lại qua `visual_mode` → generic branch đã map trong registry.
  Không thêm đường render thứ ba nếu chưa cập nhật registry + test.
