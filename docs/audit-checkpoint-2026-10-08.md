# Engine audit checkpoint — 2026-10-08

## Why this checkpoint exists

This document captures the owner's audit and agreed direction before the next
implementation session. It is a planning checkpoint only: no production code,
runtime records, or Asset Library contents were changed to create it.

## Current product goal

Connect the existing pieces into a dependable, reviewable content workflow for
the first proving category: Soccer for a Vietnamese-speaking audience, under
the **Allen Knows Ball** channel identity. The goal is no longer to harden the
foundation in isolation. The engine should turn an approved brief into a
coherent video using a stable Template Foundation and relevant, rights-aware
media selected through the Asset Library. The owner retains the final decision
on external assets and their use.

Short-form remains the near-term proving path; long-form remains a later,
stronger stress test on a more capable PC. Voice quality is deliberately not
the focus of this audit checkpoint.

## Audit findings to address

1. **Asset Library media is too sparse and weakly illustrative.** Current
   discovery is too narrow, results lack enough variety and exact narrative
   context, and video footage is missing from the useful workflow. Continuous
   production requires a fresh mix of stills and footage with enough visual
   value to support the script.
2. **Rendered layouts have many errors.** Composition, placement, timing, and
   the relationship between narration and visuals need systematic inspection
   and correction.
3. **The workflow requires too much manual intervention.** The agent should
   carry out research, planning, matching, composition, and QA automatically
   where deterministic and safe, while leaving consequential asset-use
   decisions to the owner.
4. **Aesthetic quality is far below the channel target.** More templates alone
   will not solve this. Scenes need a varied visual grammar, stronger rhythm,
   meaningful real media, and a clear hierarchy without a repetitive card
   treatment or generic “cinematic AI” effects.

## Architecture direction

Move the visual decision-making out of renderer-specific drawing code and make
the composition an explicit, inspectable artifact:

```text
Content brief
  → research and script plan
  → beat timeline
  → asset planner + deterministic visual planner
  → Visual Scene Graph / composition spec
  → renderer
  → FFmpeg output
  → structural, semantic, visual, temporal, and brand QA
  → owner review
```

The model should express semantic intent (what the viewer needs to understand,
the evidence type, focal entity, emphasis, and needed motion). A deterministic
planner should choose the visual grammar and composition. The renderer should
render that plan; it should not invent the story or make unsupported editorial
decisions.

Use a small set of distinct visual grammars under one channel identity, for
example editorial, tactical, statistical, documentary, and fast-hook. A beat
should carry purpose, duration, evidence/asset needs, text, motion, transition,
and audio role. The system should vary composition to fit the story rather than
forcing every beat into a framed card.

Ollama/local LLM belongs in research, script planning, classification, semantic
visual intent, and QA support. It should not control low-level renderer
coordinates or draw the output itself.

## Visual planning and rendering principles

These are design constraints for the visual architecture:

- **LLM outputs semantic beat intent only.** It may propose the visual goal,
  focal subject, evidence type, and emphasis. It must not author pixel
  coordinates, font sizes, or color codes.
- **Visual Planner makes composition deterministic.** It resolves semantic
  intent against available/approved assets and the pinned Template Foundation.
  The same inputs and versions should produce the same composition plan.
- **Scene Graph records semantic roles and timing.** Use roles such as
  `hero_image`, `data_chart`, `player_focus`, `headline`, and `source`, with
  their timing, motion, and transitions. The graph is the inspectable contract
  between planning and rendering, not a dump of drawing commands.
- **Renderer turns Scene Graph into pixels and motion.** Pillow can remain a
  suitable implementation for some static layers. The architectural boundary
  matters: visual grammar and layout decisions live in the planner/template
  layer, not as hidden renderer-specific storytelling logic.
- **Visual grammar provides variation; Template Foundation preserves identity.**
  Editorial, tactical, statistical, documentary, and hook grammars can coexist
  under the same channel identity and design tokens.
- **QA inspects the rendered scenes.** Presence of an asset in the final video
  is not enough for a pass. QA should evaluate whether the rendered asset
  supports the narration, whether text is clipped, whether visual density is
  appropriate, and whether visual timing follows narration. Where automatic
  QA cannot judge reliably, it should flag the scene for owner review rather
  than report a false pass.

## Asset Library research conclusions to preserve

- The fact that football channels visibly use match footage does not establish
  that a given clip is permitted for reuse. Some publishers may have licenses,
  deals, tolerated claims, or different risk decisions.
- Platform monetization/reused-content rules and copyright permission are
  separate questions. Attribution or a disclaimer does not itself grant rights,
  and there is no universal “safe number of seconds.” Legal exceptions vary by
  jurisdiction; US fair-use concepts must not be presented as a Vietnam-wide
  rule.
- Free stock sources can add useful generic football imagery and motion, but
  may not supply exact match/player evidence. Licensed sports footage requires
  a provider or explicit license scope. No paid provider or purchase should be
  introduced without an owner decision.
- Expand discovery through provider adapters and support both still images and
  video. Preserve source/provenance and evidence. Score candidates on narrative
  relevance, subject/competition exactness, freshness, visual quality,
  technical suitability, motion/shot variety, and the beat they can support.
- Keep rights eligibility separate from visual suitability. Record basis,
  allowed platform/territory/monetization/purpose, term, transformation and
  attribution requirements, and license evidence. Unknown, expired, or
  incompatible rights should not silently become approved use. Exceptional or
  uncertain cases go to owner review; an LLM must not approve legal status.
