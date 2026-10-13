# Card selector — script beats → render-ready cards (`apps/card_selector.py`)

`select_cards(segments, assets, content_type)` maps every script beat to:
`visual_mode` (renderer-supported) + `starter_id` (Sprint 1/2/3 card cho Studio,
`None` khi chưa có mẫu đúng aspect) + `graphic_data` (hoàn thiện) +
`media_asset_id` (đã validate) + `score` 0–100 kèm `reasons` + `warnings`.

## Quy tắc (đều có test khóa trong `tests/test_card_selector.py`)

- Beat 0 luôn mở bằng `hook_card`; `hook_text`/`claim` suy từ narration
  (tối đa 8 từ / 220 ký tự). Số liệu/source/date KHÔNG bao giờ bịa.
- Fit score rule-based, 0 model cost: slot coverage từ
  `graphic-templates.json` (test `test_registry_slots_match_package` giữ đồng bộ),
  +10 portrait verified, −25 thiếu portrait, −10 lặp card liền kề, thêm −5 khi
  một card áp đảo 3 beats gần nhất (đôi được, ba thì đổi cho đa dạng).
- Mirror renderer (`video_renderer.py`): asset bound + mode không thuộc
  `PORTRAIT_MODES` → `media_b_roll`; `media_b_roll` không asset → pitch plate;
  binding unverified/không tồn tại bị gỡ + warning (render crash nếu lọt).
- Mirror slot-contract: chỉ asset image + verified + active; portrait phải
  khớp tên cầu thủ (advisory match qua subjects/metadata, identity chuẩn nằm
  ở `player_identity`), thiếu thì chữ typographic + warning.
- Tactical long-form chọn starter theo nội dung (Sprint 2): pressing → TA-06,
  cầm bóng → TA-05, khoảnh khắc/phút → TA-11, còn lại TA-03. Đủ 9 signals
  (`test_long_tactical_signals_map_to_sprint2`).
- Storytelling short-form chọn starter theo nội dung (Sprint 3,
  `_story_starter`, test `test_sprint3_short_story_signals_map_to_p1`):
  hook breaking → MR-01 / story → BP-01 (mặc định C-03);
  hiệp một → MR-03; POTM → MR-08 / profile → BP-03 (mặc định C-04);
  chuyển nhượng → BP-07 / derby → BP-10 (mặc định C-07);
  top/ranking → BP-15 / bảng điểm → MR-09 / chỉ số trận → MR-07;
  timeline sự nghiệp → BP-04 / rise-fall → BP-05 / lịch sử → BP-11 /
  bước ngoặt → BP-17 / timeline trận → MR-05 (mặc định MR-06);
  kiểm chứng → BP-20 / nguồn trận → MR-12 (mặc định C-09).
  `quote_card` → C-05; `fixture_list` → MR-11; `discipline_card` → MR-06;
  `welcome_card` → BP-06. Long: hook → TA-01, score/goal/fixture →
  TA-02, discipline → TA-11 (`test_sprint3_new_modes_have_starters`,
  `test_sprint3_long_hook_and_fallbacks`).

## Nối vào render (đã nối — filter mớm, renderer render)

`apply_card_plan(root, run)` chạy trong `render_full_run` và
`render_visual_only_run`, sau mọi gate (duyệt script/voice/media) và trước
`_render`. Nó chép `visual_mode` + `graphic_data` của decision vào segment,
giữ binding media của owner đã validate (gỡ cái render sẽ crash), KHÔNG BAO
GIỜ tự attach ảnh (slot-contract `requires_owner_use_decision`; đề xuất nằm ở
`suggested_asset_id` + warning để owner bấm attach), rồi lưu full plan vào
`run["card_plan"]` cho mặt review. Renderer không đổi logic, chỉ đọc segment
như cũ — nhẹ đúng ý đồ.

## Renderer hook cho plate Sprint 2 (đã nối)

- Selector ghi `graphic_data["tactical_card"] = "TA-xx"` cho beat tactical
  long-form (Sprint 1 short không cần: các mode Kit short đã render live-data
  qua `sportskit`, còn long tactical trước đây chỉ có pitch generic).
- Vòng scene của `video_renderer.py`: `tactical_explainer` + long + id hợp lệ
  → render đúng plate authored qua `_write_starter_scene`; id lạ, short, hay
  lỗi đọc → rớt về pitch generic, không bao giờ crash render.
  (`tests/test_tactical_cards.py` khóa cả hai nhánh.)
