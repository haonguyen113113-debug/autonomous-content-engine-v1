---
description: Dispatch next ACE worker with zero research — auto state + packet
agent: ace-coordinator
model: opencode/nemotron-3.5-super-vl-free
subtask: false
---

Live state (auto, do not re-derive):

! `python tools/ace_state.py --check`
! `python tools/ace_state.py --brief $ARGUMENTS`

Dispatch task $ARGUMENTS now:

1. Read `docs/coordinator/STATE.json` (already fresh per --check above).
2. Read `docs/coordinator/tasks/$ARGUMENTS/packet.md` and follow it exactly.
3. Invoke @ace-implementer pinned to `opencode/nemotron-3.5-super-vl-free`,
   restricted to the packet's allowed files.
4. Require the worker to write `docs/coordinator/tasks/$ARGUMENTS/report.md`
   then run `python tools/ace_state.py --write` and stop.
