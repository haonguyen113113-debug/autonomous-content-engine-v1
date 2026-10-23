# Renderer + QA — Scene Graph execution (workstream 4/4, 16/10/2026)

Checkpoint thay the: `docs/audit-checkpoint-2026-10-08.md` khong ton tai —
workstream nay dua tren `docs/build-audit-protocol.md` (gates),
`docs/template-build-manual.md` §6-7 (gates/release) + §8 (audit log),
`runtime/renders/6cebedb10a9f/render-report.json` (mau `quality_checks`).

## 1. Render path moi (mac dinh tu M2)

`apps/video_renderer.py` + section "Scene Graph execution path":

- **Mac dinh BAT tu roadmap M2 (2026-10-23)**: khong can env; moi render
  build 1 graph/segment va validate up front (`_attach_scene_graphs`). Legacy
  la opt-in tuong minh `ACE_SCENE_GRAPH_RENDER=0` (byte-identical, giu de doi
  chieu). Gia tri flag khong hop le -> ValueError, khong doan.
- Preview/visual-benchmark dung CUNG duong graph voi final render (preview
  ap card plan trong bo nho truoc); preview cua draft rong chi ve vo template.
- `_scene_graph_clip()` — validate tung graph (version/mode/canvas/layers/hash
  qua `apps.scene_graph.schema.validate_scene_graph`); unknown mode, hash mismatch,
  thieu/du beat deu raise. Khong bao gio remap.
- Beat timing lay tu `graph.timing` (khong tinh tu segment).
- Scene PNG ve tu `apps.scene_graph.executor.render_scene_graph_layers`
  (starter: bg + text tach lop) hoac `_paint_broll_primitive` (b-roll: void +
  anh contained, caption, credit — layout co dinh cua owner, khong re-wrap).
- **Cam tuyet doi trong SG mode**: chon lai mode/starter, chuyen mode theo
  timeline event, media forcing/drop, kinetic text tu do, ball/trail tu
  fallback spec va lower-third/caption khong co template-slot binding. Fixed
  opening/ending scenes duoc goi tu template pack cho ca short va long form.
- **Motion dong bang thuc thi**: hook/number punch zoom duoc gioi han toi
  1.035x de giu chu trong safe area; camera drift khac toi da 1.025x;
  `slide_in_right_0_3s`/`chalk_line_wipe` -> slide-in 0.3s;
  `fade_0_3s` -> fade in/out; `clean_cut` -> hard cut (tat slide).
- Overlay contract chi nhan `type`, `text`, `start_seconds`, `end_seconds`,
  va `role` tuy chon. Role preset hop le: `lower_third/name_tag` va
  `caption/hook`; key style/layout bat ky khac bi validator tu choi.
- Media rights (goi check cua workstream 1):
  `_scene_graph_media()` gom refs tu `roles.hero_image` /
  `roles.player_focus.portrait` (uu tien truoc) + `params.media_asset_id`;
  `approval_status=pending` -> raise; verified/active/file (read-only, khong
  migrate DB) -> raise neu thieu; co upload intent (`_render_purpose()` tu
  distribution destinations, khong doan) thi `is_usable_for()` deny -> raise;
  credit burn-in lay `scope.credit.text` khi co.
- Single scene/frame verify: `render_scene_png(graph, path, root=..., purpose=...)`.

## 2. QA checklist moi (`apps/measurement/render_qa.py`)

Verdict `PASS|FAIL|NEEDS_REVIEW` kem evidence, do tren scene render THAT:

| Check | PASS | FAIL | NEEDS_REVIEW |
|---|---|---|---|
| Scene graph contract | validate ok | graph invalid (khong render) | — |
| Text clipping (no-clip) | all box trong canvas (+1px) | box tran canvas, kem id | primitive (khong layer) |
| Safe area | 7% / 9% / 13% (credit 97%) | vi pham, kem slot | primitive |
| Text overlap | khong cap >2% | cap >2%, kem cap | primitive |
| Visual density | text area <=40% | >40% | primitive |
| Contrast (sampled) | sample pixel nen that, floors 4.5/3.0 | duoi floor | thieu bg layer |
| Text actually paints | box khac nen | box pixel-identical nen | so sanh loi |
| Overlay rendered | khong overlay khai bao hoac danh sach rong | graph co free-standing text overlay chua bind vao frozen template slot | — |
| Narration fit | ~words/2.6wps vua window | vuot >1.15x window | thieu narration / sat nut |
| Media rights | approved + verified/active/file + scope allowed (+credit note) / monogram | pending / unverified / missing / scope denied (kem reasons) | khong registry / khong intent / co che chua biet |
| Tactical vectors | — | — | primitive tactical (vectors tu fallback, verify bang mat) |
| Timing continuity (clip) | lien tuc tu 0, khong gap/overlap, khop target | gap/overlap/lech target | khong timing |
| Motion execution mapping (clip) | moi enter/effect/transition map duoc sang primitive da chay | — | motion hieu nao khong map duoc |
| Video structure (clip) | mo bang hook/opening, dong bang ending (khi co roles) | sai thu tu | thieu role metadata |

Tong hop: 1 FAIL -> FAIL; co NEEDS_REVIEW -> NEEDS_REVIEW; con lai PASS.
Cam PASS chay: khong bao gio PASS khi chi biet asset co mat.

Clip render (`_render` SG mode) extend `quality_checks` hinh `render-report.json`
+ them `scene_graph_qa: {mode, verdict, scenes, clip_checks}`.

## 3. Ket qua pytest

