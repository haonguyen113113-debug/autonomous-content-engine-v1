# Canva pack contract — bạn vẽ, engine lắp (v1)

Bạn thiết kế toàn bộ visual trên Canva (hoặc platform khác), export file,
thả vào thư mục drop, chạy 1 lệnh — engine validate rồi lắp thành template
package versioned, có audit page và test.

## Drop folder: `pack-drop/<version>/`

```
pack-drop/10.0.0/
  pack.json            # khai báo layouts, boxes, fonts, licenses (mẫu: chạy init)
  short-duel-columns.png      # 1080 x 1920, PNG/JPG, < 2MB
  long-duel-columns.png       # 1920 x 1080
  short-stat-leader.png
  ...
  fonts/               # optional: TTF + OFL nếu dùng font riêng
```

`pack.json` mẫu (tạo bằng `python -m apps.pack_import.init pack-drop/10.0.0`):

```json
{
  "channel_id": "allen-knows-ball",
  "template_id": "allen-knows-ball.shortform-analyst",
  "version": "10.0.0",
  "layouts": [
    {"id": "duel_columns", "title": "Doi dau",
     "boxes": [
       {"key": "metrics.0.value.home", "box": [0.08, 0.42, 0.30, 0.14],
        "font": "display", "size": 150, "color": "#F5F1E6", "align": "center"}
     ]}
  ],
  "licenses": [{"what": "Background plates", "by": "Owner (Canva export)", "terms": "Channel-owned"}]
}
```

## Quy tắc export (bắt buộc để lắp được)

1. Đúng pixel: short 1080x1920, long 1920x1080. Sai 1px cũng fail validate.
2. Vùng an toàn: không chữ/số quan trọng trong 9% top, 13% bottom, 7% hai biên.
3. Chữ tĩnh (tiêu đề, nhãn cố định) vẽ chết trên Canva; số/tên/ngày động để
   engine vẽ vào `boxes` (tọa độ 0-1 tương đối, gốc trái-trên).
4. Mỗi box: `key` trỏ vào graphic_data (`metrics.0.value.home`,
   `player_name`, `score`, `source`...), `font` chỉ 1 trong
   `display` (Barlow Condensed) / `body` (Be Vietnam Pro) / `brush` (latin),
   `size` là px trên bản short (bản long tự scale), màu hex, align.
5. Font có dấu: mọi chữ Việt engine vẽ dùng Barlow/BeVietnam đã verify;
   chữ Việt vẽ chết trên Canva phải tự bạn kiểm dấu.
6. Không crest/logo giải, không footage, không mặt cầu thủ lấy từ mạng —
   ảnh người trong plate phải là ảnh bạn có quyền (ghi vào licenses).

## Lệnh lắp

```powershell
python -m apps.pack_import.init pack-drop/10.0.0   # tạo scaffold lần đầu
python -m apps.pack_import.build pack-drop/10.0.0   # validate + lắp + audit
```

Xong: package `templates/allen-knows-ball/10.0.0/` + catalog entry (draft),
audit tại `/template-foundation/pack-audit.html`, drafts mới resolve 10.0.0.
Lỗi validate in ra từng file, từng box (sai size, thiếu file, box tràn).
