---
description: Show ACE live status — tasks, contracts, renders, freshness
agent: ace-coordinator
model: opencode/nemotron-3.5-super-vl-free
subtask: false
---

! `python tools/ace_state.py --check`
! `python tools/ace_state.py --json`

Summarize in Vietnamese: which tasks are PACKET_READY / IN_PROGRESS / DONE /
BLOCKED, contract versions, latest renders, whether state is FRESH or STALE,
and the single next dispatch. Keep it under 15 lines. Do not research further.

