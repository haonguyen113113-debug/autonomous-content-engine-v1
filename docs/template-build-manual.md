# Template v12 Build Manual (trace-back)
Ngày chốt: 16/10/2026. Mục đích: bất kỳ ai (hoặc model nào) đọc file này
cũng dựng lại được đúng pack v12 đang released, hoặc truy ra vì sao một
bước được làm theo cách đó. Mọi con số dưới đây đều là giá trị thật đã ship.

## 0. Nguyên tắc bất biến (vi phạm là build sai)
1. **Blend vào artwork, không đè lên artwork.** Nền là thiết kế có sẵn
   với void/grid có chủ đích. Chữ/số/detail đặt vào void, đo bằng máy
   (brightness + edge grid 12x12), không đoán bằng mắt.
2. **Hướng dẫn gốc để tham khảo, artwork là chuẩn cuối.** Khi instruction
   cũ (pack_import boxes mù, beds generative) xung đột với artwork thì
   artwork thắng, và instruction `docs/template-build-instruction.md`
   thắng mọi doc cũ hơn.
3. **Mỗi card giữ function/slots riêng.** 89 card = 89 JSON starter
   (90 trừ BP-12 đã xóa 16/10, xem log BP-12),
   slot names không đổi khi rework (Studio binding + test依). Chỉ sửa
   geometry/decor, không sửa content.
4. **Cấm Barlow cho chữ Việt cỡ lớn** (Pillow không raqm, vỡ marks).
   Chữ Việt chỉ Tektur/Be Vietnam Pro. Display (Barlow Condensed) chỉ
   cho numeral latin và punctuation.
5. **Badge kênh ≠ badge đội.** Badge kênh (AKB-Badge circle-crop, loại
   watermark Pippit, giữ frame tròn YouTube) chỉ bake ở opening/ending.
   Versus/information dùng slot monogram động (crest-home/away/winner/
   loser) hoặc crest kiểm duyệt quyền, không bao giờ bake.
   *Ngoại lệ owner 16/10: badge-circle watermark bake góc phải MỌI plate
   (trừ opening/ending đã có) — xem log Channel badge. Monogram động giữ
   nguyên, không thay bằng badge bake.*
6. **Không placeholder/tagline.** Tagline TBD nên không ship bất kỳ
   text/tagline tạm nào trong card, UI hay doc.
7. **Released packs bất biến.** Sửa = version mới. Draft sửa tại chỗ được.

## 1. Skill đã cài và áp dụng ở đâu (verify: `python skills/verify.py`)
ALL SKILLS OK (113 files, 9 skills): frontend-design, canvas-design,
algorithmic-art, emil-design-eng, theme-factory, design-taste,
impeccable-lite, broadcast-depth, polotno-sdk.
- frontend-design: plan token + wireframe trước khi build; hero-first;
  structure encodes information (winner scale/position); cut 1 accessory.
- canvas-design: plates gánh 90% visual, text essential-only; refine pass.
- broadcast-depth: top-light scrim veil (VOID 0.45) khi probe rớt; hero
  glow sau numeral duy nhất; grain seed 7 ở card-stage (chưa bật hàng loạt).
- design-taste: contrast đo thật từng zone (boss/large ≥3.0, text
  thường ≥4.5); Iron Law (không ship bản đầu); pre-flight mỗi sprint.
- graphic-design-system: 1 boss/frame; SUPPORT ~0.28x; WHISPER ~0.16x;
  tối đa 3 cỡ chữ (ngoại lệ có ghi chú khi encode winner/loser);
  safe area 7/9/13/7 (credit whisper tới 97%).
- theme-factory: chỉ dùng method, preset cấm; palette khóa cyber-pitch:
  VOID #060913, PANEL #0D1424, CYAN #00E5FF, MAGENTA #FF3D81,
  AMBER #FFB03A, PAPER #F2F6FF, SLATE #8296BE.
