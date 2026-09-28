## Foundation hardening invariants

The evidence-backed state subsystem must preserve the following invariants:

* Observations are immutable evidence records. Re-submitting the same observation is idempotent; reusing an observation ID for different evidence is rejected.
* Source metadata that affects evidence resolution is versioned. An observation binds to a source revision so historical belief resolution does not depend on the source's current mutable configuration.
* The integrated database has a versioned bootstrap/migration entry point. Individual module schema helpers remain idempotent primitives, but engine startup must initialize the database through the migration layer.
* Domain taxonomy is owned by domain packs. The core Asset Registry must not require Soccer-specific taxonomy tables to create or store generic assets.
* Asset provenance may bind to a source revision. Logical stored asset paths use portable `/` separators rather than host-specific path syntax.
