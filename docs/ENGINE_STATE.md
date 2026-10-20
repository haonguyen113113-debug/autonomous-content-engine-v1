# Engine state and next-session handoff

Last verified: **2026-10-20**. This is a compact handoff, not a full history.
Re-check Git and worktrees before acting because another OpenCode session may
have progressed since this snapshot.

## Product goal

Prove a dependable Soccer/Vietnamese content-production vertical slice for
Allen Knows Ball. The near-term target is short form; long form follows on the
stronger PC. Voice naturalness and publishing are not current proof gates.
The larger portfolio business in `PROJECT_SPEC.md` remains the long-term
north star, not the current implementation claim.

## Hermes boundary

Hermes is the planned external research/script/orchestration agent; ACE remains
the deterministic asset-check, template/Scene Graph, voice/render, and QA
engine. Owner review and publishing remain manual. The authenticated submit/
status API and versioned Hermes payload are not implemented. The Docker setup
was removed; the durable local queue worker remains available. See
`docs/hermes-engine-integration.md`. Short-form C-11 is the authored opening
hook card; the renderer must not invent competing text outside template slots.

## Owner's current architecture constraints

- Asset discovery is multi-source and multi-format. YouTube is source
  discovery/linking only, never a video downloader or rights grant.
- Rights scope is checked for each intended upload and remains separate from
  visual suitability. The owner decides external asset saving/use; exceptions
  require human review.
- The LLM emits semantic beat intent, not concrete layout values.
- A deterministic Visual Planner creates a versioned Scene Graph from intent,
  suitable/approved assets, and the pinned Template Foundation.
- The renderer consumes the graph. QA inspects rendered scenes and reports
  uncertainty as `NEEDS_REVIEW`, not a false `PASS`.
- Distinct visual grammars create story-fit variation while the Template
  Foundation preserves channel identity.
- Do not commit, push, publish, reset/clean the dirty tree, modify `runtime/`,
  or run long renders unless the owner explicitly asks.

## Verified repository snapshot

- Repository: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- Branch/commit: `main` / `8bac94d` (C-09/C7 checkpoint integrated with
  latest `origin/main`, including C-11 and Hermes changes).
- Integration changes are committed; the checkpoint documentation is being
  finalized in a separate commit. Verify remote sync before starting another
  task.
- The merged checkpoint includes C7 contracts for all 90 cards in both packs,
  C-09 source-card execution in 12.1.0, C-11 short opening hook in both packs,
  Scene Graph/renderer QA wiring, and the Hermes/ACE boundary documentation.
  Docker configuration is removed; local queue worker remains.
- Historical `card-media-contract.json` v1.0 remains evidence only; runtime
  reads `card-contract.json`.
- `PROJECT_SPEC.md` describes a much broader autonomous business engine than
  the current Soccer video workflow. Keep those scopes distinct.

## Current implementation, at a glance

- Present (foundations): local SQLite evidence/observation/belief; soccer
  entity seeds; asset registry/provenance/rights; local UI; Ollama script
  draft; TTS preview gate; short/long template packages; Pillow + FFmpeg
  render path.
