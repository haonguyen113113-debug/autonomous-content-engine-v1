# Scene Graph contract (workstream 3/4 — Visual Planner + Scene Graph)

Trạng thái: implemented trên branch `feature/template-nova`.
Đọc cùng: `docs/build-audit-protocol.md`, `docs/template-build-manual.md`
(§5 blend, §6 gates, §8 audit log), `docs/workflow-probe-2026-10-10.md`.

## 1. Nguyên tắc

- LLM chỉ sở hữu **ý nghĩa beat**: `image_goal`, `focus_subject`,
  `evidence_type`, `emphasis_level` (xem §3). LLM **không** chọn layout,
  starter, camera, motion, transition, màu, font.
- Planner quyết composition từ **intent + asset phù hợp/được duyệt +
  template khóa**: `apps.card_selector` chọn mode/starter/media binding;
  `apps.scene_graph.builder` freeze thành graph tuyệt đối, xác định
  (cùng input + cùng version → cùng JSON → cùng `graph_hash`).
- Renderer chỉ execute graph đã `validate()` verbatim, không remap.
- Không tải asset ngoài, không sửa released pack 12.0.0 (read-only),
  không đụng `runtime/`, không commit/push.

## 2. Schema v1 (mở rộng, không schema cạnh tranh)

`version` giữ `"1.0.0"`. Các block mới là **additive/optional khi đọc**,
builder luôn emit. Graph legacy (không có chúng) vẫn `validate()` pass;
graph có chúng thì check strict + check hash khi có `graph_hash`.

Beat = các field hiện có (`version/kind/mode/starter_id/canvas/timing/
segment_id/index/design/segments/slots/params/fallback`) **cộng**:

```json
{
  "roles": {
    "hero_image": null,
    "data_chart": null,
    "player_focus": null,
    "headline": "Đêm ác mộng Etihad",
    "source": "ESPN • 14/10/2026"
  },
  "timing": {"start": 0.0, "end": 9.0},
  "motion": {"enter": "hook_punch_in", "stagger_seconds": 0.18,
             "effect": "none", "count_up_steps": 0},
  "transition": {"in": "clean_cut", "out": "clean_cut"},
  "provenance": {"builder": "apps.scene_graph.builder",
                 "starter_id": "C-03", "template_version": "12.0.0",
                 "graph_hash": "1f3f…aed7",
                 "beat_intent": {"image_goal": "establish_moment",
                                 "focus_subject": "Etihad, đêm thua 2-4",
                                 "evidence_type": "match_event",
                                 "emphasis_level": "hero"}}
}
```

- `roles.headline/source`: chuỗi reviewed (sao `*accent*` đã strip ở
  headline; slots giữ nguyên marker cho executor two-tone). `""` khi
  không có text reviewed — trung thực, không bịa (QA flag riêng).
- `roles.hero_image`: set khi beat có `media_asset_id` bound và mode
  **không** thuộc portrait (ảnh là bối cảnh/minh họa). Portrait modes
  (`player_card/poster*/potm/welcome/score/quote`) thì ảnh nằm ở
  `player_focus.portrait`, không nhân đôi.
- `roles.data_chart`: `{chart_kind, values}` — pass-through số reviewed,
  không tính lại. Kinds: `duel_bars`, `hero_number`, `leader_list`,
  `comparison`, `timeline`, `scoreline`, `player_stats`.
- `roles.player_focus`: `{player_name, portrait}`; chưa có ảnh duyệt thì
  `portrait.kind = "monogram_fallback"` (typographic, approved).
- Asset ref shape: `{asset_id, kind, rights_scope, approval_status,
  license_type, purpose_code}`; `kind ∈ {library_image,
  monogram_fallback, none}`, `approval_status ∈ {approved, pending}`.
- `motion.enter ∈ {hook_punch_in, slide_in_right_0_3s, fade_0_3s}`
  (ngôn ngữ timeline pack: punch hook beat-0, scene_enter template,
  fade cho b-roll); `effect ∈ {none, freeze_and_trace, number_pop,
  pitch_grid}` (đúng `timeline.effects`); data beats → `number_pop`
  + `count_up_steps 6`; tactical → `pitch_grid`.
- `transition.in ∈ {clean_cut, chalk_line_wipe}`, `out = clean_cut`
  (luôn). Chalk chỉ cho `{tactical_explainer, chart_timeline}`, tối đa
  **2/clip** (candidates đầu thắng), beat-0 luôn `clean_cut`.
