---
description: Dispatch sprint P0/R-task with zero research — auto state + packet
agent: ace-coordinator
model: opencode/nemotron-3.5-super-vl-free
subtask: false
---

Sprint 2-day render quality on 12.0.0 released. Old W-packets PAUSED
unless R1 proves a contract gap blocks render. P0 ports 12.0.0 first.

! `python tools/ace_state.py --check`
! `python tools/ace_state.py --brief $ARGUMENTS`

Dispatch task $ARGUMENTS now:

1. Read `docs/coordinator/STATE.json` (already fresh per --check above).
2. Read `docs/coordinator/tasks/$ARGUMENTS/packet.md` and follow it exactly.
3. P0 uses @ace-implementer to port 12.0.0. R1 uses @ace-implementer
   read-only + render. R2/R3 use @ace-implementer on short-form path
   only. R4 uses @ace-reviewer read-only.
4. Require report at `docs/coordinator/tasks/$ARGUMENTS/report.md`
   (R4 also writes `docs/coordinator/reviews/R4-final-gate.md`)
   then `python tools/ace_state.py --write` and stop.
