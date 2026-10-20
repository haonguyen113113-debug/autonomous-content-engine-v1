# v12 design notes (skill trace, instruction S2/S3/S8)
Design Read: night cyber broadcast plates for VN football fans; condensed
display numerals with Be Vietnam Pro text; one boss per frame. Dials:
variance 6, motion 5, density 6.
- frontend-design: hero-first single numeral on data cards; kicker only where
  the mode needs it; boxes measured from each plate's real dark empty zone;
  hook carries no logo bumper (Nova brief); cut one accessory per layout
  (no eyebrows, no baked latin micro-labels, brush unused).
- Instruction S3 BARLOW BAN: all Vietnamese boxes use body (Be Vietnam Pro,
  raqm-safe precomposed glyphs, verified in proofs); display (Barlow
  Condensed) only for latin numerals and score punctuation.
- graphic-design-system: BOSS single biggest size; SUPPORT about 0.28x;
  WHISPER about 0.16x; at most 3 sizes per frame; all boxes inside 7/9/13/7
  safe area (asserted at prepare time); contrast probed per zone in
  pack-drop/12.0.0/contrast-report.json, 83/92 pass, 9 whisper zones queued
  for card-stage scrim (pill 0.45), never guessed.
- canvas-design: plates carry the visual weight, boxes carry essential text
  only; refine pass, no new graphics except channel identity badge.
- theme-factory: locked cyber-pitch palette only; presets never touch it.
- detailing: provenance whisper (source/date) on every layout whose registry
  slots require it; corner marks, perforation, ticks and pinstripes stay
  starter-stage primitives on dead zones, never over data (detailing.py).
- broadcast-depth + emil + algorithmic-art: deterministic seeds recorded;
  depth finishing (top-light, hero glow, grain seed 7) applies at card
  render stage, not baked into owner art.
- impeccable-lite: one committed direction; verification bounded to
  validate, proofs, registry/slot conformance and the instruction gates.
- Tagline TBD: no placeholder text ships in any box, doc or proof.
