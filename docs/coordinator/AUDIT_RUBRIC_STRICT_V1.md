# Audit rubric — render beauty, strict mode — v1.1 (12.0.0)

Owner decision 2026-10-18: priority is beautiful render plus image QA.
Canonical pack is 12.0.0 released (0.8.0 obsolete).
Threshold mode is STRICT: small visible defects FAIL to force high quality.

## Scope

- Gate A (now): `allen-knows-ball.shortform-analyst@12.0.0` released,
  1080x1920, 30-58s, Vietnamese audience, Cyber Pitch look.
- Gate B (later, stronger PC): long-form 12.0.0, 8-20 minutes. No
  long-form work until Gate A passes three consecutive runs.

## Verdicts

- `PASS`: every check below passes on inspected frames and the MP4.
- `FAIL`: any single check fails, however small. Fix at the responsible
  layer (planner, renderer, template, asset) instead of patching around it.
- `NEEDS_REVIEW`: tooling or evidence is missing so no verdict is possible.
  Never upgrade this to `PASS`.
- No `PARTIAL` or `NOT ASSESSED` counts as a pass under strict mode.

## Gate A checks (all mandatory, all on rendered output)

### S1 structural (ffprobe plus container)

- H.264 MP4 playable, 1080x1920 exact, 30fps, duration within pinned
  template range, no black or frozen intervals, audio presence matches the
  declared mode (silent preview or muxed narration).

### S2 layout and legibility (contact sheet plus OCR or pixel bounds)

- No text outside safe area (top 9, bottom 13, left 7, right 7 percent).
- No overlap of text on text, text on focal subject, or graphics on the
  safe-area boundary.
- Vietnamese diacritics intact, no synthesized bold on body copy, hook is a
  short phrase with one emphasized word only.
- Three-step hierarchy visible: hook, key evidence, quiet attribution.

### S3 visual grammar and identity (human plus Nemotron VL look)

- Correct grammar per beat from 12.0.0 `visual-modes.json` (hook_card,
  duel_columns, stat_leader, player posters, goal/fixture/score/quote/
  potm/discipline/welcome cards, tactical_explainer, source_card,
  conclusion). Never repeat one mode more than twice in a short. No
  legacy HUD filler (perforation dots, tick rulers, corner brackets).
- Channel identity intact: void/panel, neon cyan + pulse magenta + amber,
  Tektur display/numerals, Be Vietnam Pro body, 1 boss per frame, max 3
  type sizes, provenance whisper on evidence, no prohibited effects
  (glitch, shake, flashing, fake broadcast bug, fake scoreboard,
  unlicensed crest, uncited stat, synthesized faces, orange body text,
  floating unbordered identity).
- Chart follows data semantics: bars or columns for categories, line only
  for ordered time, pie or donut only for verified part-to-whole with at
  most four parts. Zero baseline visible on bars and columns.

### S4 media and evidence honesty

- Every real-media slot shows an owner-approved, C1-eligible asset for the
  exact proposed use. Fictitious preview data is labeled as such.
- Source card shows publication, date, claim, traceable URL in separate
  visual roles.
- No YouTube-downloaded pixels anywhere.

### S5 motion and rhythm

- One eased ball move per authored pass with a decisive stop at the
  receiver. Headline reveals by short wipe, stat snaps once, vectors draw
  once. At most two signature transitions per video. No looping decoration.

## Evidence rule

Every finding cites a frame path or timestamp plus the observed text or
measurement. Reviewer records `contract_version: "c5/1.0"` and this rubric
version `audit-rubric/1.0-strict`.
