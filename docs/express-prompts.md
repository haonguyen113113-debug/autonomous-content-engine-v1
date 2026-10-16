# Express prompt pack v12 — 6 layouts, 1 system (copy từng khối)

Nguyên tắc coherence: mọi prompt = SHARED STYLE (chung, dán nguyên) +
COMPOSITION (riêng từng layout) + NEGATIVE (chung, dán nguyên). Không sửa
shared blocks giữa các lần generate, pack mới đồng nhất.

## SHARED STYLE (dán vào mọi prompt)

```
Unified sports broadcast background system, flat vector key-art, night cyber
stadium mood: deep navy-black void #060913, neon cyan #00E5FF edge lines and
grid floors, magenta #FF3D81 horizon glow accents, warm amber #FFB03A micro
lights, fine film grain, subtle vignette. No people, no faces, no logos, no
crests, no text in any Asian script, minimal latin micro-labels only
("LIVE", "MATCHDAY", round numbers allowed). Clean geometric composition,
high contrast, no photorealism, no watermark.
```

## NEGATIVE (dán vào mọi prompt)

```
No Vietnamese text, no Asian characters, no club crests, no competition
logos, no real players, no faces, no broadcast footage stills, no watermark,
no photorealistic crowd, no lens dirt blocking center, keep text-overlay
zones empty and dark.
```

## COMPOSITION từng layout (thêm sau SHARED STYLE)

1. **score_card** — short: `monumental empty dark center for a giant scoreline,
   faint giant pitch circle centered behind, glowing magenta horizon low,
   quiet top band for competition context`. long: `same, horizontal split
   energy left calm vs right charged, vertical neon edge off-center right`.
2. **duel_columns** — short: `two vertical energy columns, left calm dark,
   right charged with subtle grid, thin cyan center rule full height`. long:
   `same columns left/right of center`.
3. **stat_leader** — `clean dark field, faint oversized ghost numeral right
   edge, open left two-thirds for stat rows, low horizon glow`.
4. **player_poster** — `dark portrait void left third with soft cyan rim
   light from the left edge (empty, no person), textured dark field right
   two-thirds for name and stats`.
5. **goal_card** — `explosive cyan-magenta light burst low center, calm dark
   top half for headline, ember dots rising`.
6. **fixture_card** — `clean minimal schedule board, generous dark whitespace
   rows center, thin neon frame lines, calm`.

Kích thước: short `1080x1920`, long `1920x1080` — đúng pixel tuyệt đối,
mỗi file < 2MB, tên `short-<id>.png` / `long-<id>.png`.

## Vùng trống cho boxes (đã khai báo mẫu trong pack.json)

Mặc định mỗi layout có 1 box headline dải ngang trên (y 0.10–0.20). Sau khi
có ảnh, tôi sẽ đo vùng trống thực tế và chỉnh boxes rồi build — bạn không
cần đụng pack.json. Quy ước khi generate: giữ 9% top, 13% bottom, 7% hai
biên thoáng và tối cho chữ.
