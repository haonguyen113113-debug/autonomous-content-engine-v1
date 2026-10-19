# Voice decision matrix — 2026-10-16 (clip 1 tồn: chốt giọng TTS)

Trạng thái: **CHƯA CHỐT — chờ owner nghe samples và tick chọn.**
Không tự chọn thay owner. Không bịa kết quả nghe.

Bối cảnh đã xác minh:
- Clip 1 `runtime/runs/6cebedb10a9f.json:271-276` voice_preview engine
  `elevenlabs/eleven_multilingual_v2`, voice `George`, local_only false —
  làm ngoài, code chưa có tích hợp ElevenLabs (grep repo chỉ thấy
  `docs/template-build-manual.md:283,290`, không thấy code gọi API).
- Pipeline local chính: `apps/voice_tts.py:106-174`
  (VieNeu-TTS-v3-Turbo, reference `runtime/voice/allen-reference.wav` +
  `profile.json`, hoặc preset qua `TTS_VOICE`), worker
  `apps/tts_preview_worker.py:31-41`, baseline `docs/voice-baseline.md:1-26`,
  `.env.example:49-58`.
- `runtime/voice/` hiện có `allen-reference.wav` + 3 preview
  (`1370343377aa`, `1af228a61ae7`, `6cebedb10a9f-George` 5572880 bytes).
- Render report `runtime/renders/6cebedb10a9f/render-report.json:86-90`
  voice `PENDING OWNER AUDIT`.
- `.env` máy này có `TTS_SILENCE_P=0.08`, **chưa set `TTS_VOICE`**
  (nghĩa là mặc định clone `allen-reference`); có dòng
  `ELEVENLABS_API_KEY` do owner cung cấp — không in giá trị ra đây,
  không hardcode vào script.

## (a) Đoạn narration chuẩn (dùng chung cho mọi sample)

Lấy nguyên văn 2 câu đầu beat-1/beat-2 clip 1
(`runtime/runs/6cebedb10a9f.json:29,65`):

> Manchester City vừa thua Paris Saint-Germain hai bốn ngay trên sân nhà
> Etihad. Hiệp một khép lại với tỷ số không tưởng: đội khách dẫn ba không
> chỉ sau ba mươi hai phút.

File text chuẩn để pipe vào worker (tạo local, không commit):

`runtime/voice/sample-standard.txt` — nội dung đúng 2 câu trên.

## (b1) Preset VieNeu local — kết quả list thật (không cần key)

Lệnh đã chạy thật ngày 2026-10-16 (chỉ list, không synth):

```powershell
runtime/tts-venv/Scripts/python.exe -c "import sys; from vieneu import Vieneu; e=Vieneu(mode='v3turbo', backend='onnx'); v=e.list_preset_voices(); open('voice_list_tmp.json','w',encoding='utf-8').write(__import__('json').dumps(v, ensure_ascii=False, indent=2)); print('wrote', len(v))"
# => wrote 25 (file tạm đã xóa sau khi đọc)
```

`Vieneu(mode='v3turbo', backend='onnx')` expose:
`list_preset_voices() -> List[tuple]`, `resolve_voice_name(name)`,
`infer(text, ref_audio=None, voice=None, ... silence_p=0.15, ...)`.
Worker `apps/tts_preview_worker.py:35-41`: nếu `TTS_VOICE` set thì gọi
`engine.infer(text=text, voice=preset, ...)`, bỏ qua `ref_audio`.

25 preset thật (dạng `[label, voice-name]` — dùng **voice-name** cho `TTS_VOICE`):

