# ACE Coordinator — inbox / outbox / reports

This directory is the handoff surface between the external coordinator (Cline)
and the Nemotron workers inside OpenCode. Workers never take assignments from
chat history; they take them from a packet file here.

## Layout

- `contracts/` — frozen shared contracts. Workers implement against these
  versions only. The coordinator freezes them before parallel work starts.
- `tasks/<task-id>/packet.md` — one assignment per worker: goal, worktree or
  branch, allowed files, forbidden paths, contract versions, acceptance
  checks, report path.
- `tasks/<task-id>/report.md` — worker output. The worker writes this and
  stops. It never rewrites `docs/ENGINE_STATE.md`.
- `reviews/<task-id>.md` — reviewer findings with severity, confidence, and
  file or frame evidence.

## Rules

1. One task owns one disjoint file set. No two active tasks share an
   implementation file.
2. Only the coordinator writes packets and updates `docs/ENGINE_STATE.md`.
3. Only the assigned worker writes inside its `report.md` and its allowed
   files.
4. `runtime/`, `.env`, credentials, voice recordings, and generated renders
   are off-limits unless the packet explicitly allows them.
