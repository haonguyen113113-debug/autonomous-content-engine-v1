# C7 — Unified card contract (every built card, one executable record) — v2.0

Status: frozen for worker tasks. Changes require coordinator approval and a
contract rebuild. Supersedes C6 v1.0 as the runtime card contract; the C6
`player_portrait` slot is carried forward unchanged.

Pack history: the upstream `C-11` short opening hook card is included in the
released **12.0.0** pack and is contract-executable there (20/7/63). **12.1.0**
adds exactly one further execution promotion: `C-09` `source_card` (21/7/62).
The contracts are pinned by pack version. 12.1.0 reuses the 12.0.0
font/kit/pack resources byte-for-byte and does not change C-09's starter JSON,
boxes, fonts, colours or background art.

## Rule

Every built card has exactly one record in the pinned Template Foundation
package. The record declares the authored text/data slots, the fixed canvas,
the renderer route, and any variable-media region. A card with no variable
media still has a record with `media_slots: []`; absence from a separate media
file is not coverage. The planner resolves card, text and media decisions from
this record and freezes them into the Scene Graph. The renderer executes the
frozen graph; it does not choose cards, assets, regions, wording, typography or
coordinates.

Authoritative runtime file:
`template_foundation/templates/allen-knows-ball/12.1.0/card-contract.json`
(`schema_version` 2.0, `template_version` 12.1.0, `contract_id`
`card-contract`, `contract_hash`
`512dbbd9ccfc5bdcdecf584294bd8e7ad5a24c465e412778af8e701648e16bed`).
The historical file
`template_foundation/templates/allen-knows-ball/12.0.0/card-contract.json`
hash: `2fa0a5249a51b8b93654bfe366d4d035499effe756814aad4510daef9dc054f7`.

Build/check tool: `tools/build_card_contract.py --version <version>`.
Loader/validator: `apps/studio_templates/card_media.py`.

The deterministic builder derives records from:

- `apps/studio_templates/card_registry.py` — card identity, aspect, family,
  declared data slots, renderer route;
- `apps/studio_templates/<card>.<aspect>.json` — authored starter design,
  pack bed, text layers, boxes, fonts and z-order;
- `apps/studio_templates/card_selector.py` + `graphic-templates.json` — the
  selected mode's declared data requirements and the card's supported modes;
- the authored pack's `graphic-templates.json` layout grammar (hash-pinned).

`python tools/build_card_contract.py --check` must match the on-disk contract
byte-for-byte. A changed registry, starter JSON, selector mapping or layout
grammar without a rebuild is drift and fails validation.

## Record shape

Each `cards[]` record declares:

| Field | Meaning |
|---|---|
| `card_id`, `starter_id`, `aspect`, `family` | Registry identity. `starter_id` equals `card_id`; `aspect` is `short` or `long`; canvases are 1080×1920 and 1920×1080. |
| `canvas` | Authored width/height; the only coordinate space for boxes. |
| `starter_file`, `starter_sha256` | The exact authored starter JSON the record was derived from. |
| `template_version` | Pinned Template Foundation version per record (must match the package). |
| `modes` | Registry modes that selected this card, including the synthetic `frame` marker for non-scene-graph frame cards. |
| `renderer_route` | Registry route: `starter`, `frame`, or `generic/<mode>`. |
| `execution` | `route`, `status`, executable `modes`, `legacy_modes`, `reason`. |
| `data_slots[]` | One entry per slotted authored text layer. |
| `static_text_layers[]` | Text layers without a slot (empty in 12.0.0; supported for future packs). |
| `editor_notes[]` | Non-export instructional text (`showInExport: false`); must remain hidden and is never editable data. |
| `media_slots[]` | Declared variable-media regions; empty for all but three portrait cards. |

### Data slots

A data slot declares:

- `slot_id`, `layer_id`, `type` (`text`), semantic `role`;
- `active_modes` (modes in which the slot is shown) and `required_for_modes`;
- ordered `sources` (`hook_text`, `claim`, `metrics[0].label`, `crest:home`,
  `stats[0].value`, etc.);
- optional `join`: when present, every declared source is required and is
  concatenated with that literal (12.1.0 uses it for C-09 `credit`:
  `source` + `" • "` + `date`; joined attribution never borrows an evidence
  fallback);
- `fallback`: `authored_text` or `hide`;
- `required` (required in at least one active mode);
- frozen `box_px`, `font` (family, authored size, weight, align),
  `fit` (shrink floor), `max_lines`, `max_words`, `max_chars`;
- `validation` (`non_empty`, length/word/line limits, optional pattern).

