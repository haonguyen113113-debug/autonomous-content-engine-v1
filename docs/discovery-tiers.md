# Tiered discovery — free-first with keyed escalation

Học từ Visibly AI (MCP tools dùng Google data free khi đã connect, chỉ
fallback DataForSEO tốn credits khi thiếu, luôn trả `data_source`).

## Quy tắc

```
library (reuse-first, 0 cost)
  → keyless: Openverse + Wikimedia Commons (0 quota)
    → keyed: Pexels + Pixabay (200/hr, 20k/mo — chỉ khi thiếu)
```

`search_candidates_tiered()` trong `apps/asset_library/discovery.py`:

- Phase 1 chỉ query keyless. Đủ `min_free` (default 6) → dừng, keyed
  không bị chạm tới (giữ quota). `min_free=0` = free-only.
- Thiếu mới escalate sang keyed rồi merge + rank lại.
- Trả `(candidates, statuses, tier_report)` với `tiers_queried`,
  `free_count`, `keyed_count`, `escalated`, `escalation_reason`,
  `keyed_available`. Mỗi candidate stamped `source_tier`.
- `search_candidates()` cũ giữ nguyên behavior cho caller hiện tại
  (`content_workflow` không truyền keys nên keyed vốn dormant).

## Nối sẵn

- `POST /api/discovery-search` dùng tiered, response thêm
  `tiers_queried/escalated/escalation_reason/keyed_available`
  (additive — `app.js` cũ vẫn chạy).
- Khóa bằng `tests/test_discovery_tiers.py`: free đủ thì keyed
  không được gọi (boom guard), thiếu thì merge, không keys thì
  không escalate.
