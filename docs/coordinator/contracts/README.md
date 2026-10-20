# Contract index — frozen before parallel work

Read these seven contracts before any implementation task. Packets cite the
exact version below. If a task needs a contract change, stop and return to
the coordinator instead of editing the contract inside a worker task.

| # | Contract | File | Version |
|---|----------|------|---------|
| C1 | Upload-use rights scope and eligibility | `contracts/c1-rights-scope.md` | 1.0 |
| C2 | Candidate board, suitability, and owner approval | `contracts/c2-candidate-suitability.md` | 1.0 |
| C3 | Semantic beat intent (LLM output boundary) | `contracts/c3-beat-intent.md` | 1.0 |
| C4 | Visual Scene Graph (deterministic planner output) | `contracts/c4-scene-graph.md` | 1.0 |
| C5 | QA finding (rendered-scene verdicts) | `contracts/c5-qa-finding.md` | 1.0 |
| C6 | Card media slots (authored variable-media regions) | `contracts/c6-card-media.md` | 1.0 (frozen history; superseded by C7) |
| C7 | Unified card contract (every built card) | `contracts/c7-card-contract.md` | 2.0 (pack 12.0.0 frozen; 12.1.0 adds C-09 `source_card`) |