| # | label | voice-name (`TTS_VOICE=`) | Ghi chú |
|---|-------|---------------------------|---------|
| 1 | ⭐ Adam bựa — Nam · Bắc · Phong cách tự nhiên | `Adam bựa` | Nam, giọng Bắc |
| 2 | ⭐ Trúc Ly — Nữ · Bắc · Phong cách tự nhiên | `Trúc Ly` | Nữ, Bắc |
| 3 | ⭐ Thiện Minh — Nam · Bắc · Phong cách kể chuyện | `Thiện Minh` | Nam, Bắc |
| 4 | ⭐ Mai Anh — Nữ · Bắc · Phong cách tin tức | `Mai Anh` | Nữ, Bắc |
| 5 | ⭐ Hải Đăng — Nam · Bắc · Phong cách tự nhiên | `Hải Đăng` | Nam, Bắc |
| 6 | ⭐ Thùy Dung — Nữ · Nam · Phong cách tin tức | `Thùy Dung` | Nữ, **Nam** |
| 7 | ⭐ Thiền Tâm Đức — Nam · Bắc · Phong cách kể chuyện | `Thiền Tâm Đức` | Nam, Bắc |
| 8 | ⭐ Ngọc Huyền — Nữ · Bắc · Giọng đọc tự nhiên | `Ngọc Huyền` | Nữ, Bắc |
| 9 | ⭐ Quang Sơn — Nam · Trung · Phong cách tự nhiên | `Quang Sơn` | Nam, Trung |
| 10 | ⭐ Ngọc Trân — Nữ · Trung · Phong cách tự nhiên | `Ngọc Trân` | Nữ, Trung |
| 11 | Minh Đức — Nam · Bắc · Phong cách tin tức | `Minh Đức` | Nam, Bắc |
| 12 | Phạm Tuyên — Nam · Bắc · Phong cách tự nhiên | `Phạm Tuyên` | Nam, Bắc |
| 13 | Thái Sơn — Nam · Nam · Phong cách kể chuyện | `Thái Sơn` | Nam, **Nam** |
| 14 | Xuân Vĩnh — Nam · Bắc · Phong cách tự nhiên | `Xuân Vĩnh` | Nam, Bắc |
| 15 | Thanh Bình — Nam · Bắc · Phong cách kể chuyện | `Thanh Bình` | Nam, Bắc |
| 16 | Ngọc Linh — Nữ · Bắc · Phong cách kể chuyện | `Ngọc Linh` | Nữ, Bắc |
| 17 | Đoan Trang — Nữ · Bắc · Phong cách tự nhiên | `Đoan Trang` | Nữ, Bắc |
| 18 | Thục Đoan — Nữ · Nam · Phong cách kể chuyện | `Thục Đoan` | Nữ, **Nam** |
| 19 | Minh Triết — Nam · Nam · Phong cách tin tức | `Minh Triết` | Nam, **Nam** |
| 20 | Mỹ Duyên — Nữ · Nam · Phong cách đọc truyện | `Mỹ Duyên` | Nữ, **Nam** |
| 21 | Quỳnh Anh — Nữ · Bắc · Phong cách đọc truyện | `Quỳnh Anh` | Nữ, Bắc |
| 22 | Đức Trí — Nam · Nam · Phong cách đọc truyện | `Đức Trí` | Nam, **Nam** |
| 23 | Kim Thanh — Nữ · Nam · Phong cách đọc truyện | `Kim Thanh` | Nữ, **Nam** |
| 24 | Adam — Nam · Nam · Giọng đọc tự nhiên | `Adam` | Nam, **Nam** |
| 25 | Quốc Tuấn — Nam · Bắc · Phong cách tự nhiên | `Quốc Tuấn` | Nam, Bắc |

Ứng viên nam giọng Nam hợp bóng đá Việt (khớp `.env.example:52-54`):
`Adam`, `Minh Triết`, `Thái Sơn`, `Đức Trí` + baseline `allen-reference`
(clone, không set `TTS_VOICE`).

## (b2) Lệnh generate sample local (owner chạy, nghe rồi tick §d)

Mỗi preset ~10-15 giây cho 2 câu chuẩn. Output để ngoài git
(`runtime/` + `*.wav` đã git-ignored — không commit).

```powershell
# 1. Tạo file text chuẩn (2 câu §a)
"Manchester City vừa thua Paris Saint-Germain hai bốn ngay trên sân nhà Etihad. Hiệp một khép lại với tỷ số không tưởng: đội khách dẫn ba không chỉ sau ba mươi hai phút." | Out-File -Encoding utf8 runtime/voice/sample-standard.txt

# 2. Sample từng ứng viên (chạy từng dòng, nghe từng file):
$env:PYTHONUTF8="1"; $env:PYTHONIOENCODING="utf-8"
Get-Content runtime/voice/sample-standard.txt -Raw -Encoding utf8 | $env:TTS_VOICE="Adam" runtime/tts-venv/Scripts/python.exe apps/tts_preview_worker.py runtime/voice/allen-reference.wav runtime/voice/sample-Adam.wav
Get-Content runtime/voice/sample-standard.txt -Raw -Encoding utf8 | $env:TTS_VOICE="Minh Triết" runtime/tts-venv/Scripts/python.exe apps/tts_preview_worker.py runtime/voice/allen-reference.wav runtime/voice/sample-Minh-Triet.wav
Get-Content runtime/voice/sample-standard.txt -Raw -Encoding utf8 | $env:TTS_VOICE="Thái Sơn" runtime/tts-venv/Scripts/python.exe apps/tts_preview_worker.py runtime/voice/allen-reference.wav runtime/voice/sample-Thai-Son.wav
Get-Content runtime/voice/sample-standard.txt -Raw -Encoding utf8 | $env:TTS_VOICE="Đức Trí" runtime/tts-venv/Scripts/python.exe apps/tts_preview_worker.py runtime/voice/allen-reference.wav runtime/voice/sample-Duc-Tri.wav
# baseline clone (không preset — unset TTS_VOICE):
Remove-Item Env:\TTS_VOICE -ErrorAction SilentlyContinue
Get-Content runtime/voice/sample-standard.txt -Raw -Encoding utf8 | runtime/tts-venv/Scripts/python.exe apps/tts_preview_worker.py runtime/voice/allen-reference.wav runtime/voice/sample-allen-reference.wav
```

