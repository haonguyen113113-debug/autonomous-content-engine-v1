# Locked soundpack (`soundpacks/v1`)

Chủ đề nào nghe sound đó — mapping cố định trong `manifest.json`, engine
không discovery nhạc, không chọn nhạc, không synth nhạc.

## Pack gồm gì

- **4 beds** (CC0/BY 4.0, file thật trong `tracks/` + sidecar `<slot>.json`
  ghi title/creator/license/URLs/sha256): tension, neutral, uplift, dramatic.
- **3 stingers**: hook-hit (giây 0), transition-whoosh (mỗi chapter),
  end-jingle (2s cuối).
- **mapping** story form → bed (5 forms + default). Đổi set nhạc = bump
  pack version mới; run pin version đang dùng.

## Mix trong render (`_render`, full render only)

Bed loop dưới voice, ducking `sidechaincompress` theo đúng spec template
(`music ducks under speech`), stingers ở slots cố định, loudnorm I=-14
(Shorts target), AAC 192k. Preview/benchmark câm như cũ. Pack lỗi/thiếu
file/`SOUNDPACK_ENABLED=false`/override `none` → voice-only + report note.
Nhạc không bao giờ block video.

## Chọn/đổi

- Mặc định theo mapping. Fix trong summary: section `sound`, note = bed id
  hoặc `none` (validate against manifest).
- Thêm track mới: drop file vào `tracks/` + sidecar + dòng LICENSES.md +
  khai `beds`/`licenses` trong manifest. **Không license coi như không tồn
  tại** — file không list không bao giờ được dùng.
- 2 beds BY 4.0 (uplift, dramatic): credit creator trong description khi
  publish (bước tay lúc publish).

## Nguồn tracks v1

Tìm qua Openverse Audio (`license=cc0,pdm,by`, 10/2026): Freesound previews
(kế thừa license gốc) + 1 file Wikimedia Commons. Tránh recordings thương
mại dính Content ID. Nếu YouTube flag track nào: thay file + sidecar, bump
version.

Khóa bằng `tests/test_soundpack.py` (manifest, mapping đủ 5 forms, resolve,
placement, filter string) + summary tests (section, fix, none).
