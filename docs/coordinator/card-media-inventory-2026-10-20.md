# Card and media inventory — 2026-10-20

Status: read-only inventory, updated for the unified card contract v2.0. No
pack, starter JSON, runtime data or render was modified to produce it. This
inventory was requested by
`docs/coordinator/card-media-contract-audit-2026-10-19.md`; the media-slot rule
is frozen as `docs/coordinator/contracts/c6-card-media.md` and is now carried
unchanged into the executable `docs/coordinator/contracts/c7-card-contract.md`.

## Purpose

Map every built card to its declared text/data slots, fixed pack artwork,
variable-media support and renderer path, so later media work extends explicit
authored regions instead of adding renderer-side composition.

## Method and sources

Read-only inspection of:

- `apps/studio_templates/card_registry.py` (card IDs, aspect, family, declared
  data slots, renderer route). The registry remains the card-level index.
- `apps/studio_templates/<card>.<aspect>.json` (authored starter designs:
  pack bed, children, z-order, text boxes).
- `template_foundation/templates/allen-knows-ball/12.0.0/card-contract.json`
  (the single executable contract for all 89 cards; C7 v2.0). The historical
  `card-media-contract.json` (C6 v1.0) is retained as evidence only and is not
  read by the runtime.
- `apps/studio_templates/card_media.py`,
  `apps/scene_graph/builder.py`, `apps/scene_graph/schema.py`,
  `apps/measurement/render_qa.py`, `apps/studio_templates/render_starters.py`
  (binding, validation, QA and render behavior).

Checks run: `python apps/studio_templates/check_starters.py` →
**89 files, 0 errors**; `python tools/build_card_contract.py --check` →
**89 cards, exact match**. The inventory table below was generated from the
registry + starter JSONs + contract, then reviewed.

## Summary

- Registry cards: **89** built (49 short, 40 long). Families: core 10, match
  12, narrative 16, story 19, tactical 24, utility 8.
- Authored starter files on disk: **90**. The extra file is
  `duel_columns.short.json`, an unregistered builder template excluded by
  `check_starters.py`; the registry and its tests count 89.
- Distinct pack bed files used by the 89 cards: **25** (many cards share one
  authored plate, e.g. utility cards on `short-hook_card.jpg`).
- Contract records: **89 / 89** cards exactly once. Each record freezes
  `card_id`, aspect/canvas, starter file + SHA-256, renderer route, execution
  status, **505 data slots** (143 distinct slot keys), editor notes and media
  slots. Cards without variable media explicitly declare `media_slots: []`.
- Cards with a variable-media slot: **3** — `C-04`, `MR-08`, `BP-03`, each a
  `player_portrait` slot on five player-card modes (C6 geometry unchanged).
- `media_slot` layers in authored starter JSONs: **0**. Slots exist only in
  the contract and are inserted by the planner at the frozen z-order anchor.
- Cards whose purpose mentions a portrait but have no contract slot: `LC-11`
  (long-form player focus; deferred with long form).
- Renderer routes: 20 `frame`, 19 `starter`, 50 `generic/<mode>`.
- Execution coverage: **19 `contract`**, **7 `partial`**, **63
  `legacy_non_ready`**. Partial cards still have at least one executable mode;
  legacy modes are named in C7 and are never QA-`PASS` as contract-ready.

## Variable media support (contract v2.0, C6 slot unchanged)

| Card | Modes | Slot | Box px @1080×1920 | Fit / focal / mask | Fallback |
|---|---|---|---|---|---|
| C-04 | `player_card`, `player_poster`, `player_poster_side`, `player_poster_top`, `potm_card` | `player_portrait` | `0, 282, 424×1240` | cover / `0.5,0.30` / rounded `[0,52,52,0]` | keep pack artwork |
| MR-08 | same | `player_portrait` | same | same | keep pack artwork |
| BP-03 | same | `player_portrait` | same | same | keep pack artwork |

