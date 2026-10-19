# MR-02 redesign plan (frontend-design process applied)

Subject: final-score reveal card, Allen Knows Ball, 1080×1920, Vietnamese
football audience. Job: answer who won / by how much / in which match in
under 2 seconds on a phone screen.

## Token system

- Color (locked brief palette, no new hues): ink `#161B2C` loser ground,
  coral `#E0705F` winner ground, paper `#F4F2EC` chalk type, slate `#5A6B8C`
  dimmed loser numeral, mist `#8B96B0` provenance microcopy.
- Type: Barlow Condensed Bold = Vietnamese names/labels (diacritics
  required, brand-locked). Be Vietnam Pro Regular = venue/provenance.
  BigShoulders Bold (canvas-fonts, OFL) = score numerals ONLY — latin digits
  need no diacritics, and the numeral is treated as a visual element, not
  text. Two display voices kept clearly distinct by role (names vs numbers).
- Layout concept: split pitch. Winner coral field ~58% top, loser ink field
  below, one paper halfway rule + faint center circle. Left-aligned broadcast
  stack; nothing centered by default.

```
+------------------------------------------------+
| V.League · Tối nay • Hàng Đẫy        (small)   |
| HÀ NỘI                             (Barlow 130)|
|  2                     <- BigShoulders ~560px  |
|                            (paper on coral)    |
|------------------------------------------------| paper rule + circle motif
|  0  NAM ĐỊNH              (slate numeral+name)  |
|                                                |
|  Nguồn + ngày                        (mist)    |
+------------------------------------------------+
```

- Principles: color encodes the winner; size encodes importance (goals >
  names > context > provenance); one memorable element (monumental winner
  numeral); everything else quiet.

## Review against the brief (uniqueness check)

- Generic default rejected: centered stack with floating "2 - 0" (the
  original), SaaS-card kit boxes, ALL-CAPS eyebrow labels, numbered markers
  (a score is not a sequence), single-word accent coloring.
- Kept from the brief because the brief wins: ink/coral/paper palette, Barlow
  + Be Vietnam for all Vietnamese text, credit line position, safe areas,
  identical required data slots (comp/when/home/away/score/source+date) so
  the card-selector filter and renderer keep working unchanged.
- Deliberate risk taken: third typeface for numerals + asymmetric split
  instead of centered symmetry. Justified: numerals carry no diacritics and
  broadcast score bugs traditionally set numbers apart from names.

## Critique of the original (what changed and why)

1. Dead void lower half (~700px, zero information) → loser territory with
   dimmed numeral + name; every pixel now answers one of the three questions.
2. Floating "2 - 0" with spaced hyphen (reads as arithmetic, winner
   ambiguous) → numerals anchored to their teams, winner monumental in
   paper-on-coral, loser dimmed in slate.
3. Teams divorced from numbers in a separate band → each name sits with its
   numeral; structure encodes who-won without any extra label.
4. No venue/competition hierarchy → single quiet context line on top.
