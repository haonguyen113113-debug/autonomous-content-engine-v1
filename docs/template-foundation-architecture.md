# Template Foundation — architecture proposal

## Purpose

Template Foundation supplies the engine's stable visual and audio language: type, opening and ending, transitions, effects, motion rules, title treatment, pacing, and output-safe areas. It is a versioned design system used to compose a particular content item. It is not a catalog of campaign imagery and it does not perform web discovery.

The foundation is intentionally changed infrequently. A content run pins an exact released version; everyday content production selects from that version without modifying it. Updates are deliberate design releases after preview and approval.

## Boundary with Asset Library

| Template Foundation | Asset Library |
| --- | --- |
| Stable, authored visual/audio building blocks | Variable media selected for a content need |
| Fonts, title styles, intro/outro, transitions, effects, motion and layout rules | Photos, footage, illustrations, narration, campaign-specific music |
| Versioned as a complete compatible package | Reuse-first inventory with provenance, context, rights and lifecycle |
| Chosen by template ID and pinned version | Queried by a resource requirement; may recommend or search externally |
| Updated deliberately and infrequently | Changes as approved assets are ingested or retired |

A template may declare slots that the composition workflow fills from the Asset Library. The library returns asset references and suitability evidence; it cannot change template rules. The template package can bundle fixed design resources (for example a licensed typeface or a signature sound), but those are immutable package dependencies with their own license/provenance records, not ordinary discoverable campaign assets.

## Package layout

```text
template_foundation/
  catalog.json
  templates/
    <template-id>/
      <semver>/
        manifest.json
        design-tokens.json
        timeline.json
        previews/
        resources/
        LICENSES.json
```

Packages are local and portable. A released directory is immutable; a change creates a new semantic version. `catalog.json` marks versions as draft, released, or retired. Existing runs continue to refer to their pinned package even after retirement.

## Package contract

`manifest.json` identifies the template, version, compatible renderer, intended channels and aspect ratios, supported locales, duration range, color space, frame rate, and required slots. The package also records creator, release date, and approval state.

`design-tokens.json` holds locked values such as font families and weights, type scale, colors, spacing, safe margins, corner treatment, shadow/effect parameters, and transition timing. Content workflows cannot override locked tokens.

`timeline.json` describes authored segments and permitted substitutions: opening, title/identity reveal, body, transition points, ending, and fixed effects. Slots have typed inputs (text, image, video, voice, optional music), crop/fit rules, character limits, timing windows, and fallback behavior. Slots accept references; they do not contain discovery logic.

Fixed resources are addressed by package-relative paths and listed in `LICENSES.json` with origin, allowed uses, required attribution, and license terms. Unlicensed or incompatible resources prevent release.

## Runtime flow

1. A content brief or user selects a template ID. The run resolves the current released version or accepts an explicit version pin.
2. The workflow creates a composition request containing the template pin, channel/output profile, content values, and typed slot requirements.
3. Asset Library evaluates only the variable asset requirements. The human reviews external candidates and decides whether to save or use them.
4. Composition fills slots without mutating the package. Locked design tokens and authored timeline segments remain unchanged.
5. The renderer produces a preview using the pinned package. Structural QA checks required slots, dimensions, safe margins, duration, typeface availability, and package compatibility; review checks legibility and visual quality.
6. A passing artifact records the template ID/version, asset IDs and versions, renderer version, and QA result. A failed artifact returns for correction or review without silently changing the template.

## Release and maintenance

Template editing belongs to a design-time workflow, separate from production runs. Drafts can be previewed against representative content and output sizes. A human approves a release; released packages are immutable. The owner may update the foundation on a long, deliberate cadence or when a real compatibility, accessibility, licensing, or brand need requires it. The engine never tunes the foundation from individual performance data.

A new major version is appropriate when the authored structure or slot contract breaks compatibility. Minor versions add compatible templates or slots. Patch versions correct a defect without changing the established slot contract. The release process should record a short change note and keep the prior version available for reproducibility.

## Minimal first slice

Start with one portrait short-video template and one horizontal adaptation only if the same authored system can support it cleanly. Define the package contract, create a single released visual system with an opening, title/body treatment, two transitions, a closing, and a small approved effect set. Add preview and package validation before connecting a renderer. Do not add automatic template generation, a marketplace, per-channel personalization logic, or learning-based style mutation at this stage.

## Deliberately separate from current Asset Library work

The current integration phase completes resource checking, multi-provider image discovery, and explicit human approval. Template Foundation should begin as a separate package and release lifecycle. The only integration is a typed boundary: template slots emit resource requirements, and the workflow passes resolved asset references back into those slots.

## Current instantiation: Allen Knows Ball

The first proving category is Soccer for a Vietnamese-speaking audience. The package lives under `template_foundation/`, outside the Asset Library code and runtime records. `Allen Knows Ball` is retained as the channel name: in casual sports slang, “knows ball” means the host understands the game. The Vietnamese audience promise is “Bóng đá, nhìn thêm một nhịp.”

The v0.1.0 package is a draft for owner audit, not a production release. It fixes the channel identity, Vietnamese voice rules, bundled fonts, palette, motion/effect limits, a 45-second portrait-video rhythm, and three closed soccer story forms. `slot-contract.json` defines only variable match/player media needs. The package's loader refuses draft packages by default; preview code must opt into draft resolution. No run is yet connected to a video renderer.