Mở rộng sang preset khác (nếu muốn nghe thêm giọng Bắc/Trung/Nữ):

```powershell
$env:TTS_VOICE="<voice-name đúng dấu ở bảng §b1>"
Get-Content runtime/voice/sample-standard.txt -Raw -Encoding utf8 | runtime/tts-venv/Scripts/python.exe apps/tts_preview_worker.py runtime/voice/allen-reference.wav runtime/voice/sample-custom.wav
```

Full-preview cả clip 59s với preset đã shortlist (qua pipeline chuẩn,
yêu cầu script owner-approved — dùng luôn run clip 1 trên bản copy test,
không ghi đè preview George gốc):

```powershell
# Ví dụ: copy run sang id test 12 ký tự, approve, set TTS_VOICE rồi gọi API/pipeline.
# Hoặc nhanh: tạm set TTS_VOICE=Adam trong .env rồi chạy preview trên run test.
# Kiểm tra overrun: so duration wav vs duration_target_seconds=59, yêu cầu <= 59*1.25.
```

Nghe lại 3 preview đã có (không cần generate):

```powershell
start runtime/voice/6cebedb10a9f-voice-preview.wav   # George (ElevenLabs, ngoài)
start runtime/voice/1af228a61ae7-voice-preview.wav
start runtime/voice/1370343377aa-voice-preview.wav
```

## (b3) George / Charlie / River / Liam (ngoài — cần key owner)

- Code repo **chưa có** tích hợp ElevenLabs: không có module gọi API,
  không có tham số `ELEVENLABS_*` trong `apps/voice_tts.py`, worker hay test.
  Clip 1 George làm ngoài với `elevenlabs/eleven_multilingual_v2`.
- Muốn samples Charlie/River/Liam (hoặc George lại): cần
  `ELEVENLABS_API_KEY` do owner cung cấp (đã có dòng key trong `.env` máy
  này — **không in giá trị, không hardcode, không commit**).
  Cách làm: owner tự generate trên ElevenLabs (web/API) với model
  `eleven_multilingual_v2`, cùng 2 câu chuẩn §a, rồi thả file vào
  `runtime/voice/sample-George.wav`, `sample-Charlie.wav`,
  `sample-River.wav`, `sample-Liam.wav` để nghe A/B với 5 sample local.
- Chỉ khi owner quyết định dùng ElevenLabs làm giọng chính mới tính
  chuyện viết tích hợp code (ngoài scope doc này).

## (c) Tiêu chí nghe (chấm trước khi tick)

1. **Tự nhiên tiếng Việt** — dấu thanh, tên riêng (Etihad, PSG) rõ, không
   robot, không nuốt chữ ở tốc độ shorts.
2. **Hợp bóng đá Việt** — nam, năng lượng bản tin thể thao, không quá
   trầm kể chuyện, không quá hài (lưu ý `Adam bựa` là preset riêng,
   khác `Adam` giọng đọc tự nhiên).
3. **Bền 60s** — nghe hết sample ngắn không mệt; shortlist phải qua thêm
   vòng full 59s trước khi lock.
4. **Overrun ≤ 1.25** (baseline `CHARS_PER_SECOND=14`,
   `MAX_SPEECH_OVERRUN=1.25`) — duration wav full-preview ≤ 73.75s cho
   target 59s; render clip 1 vừa FAIL duration (59s → 63.00s) nên giọng
   quá chậm sẽ bị loại dù hay.

## (d) Bảng owner tick chọn (owner điền)

| Ứng viên | File sample | Nghe (pass/fail) | Ghi chú owner |
|----------|-------------|------------------|---------------|
| allen-reference (clone, mặc định) | `runtime/voice/sample-allen-reference.wav` | ☐ | |
| Adam (Nam, tự nhiên) | `runtime/voice/sample-Adam.wav` | ☐ | |
| Minh Triết (Nam, tin tức) | `runtime/voice/sample-Minh-Triet.wav` | ☐ | |
| Thái Sơn (Nam, kể chuyện) | `runtime/voice/sample-Thai-Son.wav` | ☐ | |
| Đức Trí (Nam, đọc truyện) | `runtime/voice/sample-Duc-Tri.wav` | ☐ | |
| George (ElevenLabs, clip 1) | `runtime/voice/6cebedb10a9f-voice-preview.wav` | ☐ | đã có sẵn |
| Charlie (ElevenLabs) | `runtime/voice/sample-Charlie.wav` | ☐ | cần owner generate |
| River (ElevenLabs) | `runtime/voice/sample-River.wav` | ☐ | cần owner generate |
| Liam (ElevenLabs) | `runtime/voice/sample-Liam.wav` | ☐ | cần owner generate |

Sau khi tick: ghi `TTS_VOICE=<tên>` (hoặc để trống = clone) vào `.env`
máy local, chạy full-preview + audit rồi mới cập nhật
`docs/voice-baseline.md` § Locked reference (hiện vẫn để trống — xem doc
baseline).
