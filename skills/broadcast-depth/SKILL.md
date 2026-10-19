---
name: broadcast-depth
description: >-
  Faux-3D broadcast depth for offline PIL plates: light, shadow, grain, and
  atmosphere without Blender, GPU, or browser. Use when a flat 2D card needs
  to read as a lit broadcast frame — hero numerals with presence, fields
  with air, textures with craft. Deterministic (seeded), CPU-only, locked
  palette. Respects the brief: Vietnamese text stays in brand faces,
  safe areas, and slot contracts are never broken for decoration.
  <example>user: "This score card reads flat." assistant: applies
  broadcast-depth — vignette, grain, numeral glow and grass-pitch noise at
  seed 7, then re-proofs.</example>
  <example>user: "Make the duel card feel televised." assistant: uses
  broadcast-depth light direction + top-light gradient and touchline glow,
  keeps all data slots identical.</example>
---

# Broadcast Depth

Flat vector plates read as slides. Broadcast frames read as *lit spaces*.
This skill adds the light — never geometry that needs a GPU. Every technique
below runs in PIL on CPU, is seeded for reproducibility, and stays inside the
locked palette (grain/noise included: monochrome alpha over palette colors,
never new hues).

## The five moves (apply in this order, stop when it reads lit)

1. **Top-light gradient.** Broadcast light falls from above. Overlay a
   vertical white-to-transparent gradient (alpha 0→26) on the upper third of
   each field, and a black-to-transparent gradient (alpha 0→40) on the lower
   sixth. One light direction per card, always from the top.
2. **Hero glow.** The single memorable element gets one light treatment:
   duplicate the hero numeral in paper at low alpha, offset (0, +10), blur
   radius 18, composited *behind* the numeral. Glow color must be a locked
   palette color (paper on coral fields, coral on ink fields) — never white
   bloom, which reads as cheap plugin glare.
3. **Seeded grain.** Film grain is what separates "rendered" from
   "photographed." Add monochrome Gaussian noise (sigma 5–7) masked to
   35–45% strength over field areas only — never over small body text or
   provenance microcopy, where it harms legibility. Seed every grain pass
   (e.g. seed 7) and record the seed next to the proof so re-renders match.
4. **Atmosphere bands.** Two or three horizontal translucent bands (palette
   color at 6–10% alpha, 60–120px tall) drifting across dead zones suggest
   stadium light haze and kill flat voids without adding objects. Never more
   than three; never over the hero numeral.
5. **Extruded edge (sparingly).** For the hero numeral only: 2–3px darker
   shade offset down-right gives cast presence. Stop at 3px — beyond that it
   becomes sticker art.

## Hard limits (brief wins over depth, always)

- Vietnamese text never changes face or position for depth. Numerals may
  glow; names and labels may not move, shrink, or recolor for effect.
- Contrast rules from the audit protocol still bind: glow must not wash the
  numeral below its required ratio; grain must not touch microcopy.
- No new hues: every pixel must stay within the locked palette ±90 box like
  every other proof (the audit test enforces this).
- Deterministic: same seed + same data = same pixels. Record seed, volumes,
  and radii in the proof script header.

## Process

1. Proof the flat card first (existing pipeline, pixel-exact).
2. Apply moves 1→5 in order, re-proofing after move 3; stop at the first
   proof that reads lit on a phone screen at arm's length.
3. Self-critique against frontend-design: if any move reads as decoration
   rather than light, remove it (Chanel's rule — take one accessory off).
