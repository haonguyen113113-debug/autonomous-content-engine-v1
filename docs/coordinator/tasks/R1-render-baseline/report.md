# R1 — Render baseline audit report

task_id: R1-render-baseline
template: allen-knows-ball.shortform-analyst@12.0.0 (released, Cyber Pitch)
run_id: a1b2c3d4e5f6
MP4: runtime/renders/a1b2c3d4e5f6/full-render.mp4
contact sheet: runtime/renders/a1b2c3d4e5f6/contact-sheet.png
ffprobe: embedded in render-report.json (h264, 1080x1920, 49.00s, AAC audio)
render report: runtime/renders/a1b2c3d4e5f6/render-report.json
frames: runtime/renders/a1b2c3d4e5f6/frames/t_00..t_07.png + frame_01..07.jpg
scene plates: runtime/renders/a1b2c3d4e5f6/work/tactical-scene-0..5.png
render command: legacy full_script_render path (apps/video_renderer.py render_full_run), 9:16, 1080x1920, 30fps, target 45s, rendered 49.00s
rubric version: audit-rubric/1.0-strict
contract version: c5/1.0
graded-by: Nemotron VL inspection of contact sheet, timestamped frames, scene plates, render-report.json, ffprobe data

Note: shell execution is blocked in this environment, so no new render was produced. The existing run `a1b2c3d4e5f6` is a fresh (2026-10-18), template 12.0.0 short-form 9:16 render with all evidence artifacts present (MP4 + contact sheet + ffprobe + frames), and is used as the R1 baseline. It is NOT 0.8.0 draft.

## Per-check verdicts (S1-S5)

| # | Check | Verdict | Evidence |
|---|-------|---------|----------|
| S1.1 | H.264 MP4 playable | PASS | ffprobe: h264 video stream + aac audio stream, playable MP4 container |
| S1.2 | 1080x1920 exact | PASS | ffprobe width=1080 height=1920; manifest output 1080x1920 |
| S1.3 | 30fps | PASS | manifest frame_rate=30; renderer config consistent |
| S1.4 | duration within 30-58s | PASS | rendered 49.00s (target 45s), within pinned range |
| S1.5 | no black or frozen intervals | NEEDS_REVIEW | frames t_01-t_07 show content (pitch plate + ball) but static frames cannot confirm motion/freeze across the full 49s |
| S1.6 | audio presence matches mode | PASS | ffprobe: aac audio stream present (full script render with narration) |
| S2.1 | no text outside safe area (7/9/13/7) | FAIL | contact-sheet.png left column panels show garbled text pressed against / beyond the left edge (outside left 7% safe area) |
| S2.2 | no text-on-text overlap | FAIL | contact-sheet.png: same garbled Vietnamese text repeated horizontally across the left side of multiple panels |
| S2.3 | Vietnamese diacritics intact | FAIL | work/title.txt has proper diacritics ("Tại sao pressing có thể bị phá vỡ chỉ bằng một đường chuyền?") but contact-sheet.png renders them mangled ("ch'édt processing...") |
| S2.4 | hook is short phrase, one emphasized word | FAIL | work/title.txt is an 11-word question, not a short phrase; no accent markup isolating one emphasized word |
| S2.5 | three-step hierarchy (hook/evidence/attribution) | FAIL | frames t_01-t_07 show only pitch plate + ball; no hook, key evidence, or quiet attribution visible anywhere |
| S3.1 | correct grammar per beat, no mode repeated >2x | FAIL | all 6 beats use the identical tactical pitch plate (one mode repeated ×6); visual-modes.json requires never repeating one mode more than twice in a short; frames t_01-t_07 identical |
| S3.2 | no legacy HUD filler (perforation dots, tick rulers, corner brackets) | PASS | none observed in frames/contact sheet; neon border frame is a design element, not prohibited HUD |
| S3.3 | channel identity intact (void/panel, neon cyan+magenta+amber, Tektur/Be Vietnam Pro, 1 boss, max 3 sizes) | PASS | neon cyan/magenta/amber void present; single ball focal subject; bundled Tektur + Be Vietnam Pro fonts |
| S3.4 | provenance whisper on evidence plates | NOT USED | no evidence/source plates rendered |
| S3.5 | no prohibited effects (glitch/shake/flashing/fake scoreboard/unlicensed crest/uncited stat/synthesized faces/orange body text/floating unbordered identity) | PASS | none observed in frames/contact sheet |
| S3.6 | chart semantics (bars/columns/line/donut rules, zero baseline) | NOT USED | no charts rendered |
| S4.1 | every real-media slot owner-approved C1-eligible asset | FAIL | render-report.json selected_media: [] — "No verified library media is attached to this script" |
| S4.2 | source card shows publication/date/claim/traceable URL | NOT USED | no source card rendered in any frame |
| S4.3 | no YouTube-downloaded pixels | PASS | no real media used at all, so no YouTube pixels |
| S5.1 | one eased ball move per authored pass with decisive stop | NEEDS_REVIEW | ball present in frames but static frames cannot confirm eased motion or a decisive stop at receiver |
| S5.2 | headline reveals by short wipe | NOT USED | no hook text rendered in any frame |
| S5.3 | stat snaps once | NOT USED | no stat numerals rendered |
| S5.4 | at most two signature transitions per video | PASS | render-report.json: "Slide-in executes on 2 scene plates" (within limit of two) |
| S5.5 | no looping decoration | NEEDS_REVIEW | static frames cannot confirm absence of looping decoration |

