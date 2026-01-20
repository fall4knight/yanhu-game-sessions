# Yanhu Game Sessions — Claude Working Agreement

This repo follows `docs/PROJECT_PLAN.md` as the single source of truth.
Always align work to the Milestones and DoD described there.

## Scope (v0.1)
- Build offline post-game pipeline: ingest -> segment -> extract -> compose.
- Vision/ASR/LLM are allowed later, but do NOT block M0/M1/M2 on cloud model integration.
- Watcher is stretch/optional and should be deferred unless explicitly requested.

## Repo rules
- Keep diffs small and incremental.
- Never delete or overwrite `sessions/` outputs. No destructive operations.
- Add `sessions/` and large media artifacts to `.gitignore`.
- Prefer deterministic outputs: stable sorting, stable naming, explicit configs.

## Output contracts (must match README)
- session_id: `YYYY-MM-DD_HH-MM-SS_<game>_<runTag>`
- segments: `*_part_0001.mp4` incremental numbering
- timeline timestamps: `HH:MM:SS`, and each entry must reference segment/frame evidence.

## Development workflow
- Before writing code, list files you will create/modify.
- Implement M0 first (scaffold): `pyproject.toml`, `src/yanhu`, CLI skeleton, `.gitignore`, basic tests.
- Implement M1 next (ingest + segment): ffmpeg-based splitting, manifest, CLI command.
- Implement M2 next (extract): frame extraction per segment, update manifest, CLI command.
- Add a minimal smoke test for CLI and a unit test for segment logic.

## Safety & privacy
- Default to local processing.
- Any cloud API calls (Vision/ASR/LLM) must be explicitly gated behind config flags and require user confirmation in the plan.