- impeccable-lite: một hướng duy nhất; verify bounded (gates §7).
- algorithmic-art: seeded deterministic (veil alpha, grain seed ghi log).
- emil-design-eng: unseen details compound; review Before/After/Why.
- polotno-sdk: schemaVersion 4, id duy nhất, mọi text động có
  custom.slot, decor khóa full flags, bed full-bleed con đầu.

## 2. Nguồn vào
- Nền: `assets/originals/plates/` + manifest (nguồn Pippit AI, ngày,
  quyền; watermark plates đã inpaint; badge giữ gốc).
- Badge: `assets/originals/brand/AKB-Badge.png` 800x800 → circle-crop
  tâm (400,400) r340, feather 2px, viền PAPER 7px + VOID 4px ngoài
  (khung tròn chuẩn YouTube). Watermark Pippit góc trái-trên nằm ngoài
  circle nên bị loại hoàn toàn.
- Font khóa: Tektur-Medium, BigShoulders-Bold, BeVietnamPro
  (Regular/SemiBold/Bold), BarlowCondensed (latin/numeral), Permanent
  Marker (latin-only).

## 3. Quy trình build pack (đã chạy, draft → released 12.0.0)
1. Intake ảnh về đúng pixel tuyệt đối (short 1080x1920, long 1920x1080),
   center-crop + Lanczos, RGB, mỗi file <2MB (PNG optimize, rớt qua JPEG
   q90/85/80/75 nếu quá). Sai 1px là validate fail.
2. `pack-drop/12.0.0/pack.json`: 24 layouts theo đúng từ vựng renderer
   gọi (hook_card, goal_card, duel_columns, comparison_duel,
   statline_scorecard, stat_leader, chart_comparison, player_poster_side,
   player_poster_top, player_poster, player_card, potm_card, fixture_card,
   fixture_list, score_card, quote_card, source_card, discipline_card,
   chart_timeline, welcome_card, tactical_explainer, opening, ending,
   takes) + myth. Boxes: chữ Việt chỉ font body (BeVietnam), numeral
   latin font display; 1 boss/frame, ≤3 cỡ chữ; boxes nằm trong safe area
   (assert ở script prepare).
3. `python -c "from apps.pack_import import build"` (CLI `__main__` vỡ
   sẵn: import function thay vì module — không sửa file dùng chung, gọi
   trực tiếp). Output: `templates/allen-knows-ball/12.0.0/` +
   `longform-12.0.0/` + catalog draft + audit page.
4. Enrich anatomy theo instruction §2: design-tokens + color-systems
   cyber (giữ colorway id `cyber-pitch` — contract với content_workflow),
   graphic-layout-styles, timeline, story-forms, visual-modes,
   slot-contract + identity slots, manifest (font_resources đủ Tektur +
   BigShoulders), LICENSES (owner + third-party AI bed), fonts union
   (lấy Tektur/BigShoulders từ 11.0.0 vì importer chỉ copy base 10.0.0),
   kit (6 sprites), beds generative (giữ cho tới khi rewire xong, rồi xóa),
   badge-circle.png, previews + composite-proof.png + preview.html có
   marker `<!-- SPRINT1-AUDIT -->` + danh sách 90 card ID.
5. Contrast probe từng box zone trên nền thật
   (`pack-drop/12.0.0/contrast-report.json`): 83/92 pass, 9 vùng whisper
   đưa vào hàng đợi scrim ở card-stage.

## 4. Quy trình build 90 starters
- 69 cũ giữ nguyên content/slots (builder v11 là lịch sử, không chạy lại).
- 21 mới (TA-20..24, LC-01..16): `apps/studio_templates/build_starters_v12.py`
  (dùng đúng vocabulary helper v11: locked_rect/circle, ring, val_text,
  badge monogram, l_pitch+token/ball/arrow, corner/quotes/money/history/
  myth/poster/versus/end). Sample tiếng Việt thật, không placeholder.