- The library can discover, rank, and explain candidates. The owner remains the
  final decision-maker for saving and using external assets.

These conclusions align with the existing boundary in
`template-foundation-architecture.md`: Template Foundation is the stable,
versioned channel identity; Asset Library supplies variable, approved media.

## Asset Library architecture decisions

The owner proposed the following concrete architecture. Treat these as design
requirements for the next Asset Library work, not as implementation already
completed:

1. **Multi-source, multi-format discovery.** Discover still images and video
   from open sources; provide adapters for stock-video catalogs and licensed
   footage libraries. YouTube can be used to discover and link to a source, but
   downloading/reusing a YouTube video must not turn it into an Asset Library
   asset with presumed usage rights.
2. **Rights scope belongs to each intended use.** Capture the basis for use,
   license/evidence source, platform, territory, commercial/monetized purpose,
   validity period, editing rights, attribution requirements, and clip-length
   limits. “Rights checked” is not a blanket approval: suitability must be
   evaluated for the specific video and upload target.
3. **Visual value is scored separately from rights.** Rank narrative/topic,
   match/player exactness, recency, whether the action actually illustrates
   the narration, image quality, duration, camera angle, and shot diversity.
   Generic football footage must be labeled and must never be presented as
   footage from the match under analysis.
4. **Candidate board precedes ingestion and rendering.** The engine discovers,
   filters, scores, and presents options with preview, license, credit, and
   scope warnings. The owner decides which candidates are saved or used. The
   renderer accepts an asset only when its rights scope matches the selected
   upload objective. Copyright-exception/fair-use theories follow a separate
   human-review path; an LLM cannot conclude that a video is fair use.

The candidate record should therefore keep at least three distinct concepts:
discovery/provenance, visual suitability for a beat, and rights eligibility
for a specified use. Owner approval of one candidate/use should be recorded
with that scope and must not silently expand to other platforms, territories,
purposes, or future uploads.

## Work sequence for upcoming sessions

### 1. Broaden and improve Asset Library discovery

- Inventory current provider coverage and image-only assumptions.
- Add source adapters for meaningful image and footage coverage, including
  free/open sources and optional stock integrations where practical.
- Make video candidates first-class: preview metadata, duration, thumbnail,
  source, rights evidence, and suitability for a specific beat.
- Improve query expansion and candidate ranking for exact football context,
  variety, freshness, and aesthetic usefulness.
- Preserve the human save/use decision and rights review gate.
- Treat YouTube as a source-discovery/link surface only, not a downloader or
  rights-clearing path.
- Put external candidates on a review board before ingestion; show preview,
  provenance, visual score, license/credit details, and use-scope warnings.
- Require a use-specific rights match for the selected upload objective before
  a candidate can enter the render composition. Keep exception-based use in a
  separate human-review state.

### 2. Introduce an explicit visual planning contract

- Define versioned schemas for beats, semantic visual intent, asset
  requirements, composition/scene graph nodes, motion, and transitions.
- Map visual modes to distinct grammars deterministically.
- Keep plan generation inspectable and reproducible by recording schema,
  planner, template, asset, and renderer versions.

### 3. Connect approved media and scene graph to rendering

- Render approved stills and footage in the relevant scene slots.
- Resolve timing, crop, safe areas, overlays, and transitions from the scene
  graph and pinned Template Foundation.
- Retain tactical/data graphics as explanatory evidence when real footage is
  unavailable or would not communicate the claim as clearly.

### 4. Fix layout and build layered QA

- Structural: dimensions, frame rate, duration, safe area, fonts, audio,
  missing/invalid media.
- Semantic: narration/claim ↔ evidence ↔ selected asset and chart data.
- Visual: readability, overlap, hierarchy, contrast, density, and scene
  variation.
- Temporal: narration/visual alignment, transition timing, dead frames, and
  motion completion.
- Brand: pinned template identity, palette, typography, opening, and ending.
- Add visual-density feedback that identifies scenes as too empty, balanced,
  dense, or overloaded; treat it as a review signal until calibrated against
  owner-approved examples.

### 5. Run an owner-audited short-form iteration

Use a real Soccer/Vietnamese brief and approved media. Inspect the scene graph,
candidate choices, render, and QA report in sequence. Record concrete defects
and fix them at the responsible layer instead of compensating with manual
renderer edits. Once short-form is dependable, run the long-form stress test on
the stronger PC.

## Acceptance checkpoint

The next proving run should demonstrate that the engine can, from a brief:

- find a varied set of relevant still and video candidates and explain why
  each supports a beat;
- clearly show provenance and rights status without silently approving use;
- build a reviewable beat timeline and deterministic scene graph;
- render selected, owner-approved media with correct layout, timing, and
  transitions under the pinned channel template;
- produce layered QA findings that catch the observed layout, media, semantic,
  temporal, and aesthetic failures;
- complete with limited owner intervention while keeping asset-use decisions
  with the owner.

This is a staged target, not a claim that the current engine already passes it.

## Related project documents

- `docs/template-foundation-architecture.md` — boundary and lifecycle of the
  fixed channel template.
- `docs/template-research-adaptation.md` — visual references and current
  renderer/template capabilities and limits.
- `docs/transferable-runtime.md` — portable local runtime and known render
  constraints.
