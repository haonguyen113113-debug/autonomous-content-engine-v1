# Pre-production summary — một cửa duyệt thay năm cửa

Bạn nhập title → engine draft + check + plan → `GET /api/content/summary/<run>`
trả MỘT bản summary (`runtime/summaries/<run>.json`) gồm 5 sections:

| Section | Nội dung | blocked khi |
|---|---|---|
| script | beats + narration, score 0-100, unresolved markers | còn `[CẦN NGUỒN]`/`[KẾT LUẬN CỦA ALLEN]` |
| narrative | topic, story arc map từng beat, tổng giây vs target | — (derived) |
| asset | từng need: eligible/shortfall, autosaved, top candidates + tier | need thiếu mà không có candidate lẫn eligible |
| template | card decisions (mode/starter/score/reasons), warnings | — (attention khi có warnings) |
| voice | tổng ký tự, ước lượng giây, preset/reference | chưa có voice để synth sau duyệt |

## Checkboxes fix (`POST /api/content/summary-review`)

`{run_id, approved, fixes:[{section, target, note}]}` — mỗi section tick +
target + note 1-500 ký tự:

- **script** (target = beat id): regen đúng beat đó bằng machinery draft
  (guards length/overlap/facts giữ nguyên), giữ slot timing, gỡ media đã
  gắn nếu visual đổi. Fail loudly kèm lý do.
- **asset** (target = requirement id): re-discovery với query + note.
- **template** (target = beat id): note phải là tên visual_mode hợp lệ
  → set declared mode, recompute plan.
- **voice/narrative**: ghi nhận note (voice synth lại sau duyệt, narrative
  recompute từ script).

Xong rebuild summary mới (`approved:false`). `approved:true` đi kèm fixes
sẽ 400.

## Bulk approve (một nút)

Chạy đúng validations của từng gate cũ, chỉ gộp thành một lần bấm:

1. Không markers (kèm list beats) → `script_owner_approved` +
   `evidence_verified_by_owner` (mirror `_approve_script`).
2. Auto-attach ảnh verified được suggest (mirror `_attach_segment_media`).
3. Synth voice → auto-check file + duration fit → `voice_preview_audited`
   với `voice_audit_method: summary-bulk-auto` (ủy quyền nghe, minh bạch
   trong run file — khác `listened` tay).
4. `render_full_run` → `full-render.mp4` + report.
5. Trả `next_action`: review render rồi plan/stage distribution.
   **Publish vẫn bấm tay** (ranh giới uy tín/tiền).

## Asset auto-save (standing grant)

`ASSET_AUTOSAVE=true` trong `.env` (default off): khi build summary, top
shortfall candidates tự save vào library qua intake strict
(download pinned-host, size caps, type match) với `rights_reviewed=True`
theo ủy quyền của bạn; mọi thuộc tính reuse (license, source, tier,
provenance sidecar) ghi đủ. Eligible counts recompute ngay.

## UI

Panel "Pre-production summary" trong Workflows: Build summary → 5 cards
mỗi card có checkbox "Cần sửa" + target + note → Send fix requests /
Approve everything. Endpoints cũ (duyệt từng component) giữ nguyên.