Each media slot declares its rights/use constraints (`requires_verified`,
`requires_active`, `requires_persisted_human_grant`, `purpose_specific`,
`human_review_required`, all true). The planner still enforces them against the
actual asset record and the run's upload purpose; the declaration is not a
grant.

Everything else in the table below is fixed pack artwork plus authored text
boxes. "No variable media" means contract v2.0 declares `media_slots: []` for
that card; it does not forbid a future contract version from adding a designed
region.

The legacy `media_b_roll` primitive is **not** a card media slot. The selector
may force that mode outside portrait modes, and the renderer paints a
contained image with caption/credit/disclaimer in its own void. It remains a
separately planned scene, not an insertion into a starter card region, and is
marked legacy/non-ready.

## Text/data support in the same record

The 89 records make text coverage explicit rather than implied by the starter
file:

- every slotted authored text layer has one `data_slot` with its sources,
  active/required modes, box, font, shrink floor, length/word/line limits and
  fallback (`authored_text` or `hide`);
- `C-07` keeps the authored title `ĐỐI ĐẦU` and maps `label-0` to
  `metrics[0].label`, fixing the previous overwrite/hidden-label drift;
- stat-row cards `MR-07`, `MR-09`, `BP-15` execute only on `stat_leader`;
  their registry `duel_columns` mode is legacy;
- `BP-06` is executable only on `stat_leader`; its selected `welcome_card`
  mode is legacy;
- `MR-04` executes `score_card` only; `goal_card` is legacy because the
  layout grammar requires `hook_text` that the authored score card cannot
  supply;
- hidden instructional text (`showInExport: false`) is recorded as
  `editor_notes`, excluded from data slots and must stay hidden.

## Findings and drift to watch

1. **Registry count drift.** The `card_registry.py` docstring says "90 starter
   cards", but the list and `tests/test_card_registry.py` assert 89. The 90th
   file on disk is the unregistered `duel_columns.short.json`. Correct the
   docstring or register/remove the file in a separate cleanup; behavior is
   unaffected.
2. **Long-form portrait gap.** `LC-11` declares `player_name` + `stats` and
   routes to `generic/player_poster_side`, but has no media contract; do not
   assume the short-form portrait slot applies to it.
3. **Selector proposes; the contract decides execution.** The selector may
   still suggest a legacy card for review (e.g. `BP-04` for `chart_timeline`),
   but the decision now carries `card_execution` and the plan lists
   `legacy_starters`. The builder freezes a primitive non-ready graph rather
   than silently executing an unsupported authored design. Do not "fix" a
   mismatch by loosening the builder.
4. **Pack-bed pairings vary by authoring, not contract.** E.g. `MR-07`,
   `MR-09` and `BP-15` route to `duel_columns` but sit on
   `short-stat_leader.jpg`. The contract says nothing about bed choice; check
   visually before reusing those cards in a run.
5. **Images only in v2.0.** The schema accepts `video`, but no card declares a
   video slot. Do not infer footage support from the schema value.
6. **Legacy surface remains large.** 63 cards have no contract-executable
   selected mode (frame, generic/long, source/fixture/quote/timeline/career),
   and 7 partial cards have named legacy modes. They render through primitive
   routes, carry `legacy_non_ready`/`fallback` provenance, and QA returns
   `NEEDS_REVIEW` — never a contract-ready `PASS`. Long form is deferred.
7. **Graphs must be rebuilt after a contract change.** The planner freezes the
   contract SHA-256 and the starter SHA-256; regenerating `card-contract.json`
   invalidates frozen graphs by design.

## Appendix — per-card inventory

Columns: registry data slots (text/data only), renderer route from the
registry, authored pack bed, and contract v2.0 variable media. `—` means none.
The renderer route is the registry's declared route, not the execution status:
see C7 for which modes are contract-executable and which are legacy.

