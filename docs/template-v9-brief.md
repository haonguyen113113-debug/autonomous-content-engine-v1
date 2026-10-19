# Template v9.0.0 "Kit" — rebuild brief (from scratch)

v8 aliased Nova plates; owner audit: chưa đạt. v9 rebuilds every Sports Kit
plate from the reference anatomy (`docs/sport-design-research.md`) as
dedicated code in `apps/sportskit/plates.py` + mirrored Manim atoms.

## Palette (locked)

kit_red #C8102E, ink #0B0D10, paper #F5F1E6, navy #0A1A3C, orange #E8590C,
winner_lime #8CFF00, muted #9AA3A8. Defaults: red field + ink; navy/orange
only for duels; lime only for winners (never body text).

## Type (locked)

- BOSS: Barlow Condensed Bold (giant numerals, backdrop words, headers).
  Full Vietnamese diacritics, verified in frames.
- SUPPORT/WHISPER: Be Vietnam Pro (labels VN, micro provenance).
- Brush: PermanentMarker, latin surnames/digits only, never Vietnamese.

## Layouts (12, all dedicated)

duel_columns, stat_leader, player_poster_side, player_poster_top, goal_card,
fixture_card, fixture_list, score_card, quote_card, potm_card,
discipline_card, welcome_card. hook_card (Nova frame-0) + tactical/charts/
source from v7 stay for analysis beats; runs pin versions.

## Data integrity

Values only from reviewed evidence with source+date; winner computed from
supplied numbers (never ties broken silently — ties render both white);
portraits only approved library images of the named player; no crests,
no footage, no invented fixtures.

## Motion (Manim, build-time)

punch-in (goal/hook), slide-in 0.3s ease-out, count-up 6 steps, stagger
0.18s, ticker scroll, duel bar grow + winner-pop. Engine serves without Manim.

## Acceptance

- 12 PIL plates x 2 aspects render, diacritics intact, contrast >= 4.5 boss.
- 8 Manim atoms render 1080x1920.
- `pytest tests/test_template_kit.py` green; drafts resolve 9.0.0.
