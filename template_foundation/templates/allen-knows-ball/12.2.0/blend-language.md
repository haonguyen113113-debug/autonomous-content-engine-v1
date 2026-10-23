# Blend design language v12 (rebuild from skills, no legacy HUD kit)
Source of truth for the 90-card rework. Every composition decision below
traces to one installed skill. The old cyber-HUD filler (perforation dot
rows, tick rulers, corner brackets, section rails, generic rings-as-texture)
is removed everywhere. Kept only: bed plate, slot-bound text, team
monogram rings (identity), winner bar (information), hero glow, pitch
motifs (stroke-only), portrait/wide slot markers (outline-only).

## Per-skill rules (applied, not cited)
- frontend-design: ground in night-broadcast football, not SaaS cards.
  One boss per frame. Structure encodes information (winner gets scale and
  the brighter half; loser dims). Cut one accessory per card. No eyebrow
  on every card; kicker only where the card's function needs orientation.
- canvas-design: plates carry 90 percent of the visual weight. Text is
  essential-only. Refine pass: remove, never add.
- broadcast-depth (lite, deterministic): top-light scrim veil behind text
  that fails contrast (black pill 0.45, seeded, recorded per card);
  hero glow behind the single hero numeral (palette color, blur 18);
  grain masked to field areas only, never over microcopy.
- design-taste: contrast measured per text zone on the real plate
  (boss 4.5, other 3.0); pre-flight per sprint (squint, 3 sizes, breaks,
  measured contrast); no AI slop (no gradient text, no identical grids,
  no em dashes, sentence-case microcopy).
- graphic-design-system: BOSS single biggest size, SUPPORT about 0.28x,
  WHISPER about 0.16x; room of one text line around the boss; safe area
  7/9/13/7; semantic breaks only.
- theme-factory: locked cyber palette only, presets never touch it.
- impeccable-lite: one committed direction; bounded verification
  (schema, slots, safe area, contrast probe, proofs, full pytest).
- algorithmic-art: seeded deterministic params (veil alpha, grain seed 7).
- emil-design-eng: unseen details compound (provenance whisper on every
  card whose slots require it); Before/After/Why review per sprint.
- polotno-sdk: schemaVersion 4, unique ids, every dynamic text has
  custom.slot, decor locked with full flags, bed first child full-bleed.
- Instruction S3: Vietnamese text only in Tektur or Be Vietnam Pro.
  Tagline TBD: no placeholder text ships anywhere.

## Slot zoning (empty space is a feature)
- Team badges: monogram rings only, seated in plate voids beside the
  score/duel/fixture they belong to. Real crests bind later without
  moving the slot. Never baked, never on data-free cards.
- Team/player names: set in the darkest empty band of the plate; veil
  only if the probe fails.
- Portrait slot: outline-only ring marker in the plate portrait void;
  no filled panel, no fake photo. Face-safe framing recorded per card.
- Wide slot (team/group/related image): outline-only frame + caption
  line; layout never reflows with or without the photo.
- Data (numbers, metrics, quotes): hero zone per family map; support
  and whisper stacked beneath at 0.28x/0.16x.