| Card | Aspect | Family | Declared data slots | Renderer path | Fixed pack bed | Variable media (v2.0) |
|---|---|---|---|---|---|---|
| C-03 | short | core | hook_text | generic/hook_card | short-hook_card.jpg | — |
| C-04 | short | core | player_name, stats | generic/player_poster_side | short-player_poster_side.jpg | player_portrait |
| C-06 | short | core | stats, source, date | generic/stat_leader | short-stat_leader.jpg | — |
| C-07 | short | core | metrics, source, date | generic/duel_columns | short-duel_columns.jpg | — |
| C-09 | short | core | source, date | generic/source_card | short-source_card.jpg | — |
| C-10 | short | core | — | frame | short-ending.jpg | — |
| U-02 | short | utility | player_name | frame | short-hook_card.jpg | — |
| U-03 | short | utility | competition | frame | short-hook_card.jpg | — |
| U-05 | short | utility | label | frame | short-hook_card.jpg | — |
| MR-01 | short | match | hook_text | generic/hook_card | short-hook_card.jpg | — |
| MR-02 | short | match | home, away, score | generic/score_card | short-score_card.jpg | — |
| MR-04 | short | match | home, away, score | generic/score_card | short-score_card.jpg | — |
| MR-06 | short | match | moments | frame | short-chart_timeline.jpg | — |
| MR-10 | short | match | hook_text | generic/hook_card | short-hook_card.jpg | — |
| MR-12 | short | match | source, date | generic/source_card | short-source_card.jpg | — |
| BP-01 | short | story | hook_text | generic/hook_card | short-hook_card.jpg | — |
| BP-02 | short | story | hook_text | generic/hook_card | short-hook_card.jpg | — |
| BP-08 | short | story | stats, source, date | generic/stat_leader | short-stat_leader.jpg | — |
| BP-13 | short | story | claim | generic/quote_card | short-myth.jpg | — |
| BP-14 | short | story | metrics, source, date | generic/duel_columns | short-duel_columns.jpg | — |
| BP-16 | short | story | stats, source, date | generic/stat_leader | short-hook_card.jpg | — |
| BP-18 | short | story | hook_text | generic/hook_card | short-hook_card.jpg | — |
| BP-19 | short | story | hook_text | generic/hook_card | short-hook_card.jpg | — |
| BP-20 | short | story | source, date | generic/source_card | short-source_card.jpg | — |
| TA-01 | long | tactical | hook_text | generic/hook_card | long-hook_card.jpg | — |
| TA-02 | long | tactical | home, away, score | generic/score_card | long-score_card.jpg | — |
| TA-03 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-05 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-06 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-11 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-12 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-14 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-16 | long | tactical | stats, source, date | generic/stat_leader | long-stat_leader.jpg | — |
| TA-18 | long | tactical | takeaways | frame | long-takes.jpg | — |
| TA-19 | long | tactical | hook_text | generic/hook_card | long-hook_card.jpg | — |
| TA-04 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-07 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-08 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-09 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-10 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-13 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-15 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-17 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| MR-03 | short | match | home, away, score | generic/score_card | short-score_card.jpg | — |
| MR-05 | short | match | moments | frame | short-chart_timeline.jpg | — |
| MR-07 | short | match | metrics, source, date | generic/duel_columns | short-stat_leader.jpg | — |
| MR-08 | short | match | player_name, stats | generic/player_poster_side | short-player_poster_side.jpg | player_portrait |
| MR-09 | short | match | metrics, source, date | generic/duel_columns | short-stat_leader.jpg | — |
| MR-11 | short | match | home, away, date | generic/fixture_card | short-fixture_card.jpg | — |
| BP-03 | short | story | player_name, stats | generic/player_poster_side | short-player_poster_side.jpg | player_portrait |
| BP-04 | short | story | moments | frame | short-chart_timeline.jpg | — |
| BP-05 | short | story | moments | frame | short-chart_timeline.jpg | — |
| BP-06 | short | story | stats, source, date | generic/stat_leader | short-stat_leader.jpg | — |
| BP-07 | short | story | metrics, source, date | generic/duel_columns | short-duel_columns.jpg | — |
| BP-09 | short | story | hook_text | generic/hook_card | short-hook_card.jpg | — |
| BP-10 | short | story | metrics, source, date | generic/duel_columns | short-duel_columns.jpg | — |
| BP-11 | short | story | moments | frame | short-chart_timeline.jpg | — |
| BP-15 | short | story | metrics, source, date | generic/duel_columns | short-stat_leader.jpg | — |
| BP-17 | short | story | moments | frame | short-chart_timeline.jpg | — |
| C-01 | short | core | — | frame | short-opening.jpg | — |
| C-02 | short | core | hook_text | generic/hook_card | short-hook_card.jpg | — |
| C-05 | short | core | claim, source | generic/quote_card | short-quote_card.jpg | — |
| C-08 | short | core | takeaways | frame | short-takes.jpg | — |
| U-01 | short | utility | label | frame | short-hook_card.jpg | — |
| U-04 | short | utility | date | frame | short-hook_card.jpg | — |
| U-06 | short | utility | claim | frame | short-hook_card.jpg | — |
| U-07 | short | utility | — | frame | short-ending.jpg | — |
| U-08 | short | utility | source, date | generic/source_card | short-source_card.jpg | — |
| TA-20 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-21 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-22 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-23 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| TA-24 | long | tactical | tactical_diagram | starter | long-tactical_explainer.jpg | — |
| LC-01 | long | narrative | hook_text | generic/hook_card | long-hook_card.jpg | — |
| LC-02 | long | narrative | hook_text | generic/hook_card | long-hook_card.jpg | — |
| LC-03 | long | narrative | moments | frame | long-chart_timeline.png | — |
| LC-04 | long | narrative | metrics, source, date | generic/duel_columns | long-duel_columns.jpg | — |
| LC-05 | long | narrative | stats, source, date | generic/stat_leader | long-stat_leader.jpg | — |
| LC-06 | long | narrative | claim, source | generic/quote_card | long-quote_card.png | — |
| LC-07 | long | narrative | stats, source, date | generic/stat_leader | long-stat_leader.jpg | — |
| LC-08 | long | narrative | moments | frame | long-chart_timeline.png | — |
| LC-09 | long | narrative | claim | generic/quote_card | long-quote_card.png | — |
| LC-10 | long | narrative | metrics, source, date | generic/duel_columns | long-duel_columns.jpg | — |
| LC-11 | long | narrative | player_name, stats | generic/player_poster_side | long-player_poster_side.jpg | — |
| LC-12 | long | narrative | hook_text | generic/hook_card | long-hook_card.jpg | — |
| LC-13 | long | narrative | source, date | generic/source_card | long-source_card.png | — |
| LC-14 | long | narrative | — | frame | long-ending.png | — |
| LC-15 | long | narrative | home, away, date | generic/fixture_card | long-fixture_card.jpg | — |
| LC-16 | long | narrative | source, date | generic/source_card | long-source_card.png | — |

## Next steps

- Reconcile the contract with the R3/R4 packets before any final-gate render;
  see `docs/coordinator/r3-r4-c6-c7-reconciliation-2026-10-20.md`. The
  contract fixes authored text/media execution, not the R3 planner/template
  blockers (hook-card competition, empty tactical scene, outro overflow), so
  R4 remains blocked.
- Extend execution or media slots only where a card's design already has an
  authored region and the owner has seen the rendered result. Do not add slots
  to typographic, statistical or tactical cards by default.
- Keep the split: registry = card identity + data slots; contract = one
  executable record per card (text + media + execution); Scene Graph = frozen
  instance with `contract_hash` and `data_bindings`.
- Do not edit `card-contract.json` by hand; rebuild it with
  `tools/build_card_contract.py --write` and rerun `--check`.
