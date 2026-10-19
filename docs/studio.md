# Studio — owner design manual (Polotno, embedded)

Open: `http://127.0.0.1:8000/studio` (needs internet: Polotno CDN + Google Fonts).

## Flow vẽ 1 card (2 phút)

1. Chọn Pack version (vd `10.0.0`) + Layout id (vd `duel_columns`
   hoặc mã Sprint 1 như `C-07` / `TA-03`).
2. Bấm **Short 1080×1920** hoặc **Long 1920×1080** (đúng pixel pack yêu cầu).
3. Chọn **Mẫu** (35 starters Sprint 1: `C-*`/`MR-*`/`BP-*`/`U-*` short,
   `TA-*` long, kèm `duel_columns` legacy) rồi bấm **Nạp mẫu** — canvas
   tự đổi đúng khổ của mẫu.
4. Sửa chữ/số trực tiếp. Decor đã khóa (không kéo/lỡ tay); font chỉ 3 họ brand.
5. Bấm **Xuất PNG vào pack** → engine check đúng pixel rồi lưu
   `pack-drop/<version>/<prefix>-<layout>.png`. Sai khổ báo ngay, không lọt.
6. Đủ layouts → `python -m apps.pack_import.build pack-drop/10.0.0`
   (hoặc nút build sau này) → audit tại `/template-foundation/pack-audit.html`.

## Luật để file lọt pack

- Chữ Việt chỉ dùng Barlow Condensed / Be Vietnam Pro (dấu đã verify).
- PermanentMarker chỉ họ latin/số.
- Số thắng trắng đậm, thua slate; không màu ngoài palette ink/coral/paper/slate.
- Credit whisper mọi card số; ảnh người chỉ ảnh có quyền (ghi vào licenses).
- Ô động giữ nguyên vị trí/kích thước để khớp boxes pack.json.

## Key

Chưa có `POLOTNO_API_KEY` (free trial, polotno.com/cabinet → `.env`) thì vẫn vẽ
và xuất được, nhưng file có thể dính watermark — kiểm proof trước khi lắp pack.
