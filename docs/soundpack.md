# Locked soundpack (`soundpacks/v1`)

Chủ đề nào nghe sound đó — mapping cố định trong `manifest.json`, engine
không discovery nhạc, không chọn nhạc, không synth nhạc.

## Pack gồm gì

- **4 beds** (file thật trong `tracks/` + sidecar, license sạch đã verify).
  Provisional — owner confirm/thay bằng YouTube Audio Library picks (TA-L01).
- **4 stingers theo owner catalog**: hook-hit (AKB-C05) @0s,
  transition-whoosh (AKB-C02) @chapters, build-riser (AKB-C07) @endcard-6s,
  end-jingle (provisional) @2s cuối.
- **6 reserve** (AKB-C06/C04/C02B, MR-S04/S07, BP-S07): import được nhưng
  chưa wire placement — file đến mới tính.
- Pixabay chặn bot nên files đến qua **owner drop** (`soundpacks/drop/` +
  `register.csv`) và `apps/soundpack/intake.py::import_pack` validate:
  đúng slot + đúng filename lock, decode được (ffprobe), duration caps
  (bed 600s / sting 15s / reserve 90s), ≤20 MiB, license allowlist, đủ
  provenance (page URL, commercial_ok, credit cho BY), **HOLD/Content-ID
  reject**. HÀNG chưa import thì render tự skip (không bao giờ fail video).

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
