# Discovery đa nguồn đa định dạng (workstream 2/4, 2026-10-16)

Checkpoint thay thế: `docs/audit-checkpoint-2026-10-08.md` không tồn tại —
workstream này dựa trên `docs/build-audit-protocol.md`,
`docs/template-build-manual.md` §8, `docs/workflow-probe-2026-10-10.md`
(bottleneck: discovery 0 candidates cho cả 3 needs), `docs/discovery-tiers.md`.

Không tải asset ngoài khi làm việc này: mọi provider mới chỉ có code +
test với fixture/mocked provider, không chạm `runtime/`, released pack,
`scene_graph`, `video_renderer`, rights module.

## 1. Adapters (toàn bộ keyless, không paid API, không key bắt buộc)

| Provider | Media | Tier | Acquisition | Preview | License/creator metadata |
|---|---|---|---|---|---|
| Openverse | image | keyless | download | thumbnail (api.openverse.org) | CC BY/BY-SA/CC0/PDM + creator/attribution |
| Wikimedia Commons | image/video | keyless | download | thumb/upload.wikimedia.org | extmetadata LicenseShortName/Artist |
| Internet Archive (mới) | image/video | keyless | download | `archive.org/services/img/{id}` | `licenseurl`→CC label / `rights` text / unknown + creator |
| YouTube referral (mới) | video | keyless | **referral_only** | `i.ytimg.com/vi/{id}/hqdefault.jpg` (keyless) | "Unknown — YouTube Standard License assumed", creator = channel |
| Pexels / Pixabay | image/video | keyed (free key, dormant khi thiếu) | download | provider CDN | Pexels/Pixabay License + photographer |

`provider_status()` liệt kê đủ 9 entries, thêm field additive
`acquisition: download | referral_only` (server cũ vẫn chạy: chỉ đọc
label/state). `youtube_referral` luôn `ready` nhưng mặc định trả `[]` —
không có network cho tới khi planner gắn hook (mục 4).

## 2. Interface thống nhất (additive trên `ExternalAssetCandidate`)

Mọi candidate mang: `provider`, `source_url`, `preview_url` (mirror
`thumbnail_url`), `media_type` (`IMAGE`/`VIDEO`, + property `media_kind`
lowercase `image|video`), `license` (mirror `license_name`), `creator`,
`rights_scope` (shape workstream-1, mục 3), `match_grade: exact|generic`,
`verification_status` (`unverified` mặc định, `verified` chỉ sau human
review). `to_unified_dict()` trả đúng shape spec cho planner/QA.

`match_grade` — `grade_match(title, creator, query, exact_terms)`:
- Có `exact_terms` (tên trận/cầu thủ từ planner): exact khi **mọi** term
  xuất hiện trong title/creator, ngược lại generic.
- Không có: exact khi title chia sẻ ≥2 token significativa (≥3 ký tự) với
  query; vocab bóng đá chung (`football/stadium/match/goal/...`) **không
  bao giờ** được tính → footage chung luôn generic.
- Search paths (`search_candidates`, `search_candidates_tiered` +
  `exact_terms` kwarg mới) tự stamp grade; `auto_acquire` truyền
  `include_terms` làm `exact_terms` và ưu tiên exact trước (stable sort).

## 3. YouTube: chỉ tìm + dẫn tới nguồn (3 cấm)

1. **Cấm tải thành asset:** `_candidate_by_id("youtube:…")`,
   `_download_candidate`, `_download_video_candidate`,
   `save_commons_candidate` đều raise `DiscoveryError` referral-only.
2. **Cấm mặc định gán quyền:** candidate YouTube mang W1 deny-default
   (`granted_by: deny-default`, `clip_limit: 0`); `candidate_rights_decision`
   với purpose đầy đủ → `allowed=false`, `unknown-source-or-license`,
   `required_action=human_review`. `auto_acquire` skip qua `rights_blocked`
   + re-check `is_referral_only` (defense in depth) — không đường nào ingest.
3. **Cấm suy diễn license:** license luôn "Unknown — YouTube Standard
   License assumed"; quyền thật nằm ở watch page, human xác định.

## 4. Quyền: consume workstream-1 (W1-DISCOVERY, đã nối — không reinvent)

`apps/asset_library/rights_scope.py` tồn tại trong cây nên discovery
**consume trực tiếp** (import lazy + fallback deny khi thiếu module):
- `rights_scope` của candidate = scope W1 thật: `default_deny_scope(...)`
  cho YouTube/license-unknown, `scope_from_legacy({...})` cho còn lại
  (CC → backfill-allow, NC/ND → grant hẹp, unclear → deny).
- `rights_blocked(scope)` — gate auto-acquire theo semantics W1
  (`granted_by == deny-default` hoặc `allowed is False`).
- `candidate_rights_decision(candidate, purpose)` — wrapper mỏng trên
  `is_usable_for` cho planner: adapt candidate → asset mapping
  (`source_type`/`source_url`/`license_type`/`creator`/`rights_scope`/
  `metadata.license_credit`) rồi gọi W1. Verified vẫn có thể deny
  (`rights-not-verified` pre-review) — đúng quy ước "verified ≠ được dùng".
- Không sửa `rights_scope.py`, `scene_graph`, `video_renderer`.

Điểm chờ còn lại → planner/QA: truyền purpose thật
(platform/territory/commercial/monetization/`edit=True`/`credit_planned`/
`use_count`); asset deny → loại + log `reasons`; khi human approve
candidate, gọi `build_rights_scope(...)` và lưu `rights_scope_json`
(workstream-1 §6.1 — ngoài ownership workstream này).

Mở rộng YouTube search keyless sau này: `set_youtube_search_fn(fn)` hoặc
`api_keys["YOUTUBE_SEARCH_FN"]` với `fn(query, limit) -> [{video_id(11 ký
tự), title, creator?, duration_seconds?}]`; ID lạ bị loại, hook lỗi → `[]`.

## 5. Giới hạn còn lại

- YouTube search mặc định `[]` (chưa có scraper keyless — cố ý, tránh
  fragile/TOS-gray; adapter đã sẵn sàng nhận hook).
- Archive dimensions phụ thuộc field `width/height` của item (thiếu → None
  → auto-acquire loại ở ngưỡng `min_width`, đúng hướng conservative).
- Archive download chưa chạm network thật (chỉ mocked test): file pick
  ưu tiên `.mp4`/`.jpg`, cap 20 MiB ảnh / 100 MiB video, redirect qua
  `_PublicHttpsRedirectHandler` + public-HTTPS check như Pexels.
- Live-network verification của 2 adapter mới để lại cho session có mạng.

## 6. Test

`tests/test_discovery_referral.py` — 14 passed (fixture/mocked, 0 network):
shape unified ×4 providers, default YouTube (preview/watch/deny),
chặn save/download YouTube, search hook (filter ID + chịu lỗi),
grade exact/generic ×2, parse Archive + license→grant mapping,
`_archive_detail`/`_archive_file_url`, provider_status/tiers,
tiered video stamp grade, auto_acquire skip-YouTube + prefer-exact,
YouTube-only → NO_QUALIFIED. Giữ xanh: tiers + providers + identity +
rights = 60 passed tổng (mục 6 chi tiết ở report session).