- Registry `apps/studio_templates/card_registry.py`: 89 entries built
  (90 trừ BP-12 đã xóa 16/10), test đếm đã cập nhật 89/0.
- Rewire beds → plates v12 theo PLATEMAP (card → mode plate đúng aspect),
  assert zero `/resources/beds/` còn sót, rồi xóa thư mục beds (phần thừa).
- Server phục vụ `resources/pack/<short|long>-<mode>.(png|jpg)` + chọn
  package long/short đúng aspect; `render_starters.py` resolve beds rồi
  tới pack (`_art_file`); Studio dropdown đủ 90 option (thêm nhóm
  Tactical+/Narrative long).

## 5. Quy trình Blend rework từng card (short đã xong 50/50)
1. Strip kit HUD cũ khỏi JSON: perforation, ticks, corner brackets, rails
   (tổng 2297 elements) + big VOID/PANEL backings (trừ board tactic của
   TA và data bars). Badge vuông → vòng outline mờ. Giữ: text/slot,
   monogram, winner bars (tính đúng phe thắng từ sample), seal disc,
   pitch motif nét, rule thông tin.
2. Đặt lại geometry theo void đã eyeball từng family (ghi trong
   `blend-language.md`): hook stack giữa; portrait tên/phải + ảnh/trái;
   evidence hero số; quote né beam/chữ rác/burst; myth split; duel 2 cột;
   score 2 nửa winner/loser + bars trên vạch giữa sân; versus tên/badge
   trong 2 khung có sẵn; opening/ending wordmark dưới badge baked.
3. Contrast probe decor-aware (backing nhỏ nhất thắng) + ngưỡng đúng
   (large ≥3.0, thường ≥4.5). Fail thật → scrim veil VOID 0.45 có padding,
   verify bằng composite alpha (không đoán).
4. Overlap gate: text-text >2% fail; decor đè text >5% fail; box khít
   glyph (render căn giữa theo box nên thu box là dời glyph — giữ tâm visual).
5. Render proofs → eyeball mẫu mỗi family → full pytest.
6. Myth là layout thêm sau (F8 art, inpaint watermark, split design);
   takes tương tự (F13). Renderer bỏ qua layout lạ nên an toàn.

## 6. Gates (đỏ 1 gate là dừng)
- `python apps/studio_templates/check_starters.py` → 90 files, 0 errors
  (schema v4, pixel-exact, palette, contrast boss≥4.5/rest≥3.0 theo
  audit_cards (size≥48 & opaque → 4.5, còn lại 3.0), safe area, no-clip,
  slots, bed first-child full-bleed tồn tại).
- `python -m pytest tests/ -q` → 294 passed (đã xóa test_template_santrang
  theo pack v10; các test pin-version trỏ 12.0.0 theo ripple §6).
- Blend audit 521 zones → 0 fail (`blend-audit.json` trong package).
- Eyeball: 1 mẫu mỗi family + card nghi ngờ.

## 7. Release (đã làm khi UI rework xong)
Catalog 12.0.0 → released (short+long), xóa hẳn 10.0.0/longform-10.0.0/
11.0.0/longform-11.0.0 (9.0.0 vốn đã không còn file). Hấp thụ trước khi
xóa: kit, beds (về sau xóa khi rewire xong), ai-night-pitch + license,
69 starter proofs, fonts Tektur/BigShoulders. Ripple §6: studio.html
packVersion 12.0.0 + nhãn Cyber Neon; importer/check_starters/detailing/
render_starters/build_beds/redesign_mr02 trỏ 12.0.0; tests pin-version;
colorway `cyber-pitch` giữ nguyên nên content_workflow/worker/server
không đổi logic (chỉ 2 dòng text ví dụ semver giữ nguyên, không ảnh hưởng).

