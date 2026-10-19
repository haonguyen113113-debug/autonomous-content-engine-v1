# Owner goal and audit thresholds — decided 2026-10-18, sprint 2-day

## Canonical template: 12.0.0 released (NOT 0.8.0)

- Owner correction 2026-10-18: 0.8.0 is obsolete. The real pack is
  `allen-knows-ball.shortform-analyst@12.0.0` plus
  `allen-knows-ball.longform-analyst@12.0.0`, both `released` in the
  Default Project worktree (commits `ecdba9c` + `14a62eb`).
- 12.0.0 look: Cyber Pitch owner pack — void/panel backgrounds, neon
  cyan + pulse magenta + amber, Tektur display/numerals, Be Vietnam Pro
  body, 16 visual modes (hook_card, duel_columns, stat_leader,
  player posters, goal/fixture/score/quote/potm/discipline/welcome
  cards, tactical_explainer, source_card, conclusion).
- Locked rules: 1 frame = 1 boss, max 3 type sizes, safe area 7/9/13/7,
  provenance whisper on evidence plates, no prohibited effects.
- Desktop repo is NOW SYNCED to pack 12.0.0 released (commits `ecdba9c` +
  `14a62eb` + `edd522e`) via working-tree checkout from origin/main on
  2026-10-18. P0 port is complete — no manual port needed. Do not grade
  against 0.8.0 ever again.

## Goal

Priority is beautiful render plus image QA on 12.0.0 short-form 9:16
ONLY. Long-form 12.0.0, discovery V2, planner V2, distribution,
publishing, analytics are OUT for this sprint.

## Deadline: 2 days full-run to render quality

Day 1: P0 port 12.0.0 pack + renderer into Desktop, then R1 baseline
audit on 12.0.0 (see what render actually looks like now) plus R2
rights gate minimal (renderer refuses ineligible assets).
Day 2: R3 beauty fix loop (worst S2-S5 defects first) plus R4 final gate.
Done means one short-form 12.0.0 MP4 passes S1-S5 strict with human
eyes, not four workstreams merged.

## Threshold mode: STRICT

Small visible defects FAIL to force high quality. No `PARTIAL` or
`NOT ASSESSED` counts as a pass.

## PASS gate: human eyes required

A short-form render passes only when ALL of these hold:

1. `python -m pytest` for the task's focused tests passes.
2. S1 structural checks pass via ffprobe (1080x1920, 30fps, duration in
   range, playable MP4, no black or frozen intervals).
3. S2-S5 graded FAIL-free on an actual contact sheet plus the MP4.
4. A human (owner or coordinator) opens the contact sheet and the MP4 and
   records per-check verdicts. Nemotron VL findings alone never conclude
   PASS. Automated tool output alone never concludes PASS.

## Evidence tiers

- Tier 0 — tool only (ffprobe, pytest, pixel bounds): supports FAIL, never
  PASS alone.
- Tier 1 — Nemotron VL review of frames against S2-S5: supports FAIL and
  NEEDS_REVIEW, never PASS alone.
- Tier 2 — human inspection of contact sheet plus MP4: required for PASS.

## Sprint task order (P0 done, start at R1)

1. R1 render baseline audit on 12.0.0 — read-only + one render (Day 1 AM).
2. R2 rights gate minimal — renderer refuses C1-ineligible assets (Day 1 PM).
3. R3 beauty fix loop — worst S2-S5 defects from R1, one layer at a time (Day 2 AM).
4. R4 final gate — full S1-S5 strict on a fresh 12.0.0 render (Day 2 PM).
5. P0 port 12.0.0 pack + renderer delta — DONE via origin/main sync, no action needed.
6. Old W1/W2/W3 packets are PAUSED unless R1 proves a contract gap
   blocks render. Do not run them in parallel with R-tasks.
7. Gate B long-form stays out until Gate A passes three consecutive runs.

