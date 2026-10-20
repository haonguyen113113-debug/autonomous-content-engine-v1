# R3/R4 reconciliation with C6/C7 — 2026-10-20

Status: coordinator note. Read-only reconciliation of the completed card
contract work (C6 v1.0 history, C7 v2.0 runtime) against the R3 beauty-fix
report and the R4 final-gate packet. No render was started. No R3/R4 verdict
is upgraded by this note.

## What is now complete

- **C7 unified card contract v2.0**: 89/89 built cards have one explicit
  record (`card-contract.json`) with canvas, starter SHA-256, renderer route,
  execution status, 505 data slots, editor notes and `media_slots` (empty for
  86 cards).
- **C6 `player_portrait` rule carried unchanged** for `C-04`/`MR-08`/`BP-03`;
  media binding is fail-closed on `verified`+`active` plus a persisted
  human-granted use scope.
- **Planner freeze**: `data_bindings`, `media_bindings`, contract/starter
  hashes and status are in the graph; frozen graphs reject post-freeze text,
  geometry, media and hash tampering.
- **QA**: a legacy/fallback/contract-less graph returns `NEEDS_REVIEW`; text
  fit measures frozen text at the drawn size; media placement still compares
  rendered pixels against the pack-only baseline.
- **Legacy surface is explicit**: 19 `contract`, 7 `partial`, 63
  `legacy_non_ready`; long form is `legacy_long`.

## What C6/C7 does not fix

R3's remaining blockers are aesthetic/planner/template/data decisions, not
card-contract coverage. The contract records what is authored; it does not make
an unauthored choice.

| R3 blocker | Responsible layer | C6/C7 effect | R4 status |
|---|---|---|---|
| S3.1 five repeated `tactical_explainer` beats; no distinct per-beat grammar | Planner/card selector | C7 makes card/mode execution explicit and marks unsupported pairs legacy, but does not assign a varied mode sequence. The selector can still choose `tactical_explainer` for undeclared beats. | **Blocked** |
| S4.1 no owner-approved real media (`selected_media: []`); no upload purpose | Run/owner + planner | C6/C7 can bind media only through a declared region, with a purpose and human-granted rights scope. It cannot invent a purpose or approve an asset. | **Blocked** pending owner purpose + approved candidate |
| S3.5 / S4.2 no source-card beat / provenance whisper | Planner | Source cards exist in the registry, but their selected `source_card` mode is `legacy_non_ready` in C7; no planner rule yet emits a source beat with complete data. | **Blocked** |
| S2.5 hook → evidence → attribution hierarchy | Planner/copy + template | C7 freezes the authored hook text slots and blocks undeclared text, but the hook layout still has only its authored boxes; it does not add an evidence/attribution structure. | **Blocked** |
| S5.2 headline reveals by slide-in, not short wipe | Template/planner | C7 does not change design-tokens motion; the scene-enter rule is unchanged. | **Blocked** |

The 2026-10-19 diagnostic clip `1caa81740bdd` also showed an extra renderer
title competing with the hook, an empty tactical pitch and outro text
overflow. Those are not cleared by C7 and still need owner inspection and
layer-appropriate fixes.

## R4 gate decision

R4 packet step 1 says: if R3 still has unresolved BLOCKED items, stop before
rendering and report R4 as blocked. That condition is still true. C6/C7
completes the card text/media contract preconditions; it does **not** clear
S2.5, S3.1, S3.5, S4.1 or S5.2.

**R4 remains blocked. Do not start a fresh render for the final gate** until:

1. the planner/template/data blockers above are fixed at their responsible
   layer, or the owner explicitly accepts a scoped exception;
2. a run-level upload purpose and owner-approved media are available for S4.1;
3. the owner has reviewed a fresh clip visually; and
4. R4's reviewer records frame/timestamp evidence for every S1–S5 check and a
   human confirms the verdict.

## What can be exercised now without a final-gate claim

- Contract/graph tests and static gates (the suite and `--check` above).
- A synthetic portrait/box inspection for contract geometry only, clearly
  labelled non-publishable.
- A diagnostic render for a specific defect, if the owner asks, without
  calling it an R4 final gate and without modifying `runtime/` beyond the
  approved render path.

No commit, push, publish or long render is part of this note.