## 8. Audit log (owner eyeball — cập nhật sau mỗi session)
- **Short PASS (giữ nguyên, không rework):** BP-03, BP-04, BP-05, BP-06,
  BP-08, BP-11, BP-15, BP-17, C-04, C-06, C-08, MR-05, MR-06,
  MR-07, MR-08, MR-09, U-01, U-02, U-03, U-04, U-05, U-06 (22 card firm;
  portrait trio + evidence/money pass 16/10).
- **Short PASS sau rework (owner duyệt 16/10/2026):** MR-02, MR-03, MR-04
  (nhóm score, fix surgical 3 vòng theo bố cục owner + feedback; chi tiết
  các vòng fix ở ghi chú nhóm chờ audit bên dưới).
- **Short PASS sau rework (owner duyệt 16/10/2026):** BP-07, BP-10, BP-14,
  C-07 (nhóm duel: fix dọc + winner dot AMBER core d34/halo d44 theo
  research platform Bold-winner + W/D/L dots + gold accent; chi tiết các
  vòng fix ở ghi chú nhóm chờ audit bên dưới).
- **Short PASS sau rework (owner duyệt 16/10/2026):** BP-20, C-05, C-09,
  MR-12, U-08 (nhóm badge: gỡ seal-disc + AKB, inpaint chữ baked, badge
  watermark góc phải; xem log Channel badge).
- **Short PASS sau rework (owner duyệt 16/10/2026):** BP-13 (giữ lại,
  typo 56 lớn hơn; BP-12 trùng nội dung đã xóa — xem log BP-12).
- **Short PASS blanket (lệnh owner 16/10/2026, chỉ còn MR-11 cần fix):**
  BP-01, BP-02, BP-09, BP-16, BP-18, BP-19, C-01, C-02, C-03, C-10,
  MR-01, MR-10, U-07. *Ghi rõ: các card này owner pass gộp chưa eyeball
  từng card (khác 29 card pass lẻ ở trên); nếu phát hiện lỗi khi dùng thì
  mở lại vòng fix riêng.*
- **Short PASS sau rework (owner duyệt 16/10/2026):** MR-11 (fixture theo
  plate owner; badge NĐ căn giữa grid thật x737-977 đo bằng contour/edge,
  không đoán mắt; tên cùng trục quang học; xem log MR-11 fixture).
  SHORT PACK ĐỦ (49/49 pass, BP-12 đã xóa) — sẵn sàng release + chạy engine
  thử clips.
