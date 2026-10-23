# R4 — Final gate report

**Status: RUN twice; verdict still not PASS — render layer now clear, one
measurable FAIL (no real media) plus owner/human gates remain.**

**Date:** 2026-10-23
**Branch:** `arena/3a4ff34c-autonomous-content-engine-v1` (from `94078f5`)
**Run:** `4a4f0c1d2e3b` · template `12.2.0` · renderer `ace-ffmpeg-0.9.0`

This report replaces the 2026-10-20 "BLOCKED — do not render" state. That
state was correct for the read-only reviewer: R3 still had open blockers and
the reviewer could not change code. The M0–M3 roadmap changed the mandate —
it fixed the blockers at their responsible layer — so the gate was run, not
skipped.

## Result

| | |
|---|---|
| Fresh MP4 | `runtime/renders/4a4f0c1d2e3b/full-render.mp4` — 23,012,774 B, 25.000 s, 1080×1920, 30 fps, H.264 + AAC |
| Contact sheet | `runtime/renders/4a4f0c1d2e3b/contact-sheet.png` |
| Evidence | `runtime/renders/4a4f0c1d2e3b/gate-evidence.json` (schema `ace-r4-gate/1`) |
| Quality checks | **37 PASS** · **1 FAIL** · 10 NEEDS_REVIEW · 1 PARTIAL · 1 PENDING OWNER AUDIT · 4 NOT USED |
| Clip QA | **NEEDS_REVIEW** (only "narration fit" — silent WAV) |
| Encoded-frame contrast | hook **15.07** · reading **4.31** · conclusion **6.60** (floors 4.5 / 3.0 / 4.5) — all PASS |
| Recommended verdict | **FAIL (not cleared)** — S4.1 media + owner review + human eye |

Full grading table, five defects (F1–F5) and the unblock checklist:
`docs/coordinator/reviews/R4-final-gate.md`.

## The one-line version

The render layer now passes: every beat moves for its whole duration, contrast
is clean *on the encoded frames* (15.07 / 4.31 / 6.60 against floors 4.5 / 3.0
/ 4.5), text-fit is clean, and every declared text slot paints. What still blocks a PASS is **not code**:
no owner-approved media
(S4.1), no owner visual record for C-09 on 12.2.0, and no human on the contact
sheet / MP4 (speech is a silent placeholder).

## What changed since the BLOCKED report

| R3 blocker | Status after M0–M3 |
|---|---|
| S3.1 per-beat grammar not assigned | **Cleared at the planner**: 3 distinct modes, `grammar_variety_ok=true`; repetition is a hard gate and a variety breaker now blocks `production_ready`. |
| S3.5 / S4.2 no source-card beat | **Partly cleared**: C-09 executes the contract with visible claim + source + date; it is still `NEEDS_REVIEW` because no owner record covers 12.2.0. |
| S2.5 hook → evidence → attribution | **Needs a human** on the contact sheet; contrast (F2) now PASSes on the encoded frames at 15.07 / 4.31 / 6.60. |
| S5.2 headline wipe motion | **Motion fixed** (F1: per-beat frame-hash verified); `chalk_line_wipe` still maps to a 0.3 s slide, so S5 stays NEEDS_REVIEW. |
| S4.1 no owner-approved media | **Still open** — unchanged, needs a real asset + upload purpose. |

## Scope notes

- The packet pinned `12.0.0`; M1 shipped `12.2.0`, and the gate grades the
  pack the engine actually pins.
- The packet allowed only `runtime/renders/` + two docs and forbade code
  edits. This run was executed under the M0–M3 remediation mandate, which
  explicitly includes code changes; every code change is listed in the
  session diff and covered by the test suite (**674 tests**).
- The gate tool (`tools/r4_gate.py`) is committed so the run is reproducible;
  it writes only under `runtime/` and grades five beats (three encoded, two
  stills with the same `qa_scene`).

## Artifacts and references

- `docs/coordinator/reviews/R4-final-gate.md` — verdict package (S1–S5)
- `docs/coordinator/AUDIT_RUBRIC_STRICT_V1.md` — rubric graded here
- `docs/ENGINE_STATE.md` — Scene Graph default + remaining work

No publish, no platform upload, no real media was used.
