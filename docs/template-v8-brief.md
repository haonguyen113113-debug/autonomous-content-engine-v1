# Template v8.0.0 "Sports Kit" — rebuild brief (Nova + 3 bộ card)

Nguồn minh họa owner gửi (3 bộ, diễn giải lại, không copy asset):

- **Bộ 1 — Comparison:** panel STATS đen (possession/shots/target/corners...),
  stat dọc PASSES 45 / ASSISTS 12 / GOALS 05 / SHOTS 05 + cutout cầu thủ.
- **Bộ 2 — Player poster 2x2:** mép giấy xé, ảnh split, họ brush cỡ lớn
  (LEWIS/WASHINGTON/MOORE/LITTLE), meta HOMETOWN/HEIGHT/SCHOOL,
  stats 289/2/23, ticker chéo lặp tên.
- **Bộ 3 — Match kit:** GOAL/GOAAAAL, NEXT MATCH V + date/stadium, POTM,
  RED CARD dọc R...D, UP NEXT fixture 3 hàng, THANK YOU sọc chéo,
  WELCOME nền X, FULL TIME + score bug 1-0/2-0 trên ảnh action.

## Quyết định Nova (từ `docs/template-nova-brief.md`, giữ nguyên)

1. Frame 0 là hook card 5–8 từ, punch-in, không bumper/logo.
2. Một số một card (hero-metric 3x + pop).
3. Dark broadcast editorial; đỏ/vàng tin tức VN không làm mặc định.
   Kit đỏ Canva chỉ là colorway phụ `matchday-red`, mặc định vẫn `san-dem` mực.
4. Barlow Condensed Bold (display, có dấu Việt) + Be Vietnam Pro (body).
   Brush chỉ cho họ latin/ký số, không cho câu tiếng Việt (PermanentMarker
   không có dấu — render brush bằng Arial Bold Italic trong Manim proof,
   bản PIL dùng PermanentMarker cho latin).
5. Motion không đứng yên: slide-in 0.3s, count-up 6 bước, stagger 0.18s,
   ease-out cubic, parallax 3 lớp, grain+vignette+1 hướng sáng.
6. Không footage trận, không crest/logo giải, số chỉ từ evidence đã duyệt
   kèm source+date.

## Manim ở đâu (theo `requirements-motion.txt`: build-time only)

- PIL giữ chuẩn chữ Việt (bundled TTF) cho plates tĩnh.
- Manim dựng motion atoms cho 6 layout mới: `hook_card` (đã có, thêm punch),
  `comparison_duel`, `stat_leader`, `player_poster`, `goal_card`,
  `fixture_card`. Các biến thể (POTM/WELCOME/THANK YOU/score/discipline/quote)
  là cấu hình của 6 atoms này + plates PIL, không thêm scene mới cho tới khi
  có proof (spec §17).
- Engine serve/render không cần Manim; proofs lưu `previews/manim/`.

## Layouts mới trong v8 (cộng với toàn bộ v7 giữ nguyên để tương thích)

| id | bộ | required_data | giới hạn |
|---|---|---|---|
| `comparison_duel` | 1 | metrics(≤5, home/away), source, date | 2 teams, zero-baseline bars |
| `stat_leader` | 1 | stats(≤4 label/value), source, date | 1 số/1 hàng, số 3x |
| `player_poster` | 2 | player_name, stats(≤3), source, date, media_file? | ảnh phải duyệt, không faces giả |
| `goal_card` | 3 | headline/scoreline, source, date | 1 claim 5–8 từ |
| `fixture_card` | 3 | fixtures(≤3 home/away/date), source, date | không crest thật |
| `score_card` | 3 | home/away/score, source, date | score bug trung thực |

## Acceptance v8

- `manim -qm` render 6 scenes dọc 1080x1920 PASS (proof mp4 trong previews/manim).
- PIL previews cho 6 layouts mới ở cả 2 aspect PASS, diacritics nguyên.
- `pytest tests/test_template_sportskit.py -q` PASS; drafts mới resolve 8.0.0,
  runs cũ pin version cũ.
- Old default tests chuyển sang pinned (6.0.0/7.0.0) để không vỡ khi thêm version.
