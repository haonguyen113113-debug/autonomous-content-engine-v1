# Task packet template

Copy this file to `docs/coordinator/tasks/<task-id>/packet.md` and fill every
field. The worker reads this file, not chat history.

## Task

- task_id:
- goal (one paragraph, observable outcome):
- repo_root: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- worktree_or_branch:
- agent: `@ace-implementer` with model `opencode/nemotron-3.5-super-vl-free`

## First reads (in order)

1. `docs/ENGINE_STATE.md`
2. Linked decision or audit doc for this task:
3. Frozen contracts in `docs/coordinator/contracts/` (list versions):

## Allowed files (disjoint — no overlap with other active tasks)

- ...
- ...

## Forbidden paths (always)

- `runtime/`, `.env`, credentials, voice recordings, generated renders
- `docs/ENGINE_STATE.md` (coordinator owns this file)
- Any file owned by another active task

## Architecture constraints (repeat in every packet)

- Template Foundation is stable channel identity; Asset Library supplies
  variable media and never owns the template.
- LLM proposes semantic beat intent only (visual goal, focal subject,
  evidence type, emphasis, conceptual motion). No pixels, font sizes, color
  codes, or layout coordinates from the model.
- Deterministic Visual Planner maps intent plus suitable and approved assets
  plus the pinned template to a versioned Scene Graph. Same inputs and
  versions yield the same plan.
- Renderer consumes the Scene Graph. Pillow may render static layers but must
  not hide layout or storytelling decisions.
- Rights eligibility is per proposed use and upload scope, separate from
  visual suitability. `verified` is not blanket permission. Copyright
  exceptions need human review; the model cannot approve them.
- YouTube is discovery links only. Never download its video as an asset or
  infer usage rights.

## Acceptance checks

- [ ] Focused tests to run (exact command):
- [ ] Contract version recorded in code or artifact:
- [ ] Determinism check (if planner): same inputs rerun yields same graph:
- [ ] Render inspection (if renderer): frames or contact sheet path inspected:

## Report

- Write to: `docs/coordinator/tasks/<task-id>/report.md`
- Include: files changed, contract versions used, exact test command and
  result, render evidence path if any, remaining risks.
- After writing the report, run `python tools/ace_state.py --write` so the
  next worker gets a fresh STATE.json, then stop.
- Do not commit, push, publish, or buy a service. Stop after refreshing state.
