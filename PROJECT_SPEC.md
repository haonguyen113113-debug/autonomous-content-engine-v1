# Project Specification

## 1. Objective

Create a portable autonomous value-creation and distribution engine that can operate continuously with minimal human intervention and can evolve from a single content experiment into a broader autonomous business system.

The engine should:

1. Discover market/category opportunities.
2. Identify and evaluate audiences by size, qualification, intent, accessibility, competition, and economic potential.
3. Maintain a focused portfolio of core categories while reserving limited capacity for exploration.
4. Discover themes and channel concepts within selected categories.
5. Treat channels as persistent digital assets with their own audience, theme, history, performance, and economics.
6. Discover concrete opportunities inside active category/theme portfolios.
7. Create useful value artifacts for the intended audience.
8. Validate factual accuracy, provenance, originality, usefulness, differentiation, and platform constraints.
9. Route each artifact to the most appropriate channel(s) and platform(s) rather than broadcasting indiscriminately.
10. Adapt artifacts to platform-native formats.
11. Publish through replaceable platform adapters without per-item human intervention once required authorization and capabilities are configured.
12. Capture real audience, conversion, revenue, and payout data.
13. Use historical results to improve category, theme, channel, content, distribution, and resource-allocation decisions.
14. Retire weak channels/categories and promote validated opportunities from exploration into the core portfolio.

## 2. Architecture principle: generic engine, configurable markets

The engine itself must remain domain-agnostic.

Category, market, language, audience, source universe, regulatory constraints, monetization options, and content conventions are configuration/domain-layer concerns, not hard-coded core-engine logic.

The same core should be able to operate:

* domestic and foreign markets
* multiple languages
* multiple categories
* multiple audience segments
* multiple channel themes

Vietnam is an important initial proving ground, not a permanent architectural constraint.

### 2.1 Core engine vs domain packs

The system must distinguish **mechanism** from **domain knowledge**.

The reusable core engine owns generic mechanisms such as:

* resource requests
* asset search and retrieval
* ranking/matching
* reuse-first selection
* discovery and acquisition
* deduplication and hashing
* technical metadata extraction
* provenance tracking
* rights/lifecycle state
* source registration
* observation history
* belief resolution
* quality gates
* storage/indexing interfaces
* orchestration and state handling

A **domain pack** supplies category-specific knowledge and rules without forking the core engine. A domain pack may contain:

* taxonomy and category definitions
* entity types and relationships
* aliases and naming rules
* source universe and source metadata
* retrieval/search rules
* resource requirements and purpose profiles
* quality profiles
* domain-specific rights or compliance constraints
* adapter configuration for external sources where required

A new category should therefore reuse the same Asset Library Engine and normally require only a new domain pack. A category-specific adapter may be added when an external provider, API, media format, or data model is genuinely different, but that adapter must plug into the existing generic interfaces rather than create a parallel library implementation.

**Soccer is the first proving domain, not the architectural boundary.** It is intentionally used to validate the generic mechanism before expanding to additional categories.

## 3. Portfolio and focus model

The engine must not freely change category every day.

Use two decision loops:

### Strategic loop

A slower loop evaluates the market and decides:

* which categories remain core
* which categories are exploratory
* allocation of attention/compute/capital across them
* promotion, demotion, or retirement decisions

### Execution loop

A faster loop operates inside the selected portfolio:

* discover opportunities
* select themes
* create value
* route to channels
* distribute
* measure

Initial operating constraint:

* maintain roughly 3–4 core categories at a time
* reserve a limited exploration allocation for new categories

These are starting constraints, not immutable constants. Promotion or replacement must be evidence-driven.

## 4. Core abstraction layers

The architecture should preserve the separation:

**Market → Category → Audience → Pillar/Theme → Channel → Opportunity → Artifact → Distribution → Outcome → Learning**

Definitions:

* **Market:** geographic/language/regulatory/economic context.
* **Category:** broad subject/market opportunity area.
* **Audience:** identifiable group with measurable size, qualification, intent, and economic value.
* **Pillar/Theme:** persistent content positioning inside a category.
* **Channel:** a persistent distribution asset built around a theme and audience.
* **Opportunity:** a specific time-sensitive or structural reason to create value.
* **Artifact:** any useful output; content is only one artifact type.
* **Distribution:** a routing/execution layer between artifacts and platforms.
* **Outcome:** audience and economic response.
* **Learning:** updates to future selection, production, routing, and allocation decisions.

## 5. Channel portfolio model

A channel is an asset, not merely a publishing destination.

Each channel should have persistent metadata including:

* theme
* target audience
* market/language
* tone and positioning
* preferred formats
* platform set
* publishing cadence
* content constraints
* historical performance
* audience quality
* intent/conversion data
* economics
* lifecycle state

The system should be able to:

* create candidate channels
* test them
* increase/decrease allocation
* pause them
* retire them
* learn from their history

## 6. Content and value creation

The engine must not treat generic rewriting or paraphrasing as sufficient value creation.

Artifact types may include:

* analysis
* comparison
* decision guide
* tutorial
* checklist
* research synthesis
* calculation/model
* workflow
* tool
* lead magnet
* article
* short-form video
* other useful formats

A content candidate should be created for a specific audience and theme, then classified/routed to the channel where it has the strongest fit.

One underlying opportunity may produce different artifacts for different markets or audiences. Localization must create contextual relevance, not simply translation.

## 7. Audience and opportunity intelligence

Opportunity scoring must be explainable and multi-factor.

Do not collapse important decisions into an opaque single score.

Relevant dimensions may include:

* audience size
* audience qualification
* audience intent
* need/pain intensity
* accessibility
* competition
* timeliness
* content/value-creation potential
* conversion potential
* expected economics

Scores should retain the component evidence/reasons that produced them.

## 8. Asset Library and resource acquisition

The Asset Library is production infrastructure, not a passive file folder.

Whenever an artifact or production workflow requires a resource, it should issue a domain-agnostic resource request to the Asset Library Engine. The library should follow a **reuse-first** strategy:

**resource requirement → search existing library → validate suitability → reuse**

Only when suitable inventory is missing, insufficient, stale, or invalid should the system continue:

**resource requirement → external discovery → candidate acquisition → provenance capture → rights verification → quality gate → register → reuse**

Every newly accepted external resource should become reusable library inventory rather than remaining tied only to the task that triggered its acquisition.

The core resource request should remain generic enough to support multiple categories, for example:

* asset type
* subject/entity
* purpose
* quality constraints
* temporal constraints
* market/language constraints
* rights constraints
* format constraints

The Asset Library must not decide what the business should create. Upstream market, audience, opportunity, research, or artifact-composition layers determine the requirement. The Asset Library determines how to satisfy that requirement from reusable inventory or approved external acquisition paths.

The system must support category expansion without rebuilding the library. Category-specific behavior belongs in domain packs and replaceable adapters; generic acquisition, registration, provenance, rights, quality, indexing, and reuse mechanisms remain shared.

External acquisition must remain auditable. The system should preserve the source, locator, acquisition time, provenance, rights state, quality result, and relationship to the resulting registered asset.

## 9. Routing and distribution

Content generation must remain separate from routing and distribution.

Target flow:

**opportunity → artifact → quality gate → theme classification → channel routing → platform adaptation → publish → measure**

An artifact should not automatically be broadcast to every channel.

Platform adapters must remain replaceable.

The engine should support multiple destinations per channel and market where appropriate.

## 10. Automation and autonomy contract

After the engine is booted, required accounts are linked/authorized, and required tools/capabilities are provisioned, normal operation must be zero-touch at the individual-task level.

Human actions are intentionally limited to:

1. Boot/restart the engine when required.
2. Link and authorize platform accounts/capabilities.
3. Provision required tools/plugins/services/capabilities for the engine.
4. Periodically perform reality checks against actual platform state/feedback.
5. Verify actual monthly payouts/payments reached the designated account.