The planner resolves sources in order. An unfilled optional slot stays hidden;
a missing required slot produces a declared fallback, never a partial authored
render. Shrink-to-fit happens at plan time; the renderer draws the frozen font
size.

The three editor notes (`showInExport: false`, e.g. `spot-photo-note`) are
recorded for drift detection but are not data slots and cannot be filled.

### Media slots

Media slots retain C6 v1.0 geometry and eligibility:

| Card | Executable modes | Slot / role | Box px @1080×1920 | Fit | Focal | Mask | z-order | Fallback |
|---|---|---|---|---|---|---|---|---|
| C-04 | `player_card`, `player_poster`, `player_poster_side`, `player_poster_top`, `potm_card` | `player_portrait` | `0, 282, 424×1240` | cover | `0.5, 0.30` | rounded `[0,52,52,0]` | after `bed-60` | keep pack artwork |
| MR-08 | same | `player_portrait` | same | same | same | same | same | same |
| BP-03 | same | `player_portrait` | same | same | same | same | same | same |

Every other card declares `media_slots: []`. No media region exists on a card
whose artwork has no authored region, and no video slot is declared in 12.0.0
or 12.1.0.
Each media slot also declares its right/use constraints:
`requires_verified`, `requires_active`, `requires_persisted_human_grant`,
`purpose_specific`, `human_review_required` (all true). Eligibility is
fail-closed: `asset_type` must match, the record must be `verified`+`active`,
and the frozen ref must be `approved` from a persisted human-granted use
scope. `verified` alone never suffices. Ineligible proposals freeze as
explicit `fallback` bindings retaining `proposed_asset_id`.

## Execution coverage

| Status | 12.0.0 | 12.1.0 | Meaning |
|---|---:|---:|---|
| `contract` | 20 | 21 | All selected modes execute the authored starter design through the contract. |
| `partial` | 7 | 7 | At least one selected mode is executable; the card also has legacy modes. |
| `legacy_non_ready` | 63 | 62 | No selected mode is contract-executable; rendered by a legacy path and never QA-`PASS` as contract-ready. |
| **Total** | **90** | **90** | Exactly one record per registry card. |

Contract-executable cards and modes (12.1.0):

- hook: `C-02`, `C-03`, `MR-01`, `MR-10`, `BP-01`, `BP-02`, `BP-09`,
  `BP-18`, `BP-19`, `C-11` on `hook_card`;
- score: `MR-02`, `MR-03` on `score_card`; `MR-04` on `score_card` only
  (`goal_card` is legacy because the layout requires `hook_text`, which the
  authored score card cannot supply);
- duel: `C-07`, `BP-07`, `BP-10`, `BP-14` on `duel_columns`;
- stat rows: `MR-07`, `MR-09`, `BP-15` on `stat_leader` (their registry
  `duel_columns` mode is legacy);
- stat claim: `C-06`, `BP-16` on `stat_leader`;
- money: `BP-08`, `BP-06` on `stat_leader` (`BP-06` is legacy on
  `welcome_card`);
- portraits: `C-04`, `MR-08`, `BP-03` on all five player-card modes;
- source attribution: **`C-09` only** on `source_card`. `src-title` keeps the
  authored `NGUỒN`; `src-body` receives only the reviewed `claim`; `credit`
  receives `source` + `date` and is required. `claim`, `source` and `date` are
  all required; no claim is derived from narration or replaced by the source
  name.

`BP-20` (fact check), `MR-12` (match source), `U-08` (correction) and all
long-form source cards (`LC-13`, `LC-16`) stay `legacy_non_ready`; the
promotion is per-card and must not become a global `source_card` allowlist.

Legacy modes are explicit: `chart_comparison` (C-06), `comparison_duel` and
`statline_scorecard` (C-07), `welcome_card` (BP-06), `duel_columns`
(BP-15/MR-07/MR-09), `goal_card` (MR-04). All long-form cards are legacy for
now (`legacy_long`); the Scene Graph builder composes short starters only.

## Planner freeze

For the chosen card/mode the planner writes:

- `starter_id`, `mode`, `design` (the authored starter design with frozen text
  values, hidden optional layers, frozen font sizes and frozen media layers);
- `slots` (the final visible text values) and `data_bindings` (slot id, layer
  id, role, value, sources, required, visible, fallback, mode);
- `media_bindings` (slot id, role, status `bound`/`fallback`, frozen box,
  fit/focal/mask, asset ref and rights scope when bound, `proposed_asset_id`
  and reason when not);
- `provenance.card_contract` (`contract_id`, `schema_version`,
  `template_version`, contract and starter SHA-256, card id, route, status,
  reason) and the normal `graph_hash`.

