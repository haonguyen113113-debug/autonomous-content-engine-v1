# R4 — Final gate (strict S1–S5) — verdict package

**Status: NOT CLEARED — the render layer passes on measured evidence; one
measurable FAIL (no real media) plus owner review and human judgement remain.
Recommended human verdict: FAIL.**

| | |
|---|---|
| Date | 2026-10-23 (third gate run, after the F1/F2/F5 fixes) |
| Branch | `arena/3a4ff34c-autonomous-content-engine-v1` (from `94078f5`) |
| Run id | `4a4f0c1d2e3b` |
| Template pin | `allen-knows-ball.shortform-analyst@12.2.0` |
| Renderer | `ace-ffmpeg-0.9.0` (FFmpeg 7.0.2), Scene Graph path on by default |
| Contract | `12.2.0` sha256 `c38baed792a7fa19…` (92 cards) |
| Rubric | `audit-rubric/1.0-strict`, contract `c5/1.0` |

## 1. Artifacts

| Artifact | Path | sha256 |
|---|---|---|
| MP4 (25.000 s) | `runtime/renders/4a4f0c1d2e3b/full-render.mp4` | `865e9ea47029b111…` |
| Contact sheet | `runtime/renders/4a4f0c1d2e3b/contact-sheet.png` | — |
| Evidence JSON | `runtime/renders/4a4f0c1d2e3b/gate-evidence.json` | — |
| Render report | `runtime/renders/4a4f0c1d2e3b/render-report.json` | — |

`runtime/` is gitignored: reproducible with the command in §8.

## 2. Render facts (measured)

- MP4, 25.00 s, **23,012,774 B**, H.264 Constrained Baseline **1080×1920**,
  30 fps, yuv420p bt709, AAC-LC 44.1 kHz mono (silent WAV).
- `freezedetect` (n=0.003, d=0.60): **one** interval, `21.7 → 25.0 s` — the
  authored static ending card. No freeze inside a story beat.
- Frame identity (output-side seek): 9.0 s, 10.0 s, 12.0 s and 17.0 s / 19.0 s
  are all different frames (mean pixel diff 5.32 / 7.99 / 8.09).
- **Contrast measured on the encoded frames** (new `frame_contrast` block):
  hook **15.07** (floor 4.5), reading **4.31** (floor 3.0), conclusion
  **6.60** (floor 4.5) — every beat passes against the pixels it actually
  ships, not against a zoom-1.0 still.

## 3. Beats, planner and contract

| Beat | Role | Card | Contract | Text fit | In MP4 | Frame contrast |
|---|---|---|---|---|---|---|
| `beat-hook` | hook | C-11 | PASS | PASS | frame @3.5 s | 15.07 |
| `beat-stat` | stat | BP-16 | PASS | PASS | still + scene QA | n/a (still) |
| `beat-reading` | tactical | C-12 | PASS | PASS | frame @10.5 s | 4.31 |
| `beat-source` | source | C-09 | **NEEDS_REVIEW** | PASS | still + scene QA | n/a (still) |
| `beat-conclusion` | takeaway | C-13 | PASS | PASS | frame @17.5 s | 6.60 |

Planner: `production_ready=false`, `non_ready_roles=["source"]`,
`rendered_review_pending=["beat-source"]`, `grammar_variety_ok=true`.
Every beat renders all declared text slots (`text_slots_hidden` empty ×5).

## 4. Strict grading

| Check | Verdict | Evidence |
|---|---|---|
| **S1** container / motion | **PASS (container)** | 1080×1920/30 fps/H.264+AAC; no black frames; no freeze in a beat; frames differ within every beat. Speech not assessable (§9). |
| **S2** layout / legibility | **NEEDS_REVIEW** | Safe area, no-clip, overlap, density, text-fit PASS; contrast PASS both on stills and on encoded frames; hierarchy/taste need a human. |
| **S3** grammar / identity | **NEEDS_REVIEW** | Variety gate PASS (3 modes); identity/diacritics need a human or VL inspection. |
| **S4** media / evidence | **FAIL** | `Asset Library media` FAIL — no verified media (F4); C-09 has no owner review for 12.2.0 (F3). |
| **S5** motion / rhythm | **NEEDS_REVIEW** | Drift now runs for the whole beat in every encoded beat; `chalk_line_wipe` still maps to a 0.3 s slide (PARTIAL); rhythm needs an eye on the MP4. |

Strict mode: FAIL and NEEDS_REVIEW both block a PASS verdict.

## 5. Defects — status after this run

### F1 — Encoded video froze inside beats — **FIXED**

- Cause: every plate is a `-loop 1` input consumed from t=0, so zoompan's `on`
  counted frames since the start of the **video**, not the beat. Later beats
  entered with drift already saturated, and the punch ramp hit its 1.035
  ceiling after 3.3 s and held.
