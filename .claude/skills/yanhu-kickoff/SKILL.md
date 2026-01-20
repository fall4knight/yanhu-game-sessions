---
name: yanhu-kickoff
description: Scan repo + README, then write/update docs/PROJECT_PLAN.md with requirements, MVP spec, milestones, risks, and progress log.
allowed-tools: Read, Grep, Glob, Write
---

You are the TL/architect for this repo.

Primary goal:
- Create or update docs/PROJECT_PLAN.md as the single source of truth for the project plan.

Rules:
- Use ONLY information from README.md and the current repository state.
- Do not invent new requirements or directory layouts.
- If docs/PROJECT_PLAN.md already exists, UPDATE it in-place:
  - Preserve existing structure and wording unless required to reflect README changes.
  - Keep any user-added notes.
- Always keep Progress Log present and intact. If milestones change, update the table accordingly.

Deliverables (must be concrete and written to docs/PROJECT_PLAN.md):
1) Executive Summary (max 5 lines)
2) Requirements Map: list requirements from README and map each to modules + acceptance tests
   - If a requirement is “stretch/optional” (e.g., watcher), mark it explicitly in Notes or in the milestone section.
3) MVP v0.1 Spec: inputs/outputs, folder layout, file formats (manifest/analysis/events), aligned with README example output
4) Milestones: ordered milestones with Definition of Done + checklist per milestone
5) Risks & Mitigations: ffmpeg, performance, privacy, costs, rate limits
6) Progress Log table: Date, Milestone, Status, Notes
   - Do not mark milestones as Started/Done unless there is evidence in repo (files/commands/tests).
   - Today’s date can be added if needed, but avoid false progress.

After writing:
- Print a short summary of what changed (bullets), and which files were modified.
