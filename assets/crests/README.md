# Crest store (bản quyền) — `assets/crests/`

Kho crest CLB có bản quyền cho slots `crest-home/away/winner/loser`.
Hiện render dùng monogram initials (MC, PSG); crest thật chỉ thay thế khi
đủ điều kiện bản quyền dưới đây. Tuyệt đối không tải/sao chép logo CLB từ mạng.

Policy cấm crest/logo ngoài (vẫn hiệu lực):

- `docs/canva-pack-contract.md` (§quy tắc export)
- `docs/express-fullpack-plan.md`, `docs/template-build-instruction.md` (§4),
  `docs/template-v8-brief.md`, `apps/studio_templates/build_v11_pack.py`
  ("unlicensed club crests")

## 1. Quy ước sử dụng

- Chỉ file **do owner cung cấp trực tiếp** mới được đặt vào thư mục này.
- Một crest chỉ được render khi TẤT CẢ đúng:
  1. có entry trong `manifest.json` với `club_slug` khớp,
  2. `rights_reviewed: true`,
  3. `file` trỏ tới file raster tồn tại trong chính thư mục này
     (`.png` / `.jpg` / `.jpeg` / `.webp`; không `.svg`, không path traversal).
- Còn lại (thiếu file, `rights_reviewed: false`, không có entry) →
  `resolve_crest()` trả `None`, render **fallback monogram** như hiện tại.
- `data/entities/clubs.json` chỉ là metadata danh tính (slug/canonical/alias),
  không phải nguồn ảnh/quyền.

## 2. Schema `manifest.json`

| field            | type         | bắt buộc | nghĩa                                            |
|------------------|--------------|----------|--------------------------------------------------|
| `club_slug`      | string       | yes      | slug khớp `data/entities/clubs.json` (vd `manchester-city`) |
| `file`           | string\|null | yes      | tên file trong thư mục này; `null` = đang chờ   |
| `source`         | string       | yes      | nguồn cung cấp (vd `owner-supplied`)             |
| `license`        | string       | yes      | căn cứ quyền (vd `club media licence 2026-27`)   |
| `acquired_at`    | string       | yes      | ngày nhận `YYYY-MM-DD` (`""` khi đang chờ)       |
| `rights_reviewed`| boolean      | yes      | owner đã duyệt quyền; `false` = cấm dùng        |
| `allowed_use`    | string       | yes      | phạm vi cho phép (vd `broadcast+social 2026-27`) |

## 3. Owner nộp crest (từng bước)

1. Đặt file vào thư mục này, tên theo slug:
   `assets/crests/manchester-city.png`, `assets/crests/paris-saint-germain.png`
   (nền trong suốt hoặc trắng, ≥512px cạnh ngắn).
2. Sửa entry tương ứng trong `manifest.json`: điền `file`, `source`,
   `license`, `acquired_at`, `allowed_use`, bật `rights_reviewed: true`.
3. Chạy kiểm tra:
   `python -m pytest tests/test_crest_store.py -q`
4. Không bao giờ commit file lấy từ mạng tìm kiếm/Google Images.

## 4. Tra cứu khớp tên (`apps/sportskit/crests.py`)

`resolve_crest(name_or_slug)` khớp case-insensitive + strip accents với:
slug, canonical_name, alias (`clubs.json`), entity_id (full + hậu tố),
và initials của canonical name (vd `PSG` → `paris-saint-germain`,
`MC` → `manchester-city`). `crest_status()` dùng cho audit.

## 5. Spec tích hợp render (CHƯA implement — TODO, lý do rủi ro)

Chưa sửa `starter_scenes._compose` / `render_design` vì 3 rủi ro:

1. `render_design` hiện chỉ biết `image` bed full-bleed (`_art_file` resolve
   pack/beds); crest cần element image gắn theo slot + circle-crop — code path mới.
2. `palette_stats`/`audit_blends` sẽ flag màu crest ngoài palette locked
   (TOLERANCE box) → cần exemption theo bounding box crest + cập nhật gates.
3. `render_starter_layers` tách bg/text layers; crest (decor layer) phải giữ
   geometry/slot y hệt monogram để không vỡ proof pixel hiện tại.

Khi kho đã có file licensed, implement theo spec:

- Trong `_compose`, sau khi `_fill_score`/`duel_columns` điền monogram:
  với mỗi slot `crest-*`, gọi `resolve_crest(team_name)`; nếu có Path →
  chèn child `{"type": "image", "id": "img-<slot-owner-id>", "x/y/width/height"
  = copy từ ring figure `ring-<slot-owner-id>`, "src": "crest:<club_slug>"}`
  ngay sau ring, và đặt text monogram tương ứng `showInExport: false`.
  Giữ nguyên ring (viền) + tọa độ; không dời bất kỳ phần tử nào khác.
- Trong `render_design` image branch: `src` bắt đầu `crest:` → load từ Path
  của loader (không qua `_art_file`), resize vừa box, circle-crop (mask ellipse
  + paste RGBA) rồi alpha_composite — khớp với badge ring hiện tại.
- `resolve_crest() is None` → không chèn gì (monogram giữ nguyên).
- Tests đi kèm: crest licensed render ra pixel khác monogram trong box ring;
  thiếu quyền render byte-identical với hiện tại; audit palette exempt đúng box.

TODO: implement spec trên (kèm test render + cập nhật gates) khi owner đã nộp
file licensed đầu tiên. Không implement trước để tránh code chết + vỡ proof.

## 6. Trạng thái hiện tại (clip 1, run `6cebedb10a9f` beat-2/3/4)

- `manchester-city`: THIẾU — entry pending, chờ owner cung cấp.
- `paris-saint-germain`: THIẾU — entry pending, chờ owner cung cấp.
- Render giữ monogram initials cho tới khi 2 file trên đủ điều kiện §1.
