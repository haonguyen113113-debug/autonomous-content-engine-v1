# Rights scope — quyền sử dụng asset theo từng mục tiêu upload (2026-10-16)

Workstream 1/4. Checkpoint thay thế: `docs/audit-checkpoint-2026-10-08.md` không
tồn tại — workstream này dựa trên `docs/build-audit-protocol.md`,
`docs/template-build-manual.md` §8, `docs/workflow-probe-2026-10-10.md`,
`docs/voice-baseline.md` + `PROJECT_SPEC.md` §8/§13/§14.

## 1. Vì sao cần tách "verified" khỏi "được dùng"

Hiện tại mọi consumer (`apps/card_selector.py:139`,
`apps/video_renderer.py:941`, `apps/web_ui/server.py:230`,
`apps/asset_library/asset_intelligence.py:78`) chỉ check
`rights_state == "verified"` (+ `lifecycle_state == "active"`). Đó là gate
**độ phù hợp hình ảnh** (đúng người/đúng vật, đã qua kiểm duyệt), không phải
gate **quyền sử dụng cho lần upload này**. Một ảnh Etihad CC BY 4.0 đã
verified vẫn có thể sai platform, hết hạn, thiếu credit, vượt clip_limit, hoặc
nguồn YouTube không rõ quyền — và `verified` không trả lời được câu nào trong
số đó. Quy ước mới: **verified là cần nhưng không bao giờ đủ**;
`is_usable_for()` là gate thứ hai, bắt buộc trước khi attach media vào video.

## 2. API thống nhất (3 workstream kia consume)

`apps/asset_library/rights_scope.py`
`is_usable_for(asset, purpose) -> {allowed, reasons[], required_action, scope}`:

```python
from apps.asset_library.rights_scope import is_usable_for
out = is_usable_for(asset, {
    "platform": "youtube", "territory": "VN",
    "commercial": True, "monetization": True,
    "edit": True,               # composition luôn crop/scale/overlay -> truyền True
    "credit_planned": True,     # đã có credit burn-in/mô tả
    "use_count": 0,             # số clip đã dùng asset này
})
# {"allowed": bool, "reasons": [...],
#  "required_action": "human_review" | "none",
#  "scope": {"platforms": [...], "territories": [...], "commercial": bool,
#            "monetization": bool, "expires_at": "YYYY-MM-DD" | None,
#            "edit_allowed": bool, "credit": {"required": bool, "text": ...},
#            "clip_limit": int | None}}
```

`asset` chấp nhận: row library (`rights_scope_json` / `rights_scope` /
`metadata.rights_scope`), entry crest manifest (`club_slug` +
`rights_reviewed` + `allowed_use`), hoặc row legacy (tự derive conservative).
Thứ tự ưu tiên cố định: `rights_scope_json` (persisted) → `rights_scope`
(in-memory) → `metadata` → crest adapter → legacy backfill → deny-default.

`purpose` thiếu `platform`/`territory` → deny (không đoán thay caller).

## 3. Schema versioned + migration idempotent

- `RIGHTS_SCOPE_SCHEMA_VERSION = 1`; mọi scope lưu `schema_version: 1`.
  Version lạ → deny `rights-scope-version-unsupported` + `human_review`.
- `build_rights_scope(...)` — constructor cho UI duyệt quyền (human điền
  grant tường minh); invalid → `ValueError`. `validate_scope()` trả list lỗi.
- `ensure_rights_scope_schema(conn)` — migration độc lập, idempotent:
  thêm cột `assets.rights_scope_json` nếu thiếu, backfill row NULL từ
  license/source legacy, **không bao giờ ghi đè scope đã có** (rerun chỉ lấp
  chỗ trống do concurrent writer). Không đụng `schema_migrations` của
  `database.py` (thuộc workstream khác) — tích hợp sau chỉ cần gọi hàm này
  sau `connect()`, hoặc bọc thành migration-4.
- Backfill (`scope_from_legacy`): license `owned`/mở (CC0/PDM/CC BY/CC BY-SA
  không NC-ND/Pixabay/Pexels) → giữ grant social thương mại; NC/ND →
  grant hẹp phi thương mại; còn lại (unknown/pending/YouTube) → deny-default
  + `human_review`. NC/ND check dùng word-boundary (`\bNC\b`) để không nhầm
  "UNCLEAR".

