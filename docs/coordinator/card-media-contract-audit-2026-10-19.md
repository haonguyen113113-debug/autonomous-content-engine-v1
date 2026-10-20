# Card and media contract audit — 2026-10-19

## Purpose of this checkpoint

The next build session must first make card usage explicit and executable. The
current issue is broader than a renderer defect: the repository has a released
Template Foundation pack and many starter cards, but it does not yet have one
authoritative contract that tells the planner and renderer how each card may
receive and display variable Asset Library media.

This is an audit and handoff only. No implementation or tests were performed
for this checkpoint. Preserve the existing dirty worktree; do not reset, clean,
revert, or overwrite it.

## Repository snapshot and preservation

- Repository: `C:/Users/Infomation Technolog/Desktop/autonomous-content-engine-v1`
- Branch/HEAD observed: `main` / `50cf709`
- Existing modified files when this audit started: `apps/video_renderer.py`,
  `docs/ENGINE_STATE.md`, `docs/coordinator/PROGRESS.md`,
  `docs/coordinator/STATE.json`, `docs/coordinator/tasks/R4-final-gate/packet.md`,
  `tests/test_card_selector.py`, `tests/test_scene_graph_pipeline.py`, and
  `tools/ace_state.py`.
- No implementation files were changed for this audit. No tests or renders were
  run. No commit or push was made. `runtime/` was not modified.

## Main finding

There is no complete, authoritative **per-card media contract**. Existing
media behavior is split across the card registry, Template Foundation prose,
mode-based selector rules, generic Scene Graph roles, and hard-coded renderer
branches. Those pieces do not agree on a declared media slot tied to a card ID
and a concrete placement contract.

This means the useful question is not only “can the renderer draw an image?”
Some branches can. The missing contract is what lets the system decide, before
rendering, which card accepts which kind of media, what role that media plays,
where it goes, how it is fitted, what makes it suitable, and what happens when
it is absent or invalid.

## Binding architecture rule: composition is authored before rendering

The renderer is **not** an image-composition or image-selection system. It must
not invent image areas, draw illustrative imagery, choose an Asset Library
candidate, decide a crop/focal point, or add extra text outside the card's
authored text regions.

The intended flow is:

`Template Foundation card contract -> Visual Planner binds eligible Asset Library asset -> Scene Graph freezes card, media slot, asset, and text values -> Renderer places them in the authored regions`

- The **card/template contract** defines fixed media and text regions, their
  roles, geometry, fit/crop rules, typography, and allowed behavior. These are
  part of the versioned Template Foundation; runtime media must not move them.
- The **Visual Planner** chooses among Asset Library candidates using the
  beat's semantic intent, card requirements, visual suitability, and the
  use-scoped rights result. It freezes the selected card, media-slot binding,
  and supplied text values into the Scene Graph. If no eligible asset or
  required data exists, it follows the declared fallback or fails planning;
  it does not ask the renderer to improvise.
- The **Renderer** executes the frozen contract only: insert the bound asset
  into its named, predesigned media region and render supplied text into named,
  predesigned text regions. It may perform the contract's deterministic
  technical fit/crop operation, but may not choose or reinterpret the region,
  asset, layout, typography, or wording. It must not create generic title,
  caption, credit, or decorative text unless those are explicit authored
  regions and values in the contract/Scene Graph.
- **QA** checks the actual rendered result against those frozen regions and
  values. A renderer-generated fallback image or extra text is not an
  acceptable substitute for missing planner output.

The card-level media contract therefore describes **where and how an already
selected asset is inserted**, not permission for the renderer to design a new
composition. A fixed pack background is Template Foundation artwork, not a
runtime Asset Library image.

## Evidence checked

### 1. Card registry describes data slots, not media slots

`apps/studio_templates/card_registry.py` lists 90 starter cards. The four
short/long player spotlight entries (C-04, MR-08, BP-03, LC-11) mention a
“portrait slot” in `purpose`, but their declared `slots` contain only
`player_name` and `stats`. There is no structured slot with a media role,
asset type, geometry, fit mode, focal point, or fallback policy.

Most other cards declare text/data slots such as `hook_text`, `score`,
`metrics`, `source`, and `moments`; these say nothing about whether that card
can accept an illustrative image or footage.

### 2. Starter JSON images are fixed pack artwork

The `apps/studio_templates/*.short.json` files commonly contain a full-canvas
`image` child whose `src` points to a pack background such as
`short-score_card.jpg`, `short-hook_card.jpg`, or
`short-player_poster_side.jpg`. These are bundled template backgrounds. They
are not variable media slots bound to Asset Library candidates. The inspected
starter JSONs did not expose a structured `media_slot`/asset-binding contract.

### 3. Template Foundation has partial portrait intent, but not an executable slot contract

`template_foundation/templates/allen-knows-ball/12.0.0/graphic-templates.json`
has a global `identity_slots` note saying player cards have one fixed portrait
slot. The `player_poster_side` layout lists `player_name` and `stats` as
required data and defines boxes for those text/data fields, but it does not
declare portrait as a typed media slot with bounds, crop/fit behavior, focal
point, or required/optional status. `pack_bg: true` marks fixed pack artwork;
it does not itself define a variable photo region.

### 4. Selector and renderer support is mode-based and implicit

`apps/card_selector.py` defines `PORTRAIT_MODES` and attaches a matched library
image for a named player. It also forces a bound asset into `media_b_roll`
outside those portrait modes. The binding is keyed to visual mode rather than
to a declared media slot on the selected card.

`apps/video_renderer.py` has at least two separate hard-coded image behaviors:

