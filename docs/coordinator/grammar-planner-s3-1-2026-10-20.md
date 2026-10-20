# S3.1 grammar planner — contract-first selection

Date: 2026-10-20. Scope: planner only; no render, no `runtime/` change, no
contract/schema/template change.

## What changed

`apps/card_selector.py` now treats the C7 card contract as the production
allowlist instead of letting a script-declared `visual_mode` own the layout:

- A beat role is derived from `beat_intent.image_goal`, reviewed
  `graphic_data`, narration signals, and the declared mode only as a hint.
  The LLM still supplies semantics, not coordinates, fonts, colors, or motion.
- Every contract candidate must have complete required data and a card whose
  `execution.status` is exactly `contract`. `partial` cards remain
  non-production even where one mode is executable.
- `duel_columns` uses `BP-14` (not partial `C-07`); `stat_leader` uses `BP-16`
  (not partial `BP-15`/`MR-09`/`MR-07`); money stats use contract `BP-08`.
  Portraits use `C-04`/`MR-08`/`BP-03`.
- A legacy declared mode (for example `tactical_explainer`) is replaced when
  reviewed data and intent support a contract grammar. The decision records
  the override warning.
- When multiple contract candidates fit, a hard guard avoids the immediately
  previous mode and then avoids a third appearance when a genuinely fresh
  contract alternative exists. If only one valid choice exists, it is kept and
  the decision says the repeat is by constraint. Legacy modes are never
  substituted merely to manufacture variety.
- Media binds only to a declared C7 `media_slots` region. This means the
  player-portrait cards only; the planner drops bindings from stat, score,
  comparison, quote, welcome and other cards with no slot. A portrait requires
  the named player, `verified`+`active`, and `is_usable_for(asset, purpose)`
  for the upload intent. Missing media becomes an explicit
  `fallback_no_asset`, never a false media pass.
- The old bound-asset -> `media_b_roll` conversion and `apply_card_plan`
  generic b-roll pool pick are removed from the planner path. `media_b_roll`
  remains a legacy renderer primitive; C7 12.0.0 has no general b-roll slot.

Each decision now records `card_execution`, `production_ready`,
`media_status`, and `grammar` (role, source, declared mode, considered modes,
candidate scores, repetition reason). The plan records
`contract_starters`, `partial_starters`, `legacy_starters`,
`production_starters`, `contract_beats`, `partial_beats`, `legacy_beats`,
`non_ready_beats`, `non_ready_roles`, `mode_runs`, `max_mode_repeat`,
`grammar_variety_ok`, and `over_repeated_modes`. `production_ready` requires contract source + contract
card + no media fallback + complete data. Variety is measured by consecutive
runs: a run of 3+ identical modes sets `grammar_variety_ok=false`, while two
contract grammars alternating across six beats remains varied even if one mode
appears three times in total.

## Concrete blocker found

S3.1 cannot be fully cleared for the R3 tactical-only script with the current
pack. `tactical_explainer` has no C7 contract card, and the beats contain no
score/comparison/stat/player data that could legitimately select a contract
grammar. The planner therefore keeps the five tactical beats on the explicit
pitch-plate fallback, sets `grammar_variety_ok=false`, and warns:

- no contract-ready card grammar for role `tactical`;
- five beats are not production-ready;
- `tactical_explainer` repeats five times.

No card or mode was invented to hide the gap. A real fix needs an authored,
contract-versioned tactical/context/source grammar card (or an explicit owner
decision to accept the legacy surface), followed by rendered inspection. This
note does not add template geometry or change `card-contract.json`.

Context/source/timeline/fixture/quote/discipline/takeaway roles also remain
legacy/non-ready in C7; the 63 `legacy_non_ready` + 7 `partial` surface is
unchanged. R4 stays `BLOCKED`; no final-gate render or visual PASS was made.

## Verification

- Focused suite:
  `python -m pytest tests/test_card_selector.py tests/test_card_contract.py tests/test_card_media_contract.py tests/test_scene_graph_pipeline.py tests/test_scene_graph.py tests/test_renderer_scenegraph.py tests/test_scene_graph_v1_roles.py tests/test_rights_gate.py tests/test_scene_graph_executor_overlays.py -q`
  -> **219 passed in 45.04s**.
- Full suite: `python -m pytest tests -q` -> **567 passed in 115.64s**.
- `python tools/build_card_contract.py --check` -> **OK, 89 cards, exact
  match**; C7 `contract_hash` remains
  `cad623bd30050dd300f27a8eb9e39408e99f2d181703917db19282f08e4e499b`.
- `python apps/studio_templates/check_starters.py` -> **89 files, 0 errors**.
- `python tools/ace_state.py --check` -> **STALE: tree changed** (expected
  after this planner work; STATE/PROGRESS were not refreshed because they are
  coordinator-owned).
- Read-only replay of the existing R3 run
  `runtime/runs/a1b2c3d4e5f6.json` through `select_cards` (no write): 6 beats,
  `hook_card: 1` + `tactical_explainer: 5`, `production_ready=false`,
  `grammar_variety_ok=false`, `non_ready_roles=["tactical"]`.
- No render, FFmpeg, `runtime/` write, commit, or push occurred.

## Next step

Do not claim S3.1 or R4 cleared. Either author a contract-ready tactical/
context/source grammar in a new pinned pack version with rendered inspection,
or record an owner decision to accept those beats as legacy. Until then, keep
R4 `BLOCKED` and do not start a final-gate render.