- `tests/test_renderer_scenegraph.py` (moi): verbatim execution, raise thay remap,
  pending/unverified/scope-denied, QA matrix, motion mapping, bo them test overlay:
  renderer doc overlay tu `sg_graphs[index]["overlays"]` (mock verify), QA tra
  FAIL/NEEDS_REVIEW khi overlay thieu/sai timing, khong bao giu PASS chi vi co trong
  input; flag tat -> legacy khong dot overlay.
- Full suite: **366 passed** (365 + end-to-end), gom `test_scene_graph*.py`,
  `test_rights_scope.py`, `test_crest_store.py`, `test_renderer_motion.py`.
- Verify don: 1 frame b-roll cleared (1080x1920) + QA clip ngan deu chay that,
  khong render dai, khong tai asset ngoai, khong sua released pack/user data.

## 4. Gioi han con lai

- QA still (qa_scene, anh PNG) doc pixels + hinh trang dong bang (frozen
  geometry) tren khung hinh da render; QA MP4 (qa_clip) doc timing continuity
  tu graph.timing, motion execution mapping va cau truc clip. Hai luc khong
  cung doi tuong: still khong bao hieu da QA MP4.
- Motion thuc te (punch/slide/fade) can owner eyeball tren MP4; stills chi
  verify mapping. Khong duoc khong da QA MP4 neu chi doc still.
- Readiness semantics: FAIL = chan / not ready; NEEDS_REVIEW = not ready
  (khong duoc bao ready); PASS = ready. Truong `ready` trong report
  (qa_scene/qa_clip + render-report.json `scene_graph_qa`) la
  `(verdict == PASS)`. Co NEEDS_REVIEW -> `ready` la False, khong bao
  PASS vi chi biet asset/overlay co mat trong input.
- Fail-closed: duong graph (mac dinh) + thieu `scene_graphs`
  (missing/empty) -> raise ValueError, khong fallback legacy. Legacy chi
  khi opt-out tuong minh `ACE_SCENE_GRAPH_RENDER=0`, byte-identical.
- Overlay metadata van co timebase CLIP-RELATIVE va duoc `graph_hash` bao ve,
  nhung renderer khong paint free-standing overlay. Khong co frozen slot
  binding -> `Overlay rendered` FAIL, bat ke text/timing co hop le hay khong.
- `number_pop` thuc thi = punch zoom (giu nang luong pop, khong stagger tung so);
  `freeze_and_trace`/`pitch_grid` ngoai tactical chua co primitive -> NEEDS_REVIEW.
- Tactical primitive vectors tu fallback storyboard (executor cua ws3) -> QA luon
  NEEDS_REVIEW "Tactical vectors".
- `use_count`/`clip_limit` do caller dem (theo ws1); renderer truyen 0.
- Stagger 0.18s / count_up_steps khong co line-timing dong bang -> khong chay
  (re-wrap text bi cam).
- Overlay lower-third/caption ngoai graph -> SG mode khong render.
- Renderer khong tao text tu `timeline_events` hay `graph.overlays`. Text chi
  duoc render khi nam trong card art hoac supported frozen slot; slot chua duoc
  ket noi thi QA FAIL, khong can eyeball de cho qua.

## 6. Addendum — template-bound text and brand scenes (2026-10-18)

- Renderer-level title/ident, free-standing caption/lower-third, hook/hero
  kinetic copy, and end-card takeaway/tagline/version are disabled. Text must
  be part of a selected card design or a supported, frozen card slot.
- Timeline captions/lower-thirds and Scene Graph `overlays` are not painted
  until a deterministic template-slot binding exists. A graph with declared
  overlays fails `Overlay rendered` QA; presence in graph data is not proof of
  output.
- `_render` now renders and calls the fixed opening and ending scenes from the
  matching pack: short C-01/C-10; long pack opening artwork/LC-14. The unused
  credit/source placeholder is hidden. No topic or narration is injected into
  these brand-only cards.
- Body-card camera zoom is capped at 1.025x (1.035x for declared punch motion)
  to keep baked typography inside the card's safe area. Starter text and its
  background use the same transform.
- This addendum supersedes earlier lines above that described graph overlays
  as rendered, generic opener text, Ken Burns at 1.07x/1.12x, or an ending card
  only on short-form legacy renders.

## 5. Diem cho tich hop

- **Ws3 (scene_graph/builder):** freeze overlays + beat roles (opening/ending) +
  media_caption + tactical specs that vao graph (hien primitive van thieu);
  `params.media_asset_id` legacy giu song song voi roles refs (renderer uu tien roles).
- **Renderer (video_renderer):** duong path SG doc overlay CHI tu
  `sg_graphs[index]["overlays"]`, chuan bi lenh ve drawtext/filter boi role preset
  co dinh (type + role), KHONG doc lai `timeline_events`/segment va KHONG tu suy
  toa/hinh overlay. `ACE_SCENE_GRAPH_RENDER=0` -> legacy byte-identical,
  khong xay dung overlay.
- **Ws1 (rights):** planner goi `is_usable_for()` voi intent that truoc khi freeze
  (renderer chi assert lai); migration-4 boc `ensure_rights_scope_schema`
  (renderer/QA khong tu migrate); crest render path (`README.md` §5) chua co ->
  monogram van dung.
- **Ws planner (card_selector):** truyen `asset_info` + `transition_in`/`beat_intent`
  khi build clip graphs; bao dam 1 graph/segment (renderer raise neu lech).
- **Owner:** eyeball motion/video, narration fit sat nut, giong TTS, mo/dong clip;
  doc `scene_graph_qa.ready` (false khi verdict khong PASS) de chuan biet
  clip co the ship hay chua.
