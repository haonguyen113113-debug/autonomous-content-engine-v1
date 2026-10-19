# Coordinator runbook — how to dispatch Nemotron workers in OpenCode

You are the coordinator. Nemotron 3.5 Super VL (cloud, free via OpenCode)
does the implementation. This repo is the shared truth.

## 0. One-time setup (already done in this checkout)

- `opencode.json` pins model `opencode/nemotron-3.5-super-vl-free`,
  default agent `ace-coordinator`, instructions, and deny rules for
  `runtime/**` and `.env`.
- `.opencode/agents/` holds `ace-coordinator`, `ace-implementer`,
  `ace-reviewer`.
- `docs/coordinator/` holds contracts, task packets, and templates.

## 1. Open the right project

OpenCode Desktop must open this exact root:

- `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`

Do not run tasks from `Documents/Default Project` or its copies
(`autonomous-content-engine-v1`, `autonomous-content-engine-v1-main`).
Those are stale duplicates the earlier agents touched. Archive or delete
them after verifying nothing unique is inside.

## 2. Pre-flight (coordinator, every workstream)

1. Read `docs/ENGINE_STATE.md` plus the linked audit doc.
2. `git status --short`, `git worktree list`, `git log --oneline -3`.
3. Confirm the five contracts in `docs/coordinator/contracts/` are still
   v1.0. If a change is needed, freeze a new version before dispatching.

## 3. Dispatch (one message per worker, sequential or parallel)

Paste per worker, replacing `<ID>`:

```text
Read docs/coordinator/tasks/<ID>/packet.md and follow it exactly.
Use @ace-implementer with model opencode/nemotron-3.5-super-vl-free.
Work only in the allowed files. Write docs/coordinator/tasks/<ID>/report.md and stop.
```

Start with W1 alone (it is the rights gate others depend on), then run
W2/W3 in parallel, then W4 last (it consumes W3's graph).

## 4. Review gate (before any integration)

```text
Read docs/coordinator/REPORT_TEMPLATE.md and docs/coordinator/tasks/<ID>/report.md.
Use @ace-reviewer with model opencode/nemotron-3.5-super-vl-free.
Audit the diff, contract versions, and rendered evidence.
Write findings to docs/coordinator/reviews/<ID>.md.
```

## 5. Integrate (coordinator only)

1. Merge worktrees in dependency order W1 → W2/W3 → W4.
2. Run the focused tests named in each packet plus a full
   `python -m pytest tests/ -q`.
3. Inspect at least one render (frames or contact sheet) before claiming QA.
4. Update `docs/ENGINE_STATE.md` with verified commit and branch,
   completed work, remaining work, decisions, tests, and next step.
5. Never commit, push, publish, or buy a service unless the owner asks.

## 6. If workers drift

- Wrong directory → stop, re-point to the Desktop repo root, restart packet.
- Overlapping files → stop both, re-split ownership, reissue packets.
- Contract change request → freeze a new contract version first, then
  reissue affected packets.
- Uncertain QA → verdict `NEEDS_REVIEW`, never `PASS`.