- Integrated, uncommitted:
  - `apps/asset_library/rights_scope.py` — `is_usable_for(asset, purpose)`,
    use-scoped rights, deny-default, human-review exceptions.
  - `apps/scene_graph/` — `intent.py`, `builder.py`, `schema.py`,
    `executor.py`, `pipeline.py`; deterministic Scene Graph v1, `graph_hash`,
    fail-closed validate.
  - **Unified card contract v2.0** (C7, supersedes C6 as runtime):
    `template_foundation/templates/allen-knows-ball/12.0.0/card-contract.json`
    + `apps/studio_templates/card_media.py` +
    `tools/build_card_contract.py`. One record for **90/90** built cards
    (505 data slots typed `text`, 143 distinct keys), generated
    deterministically from the registry + starter JSONs + selector/layout
    mappings. Each record freezes
    card identity, starter ID/SHA-256, canvas, template version, renderer
    route, execution status, data slots (sources, boxes, fonts, fit floors,
    length limits, fallback), editor notes, and media slots (`media_slots: []`
    where none; each declares rights/use constraints).
    Execution coverage in 12.0.0: **20 `contract`, 7 `partial`, 63
    `legacy_non_ready`**. `--check` must match the on-disk contract exactly.
  - **C6 `player_portrait` slot carried unchanged** in the unified record:
    `C-04`/`MR-08`/`BP-03` across five player-card modes, box
    `[0, 282, 424, 1240]`, `cover`, focal `[0.5, 0.30]`, rounded mask
    `[0, 52, 52, 0]`, after pack layer `bed-60`. The planner binds only a
    `verified`/`active` image with a persisted human-granted scope; anything
    else freezes as `fallback` (`keep_pack_artwork`).
  - Planner contract freeze: `slots`, `data_bindings`, `media_bindings`, and
    `provenance.card_contract` (contract/starter SHA-256, status, reason)
    are covered by `graph_hash`. Required missing data → explicit primitive
    `fallback`; unsupported card/mode → primitive `legacy_non_ready`; no
    silent authored render. `C-07` keeps `ĐỐI ĐẦU` and maps `label-0` to
    `metrics[0].label`; stat rows (`MR-07`, `MR-09`, `BP-15`) execute only
    on `stat_leader`; `MR-04` executes only `score_card`.
  - `apps/card_selector.py` now records `card_execution` per decision and
    `contract_starters`/`legacy_starters` in the plan; a legacy suggestion is
    warned, not silently rendered. `apps/measurement/render_qa.py` adds
    `check_card_contract` (legacy/fallback → `NEEDS_REVIEW`, never `PASS`)
    and `check_text_fit` (frozen text vs authored box at drawn size; horizontal
    overflow `FAIL`, vertical ink overflow `FAIL` beyond a 25%-of-size font
    allowance, declared length/word/line excess `NEEDS_REVIEW`).
  - **Schema validation against the original contract**: frozen graphs
    reject changed/extra text, moved/resized layers, changed pack art,
    changed media geometry, and contract/starter hash tampering even after a
    recomputed `graph_hash`; unfrozen graphs remain inspection-only.
  - QA `check_media_placement` compares rendered background vs the pack-only
    baseline: bound slots must paint ≥1% of their box with ≤64 changed pixels
    outside; fallback slots must be pixel-identical; missing baseline →
    `NEEDS_REVIEW`.
  - `apps/worker/` (persisted queue/run state), `apps/distribution/`,
    `apps/learning/`, `apps/measurement/`, `apps/llm.py`, `apps/orchestrator/`,
    pack 12.0.0 starter JSONs and resources.
- Renderer reads Scene Graph nodes verbatim; no silent legacy fallback when
  the flag is on. Rights gate blocks attach when purpose-ineligible. QA
  returns `PASS`/`FAIL`/`NEEDS_REVIEW` with evidence; `ready == (verdict ==
  PASS)`.

## Tests and inspections run

Focused verification (re-run 2026-10-20 after merging upstream C-11 and
regenerating both C7 contracts): selector, shortform fixture, C7 contracts,
Scene Graph, renderer and motion suites → **240 passed in 54.07s**.

Full suite: `python -m pytest tests -q` → **554 passed in 94.87s**
(2026-10-20; includes 18 new unified-contract tests).

Contract generator gate (2026-10-20):
`python tools/build_card_contract.py --check --version 12.0.0` and default
12.1.0 → **OK, 90 cards, exact match**. Hashes: 12.0.0
`2fa0a5249a51b8b93654bfe366d4d035499effe756814aad4510daef9dc054f7`; 12.1.0
`512dbbd9ccfc5bdcdecf584294bd8e7ad5a24c465e412778af8e701648e16bed`.

Static starter gate (2026-10-20): `python apps/studio_templates/check_starters.py`
→ **90 files, 0 errors**. Authored starter JSONs were not modified; the
`media_slot` layer type exists only in planner-produced graphs, so the static
gate correctly never sees it.

Visual inspection (2026-10-19/20, temp artifacts only, not `runtime/`): a
synthetic portrait render and a box overlay confirmed the frozen region sits
inside the cyan portrait frame with a deliberate glow margin, the paint fills
the slot, and the rounded corners follow the frame. **This is not
publish-ready aesthetic QA** and does not clear R3/R4.