## 4. Luật cứng

- **Mặc định deny:** YouTube (`youtube.com`/`youtu.be`/…) hoặc
  source/license chưa rõ → `allowed=false`, reason
  `unknown-source-or-license`, `required_action=human_review`.
- **Ngoại lệ bản quyền bắt buộc human review, cấm LLM tự kết luận:**
  `copyright_exception` (ở scope, asset, hoặc `metadata.copyright_exception` /
  `rights_disputed`, hoặc license rights-managed/editorial) → luôn deny
  `copyright-exception-requires-human`. Flag chỉ được gỡ bằng re-review của
  human có evidence mới — không có đường code nào cho LLM clear.
- Hết hạn (`now > expires_at`) → `rights-expired` + human (gia hạn cần người).
  Expiry không parse được → `rights-expiry-unclear` + human.
- Deny do scope hẹp có thể tự sửa (sai platform/territory, thiếu credit plan,
  vượt clip_limit, lifecycle không active) → `required_action=none` để
  planner/QA tự reroute asset khác hoặc bổ sung credit rồi retry.
- Credit: `credit.required + text` trả về trong scope để renderer burn-in.

## 5. Mẫu rights-gated: crest (`crest_entry_to_scope`, read-only)

Không sửa `apps/sportskit/crests.py` — adapter đọc entry manifest:
`rights_reviewed=True` + `allowed_use` parse ra ≥1 platform mới thành grant
(vd `"broadcast+social 2026-27"` → platforms social+broadcast,
`expires_at: "2027-12-31"`); còn lại deny + monogram fallback như cũ.
`edit_allowed=True` ở grant crest nghĩa là **placement fit-to-slot
(resize/circle-crop vào ring) — không recolor/méo mó/overlay lên mark**.

## 6. Điểm chờ tích hợp (discovery / planner / QA)

1. **Discovery + duyệt quyền:** khi human approve candidate
   (`save_commons_candidate(..., rights_reviewed=...)`,
   `server._review_asset_rights`), gọi `build_rights_scope(...)` với grant
   theo đúng mục tiêu upload rồi lưu JSON vào `rights_scope_json`. Hiện tại
   2 path này vẫn chỉ flip `verified` chưa ghi scope — chưa sửa vì ngoài
   ownership; consumer tiếp theo nối vào.
2. **Planner (`card_selector`/`asset_intelligence`):** sau khi check
   `verified`, gọi `is_usable_for(asset, purpose)` với purpose của video sắp
   render (`edit=True`, platform/territory/commercial thật). Asset deny →
   loại + log `reasons`.
3. **QA/renderer:** trước attach media, assert `allowed is True`; nếu
   `credit.required`, burn-in `scope.credit.text`. (Renderer chưa đụng theo
   ownership.)
4. **Migration-4 chính thức:** bọc `ensure_rights_scope_schema` trong
   `database.py` khi integrator gom các workstream.

## 7. Giới hạn còn lại

- `edit_allowed` là boolean: chưa phân biệt resize-fit vs transform sâu;
  với mark (crest) hiện quy ước "placement fit only" trong `notes`.
- Territory match chính xác theo mã (ISO, case-insensitive) + wildcard
  `*`/`worldwide`/`global`; chưa có map VN↔Vietnam, region (EU/SEA).
- `use_count`/`clip_limit` do caller đếm và truyền vào — chưa có bộ đếm
  dùng chung trong DB.
- Parser `allowed_use` crest là best-effort; text không nhận diện được →
  deny + human (đúng hướng conservative).
- Chưa có UI nhập scope (đợi workstream discovery/planner).

## 8. Test

`tests/test_rights_scope.py` — 16 passed. Bao phủ: verified-không-scope bị
deny; đủ grant thì allow; lệch platform/territory/commercial/monetization/
edit/credit/clip_limit; YouTube + nguồn chưa rõ deny + human; copyright
exception luôn human (kể cả grant đẹp); unverified + scope đẹp vẫn deny;
crest pending deny / cleared parse đúng; backfill open giữ grant,
unknown deny; schema version + validate; migration idempotent + giữ nguyên
scope human đã thu hẹp; ưu tiên `rights_scope_json` persisted.
