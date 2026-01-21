---
name: yanhu-verify
description: Verify yanhu pipeline outputs with strict assertions (no guessing). Runs commands + checks artifacts. Fails fast if not satisfied.
allowed-tools: Read, Grep, Glob, Write, Bash
---

You are the verification gate for this repo.

Rules:
- Do NOT claim "done" unless checks pass.
- Always run the exact commands.
- If a check fails, propose the minimal fix and re-run only the failing steps.

Verification tasks you must support (choose based on user request):
A) L1 Claude Vision analysis correctness:
- Run:
  - `yanhu analyze --session <sid> --backend claude --segments <seg> --detail-level L1 --max-facts 3 --max-frames 3 --force`
- Assert in analysis/<seg>.json:
  - model starts with "claude-"
  - facts length in [1, max-facts]
  - facts must NOT contain meta terms: "帧", "segment_id", "模型", "path", "json"
  - scene_label in allowed enum
  - what_changed is non-empty and not "mock"
- Then run `yanhu compose --session <sid>` and assert timeline contains facts[0] and includes "change:" line for that segment.

Output:
- PASS/FAIL with reasons
- Commands executed
- Key artifact snippets (analysis JSON and timeline block)
