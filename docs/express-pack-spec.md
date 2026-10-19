# Adobe Express one-shot pack spec (v12.0.0)

Flow: bạn generate backgrounds trong Express → thả file vào `pack-drop/12.0.0/`
→ chạy `python -m apps.pack_import build pack-drop/12.0.0` → engine validate,
lắp thành package versioned, có audit page + test. Xong là lock, Express hết
vai trò. Chi tiết contract: `docs/canva-pack-contract.md`.

## Quy tắc bắt buộc (sai là validate fail)

1. **Đúng pixel tuyệt đối**: short `1080x1920`, long `1920x1080` cho mỗi layout.
   Tên file: `short-<id>.png` + `long-<id>.png` (`duel_columns`, `stat_leader`,
   `player_poster`, `goal_card`, `fixture_card`, `score_card`; thêm/bớt id bằng
   cách sửa `layouts` trong `pack.json`). Mỗi file < 2MB.
2. **Vùng an toàn**: không chi tiết quan trọng trong 9% top, 13% bottom,
   7% hai biên — đó là chỗ của boxes chữ engine vẽ.
3. **KHÔNG vẽ chữ tiếng Việt chết vào background.** Mọi tên/số/ngày/quotes do
   engine vẽ vào `boxes` bằng font đã verify dấu (Tektur/BeVietnam). Background
   chỉ chứa: họa tiết, dải màu, khung, nhãn trang trí latin (VD: "LIVE",
   "MATCHDAY", số áo mẫu) — chữ Việt trong ảnh AI hay vỡ dấu.
4. **Chừa chỗ trống cho boxes**: mỗi layout cần vùng trống tương ứng các box
   khai báo trong `pack.json` (tọa độ tương đối 0-1, gốc trái-trên). Box mẫu
   mặc định: headline dải ngang trên (y 0.10-0.20). Sửa box cho khớp vùng
   trống thực tế trước khi build.
5. **Cấm**: logo/crest CLB, logo giải đấu, footage, khuôn mặt cầu thủ thật,
   watermark. Ghi nguồn/quyền vào `licenses` trong `pack.json`.
6. Font trong boxes chỉ 1 trong 3: `display` (Tektur) / `body` (BeVietnam Pro) /
   `brush` (latin only). Màu box dạng `#rrggbb`, size 11-400px.

## Prompt gợi ý cho Express (copy-paste, sửa theo layout)

```
Vertical 9:16 broadcast background plate, no people, no text in Vietnamese,
no logos: <MOOD>. Deep navy void with cyan neon grid floor at the bottom,
magenta horizon glow, subtle circuit traces top corners, film grain.
Large empty dark area in the upper-middle third for headline text overlay.
Flat vector sports broadcast style, clean, high contrast, 1080x1920.
```

`<MOOD>` thay theo layout: duel = `symmetric split energy, left calm vs right
charged`; score = `monumental empty center, glowing horizon low`; poster =
`dark left portrait void with soft rim light, textured right field`; goal =
`explosive light burst low center, calm dark top`; fixture = `clean schedule
board, generous whitespace rows`.

## Lệnh chạy

```powershell
python -m apps.pack_import build pack-drop/12.0.0
```

Xong: package `templates/allen-knows-ball/12.0.0/` (+ `longform-12.0.0`) trạng
thái draft + audit tại `/template-foundation/pack-audit.html`. Bạn audit,
duyệt thì promote released như v10/v11.
