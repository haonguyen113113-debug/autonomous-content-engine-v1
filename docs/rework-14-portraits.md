# Rework với 14 portraits — tiến trình (READY, chờ lệnh bắt đầu)

Trạng thái: script + tài liệu đã lưu. CHƯA CHẠY rework. Bắt đầu khi owner
nói "bắt đầu" sau khi đủ 14 tấm portrait trong Downloads.

## Phase 0 — Intake (khi đủ file)

1. Tôi xác định từng file (aspect + xem visual) rồi chạy:
   `python apps/studio_templates/intake_plates.py "<file>=<canonical>" ...`
   Chuẩn hóa về đúng `1080x1920`, PNG RGB, <2MB vào `pack-drop/12.0.0/`.
2. Canonical names (13 shorts + long đã có):
   `short-opening`, `short-f2-statement`, `short-f1-duel`, `short-f1-score`,
   `short-f3-portrait`, `short-f5-evidence`, `short-f6-quote`, `short-f7-money`,
   `short-f8-myth`, `short-f9-moments`, `short-f10-history`, `short-f11-end`,
   `short-f14-versus`, (`long-f4-pitch` đã có).
   F12 chips + F13 takes tái dùng art F2 (không cần generate).
3. Kiểm tra từng tấm: không chữ Việt/chữ lạ, vùng trống tối-thoáng đúng chỗ
   chữ, không logo/crest/mặt người. Tấm fail → generate lại family đó.

## Phase 1 — Dựng pack v12 skeleton

`python -m apps.pack_import init` đã chạy cho 12.0.0. Bổ sung layouts
`opening`/`ending`/`hook_card` + boxes (tên kênh Tektur giữa void, tagline
để trống chờ TBD) rồi `build` khi đủ backgrounds cả 2 aspects.
(Lưu ý: còn thiếu long của 13 shorts — báo owner generate sau phase này.)

## Phase 2 — Rewire starters sang art thật (69 cards)

- Plates Express vào `resources/plates/`, route server mở rộng sang `plates/`.
- `BEDMAP` (beds generative) → `PLATEMAP` (art thật) theo map family:
  F1-duel→C-07/BP-07/10/14, F1-score→MR-02/03/04, F3→C-04/MR-08/BP-03,
  F5→MR-07/09/BP-15 + C-06, F6→C-05/09/MR-12/BP-20/U-08,
  F7→BP-06/08, F8→BP-12/13, F9→MR-05/06/BP-04/05/11/17,
  F10→BP-11, F2→statements còn lại, F11→C-01/10/U-07, F14→MR-11,
  F12/F13→F2 art.
- Text colors giữ nguyên hệ cyber (probe quyết định); vá veil/reposition
  từng card fail probe — như đã làm với duel veil + tag TA-14/15.

## Phase 3 — Cards long-form mới (21 cards: TA-20..24, LC-01..16)

Builders mới trong `build_starters_v11.py` (giữ IDs/aspect/slots theo
`docs/express-fullpack-plan.md` mục 1), beds = art long khi có, tạm dùng
beds generative cyber cho long cho đến khi art long về.

## Phase 4 — Gates + release

`check_starters` + `audit` + `audit_text_zones` + `audit_blends` phải 0
issues toàn bộ → proofs → `preview.html` → audit page → owner duyệt →
promote released (v11 released giữ nguyên làm fallback).

## Rủi ro đã biết

- Art thật sáng hơn beds generative → probe fail nhiều hơn; veil là công cụ
  chính (đã chứng minh với duel).
- File generate sai pixel → intake crop/upscale xử lý, chất lượng nền mềm
  chấp nhận được.
- Thiếu long aspects → Phase 1 báo danh sách thiếu, không block Phase 2.