The contract status is one of:

- `contract` — the authored starter executes under the contract;
- `fallback` — required data/media is missing, so a primitive fallback is
  frozen with the reason; QA is `NEEDS_REVIEW`;
- `legacy_non_ready` — the card/mode has no executable contract; the graph is
  a primitive legacy render; QA is `NEEDS_REVIEW`;
- `missing_contract_record` / `no_contract` — the pack/card predates the
  record; rebuild from the pinned pack, never silently execute.

## Validation and tamper rejection

`validate_scene_graph` is fail-closed for frozen graphs. It checks, against the
original contract (not only layers created in the same graph):

- contract hash and starter hash match the current pinned pack;
- every starter child is present exactly once; no extra text/layer was added;
- every data slot's text, font size, box, visibility and binding agree;
- static text and hidden editor notes agree;
- media slot geometry, role, fit, focal point, mask and z-order agree;
- no pack art was replaced, moved or resized;
- `graph_hash` covers the whole frozen graph; changing any of the above and
  recomputing `graph_hash` still fails the contract comparison.

Unfrozen graphs remain inspection-only and must not be reported as ready.

## Renderer boundary

The renderer consumes the frozen graph:

- it paints only the authored design, text values, frozen font sizes and media
  bindings it was given;
- it cannot choose/change a card or asset, create a region or layout, choose a
  crop or coordinates, add wording/typography, or add a headline, caption,
  credit, disclaimer or decorative text outside a declared slot;
- it does not use `media_b_roll`, `media_file`, procedural title/credits/
  disclaimers or card-specific image painting for a contract graph. Those
  legacy paths are separate primitive routes and carry non-ready provenance.

A missing contract graph with `ACE_SCENE_GRAPH_RENDER=1` still fails closed;
there is no silent legacy fallback in that mode.

## QA

`apps/measurement/render_qa.py` adds two independent checks:

- **Card contract** — contract status/hash, required bindings visible, media
  slots bound or fallback as declared. A primitive/legacy/fallback graph is
  `NEEDS_REVIEW`, never `PASS`. For `source_card`, `src-body` must bind only
  `claim`; `credit` must be visible and declare both `source` and `date`.
  C-09 remains `NEEDS_REVIEW` until a rendered frame is inspected and the
  owner approves it; graph-level execution is never a visual `PASS`.
- **Text fit (contract)** — measures every visible frozen data slot and static
  text layer against its authored box at the drawn font size, using the
  renderer's explicit-newline and `fontSize * 1.25` line rules. Horizontal
  overflow is `FAIL`; vertical ink overflow is `FAIL` beyond a 25%-of-drawn-
  size font allowance (the authored box is a layout rectangle, not a clip).
  Exceeding declared length/word/line limits is `NEEDS_REVIEW`
  (shrink-to-fit is not editorial approval).

Existing `check_media_placement` still compares rendered pixels against a
pack-only baseline: a bound slot must paint inside its box with no leakage; a
fallback must remain pixel-identical. Asset presence is never a `PASS`.

## Known legacy / non-ready surface

- 62 cards with no contract-executable selected mode (frame, generic/long,
  non-C-09 source, fixture/quote/timeline/career cards).
- 7 partial cards with named legacy modes above.
- `BP-20`, `MR-12` and `U-08` source semantics remain legacy/non-ready.
- C-09 rendered-frame inspection and owner visual approval are still pending;
  the fixture's 82-character claim fails text fit and its short replacement
  passes text fit only (not aesthetic approval).
- Long-form starter execution is deferred; `LC-11` has a portrait purpose but
  no media slot.
- `media_b_roll` remains a separate generic scene, not a card media slot.
- The generic renderer still composes procedural title/credit/disclaimer text
  for primitive routes. Those routes are marked non-ready and QA must not
  `PASS` them.

These are explicit limitations, not silent fallbacks. Extending execution or
adding a media slot requires a new contract version/pack release, rendered
inspection, and owner approval.

## Change control

- Edit the registry/starter JSONs/selector mapping, then run
  `python tools/build_card_contract.py --write --version <pack>` and
  `python tools/build_card_contract.py --check --version <pack>`; regenerate
  scene graphs because `contract_hash` changes. Never rebuild 12.0.0 while
  extending a later pack. `--version 12.0.0` must remain byte-exact.
- Do not hand-edit `card-contract.json` or a frozen graph.
- C6 v1.0 (`docs/coordinator/contracts/c6-card-media.md`) remains the frozen
  history of the media-slot rule; its `player_portrait` geometry is unchanged
  here and is not independently executable.
