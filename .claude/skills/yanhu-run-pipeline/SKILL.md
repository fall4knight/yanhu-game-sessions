---
name: yanhu-run-pipeline
description: Run the local pipeline end-to-end on a given video and produce overview.md, timeline.md, highlights.md with artifact links.
---

When invoked, do:
1) Confirm input video path and session_id naming.
2) Run CLI steps in order: ingest -> segment -> extract -> understand(asr/vision if configured) -> compose.
3) Verify outputs exist and links resolve:
   - sessions/<session_id>/manifest.json
   - sessions/<session_id>/timeline.md
   - sessions/<session_id>/highlights.md
4) If any step fails, diagnose with minimal edits and re-run only the failed step.

Rules:
- Never delete sessions/ outputs.
- Prefer incremental reruns (cache by segment hash).
