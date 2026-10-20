# C6 — Card media slot contract (authored regions for variable media) — v1.0

> **Superseded as the runtime contract by C7 v2.0**
> (`docs/coordinator/contracts/c7-card-contract.md`). The v1.0 media-slot rule
> and `player_portrait` geometry below remain frozen and are carried unchanged
> into `card-contract.json` schema 2.0. `card-media-contract.json` is retained
> as historical evidence only; the runtime reads `card-contract.json` and
> ignores the old file.

Status: frozen for worker tasks. Changes require coordinator approval.

## Rule

Variable Asset Library media may enter a card only through a media slot
declared by the pinned Template Foundation package. The planner binds an
eligible asset and freezes slot geometry, fit, focal point, mask, z-order and
fallback into the Scene Graph. The renderer paints the frozen asset into the
frozen region and nothing else.

Authoritative file (historical v1.0):
`template_foundation/templates/allen-knows-ball/12.0.0/card-media-contract.json`
(`schema_version` 1.0, `template_version` 12.0.0).
Executable source of truth from C7:
`template_foundation/templates/allen-knows-ball/12.0.0/card-contract.json`
(`schema_version` 2.0).

Loader/validator: `apps/studio_templates/card_media.py`. A present-but-invalid
contract raises; an older pack without a contract returns none (no fallback
slot is invented).

## Declared slots (v1.0)

| Card | Modes | Slot / role | Asset | Box (px on 1080×1920) | Fit | Focal | Mask | z-order | Fallback |
|---|---|---|---|---|---|---|---|---|---|
| C-04 | `player_card`, `player_poster`, `player_poster_side`, `player_poster_top`, `potm_card` | `player_portrait` | image | `[0, 282, 424, 1240]` | cover | `0.5, 0.30` | rounded_rect `[0, 52, 52, 0]` | after `bed-60` | `keep_pack_artwork` |
| MR-08 | same five | `player_portrait` | image | `[0, 282, 424, 1240]` | cover | `0.5, 0.30` | rounded_rect `[0, 52, 52, 0]` | after `bed-60` | `keep_pack_artwork` |
| BP-03 | same five | `player_portrait` | image | `[0, 282, 424, 1240]` | cover | `0.5, 0.30` | rounded_rect `[0, 52, 52, 0]` | after `bed-60` | `keep_pack_artwork` |

Slot subject rule: `depicts_named_player_only`. Minimum source: `400×400`.
The authored pack silhouette remains when no eligible portrait is bound.

## Planning and eligibility (fail-closed)

The planner binds a slot only when all of the following hold:

1. The card ID is declared by the contract for this template version, and the
   scene's visual mode is one of the declared modes.
2. The asset registry row's `asset_type` equals the slot's `asset_type`
   (`image` in v1.0).
3. The row is `rights_state == verified` **and** `lifecycle_state == active`.
4. The frozen ref carries `approval_status == approved`, derived from a
   persisted human-granted use scope (`rights_scope_json`). `verified` alone
   is never enough; deny-default scope stays `pending`.

Anything else produces an explicit `fallback` binding with
`proposed_asset_id` and a reason. The planner never invents a substitute asset
and never asks the renderer to improvise.

## Frozen graph shape

`graph["media_bindings"]` (starter graphs only) records exactly:

`slot_id`, `role`, `asset_type`, `layer_id`, `box_norm`, `box_px`, `fit`,
`focal_point`, `mask`, `min_source_px`, `qa`, `status`, `reason`,
`proposed_asset_id`, `asset`.

A `media-<slot_id>` design layer (`type: media_slot`) is inserted at the
contract's z-order anchor. Validation rejects: tampered box/geometry, extra
keys, a bound asset that is not `approved`/`library_image`, a fallback that
carries an asset, and a `media_slot` layer without a matching binding.

## Renderer boundary

- May perform only the contract's deterministic technical fit: `cover` crop
  around the frozen focal point, rounded-rect mask, minimum source size.
- Must not choose or replace the asset, slot, region, z-order, fit, focal
  point or wording; must not create text or decoration in the slot.
- A bound slot is resolved through both rights gates before painting. Any
  failure (pending approval, registry/file missing, scope denied) raises and
  blocks the render; the renderer never silently substitutes pack artwork.
- A fallback slot paints nothing, so the authored pack artwork remains.

## QA minimum

- `Media placement`: compare the rendered background layer against the
  pack-only baseline (same graph rendered with no media). A bound slot must
  change at least `qa.min_painted_fraction` (1%) of its box and change no more
  than `qa.max_outside_leak_pixels` (64) outside it. A fallback slot must be
  pixel-identical to the baseline inside and outside its box. A missing
  baseline is `NEEDS_REVIEW`, never `PASS`.
- `Media rights`: bound refs must resolve to `verified`/`active` images inside
  `runtime/assets/library` and pass the C1 use-scope gate. `pending` approval
  is `FAIL`. Fallback slots paint no image, so no licence is required for
  them.
- Asset presence alone is never a visual pass.

## Change control and non-goals

- Extending slots to other cards or modes, or changing geometry/fit/mask,
  requires a new contract version and pack release; do not edit regions in
  place or add renderer-only overrides.
- v1.0 declares images only. `video` is a schema value but no card uses it yet.
- Fixed pack beds are Template Foundation artwork, not variable media.
- Long-form portrait card `LC-11` is not yet contracted; long form remains a
  later stress test.
- The renderer never designs layouts, and the planner never emits pixel
  coordinates beyond selecting a declared slot.