- **Ghi chú vòng fix tham chiếu:** MR-02/03/04 bố cục owner tên thắng trên /
  badge trái + số phải từng nửa / tên thua dưới; số lùi khỏi viền neon
  phải x985→930; badge canh giữa theo số; tên chuyển BeVietnam do Tektur
  vỡ dấu huyền; MR-03 cue "Hết hiệp 1", MR-04 context thêm scorer, credit
  mẫu thật; script `apps/studio_templates/fix_mr_score_layout.py`, gates
  xanh; vòng 2: Badge sát Số thành 1 cụm center (gap ~50px), 2 hàng đối
  xứng quanh tim sân y960 (plate không có vạch giữa vẽ sẵn, trục dùng là
  tim hình học sân); vòng 3: Badge x296→256, Số hạ căn tâm quang học vào
  tâm Badge).
  Duel BP-07/BP-10/BP-14/C-07 fix dọc 16/10 (script
  `apps/studio_templates/fix_duel_vertical.py`): header thoáng
  (title y250 / teams y390 / rings y490), hàng đều (2 hàng:
  label y700-1150 + số y760-1210; C-07 3 hàng: label y660-1185 + số
  y720-1245), bars chỉ dưới số thắng (hòa gỡ bar), chữ Việt chuyển
  BeVietnam sentence-case, mẫu thật (BP-07 VIETTEL/Nam Định, BP-14
  Hà Nội/Bình Định), credit mẫu thật; gates xanh.
  Duel vòng 2 (owner bỏ nền mờ cụm dưới 16/10): gỡ toàn bộ scrim;
  BP-07/10/14 giữ nguyên vị trí (đủ contrast không scrim); C-07 hàng 3
  dời lên chỗ sạch vệt sáng (số y1300→1245, label y1240→1185, bar y1419 —
  dò pixel nền từng y vì vệt cyan mỏng cắt qua điểm mẫu); needs trong
  blend-audit của 4 card này chỉnh theo floor audit_cards đang enforce;
  gates xanh (lúc đó file còn needs cũ nên báo 2 fails BP-12/13; về sau
  recompute rendered-truth đã bỏ needs cũ — xem log Channel badge).
  MR-11 fixture 16/10 theo plate owner (script
  `apps/studio_templates/fix_mr11_fixture.py`): monogram căn giữa 2 khung
  neon (trái x96-396, phải x656-964, chữ y962, bỏ rings tròn + chữ VS tàng
  hình vì burst art đã là VS); tên đội dưới badge mỗi cột (y1190 — dải
  duy nhất sạch tia sét cả 2 bên); caption trên y185 + ngày/giờ/sân dưới
  y1610 (vùng tối gần rìa); slot when→date khớp registry; gates xanh.
  MR-11 vòng 2: tên 2 đội cùng trục ngang y1255 (dải sạch 1210-1320,
  margin 6.3, thở 100px dưới khung); caption trên 54→64, caption dưới
  36→44; gates xanh, pytest 294 passed.
  MR-11 vòng 3: badge căn giữa khung theo mép neon đo thật (trái cx246,
  phải cx802, mực giữa dọc ~1012); tên to 56→64; cùng trục bằng cùng box
  y (blank-canvas render chứng minh baseline + ink top trùng nhau —
  offset +27 trước đó do đo nhiễm tia sét, đã revert); pytest 294 passed.
  MR-11 vòng 4 (nguyên nhân lệch thật): đỉnh mực bằng nhau nhưng tâm
  khối chữ lệch 9.5px (dấu chấm dưới Ộ sâu hơn Ị) nên mắt đọc thành lệch
  trục — fix bằng căn giữa quang học: ND +10 (y1265), trục chung c1288,
  verify bằng guide-line trên proof; gates xanh, pytest 294 passed.
  C-07 vòng 3 (16/10, theo feedback): gỡ nốt 2 bars còn lại (card không
  còn bar nào); labels nhích lên (gap label-số 70); coloring chuyển sang
  tone-encoding thay bars/scrim — thắng PAPER 1.0, thua PAPER 0.55,
  labels PAPER 0.7 (nổi hơn SLATE cũ); hàng dãn xuống dưới (labels
  660/930/1190 + số 730/1000/1260, hết y1410); hàng 3 né tia sét magenta
  bằng probe thật (vị trí 1270 fail, 1260 là mức thấp nhất còn sạch);
  giới hạn thật: dưới y1410 text fail floors (vùng glow-art) nên không
  dãn thêm được nếu không dùng scrim.
  C-07 vòng 4 (owner: giữ 2 cột cùng màu, nhấn thắng bằng chi tiết):
  số thua về PAPER 1.0 (bỏ dim 0.55/0.8); winner dot AMBER d30 dưới mỗi
  số thắng (hàng hòa không có) thay bars/tone-encoding; gates xanh.
  C-07 vòng 5 (research platform + tăng effect): quy ước Bold-winner của
  BBC/ESPN/Google/Flashscore (encode bằng weight/marker, không wash màu
  thua) + chấm outcome kiểu FotMob W/D/L + gold-vàng broadcast cho thắng
  → dot nâng lên core d34 + halo d44 AMBER 0.25; hòa không marker; gates
  xanh, pytest 294 passed.
  Channel badge + plate cleanup 16/10 (lệnh owner, làm tại chỗ 12.0.0,
  script `apps/studio_templates/fix_channel_badge.py`): gỡ seal-disc+
  text AKB khỏi BP-20/C-05/C-09/MR-12/U-08 (registry/test không pin slot
  seal); inpaint chữ gibberish baked trên short-source/quote (2 file trùng
  bytes; Telea + refine, máy quét sạch, còn grain <44 trên nền ~9 nên vô
  hình ở 100%); bake badge-circle watermark góc phải mọi plate trừ
  opening/ending (short d120@(912,48), long d96@(1704,30); pack-drop là
  gốc, resources sync byte-identical); MR-02/03/04 score-away box h260→
  200 cho khít glyph (plate re-encode làm mẫu +221 rớt 4.5→4.37, đã hồi
  xanh). blend-audit.json recompute toàn bộ theo rendered-truth (thay vì
  geometric lạc quan): 505 checks, 10 fails tồn tại trước ở card chưa tới
  lượt (BP-03/C-04/MR-08 meta scrims, TA-12/14/15 credit, LC-01/04/07/10/
  14/15, TA-24 cover) — không đụng, chờ owner giao từng card (riêng
  BP-12 fail đã xóa cùng card, xem log BP-12). pytest 294 passed.
  BP-12 REMOVED 16/10 (lệnh owner: trùng BP-13, giữ BP-13 typo 56 lớn
  hơn; cùng bed myth + slots + renderer quote_card, quote_card mode map
  về C-05 nên selector an toàn): xóa JSON + registry entry (90→89 cards,
  test counts cập nhật) + SPRINT lists (audit/render/3 tests) + studio.html
  2 options + graphic-templates card_slots/cards/purpose (cả longform) +
  preview.html gallery/audit + proof png + proof-rows + blend-audit entries
  + card-inventory; giữ nguyên builders lịch sử + proof-rows-v10/v11 +
  docs plan cũ. pytest 294 passed.
  RENDERER FIX 16/10 (lệnh owner sau clip test 1: full-bleed + starter
  scenes + media tự gắn + transitions): video ngắn vẽ panel 960x1250 +
  wordmark thường trực + pack boxes mù (vẽ cả dấu *). Fix:
  `apps/studio_templates/starter_scenes.py` MỚI (render starter JSON theo
  beat + thay slot reviewed + ẩn slot thiếu data + ring thắng theo kết
  quả + strip `*`); video_renderer full-bleed (panel=canvas, origin 0,0),
  gỡ wordmark thường trực (giữ ident 0-1.2s + endcard), skip kinetic text
  khi đã có starter scene; importer strip `*` fallback; card_selector
  auto-attach portrait verified (đổi 2 tests) + fix hyphen-match +
  migration ensure_asset_schema full-columns (DB cũ thiếu lifecycle/
  metadata → đường media chết lâm sàng, nay 14 ảnh verified thông).
  Media auto-acquire MỚI (`apps/asset_library/auto_acquire.py`, lệnh owner):
  search tiered + verify (identity terms + license allowlist + resolution)
  + ingest top-1, log đầy đủ; clip 1 tự nhập ảnh Etihad CC BY 4.0 gắn b-roll.
  Exif-transpose cho ảnh b-roll (ảnh dọc bị xoay ngang).
  SỰ CỐ viền hồng 16/10 (lỗi của tôi, đã phục hồi): lệnh sync byte-identical
  pack-drop→resources đã chép đè bản resources CÓ viền bằng bản pack-drop
  KHÔNG viền (tôi ngộ nhận khác bytes do recompress mà không so bằng mắt).
  C-01/C-10/U-07/myth thoát vì skip opening/ending (myth giữ viền nên BP-13
  còn viền). Fix: đo spec viền trên plate nguyên (inset 40, dày 3px, bo 34,
  hồng ~(238,127,190)/(252,121,191)) rồi vẽ lại toàn bộ plates đã stamp
  (idempotent, skip khi đã có viền); proofs render lại, gates + pytest 294
  xanh. Bài học: so bằng mắt trước mọi sync byte, giữ bytes gốc tối đa.
