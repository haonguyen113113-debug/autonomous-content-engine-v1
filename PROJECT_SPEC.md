# Project Specification

## 1. Objective

Create an autonomous content-to-profit engine that can operate continuously with minimal human intervention.

The engine should:
1. Discover topics and opportunities.
2. Collect and preserve source evidence.
3. Evaluate whether an opportunity is worth producing.
4. Generate one or more content assets from shared research.
5. Validate factual accuracy, provenance, originality, and required platform constraints.
6. Distribute content through replaceable platform adapters.
7. Route attention toward owned assets and monetization mechanisms.
8. Capture analytics and revenue data.
9. Use historical results to improve future topic and content selection.

## 2. Initial operating assumption

The first production experiment will likely use a Finance × AI × Vietnam content niche. The architecture itself must remain niche-agnostic.

## 3. Automation target

Long-term target:

scheduled trigger → research → decision → content → QA → distribution → measurement → learning

Normal successful jobs should run without manual intervention. Human intervention remains available for exceptions, policy-sensitive decisions, high-risk claims, and system failures.

## 4. Cost target

Prefer open-source software, local inference, local rendering, free tiers, and usage-based services only where they materially improve economics. The system must not assume paid AI APIs as a foundational dependency.

## 5. Portability requirement

A replacement PC must be able to run the same project with minimal machine-specific configuration.

No business logic may depend on:
- a specific username
- an absolute filesystem path
- a specific GPU
- a specific operating system
- a specific cloud vendor
- a single LLM provider

## 6. Security requirement

Secrets, credentials, cookies, tokens, and private keys must never be committed to Git.

## 7. Data and provenance

Every important content asset should be traceable to:
- source records
- claims
- research version
- content version
- generated assets
- publishing destination
- analytics
- monetization attribution where available

## 8. Quality requirement

The system must distinguish:

generated ≠ verified ≠ published

Critical unsupported or conflicting claims should block publishing.

## 9. Economic objective

Primary business metric:
profit attributable to content

Secondary metrics:
- reach
- engagement
- click-through rate
- lead conversion
- sales conversion
- revenue per content asset
- production cost
- contribution margin

## 10. Scope discipline

Prove a small end-to-end vertical slice before expanding to multiple niches, media formats, or platforms.