- `provenance.starter_id` phải khớp graph; `template_version`
  non-empty (pin 12.0.0 = released pack); `graph_hash` = sha256 hex của
  canonical JSON (sorted keys, compact separators) trên **mọi field trừ
  chính nó**. Đổi input/version → đổi hash; sửa sau freeze → validate
  báo `graph_hash mismatch` (rebuild, không patch).

## 3. Beat intent (LLM) — `apps/scene_graph/intent.py`

| field | vocab |
|---|---|
| `image_goal` | `establish_moment, show_evidence, compare_numbers, introduce_player, set_context, land_takeaway` |
| `focus_subject` | free text ≤120 ký tự (ai/cái gì) |
| `evidence_type` | `sourced_stat, sourced_quote, match_event, table_standing, tactical_observation, none` |
| `emphasis_level` | `quiet, standard, hero` |

- Prompt beat (`apps/content_workflow.py::_ollama_beat`) yêu cầu
  `beat_intent` + câu cấm: *"Do NOT choose layout, starter, camera,
  motion, transition, colors, or fonts…"*.
- `_clean_segment` normalize intent hỏng → default xác định theo
  mode + shape graphic_data (không bao giờ fail beat vì intent);
  index suy từ `beat-N`. `_outline_beat` mang intent mặc định
  (beat-0 `establish_moment/hero`, beat cuối `land_takeaway`).
- `build_clip_graphs` mang `beat_intent` từ draft segments
  (không qua card_selector — ownership, xem §6).

## 4. API cho Renderer/QA

```python
from apps.scene_graph import build_scene_graph, validate, graph_hash
from apps.scene_graph.builder import (
    build_from_decision, build_clip_graphs, validate as validate_alias)
from apps.scene_graph.schema import validate_scene_graph
```

- `build_scene_graph(*, segment_id, visual_mode, starter_id,
  graphic_data, evidence, content_type="short", start_seconds,
  end_seconds, index=0, media_asset_id=None, beat_intent=None,
  template_version=None, asset_info=None, transition_in=None)`.
  `template_version=None` → pin `"12.0.0"` (test pin với manifest).
  `asset_info` = record `{rights_state, lifecycle_state,
  license_type, purpose_code, rights_scope?}`; verified+active →
  `approved`, còn lại placeholder `pending-rights-review/pending`.
- `build_from_decision(decision, evidence=None, …)` — bọc 1 card_plan
  decision (đọc `beat_intent` từ decision khi caller không truyền).
- `build_clip_graphs(decisions, segments_by_id=None,
  content_type="short", template_version=None, asset_map=None)` —
  timing từ production timeline, intent từ segments, rights từ
  asset_map, budget chalk 2/clip. Cùng input/version → cùng graphs.
- `validate(graph)` — gate duy nhất renderer được gọi trước execute;
  raise `ValueError` LOUD (unknown mode, canvas, timing, roles/motion/
  transition vocab, provenance mismatch, hash mismatch). Không remap.

## 5. Ví dụ: beat-1 clip `6cebedb10a9f` (PSG 2–4 City)

Input: `hook_card` + starter `C-03`, `hook_text "Đêm ác mộng *Etihad*"`,
evidence `ESPN/BBC 14/10/2026`, timing 0–9s, no media, pack 12.0.0.
Output đầy đủ (design/segments rút gọn): xem JSON ở cuối file này —
`kind starter`, headline đã strip sao, source `ESPN • 14/10/2026`,
motion `hook_punch_in`, transition `clean_cut/clean_cut`,
`graph_hash 1f3f578b…aed7`, `validate()` pass, rebuild cho cùng hash.
Cả 6 beats của clip build + validate + deterministic
(`tests/test_scene_graph_v1_roles.py::test_clip6_all_beats…`):
beat-2 headline winner-first `"Manchester City 2–4 Paris
Saint-Germain"`, beat-3 `data_chart.duel_bars`, beat-5
`player_focus Haaland + monogram_fallback`, beat-6 `media_b_roll`
primitive + `hero_image.asset-3960da53eba5/pending`.