- Fix (`apps/video_renderer.py:_beat_zoom_expr`): subtract the beat's start
  frame; punch beats snap to 1.02 in 0.4 s, then drift so the ceiling lands at
  the end of the beat.
- Proof: `freezedetect` now reports only the authored end card; frames 9/10/12
  and 17/19 s all differ; MP4 12.6 MB → 23.0 MB.
- Tests: `tests/test_renderer_motion.py`.

### F2 — Contrast failed on the encoded beats — **FIXED (measured on the MP4)**

Three separate problems, all fixed:

1. **Sampler probed the wrong pixels.** It sampled 15/50/85 % of each
   element's declared box. C-11's title box is 250 px tall for one line, so
   the 85 % probe landed on the emblem and reported **1.32:1** for copy that
   measures **19:1** on its own ink band. `render_qa.py` now derives the ink
   band from (rendered − background), falling back to the box.
2. **The scrim was too small and too light.** The credit sits on the bed's
   brightest band, and every layer (plate *and* type) rides one zoompan chain
   that moves this bottom band down up to ~31 px at 1.035×. With the first
   scrim (`y=1802, h=76, opacity 0.70`) the box sampler read a cyan beam at
   **1.30:1**; once measured on the true glyph rows, a widened scrim at 0.82
   still sat at **2.86–3.61** — under the 3.0 floor at the start of a beat.
   C-12/C-13 now carry `credit-scrim` at `x55 y1770 w970 h108`, opacity
   **0.94**, and the same rows measure **4.31–6.60** with
   `bright_fraction = 0`.
3. **The gate had to measure the MP4, not a still.** `tools/r4_gate.py` now
   probes four timestamps per encoded beat, locates glyph rows *in the frame*,
   excludes the glyph's own glow, and records `ratio_p95`, `bright_fraction`
   and the sampled background per layer. Measured: 15.07 / 4.31 / 6.60.

### F3 — C-09 has no owner review for 12.2.0 — **OPEN (owner action)**

`check_card_contract` → `NEEDS_REVIEW`: the only signed record covers 12.1.0
and explicitly excludes other pack versions. Not a code defect.

### F4 — No owner-approved media (S4.1) — **OPEN (owner action)**

`Asset Library media` FAIL: "No verified library media is attached". The only
remaining measurable FAIL.

### F5 — BP-16 shipped half-empty while every gate passed — **FIXED**

`_contract_value` now composes `<value> <label>` for `stats[N].summary` when
the explicit field is absent; the gate records `text_slots_hidden` per beat so
a sparse card can never pass silently again. `beat-stat` now renders
"68% TỈ LỆ THẮNG BÓNG" and all five beats report `text_slots_hidden: []`.

## 6. What this run clears

- 12.2.0 renders end-to-end on the default Scene Graph path.
- Every encoded beat moves for its whole duration and is legible on the
  pixels it actually ships.
- Contract + text-fit PASS on 4/5 beats; the fifth is a version-scoped owner
  review, not a layout failure.
- 37 of 54 quality checks PASS; the only FAIL is missing media.
- The gate's own probe is unit-tested (`tests/test_r4_gate_probe.py`), so the
  two measurement traps — glyph bloom counted as background, and probing the
  wrong rows because the plate zooms — cannot silently return.

## 7. Prerequisites to a PASS

1. Owner-signed C-09 visual record for **12.2.0** (F3).
2. A rights-scoped owner-approved asset plus upload purpose (F4).
3. A human on the contact sheet + MP4 for S2/S3/S5, with real narration
   (the current voice is a silent placeholder).

## 8. Reproduce

```bash
cd autonomous-content-engine-v1
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python tools/r4_gate.py --filter-threads 1
.venv/bin/python tools/r4_gate.py --no-render --filter-threads 1   # regrade
```

## 9. Honest limits

- **Speech is not assessed**: synthetic silent WAV.
- **Aesthetics / rhythm are not assessed by a human** (S2/S3/S5).
- The MP4 encodes **3 of 5 beats**: ~4 GB RAM, no swap, no root; five beats are
  OOM-killed even single-threaded. `beat-stat` and `beat-source` are executor
  stills, graded with the same `qa_scene`, and labelled as stills.
- **Everything moves.** Plate and type share one zoompan chain: even beats
  ease in to 1.025×, odd beats ease back to 1.0, punch beats ramp to 1.035×.
  At the bottom of the canvas that is up to ~31 px of displacement, which is
  why contrast is measured on encoded frames (a zoom-1.0 still samples the
  wrong rows after the first second) and why the credit scrim keeps headroom
  above the glyphs.
- FFmpeg ran with `-filter_complex_threads 1` on this box; the default is
  unchanged. CRF 22 → 7360 kb/s: a proof render, not a delivery master.
