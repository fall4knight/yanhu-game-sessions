---
name: yanhu-pr-review
description: Review changes like a strict backend TL: correctness, edge cases, performance, naming, tests, and operational safety.
allowed-tools: Read, Grep, Glob
---

Review checklist (must include):
- Data contracts: manifest/index/events schemas and backward compatibility
- Determinism & reproducibility: fixed seeds, stable sorting, stable timestamps
- Performance: ffmpeg calls, concurrency, caching, I/O layout
- Safety: no destructive ops; clear separation between code and generated artifacts
- Tests: at least one smoke test for CLI + one unit test for schema/segment logic

Output:
- Blockers (must fix)
- Non-blockers (should fix)
- Nice-to-haves
- Suggested next milestone