Routine operational work must be automated, including:

* discovery
* category/theme/channel decisions
* content production
* QA
* routing
* platform adaptation
* scheduling
* publishing
* retries and backoff
* rate-limit handling
* state persistence
* analytics collection
* optimization
* experimentation
* portfolio reallocation
* routine reporting
* routine maintenance

Human intervention should occur only for:

* authentication/authorization requirements
* platform-mandated consent or policy workflows
* irrecoverable failures
* high-risk policy-sensitive decisions
* reality verification
* payout verification

The system must never depend on per-item manual publishing.

## 11. Measurement and economic truth

The system must distinguish:

**generated ≠ verified ≠ staged ≠ published ≠ measured ≠ paid**

The true economic loop is:

**artifact → distribution → audience response → conversion → platform earnings → actual payout → verified cash received**

Platform-estimated earnings are not equivalent to realized cash.

Primary business metric:

* profit attributable to the operating portfolio

Secondary metrics:

* qualified reach
* engagement
* click-through rate
* conversion
* revenue per artifact
* revenue per channel
* production cost
* distribution cost
* contribution margin
* realized payout

## 12. Learning and reallocation

The learning system should update:

* category allocation
* exploration allocation
* audience assumptions
* theme selection
* channel allocation
* artifact types
* distribution choices
* content production strategy

The system must be capable of deciding both:

* “change”
* “do not change”

Frequent change is not a goal. Sufficient observation and statistical signal should precede major portfolio decisions.

## 13. Quality and safety gates

The system must distinguish structural QA from semantic/value QA.

Structural QA checks that required fields and format constraints are present.

Semantic/value QA should assess, where applicable:

* factual grounding
* evidence/provenance
* unsupported or conflicting claims
* originality
* usefulness
* audience fit
* thematic fit
* differentiation
* repetitiveness
* platform constraints

Critical failures must block publishing.

QA must be allowed to reject an artifact and trigger regeneration or an alternative path.

## 14. Data and provenance

Every important artifact should be traceable to:

* source records
* claims
* research version
* category
* market
* audience
* theme
* channel
* content/artifact version
* QA result
* publishing destination
* platform/remote identifiers
* analytics
* monetization attribution
* realized payout where available

Secrets, credentials, cookies, tokens, and private keys must never be committed to Git.

## 15. Portability requirement

A replacement PC must be able to run the same project with minimal machine-specific configuration.

No business logic may depend on:

* a specific username
* an absolute filesystem path
* a specific GPU
* a specific operating system
* a specific cloud vendor
* a single LLM provider

Persistent state, configuration, workflows, and provenance must be portable.

## 16. Cost target

Prefer open-source software, local inference, local rendering, free tiers, and usage-based services only where they materially improve economics.

The engine must not assume paid AI APIs as a foundational dependency.

## 17. Development and validation strategy

Prove small vertical slices before expanding.

Every major architectural abstraction should be validated with a real behavior test before it becomes deeply embedded in the system.

Examples:

* a new category can be introduced through a domain pack without rewriting the core engine
* a new category can reuse the Asset Library Engine without rebuilding the library
* missing category resources can be acquired externally, pass provenance/rights/quality gates, and become reusable inventory
* a new market/language can use the same core
* a new channel can be created from a theme configuration
* an artifact can be routed to the appropriate channel without generator changes
* a platform can be replaced by swapping an adapter
* a publish failure can be recovered without manual per-item intervention
* measured outcomes can update future decisions

Do not equate “the pipeline runs” with “the system creates value.”


## 19. Long-term north star

The long-term system should be capable of operating a portfolio rather than merely generating content:

**Market → Category Portfolio → Audience → Themes → Channel Portfolio → Opportunities → Value → Routing → Autonomous Distribution → Measurement → Economic Feedback → Learning → Portfolio Reallocation**

Success means the user acts primarily as owner/administrator and reality verifier, not as the day-to-day operator of the business.