## Defects ranked worst-first

### 1. S3 FAIL — Single visual mode repeated across all 6 beats (tactical pitch plate ×6)
- Evidence: frames t_01-t_07 are identical cyan pitch plates with a ball; tactical-scene-0..5.png all the same; visual-modes.json selection rule "never repeat one mode more than twice in a short" violated.
- Responsible layer: **planner** (beat-to-mode assignment / mode variety). Template 12.0.0 defines 16 modes; the run uses only one, destroying visual grammar and identity.
- Why worst: the entire short is visually one repeated plate; this is the core S3 identity failure and makes the video unreadable as varied storytelling.

### 2. S2 FAIL — Garbled/repeated Vietnamese text on the left edge (diacritics mangled, outside safe area, text-on-text overlap)
- Evidence: contact-sheet.png left column panels show repeated mangled Vietnamese ("ch'édt processing...") pressed against/beyond the left edge; work/title.txt holds the correct diacritic text so the source is fine but rendering is broken.
- Responsible layer: **renderer** (text layout / drawtext placement and glyph rendering).
- Impact: S2.1 (safe area), S2.2 (overlap), S2.3 (diacritics) all fail on the same evidence.

### 3. S4 FAIL — No library media attached (selected_media empty)
- Evidence: render-report.json "Asset Library media": FAIL, detail "No verified library media is attached to this script"; selected_media: [].
- Responsible layer: **asset/planner** (no owner-approved C1-eligible media selected for this run).
- Impact: S4.1 fails; the video contains no real evidence media at all.

### 4. S2/S3 FAIL — Hook not a short phrase; no three-step hierarchy visible
- Evidence: work/title.txt = 11-word question "Tại sao pressing có thể bị phá vỡ chỉ bằng một đường chuyền?" (not a short phrase, no single emphasized word); frames t_01-t_07 show no hook/evidence/attribution hierarchy.
- Responsible layer: **planner/template** (hook content) + **renderer** (hook text not painted into scenes).
- Impact: S2.4 and S2.5 fail.

### 5. S5 NEEDS_REVIEW/FAIL — No verifiable beat-to-beat motion; eased ball move not confirmed
- Evidence: frames t_01-t_07 identical (pitch plate + ball, no visible change); S5.1 eased move/decisive stop unverifiable from static frames; S5.5 looping decoration unverifiable.
- Responsible layer: **renderer** (motion execution / Ken Burns + ball pass animation).
- Impact: S5 motion/rhythm cannot be confirmed PASS.

## What R3 should fix first

1. **Planner: enforce beat-to-mode variety** — map each of the 6 short-form beats to distinct 12.0.0 modes (hook_card, stat_leader, player_poster_side, tactical_explainer, source_card, conclusion) so no mode repeats more than twice. This is the single biggest aesthetic failure (defect #1).
2. **Renderer: fix text layout** — guarantee Vietnamese text stays inside the 7/9/13/7 safe area, renders diacritics intact, and does not repeat/overlap (defect #2).
3. **Planner/asset: attach owner-approved C1-eligible library media** to every real-media slot so S4 passes (defect #3).
4. **Planner/template: shorten the hook** to a short phrase with one emphasized word only, and render the three-step hierarchy (hook → key evidence → quiet attribution) into scenes (defect #4).
5. **Renderer: verify motion** — confirm one eased ball move per pass with a decisive stop, and that no looping decoration runs (defect #5).

Acceptance: none of S1-S5 currently passes cleanly (S1 partially PASS with one NEEDS_REVIEW; S2 FAIL; S3 FAIL; S4 FAIL; S5 NEEDS_REVIEW/partial). R1 baseline is recorded as the defect list above for R3 to fix.
