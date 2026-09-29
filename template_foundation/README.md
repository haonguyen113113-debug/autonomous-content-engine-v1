# Template Foundation — channel packages

This layer owns stable channel personality and authored presentation. It is separate from `apps/asset_library`: football media can fill declared slots, but the library does not own the wordmark, fonts, visual language, timeline, or motion system.

## Current focus: Soccer / Vietnamese

The first channel is **Allen Knows Ball**, `vi-VN`, category `soccer`, market `VN`. The name is idiomatic as a casual sports-slang brand; keep the spelling and title case. The Vietnamese tagline is **“Bóng đá, nhìn thêm một nhịp.”** The initial editorial scope follows the Soccer proving domain: Premier League, UEFA Champions League, LPBank V.League 1, and Vietnam men's national team.

The `allen-knows-ball.shortform-analyst` package has three fixed story forms under one identity: a post-match moment read, a tactical explainer, and a player/role analysis. Its first output shape is portrait short-form video. Platform accounts and publishing integration are intentionally unspecified.

## Package status

Version `0.1.0` is **draft for owner audit**. It is previewable but not production-resolvable. Change `status` to `released` in both catalog and package manifest only after the owner approves this design. Released package directories are immutable; edits create a new version.

`registry.resolve_template(root, template_id)` resolves released packages only. `allow_draft=True` is reserved for preview and owner review. The web UI's Templates page shows the draft label and the visual preview.

## Files

- `catalog.json`: channel/template identities and lifecycle state.
- `channels/allen-knows-ball/channel.json`: Vietnamese audience promise, host point of view, voice and editorial rules.
- `templates/allen-knows-ball/0.1.0/design-tokens.json`: fixed palette, type, layout, motion, and audio direction.
- `timeline.json` and `story-forms.json`: fixed production rhythm and the three soccer formats.
- `slot-contract.json`: variable football media needs. Approved assets may fill these slots; package-owned elements are explicitly excluded from Asset Library requests.
- `resources/`: wordmark and bundled open-licensed fonts with their OFL texts.
- `preview.html`: locally rendered, self-contained design preview; its match scene is illustrative and contains no factual claim or match media.
- `LICENSES.json`: third-party font and future match-media policy.

No match footage, player likeness, club crest, competition mark, or music is included. Variable football media still goes through Asset Library provenance and the human choice gate.