Diagnostic render still outstanding from 2026-10-19: run `1caa81740bdd`
(short-form 12.0.0, 28s for a 24s target, silent synthetic voice) showed an
extra renderer title competing with the hook, an empty tactical pitch, and
outro text overflow. It does not clear R3 or R4; owner review of the clip is
still needed. No long render or MP4 review was run this session.

## Decisions added/changed

- **Unified card contract v2.0 frozen (C7)**, superseding C6 as the runtime
  contract: every built card has exactly one record in
  `card-contract.json` (90/90), including `media_slots: []` cards. Text/data,
  execution status, media regions and fallback are authored in the pinned
  pack; the planner freezes them and the renderer executes them. See
  `docs/coordinator/contracts/c7-card-contract.md`. Current
  `contract_hash=2fa0a5249a51b8b93654bfe366d4d035499effe756814aad4510daef9dc054f7`;
  regenerating it invalidates frozen graphs by design.
- **C6 card media contract v1.0 remains frozen history**: variable media
  enters a card only through a declared slot; geometry/fit/focal/mask/z-order/
  fallback are authored in the pinned pack, not chosen by the renderer. Its
  `player_portrait` slot is carried unchanged into C7. Extending slots or
  changing geometry requires a new contract version/pack release.
- **Execution is explicit in 12.0.0**: 20 `contract`, 7 `partial`, 63
  `legacy_non_ready`. Legacy modes are named per card; `MR-04` executes only
  `score_card` (`goal_card` is legacy because the layout needs `hook_text`);
  stat rows `MR-07`/`MR-09`/`BP-15` execute only `stat_leader`; `BP-06`
  executes only `stat_leader`; long form is `legacy_long` and deferred.
- **Text/data bindings are frozen**: 505 data slots (143 distinct keys) from
  the authored starter JSONs. `C-07` keeps the authored title `ĐỐI ĐẦU` and
  maps `label-0` to `metrics[0].label`; hidden optional slots stay hidden;
  shrink-to-fit happens at plan time and the renderer draws the frozen size.
  Hidden instructional text (`showInExport: false`) is `editor_notes`, not a
  data slot, and must remain hidden.
- **Contract drift is a hard failure**: the generated contract pins the
  registry, starter SHA-256, boxes/fonts/limits and layout grammar hash; the
  validator rejects drift even with a recomputed contract hash. Frozen graphs
  are validated against the original contract.
- Slot `player_portrait`: normalized box `[0.0, 0.147, 0.393, 0.646]` →
  pixel box `[0, 282, 424, 1240]` on 1080×1920, `cover`, focal `[0.5, 0.30]`,
  rounded mask `[0, 52, 52, 0]`, inserted after pack layer `bed-60`.
- Planner eligibility is fail-closed: `asset_type` must match, record must be
  `verified`+`active`, and the frozen ref must be `approved` from a persisted
  human-granted scope. `verified` alone never suffices. Ineligible proposals
  become explicit `fallback` bindings retaining `proposed_asset_id`.
- Starter portrait roles now mirror only the bound ref; without a bound slot
  they are `monogram_fallback` (no pending portrait refs in starter designs).
- QA placement measures rendered pixels against a pack-only baseline; asset
  presence alone is never a `PASS`. The new card-contract check returns
  `NEEDS_REVIEW` for legacy/fallback/contract-less graphs; text-fit measures
  frozen text at the drawn font size (pixel overflow `FAIL`, declared
  length/word/line excess `NEEDS_REVIEW`).
- **S3.1 grammar planner (2026-10-20)**: `apps/card_selector.py` is now
  contract-first. Beat roles come from semantic intent + reviewed data;
  `execution.status == contract` is the production allowlist; partial cards
  remain non-production (duel uses `BP-14`, stat uses `BP-16`, money stat uses
  `BP-08`, portraits use `C-04`/`MR-08`/`BP-03`). Declared legacy modes are
  hints, not layout owners. Media binds only to declared portrait slots after
  subject + purpose-rights checks; the bound-asset → `media_b_roll` conversion
  and generic b-roll auto-pick are removed. Decisions record `card_execution`,
  `production_ready`, `media_status`, and grammar role/source/candidates/
  repetition; the plan reports contract/partial/legacy/production starters,
  non-ready beats, and `grammar_variety_ok`. A sole valid contract choice is
  retained with an explicit reason/warning, never replaced by a legacy mode.
  Verified before the upstream C-11 sync: focused 219 passed; full suite 567
  passed. **Blocker:** C7 has no contract tactical/context card,
  so the five tactical R3 beats remain explicit legacy pitch-plate fallbacks.
  R4 stays `BLOCKED`. See
  `docs/coordinator/grammar-planner-s3-1-2026-10-20.md`.