- **Long chưa audit:** toàn bộ 40 card TA/LC (19 cũ + 21 mới). Owner audit
  long xong mới rework.
- **SESSION 16/10 — chốt short pack + clip test 1 (PSG 2-4 City):**
  Short 49/49 pass (BP-12 xóa). Clip 1 render engine end-to-end 63s:
  script tay 6 beats (bypass LLM) + ElevenLabs George + soundpack + auto
  media (Etihad CC BY 4.0 tự tìm/nhập). Audit clip lòi 7 lỗi render đã fix
  hết trong session: full-bleed scenes, starter-scenes thay số liệu reviewed
  (winner-first, dots theo data, co chữ, strip `*`), text vào sau khung
  (layers), b-roll trong void, ending C-10, wordmark thường trực gỡ,
  transitions, media auto-attach + DB migration + hyphen-match + broll pool.
  Tồn: accent magenta `*` (cần two-tone), crest CLB thật (cần kho bản
  quyền), giọng TTS chốt sau khi nghe samples (George/Charlie/River/Liam).
  pytest 295 passed.
- Quy ước: card nào owner đánh pass thì chuyển tên từ nhóm "chờ audit"
  sang "PASS", kèm ngày. Card fail ghi rõ lỗi + cách sửa như mẫu MR-02.