- `media_b_roll` places a contained image in a fixed region and adds caption,
  creator/license credit, and an illustrative-image disclaimer.
- Player-card aliases use `media_file` in a split portrait composition, with a
  fixed crop/centering rule and a typographic fallback.

These are real rendering capabilities, but the card contract does not describe
them as reusable, validated media slots. A caller cannot inspect one card's
declared requirements and reliably know which behavior it will receive. Their
current implicit placement/crop logic is precisely the kind of composition
that must move behind authored card regions and a frozen planner binding; the
renderer must not retain independent image/layout decisions.

### 5. Scene Graph media roles are generic, not card placements

`apps/scene_graph/schema.py` validates generic asset references under
`roles.hero_image` and `roles.player_focus.portrait`. `builder.py` decides
between those roles from `visual_mode` and a hard-coded portrait-mode set. The
graph records asset identity/rights metadata, but there is no reference from a
media role to a template card slot/zone and no frozen crop/fit/placement
contract. The executor's media-b-roll path also requires resolution through a
separate renderer helper.

## Interpretation: pack exists, usage system is incomplete

The Template Foundation supplies a stable visual identity and fixed card
artwork. That does not, by itself, teach the engine how to use each card
effectively. The missing bridge is an explicit card contract and deterministic
composition plan that connects:

`card ID + authored text/media regions + planner-selected asset binding + frozen values + deterministic execution`

Therefore, visible failures such as a missing/poorly placed image, generic
background, awkward crop, or insufficient visual variety should not
automatically be classified as “the renderer is broken.” First determine
whether the selected card declared an applicable media slot and whether the
planner supplied a valid binding and placement. Renderer defects should be
filed only when it fails to execute a valid frozen contract.

This does not clear existing renderer issues or imply the current output is
good. It identifies the upstream contract gap that prevents consistent use of
the released pack.

## Design decisions to settle before implementation

The next session should draft and agree a versioned card/media schema before
parallel edits. At minimum, decide:

1. **Slot identity and role:** e.g. `hero_photo`, `player_portrait`,
   `supporting_photo`, `badge/logo`, `footage_window`; distinguish fixed pack
   background art from variable Asset Library media.
2. **Applicability:** which card IDs/layouts support each slot; whether the
   slot is required, optional, or forbidden for a card.
3. **Geometry:** normalized or pixel bounds, safe area, shape/mask, z-order,
   overlap rules, and relation to the card's authored text boxes.
4. **Fit and crop:** `contain`/`cover`/other approved behavior, focal-point
   support, min resolution/aspect ratio, and whether upscaling is allowed.
5. **Asset constraints:** image vs video support, subject/entity match,
   freshness/relevance, quality, and whether generic contextual imagery is
   allowed for the role. Do not present generic imagery as match footage.
6. **Rights/provenance:** bind the selected asset reference and use-scoped
   clearance/credit requirements into the composition/Scene Graph; keep rights
   eligibility separate from visual suitability.
7. **Fallback:** deterministic behavior when a slot has no eligible candidate
   (approved alternate card, intentional pack-only composition, or planning
   failure); never silently invent media or pretend a slot was filled.
8. **Renderer boundary:** planner freezes slot binding and resolved placement
   semantics; renderer inserts the frozen image and text into predesigned
   regions only. It does not select assets, create image regions, add extra
   text, or independently choose card, asset, crop intent, or geometry.
9. **QA:** verify actual rendered media presence, bounds, crop, overlap with
   text, safe margins, contrast/readability, timing for footage, and required
   credit/disclaimer. Asset presence alone is not a visual PASS.

Prefer one source of truth or a generated/validated projection across the card
registry, Template Foundation, and Scene Graph. Avoid three hand-maintained
lists that can drift again.

## Recommended next-session sequence

1. Re-check branch, HEAD, worktree, and all concurrent session changes. Keep
   the current dirty files intact.
2. Read this checkpoint plus `docs/ENGINE_STATE.md`, the relevant
   `scene-graph-contract.md`, and Template Foundation architecture docs.
3. Produce a read-only inventory mapping every built card to: text/data slots,
   fixed pack imagery, variable media support (yes/no/partial), media role,
   and actual renderer path. Use `unknown/partial` where code and pack disagree.
4. Agree the versioned media-slot contract and compatibility/migration rules
   before implementation.
5. Implement a small representative vertical slice first: one player portrait
   card with an authored portrait region, one score/stat card with an authored
   media region only if its design calls for it, and one editorial card with
   an authored image region. Prove the planner chooses/binds the asset and the
   renderer only fills that frozen region, with no renderer-invented layout or
   text.
6. Add structural tests for contract consistency and focused render tests for
   actual placement/crop/fallback. Do not claim aesthetic QA without inspecting
   produced frames/video.
7. Expand the contract across the remaining cards only after the vertical
   slice works; then revise card selection so it chooses among cards whose
   data and media requirements can actually be satisfied.

## Scope guardrails

- This checkpoint is not authorization to rewrite the renderer or redesign
  the released pack wholesale.
- Preserve the channel identity and fixed pack backgrounds. Add variable media
  only where a card contract explicitly permits it.
- Images come from the Asset Library and are selected/bound before rendering.
  The renderer may insert them only into predesigned card regions; it must not
  draw or invent image composition. Text may appear only in predesigned text
  regions with values supplied by the plan/Scene Graph.
- Do not assume every card needs a photo. Some cards should remain typographic,
  statistical, tactical, or source-led.
- Keep short-form editorial/news content distinct from tactical-analysis
  content; do not inject tactical diagrams into a short card unless its card
  contract and content purpose explicitly call for one.
- Do not commit/push unless the owner explicitly asks.
