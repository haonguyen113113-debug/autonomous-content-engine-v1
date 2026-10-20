# Hermes ↔ Autonomous Content Engine boundary

Status: target architecture agreed on 2026-10-19; API and payload contract are
not implemented yet. This document records the build direction, not a claim
that Hermes is already connected.

## Responsibility boundary

### Hermes owns

- Scheduled discovery of fresh soccer stories and supporting sources.
- Relevance and suitability assessment for Allen Knows Ball.
- Evidence-backed script drafting using a capable external agent/model.
- Packaging the approved-for-production draft in the versioned Engine input
  contract, submitting it, monitoring the job, and reporting the outcome.
- No publication credentials or publish action. The owner reviews the final
  video and publishes it manually.

### The Engine owns

- Validating the submitted contract and recording an idempotent production job.
- Resolving/selecting eligible media under existing qualification, rights,
  provenance, and purpose gates. The owner has authorized automatic saving of
  qualifying assets for workflow smoothness; that does not grant broader use
  rights or bypass those gates.
- Deterministic visual planning, template/Scene Graph execution, voice, render,
  and evidence-based QA.
- Exposing job status, artifacts, and QA results back to Hermes.

The Engine's target role is a production tool. It should not require an
in-process research agent or a local LLM to write scripts in the Hermes path.
Existing standalone/local drafting code may remain available during migration,
but it is not the target orchestration path.

## Target flow

```text
Hermes schedule
  → discover and assess stories
  → gather evidence and draft structured script
  → validate input contract
  → submit Engine job
  → Engine validates, resolves assets, plans, voices, renders, and runs QA
  → Hermes monitors and reports video + QA to owner
  → owner reviews and publishes
```

## Contract requirements to build

Use a versioned JSON Schema at the boundary. At minimum it must identify:

- `schema_version`, `idempotency_key`, channel/domain, and `content_type`
  (`short` or `long`).
- Topic and a research packet with source URLs, publication/retrieval dates,
  claim-to-evidence references, and any uncertainty that must remain visible.
- Ordered beats with narration, target duration, evidence references,
  semantic `beat_intent` only, and constrained `graphic_data` supported by the
  selected template.
- Asset needs as semantic requests. Do not accept model-authored layout,
  coordinates, typography, colors, motion, or transitions as instructions.
- An explicit destination/purpose for rights checks and render policy.

The Engine must validate independently even when Hermes or a delegated agent
claims to have emitted schema-valid JSON. Invalid or unsupported input should
fail with field-level errors and must not enqueue a partial job.

## API/job lifecycle to implement

The current local queue (`POST /api/content/batch-runs`, `GET /api/jobs`) is a
draft-job interface, not yet the Hermes production contract. Build a dedicated
versioned production-job API or evolve it explicitly; do not silently change
the existing payload semantics.

The production interface needs:

1. An authenticated submit operation that validates the complete payload,
   honors the idempotency key, and returns a stable job ID.
2. A read-only status operation for Hermes to poll, with explicit states such
   as `accepted`, `validating`, `resolving_assets`, `rendering`, `qa_failed`,
   `ready_for_owner_review`, and `failed` (final vocabulary to be frozen with
   the schema).
3. A result containing the rendered artifact location, run ID, QA verdict and
   criterion evidence, warnings, and actionable failure details.
4. Optional completion webhook after polling works; delivery must be
   authenticated and retry-safe.

Only a QA-ready artifact should be reported as ready for owner review. A
`NEEDS_REVIEW` result must remain visibly non-ready until its required review
is completed. No endpoint should publish to a platform.

## Runtime and deployment

- Run Hermes as the outer coordinator and the Engine/API plus queue worker as
  local processes on the production PC.
- Docker/Compose are removed from the repository. The queue worker remains a
  normal Python process started with `python -m apps.worker.main`.
- Keep the API narrow and authenticated. Hermes should receive only the
  permissions needed to submit jobs and read status/results, not unrestricted
  shell access or platform-publishing credentials.
- No Docker replacement, cloud deployment, or API implementation is implied
  by this architecture note.

## Rollout gates

1. Freeze and validate the versioned script/research JSON contract.
2. Implement API submit/status and connect it to the existing durable queue.
3. Run a fixture job end to end, including asset gates, render, and truthful QA.
4. Connect Hermes in draft/render/report mode; owner remains the publisher.
5. Start scheduled runs only after the known same-beat motion smoke failure is
   fixed and the visual output has been reviewed by the owner.

The latest repository checkpoint reports a smoke-test failure where frames at
3s and 8s within the same beat are identical. No newer completion report has
been verified in this checkout; treat that issue as open until rerun and
confirmed fixed.
