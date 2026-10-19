# Autonomous Content Engine — project instructions

## Start every session with the current project state

Before planning or editing, read `docs/ENGINE_STATE.md`. Then read the linked
decision/audit document relevant to the task. Treat the repository as the
shared source of truth; do not rely on chat history being available.

At the end of a workstream, the coordinating agent updates `docs/ENGINE_STATE.md`
with the verified commit/branch, completed work, remaining work, decisions,
test results, and the next concrete step. Parallel workers should report their
results to the coordinator and must not concurrently rewrite the state file.

## Product focus

- The first proving domain is Soccer for a Vietnamese-speaking audience under
  Allen Knows Ball. Keep the core mechanisms generic and put soccer knowledge
  in domain/configuration layers.
- Near-term proof is a reliable short-form workflow from brief through
  rights-aware media selection, composition, render, and honest QA. Long-form
  remains a later stress test on stronger hardware.
- The broader business portfolio in `PROJECT_SPEC.md` is the north star. Do
  not pretend the current video workflow implements it, and do not expand into
  every long-term subsystem before the proving slice is dependable.

## Non-negotiable architecture and product decisions

- Template Foundation is a stable, versioned channel identity. Asset Library
  supplies variable media; it does not own the template.
- External candidates are discovered and ranked before ingestion. The owner
  chooses whether to save/use them. YouTube may provide discovery links only;
  never download its video as an asset or infer usage rights.
- Rights eligibility is specific to a proposed use/upload scope and is
  separate from visual suitability. `verified` is not blanket permission.
  Copyright exceptions require human review; an LLM cannot approve them.
- The LLM proposes semantic beat intent only: visual goal, focal subject,
  evidence type, emphasis, and conceptual motion. It does not choose pixels,
  font sizes, color codes, or concrete layout coordinates.
- A deterministic Visual Planner maps intent, suitable/approved assets, and a
  pinned template to a versioned Visual Scene Graph. The same inputs and
  versions should yield the same plan.
- The renderer consumes the Scene Graph and renders it. Pillow may render
  static layers, but layout/storytelling decisions must not be hidden in the
  renderer.
- QA evaluates the rendered scenes, not just intended inputs. Never report
  `PASS` based solely on an asset ID or expected code path. Use
  `NEEDS_REVIEW` when a judgment is uncertain.
- Visual grammars (editorial, tactical, statistical, documentary, hook) may
  vary within the channel identity. Do not solve weak aesthetics by merely
  multiplying templates or adding generic effects.

## Parallel work and repository care

- Agree on shared data/API contracts before parallel implementation. Assign
  distinct worktrees or disjoint file ownership where possible.
- Do not overwrite another worker's changes. Inspect Git status, active
  worktrees, and diffs before integration.
- Do not modify ignored `runtime/` data, `.env`, credentials, voice recordings,
  or generated renders unless explicitly requested.
- Run focused tests for changed behavior and report exactly what was run. Do
  not claim visual/render QA unless the resulting media was actually inspected.
- Do not commit, push, publish, or buy a service unless explicitly requested.

