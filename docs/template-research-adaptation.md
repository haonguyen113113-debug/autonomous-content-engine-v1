# Allen Knows Ball template research and adaptation

## Research references

- [Storybench interview with Tifo Football's creative director](https://www.storybench.org/how-tifo-football-is-making-soccer-analytics-more-easy-to-digest/) describes using football analytics and animation to make tactical and historical ideas easier to understand.
- [The Independent's ACFC tactical analysis series](https://www.independent.co.uk/tv/acfc/manchester-city-pep-guardiola-acfc-video-b2845062.html) frames a specific football question around a team's shape and player roles in a short analysis episode.
- [Premier League Breakdown: Liverpool's title-winning tactics](https://www.premierleague.com/en/video/4298393/the-breakdown_liverpool-champions_delivery-v3-webmp4) uses player emphasis, movement paths, and target zones to make a tactical explanation visible over match context.
- [Opta Analyst Player Radars](https://theanalyst.com/articles/opta-player-radars-comparison-tool) show how a chart can group a handful of normalized metrics into an at-a-glance player profile. The Engine should use a radar only if it has comparable normalized values and a stated benchmark; otherwise use labeled bars or statlines.
- [FourFourTwo's low-block explainer](https://www.fourfourtwo.com/features/the-low-block-football-tactics-explained) puts a tactical concept into a real match context, using team/player color distinction to make the mechanism legible.
- [Bongdaplus tactical analysis of Vietnam's 5-4-1](https://bongdaplus.vn/doi-tuyen-quoc-gia-viet-nam/goc-chien-thuat-nhung-dau-hoi-trong-he-thong-5-4-1-cua-dt-viet-nam-3435252109.html) is a local-language reference for annotating a tactical claim against a match image.
- [Coaches' Voice on video analysis](https://learning.coachesvoice.com/cv/video-analysis-coaching-bepro-notts-county/) is a process reference for using video to inspect and explain football decisions, not a style to copy.
- [Good Secrets on the HBO soccer docuseries graphics](https://nofilmschool.com/docuseries) describes a bold, handcrafted visual system combining archival treatments, scorecards, maps, and animation. The production used a repeatable template system while maintaining tactile variation.
- [Rohit Sharma's Sports Direct show graphics](https://rohitsharma.me/2022/12/11/sports-direct/) combines expressive typography and contemporary type with contrasting retro tactics-board marks and photography.
- [Grizzle's Copa90 intro case study](https://vimeo.com/159993241) uses comic-influenced illustration and character motion to give a football show a distinct personality.

These are visual references, not source assets. No channel wordmark, graphic package, player likeness, footage, or proprietary illustration is copied into this template.

## Principles carried into version 0.3.0

1. **Story before decoration.** A graphic must clarify one claim or one tactical relationship. The voice carries narrative; the screen carries evidence.
2. **One focal point.** A highlighted player, occupied space, or target zone is the dominant element. Other marks recede.
3. **Movement has meaning.** A pass arrow, run, or press vector is drawn once and stops at its endpoint. Accent color separates possession, pressure, and the chosen path.
4. **Real context is preferred.** Owner-approved, exact-context Asset Library media should lead when it materially supports the claim. The authored pitch plate is the fallback for explaining a mechanism, not a substitute for match evidence.
5. **Distinct aspect-ratio composition.** Short form keeps the portrait pitch and chapter rail; long form uses a landscape pitch with a wider editorial rail. Neither is a scaled copy of the other.
6. **Stable identity, changing story rhythm.** Midnight ink and warm paper stay fixed. Color accents adapt to the match, editorial treatment, and data semantics. Open, evidence, tactical explanation, and close should use different visual modes.

## Version 0.4.0 additions

The short and long packages retain the chapter rail, Vietnamese type system, no-subtitle rule, and distinct portrait/landscape tactical plates. Four colorways broaden visual range without changing the channel signature. If reviewed team kit colors are supplied, they can replace the two team accents; otherwise the selected colorway supplies them.

The renderer now supports five authored visual layouts: tactical plate, statline scorecard, source card, comparison bars, and ordered timeline bars. A script beat selects its visual mode. Numeric data is never generated from layout defaults: values and source metadata must be present in the reviewed segment. The preview cards intentionally use sample numbers and are labeled illustrative.

These are visual grammar adaptations, not copies of referenced graphics, logos, footage, or channel palettes. Sources and values must be verified for each production run.

## Version 0.5.0: Touchline Editorial

The owner review identified that the previous Match Dossier still read too much like a report. Version 0.5.0 strengthens the type hierarchy and motion: Be Vietnam Pro carries expressive Vietnamese hooks; Barlow Condensed is reserved for oversized numerals and short English marks; highlight tabs, slanted edges, marker slashes, subtle grain, and short line reveals add authored energy. Tactical annotations and data labels remain legible and tied to evidence.

This adapts the broader design lesson from soccer docuseries and football show packages: use a repeatable graphic system that can mix scorecards, maps, archival/photo moments, and hand-made marks while preserving a recognizable host identity. It does not copy any one channel or studio's finished graphic assets.

## Current implementation boundary

Version 0.4.0 implements the selectable colorways and authored statline, source, and chart plates in the full renderer, selected by the reviewed segment's visual mode. It still does not composite approved Asset Library footage into the full timeline, and timed transition/effect execution remains a later integration step. The packages remain drafts pending Allen's visual audit.

## Version 0.7.0: distinct evidence-graphic grammars

The owner review found that three evidence layouts looked like variants of the same framed panel. Version 0.7.0 gives each one a different surface and reading order while retaining the channel wordmark, Vietnamese typography, and contextual team colors:

- **Statline scorecard:** dark head-to-head board. Team colors split the header and frame opposite sides; team values face each other around centered metric labels. Paired strokes reinforce only the within-metric comparison, while direct values stay visible. This follows sports scorecard and head-to-head comparison conventions (see the [Stats Perform goalkeeper comparison example](https://www.statsperform.com/wp-content/uploads/2021/06/SP_Twenty3_CaseStudy.pdf)).
- **Comparison chart:** warm paper plotting canvas, labeled zero baseline, grid ticks, scaled bars, and direct values. A single series color avoids implying categories that have no legend. Takeaway-first titles and visible chart labels adapt principles in [The Markup graphics styleguide](https://design.themarkup.org/).
- **Timeline chart:** same chart family and scale discipline, but uses an ordered line and event points rather than unordered comparison bars. The [Opta Analyst match-momentum explainer](https://theanalyst.com/articles/what-is-match-momentum) shows how a sequence can tell the match story chronologically.
- **Source note:** clipped warm-paper citation insert on an ink field. Publisher/dataset, date, claim, and URL have separate visual roles. The visible attribution remains concise; fuller source records should stay in the run data. This adapts traceability and source-placement guidance from [U.S. Data Visualization Standards](https://xdgov.github.io/data-design-standards/components/source).

The numeric/source examples in `previews/` are explicitly fictitious. These compositions are original adaptations, not copies of the referenced packages or brand identities.


## Version 0.8.0: chart family and evidence-led finish

The owner requested that charts remain a family of forms rather than a single locked visual. The renderer and script-agent contract now support horizontal bars, columns, pie, donut, and chronological line charts. Selection follows the evidence question: horizontal bars suit ranks and long labels; columns suit a few discrete groups; a line requires ordered times or dates; pie and donut require mutually exclusive parts of one known whole and are limited to four categories. Invalid pie/donut metadata falls back to a zero-based bar. Radar remains unavailable unless comparable normalized measures and an explicit benchmark are supplied, following the restraint visible in [Opta Analyst's player radars](https://theanalyst.com/articles/introducing-opta-radars-compare-players). Pie guidance follows [Datawrapper's part-to-whole criteria](https://www.datawrapper.de/academy/what-to-consider-when-creating-a-pie-chart).

Aesthetic refinements are deliberately tied to legibility: statline uses a dark face-off identity with paired comparison strokes; chart uses an editorial plotting sheet with a highlighted data cap/chronological trace and direct labels; source uses a clipped citation paper, custom drawn quotation mark, and explicit publication/date/claim hierarchy. This adapts the evidence-key discipline in [StatsBomb's shot-map design notes](https://statsbomb.com/articles/soccer/design-diary-mk-shot-maps/) and takeaway-first annotation in [The Markup graphics styleguide](https://design.themarkup.org/), without borrowing another publisher's branded package. Portrait and landscape previews show every chart type independently.

Preview data remain illustrative and are not football claims. The engine prompt now requires an explicit chart_type, source/date, values, and semantic preconditions before selecting a chart.