- Nguyên tắc audit theo session (bắt buộc): owner chỉ cần nêu tên card +
  pass/fail (+ lỗi nếu fail). Tôi tự cập nhật mục này, tự dời nhóm, tự
  ghi ngày, không để owner phải theo dõi trạng thái bằng trí nhớ. Mỗi
  session kết thúc bằng audit log đã cập nhật + gates xanh.
- Tiến độ rework Blend (16/10): gỡ pitch-whisper khỏi toàn bộ nền;  portrait trio ảnh-trái/info-phải căn giữa dọc (PASS);
  vòng badge mỗi bên song song với số của đúng nửa sân của nó (winner
  trên, loser dưới — đã sửa sau khi đặt nhầm 2 vòng cùng hàng);
  evidence/money/table ép toàn bộ content vào trong panel (x≥130, dàn đầy
  panel); myth split 2 nửa (layout myth mới từ art F8, inpaint watermark);
  takes từ art F13. Audit contrast chuyển sang đo pixel nền thật
  (bed-aware) thay vì đoán hình học. Fail-rate máy: 0% (blend audit 519
  zones + full pytest 294 passed).

## 9. Sự cố đã gặp (đọc trước khi debug)
- Compose chạy 2 lần → dim chồng dim chôn nền: compose PHẢI đọc từ
  pack-drop gốc (idempotent), không bao giờ đọc từ package.
- Veil phủ toàn cục giết line-art mảnh: cấm veil blanket; chỉ border +
  scrim điểm.
- Boxes mù (pack_import) vẽ lên ảnh chi tiết: số liệu mất im lặng khi key
  sai shape (metrics.0.value.home vs metrics.0.home). Đường video generic
  chỉ dùng khi audit, sản phẩm thật là starter scenes.
- Renderer pack path đọc bg từ package pinned trong khi spec từ draft
  mới nhất: sau release cả hai là một nên hết lỗi; khi còn draft, test
  pin package cũ phải trỏ draft (đã cập nhật 3 test).
- `python -m apps.pack_import build` crash (import function nhầm module):
  gọi `importer.build()` trực tiếp, không sửa (tránh xung đột).
- PIL anchors "mt/lt" crash với text nhiều dòng: render_starters đã vá
  vẽ từng dòng (tương thích ngược single-line).
- Vòng lặp vô hạn khi insert scrim trong lúc iterate JSON: thu thập rồi
  mới insert.
- `rework36.py` là one-shot: chạy lại sẽ xóa scrims/rings đã vá sau đó.
  Mọi chỉnh sau đợt rework phải làm bằng script surgical riêng, rồi chạy
  audit → scrim → render → gates. Không bao giờ chạy lại rework36.
