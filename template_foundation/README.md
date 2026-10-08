# Template Foundation — channel packages

This layer owns stable channel personality and authored presentation. It is separate from `apps/asset_library`: football media can fill declared slots, but the library does not own the wordmark, fonts, visual language, timeline, or motion system.

## Current focus: Soccer / Vietnamese

The first channel is **Allen Knows Ball**, `vi-VN`, category `soccer`, market `VN`. The name is idiomatic as a casual sports-slang brand; keep the spelling and title case. The Vietnamese tagline is **“Bóng đá, nhìn thêm một nhịp.”** The initial editorial scope follows the Soccer proving domain: Premier League, UEFA Champions League, LPBank V.League 1, and Vietnam men's national team.

The `allen-knows-ball.shortform-analyst` package has three fixed story forms under one identity: a post-match moment read, a tactical explainer, and a player/role analysis. Its first output shape is portrait short-form video. Platform accounts and publishing integration are intentionally unspecified.

## Package status

Short and long-form versions `0.1.0` through `0.4.0` remain available as **draft for owner audit**. Version `0.5.0` builds on the four colorways and evidence-specific graphics with expressive Vietnamese headline hierarchy, condensed display numerals, angular match annotations, tactile texture, and brief kinetic reveals. Numeric layouts use only reviewed evidence and retain visible source attribution. Version `0.5.0` is a draft preview, not production-resolvable. Released package directories are immutable; edits create a new version.

`registry.resolve_template(root, template_id)` resolves released packages only. `allow_draft=True` is reserved for preview and owner review. The web UI's Templates page shows the draft label and the visual preview.

## Files

- `catalog.json`: channel/template identities and lifecycle state.
- `channels/allen-knows-ball/channel.json`: Vietnamese audience promise, host point of view, voice and editorial rules.
- `templates/allen-knows-ball/0.5.0/design-tokens.json`: Vietnamese headline roles, condensed stat numerals, motion, and touchline editorial language.
- `templates/allen-knows-ball/0.5.0/color-systems.json`: stable identity neutrals, four selectable colorways, team color behavior, and contrast rules.
- `graphic-templates.json`: use constraints and required evidence for tactical, statline, source, and chart layouts.
- `visual-modes.json`: story-led rules for openings, match evidence, tactical explanation, sourced metrics, citations, charts, and conclusion; exact-context media requires owner selection.
- `timeline.json` and `story-forms.json`: fixed production rhythm and the three soccer formats.
- `slot-contract.json`: variable football media needs. Approved assets may fill these slots; package-owned elements are explicitly excluded from Asset Library requests.
- `resources/`: wordmark and bundled open-licensed fonts with their OFL texts.
- `preview.html`: local visual review page for both aspect ratios, data graphic types, and colorways. Example numbers are explicitly labeled as illustrative; no match media is embedded.
- `LICENSES.json`: third-party font and future match-media policy.

No match footage, player likeness, club crest, competition mark, or music is included. Variable football media still goes through Asset Library provenance and the human choice gate.