- **C-09 source attribution (2026-10-20)**: `source_card` is contract-executable
  only in pinned pack **12.1.0**. The upstream C-11 opening hook is included
  in both versioned contracts; C-09 is the only card whose execution differs
  between them. BP-20, MR-12, U-08, and long-form source cards remain legacy.
  C-09 binds reviewed `claim` to `src-body`, and explicit `source` + `date` to
  required `credit`; missing values fall back non-ready. The starter and its
  geometry are unchanged. Contract hash:
  `512dbbd9ccfc5bdcdecf584294bd8e7ad5a24c465e412778af8e701648e16bed`.
  The fixture's 82-character claim still fails text-fit; a short claim passes
  text-fit but remains non-ready pending rendered inspection and owner
  approval. The pre-sync report recorded 587 full-suite passes. Both versioned
  contract checks now pass, and the starter check reports 90 files with 0
  errors. No C-09 render or visual approval was performed. See
  `docs/coordinator/source-card-c9-12-1-0-2026-10-20.md`.
- Rights: `verified` is necessary but never sufficient; `is_usable_for(asset,
  purpose)` is the use-scoped gate. Deny-default for YouTube/unknown
  source/license, expired/unclear expiry, and copyright exceptions (human
  review only; an LLM cannot clear them).
- Scene Graph: fail-closed when `ACE_SCENE_GRAPH_RENDER=1` + missing graph;
  `graph_hash` = sha256 canonical JSON minus itself; renderer executes
  verbatim, no remap.

## Remaining work

1. **R4 is blocked; fix the R3 aesthetic/planner/template blockers before a
   final-gate render.** `docs/coordinator/r3-r4-c6-c7-reconciliation-2026-10-20.md`
   records that C7 closes card text/media execution (90/90 records) but does
   not clear S2.5 hook hierarchy, S3.5/S4.2 source beat, S4.1 owner-approved
   media/purpose or S5.2 headline motion. The S3.1 planner is now contract-first
   and reports variety honestly. C-09 closes only short-form attribution
   grammar in 12.1.0; it does not clear tactical/context roles or the remaining
   R3 visual blockers. The
   2026-10-19 diagnostic clip `1caa81740bdd` also still needs owner review.
2. **Close or explicitly accept the legacy surface before claiming the short
   slice is contract-ready**: 63 `legacy_non_ready` cards and 7 partial cards
   with named legacy modes remain (generic/frame/long, source/quote/timeline/
   fixture/career, `media_b_roll`, procedural title/credits/disclaimers).
   Extend execution or media only where a card already has an authored region
   and after rendered inspection. `LC-11` (long form) has a portrait purpose
   but no contract slot; long form is deferred.
3. Minor cleanups: extra `duel_columns.short.json` is unregistered;
   `_check_asset_ref` messages still say "roles." for binding refs;
   `_write_scene_graph_beat` retains unused `root`/`scene_number` params.
4. Keep R4 blocked until rendered review and remaining R3 gates are addressed.

## Next concrete action

Produce a **short C-09 preview using pack 12.1.0** into a temporary
location outside the repository's `runtime/`, with a short representative
claim and explicit source/date. Ask the owner to inspect the actual rendered
frame and credit readability. Keep C-09 `NEEDS_REVIEW` and R4 `BLOCKED` until
that inspection is approved; graph/text-fit checks alone are not visual QA.
Then resume the remaining R3 blockers (S2.5 hook hierarchy, S3.5/S4.2 source
beat semantics, S4.1 owner-approved media/purpose, and S5.2 headline motion)
using `docs/coordinator/r3-r4-c6-c7-reconciliation-2026-10-20.md` and the R4
packet. Do not modify `runtime/` or run a long render without a separate owner
request.