```json
{
 "canvas": {"height": 1920, "width": 1080},
 "design": "<starter C-03 absolute design: pages[0].children (pixels), truncated>",
 "fallback": null,
 "index": 0,
 "kind": "starter",
 "mode": "hook_card",
 "motion": {"count_up_steps": 0, "effect": "none",
            "enter": "hook_punch_in", "stagger_seconds": 0.18},
 "params": null,
 "provenance": {
  "beat_intent": {"emphasis_level": "hero", "evidence_type": "match_event",
                  "focus_subject": "Etihad, đêm thua 2-4",
                  "image_goal": "establish_moment"},
  "builder": "apps.scene_graph.builder",
  "crest": "monogram-fallback",
  "graph_hash": "1f3f578b95d95f7b2bc1c8bb7632a5e076e04a8240886c6369aed7e293a60d59",
  "starter_file": "C-03.short.json",
  "starter_id": "C-03",
  "template_version": "12.0.0"
 },
 "roles": {"data_chart": null, "headline": "Đêm ác mộng Etihad",
           "hero_image": null, "player_focus": null,
           "source": "ESPN • 14/10/2026"},
 "segment_id": "beat-1",
 "segments": "<pre-split *accent* segments per text element, truncated>",
 "slots": {"claim": "Đêm ác mộng *Etihad*",
           "credit": "ESPN • 14/10/2026"},
 "starter_id": "C-03",
 "timing": {"end": 9.0, "start": 0.0},
 "transition": {"in": "clean_cut", "out": "clean_cut"},
 "version": "1.0.0"
}
```

## 6. Kết quả pytest (16/10/2026)

- `tests/test_scene_graph.py` + `tests/test_scene_graph_v1_roles.py`
  (mới, 12 tests): **17 passed**.
- Suite liên quan planner (`script_decomposition, card_selector,
  llm_provider, worker_runner, card_registry`): 60–61 passed (mirror
  test order-dependent có sẵn — pass lẻ + pass đảo thứ tự; xem §7).
- Không render dài: tests chỉ render 1 frame in-memory (beat-1
  1080×1920, có sẵn từ trước).

## 7. Giới hạn còn lại (trung thực)

1. `rights_scope`/`approval_status` canonical thuộc workstream
   Rights/Discovery (chưa land): graph mang xuyên suốt + placeholder
   `pending-rights-review/pending` rõ ràng; renderer/QA **phải gate**
   `approval_status == "approved"` trước khi vẽ ảnh library
   (executor hiện raise khi thiếu file verified — đúng hướng).
2. `card_selector` chưa đọc `beat_intent` (ngoài ownership ws3):
   intent hiện điều khiển roles/motion emphasis ở builder-freeze;
   selector vẫn quyết mode/starter/media từ fit-score + asset
   verified. Tích hợp advisory sau do owner/workstream planner quyết.
3. Overlays timeline (`lower_third/caption`) chưa vào graph contract
   (renderer ws4 đã note waiting point ws3) — motion/transition của
   chúng chưa freeze.
4. `test_supported_modes_mirror_workflow` fail khi chạy batch thứ tự
   cũ (do `VISUAL_MODES.update()` toàn cục có sẵn trong
   `create_script_draft`, không phải do change này): pass khi chạy lẻ
   và khi đảo thứ tự. Không sửa (ngoài ownership, tránh rủi ro).
5. Shared-tree nhiễu chéo (16/10): `tests/test_discovery_referral.py`
   + `tests/test_renderer_scenegraph.py` (8 tests) fail vì code sibling
   (discovery 631 dòng + video_renderer scene-graph path incl.
   `render_scene_png`) nằm trong stash entry giữ lại, chưa vào tree —
   không liên quan API ws3 (7/15 tests renderer dùng `build_scene_graph`
   của ws3 vẫn pass phần builder).

## 8. Điểm chờ tích hợp Renderer/QA

- Renderer: gọi `build_clip_graphs(card_plan decisions + draft
  segments) → validate() từng graph → execute verbatim`; Beer-0
  `clean_cut` + hash-verify trước render là 2 invariant cứng.
  `transition_in`/`asset_map`/`template_version` là input của clip-build.
- QA: check `graph_hash` khớp recompute (chống patch lén), roles
  đầy (`headline/source` rỗng → flag thiếu reviewed-text, không tự
  bịa), `approval_status pending` → block vẽ ảnh, blend gates
  (`build-audit-protocol` + manual §5–6) vẫn chạy trên pixels render.
- Stash cần hoàn tác: entry `stash@{0}` (WIP feature/template-nova)
  đang giữ code tracked của session khác (`video_renderer.py` scene-graph
  path ~357 dòng, `discovery.py`, `starter_scenes.py`,
  `render_starters.py`, `importer.py`, `auto_acquire.py`,
  `voice-baseline.md`, discovery tests). Ws3 chỉ lấy lại đúng
  `apps/content_workflow.py` từ stash (`git checkout stash@{0} --
  apps/content_workflow.py`, đã làm); **không drop stash** khi chưa có
  lệnh orchestrator — các workstream tự nhận lại phần mình.
