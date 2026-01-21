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

## Prerequisites for Claude Backend

Before running any claude backend verification:

1. Check .env file exists:
```bash
[ -f .env ] && echo ".env EXISTS" || echo ".env MISSING"
```

2. Check API key is set in .env:
```bash
bash -lc 'set -a; [ -f .env ] && source .env; set +a; echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:+SET}"'
```

If .env is MISSING, immediately **FAIL** and print:
```
## FAIL: .env file not found

Create .env in project root:
  echo 'ANTHROPIC_API_KEY=sk-ant-api03-...' > .env

Note: .env is gitignored and will not be committed.
```

If .env exists but `ANTHROPIC_API_KEY` is not SET, immediately **FAIL** and print:
```
## FAIL: ANTHROPIC_API_KEY not found in .env

Add to .env:
  echo 'ANTHROPIC_API_KEY=sk-ant-api03-...' >> .env
```

Do NOT proceed with claude backend commands if either check fails.

## Verification Tasks

A) L1 Claude Vision analysis correctness:
- Run:
  ```bash
  bash -lc 'set -a; source .env; set +a; source .venv/bin/activate && yanhu analyze --session <sid> --backend claude --segments <seg> --detail-level L1 --max-facts 3 --max-frames 3 --force'
  ```
- Assert in analysis/<seg>.json:
  - model starts with "claude-"
  - facts length in [1, max-facts]
  - facts must NOT contain meta terms: "帧", "segment_id", "模型", "path", "json"
  - scene_label in allowed enum
  - what_changed is non-empty and not "mock"
- Then run:
  ```bash
  bash -lc 'set -a; source .env; set +a; source .venv/bin/activate && yanhu compose --session <sid>'
  ```
- Assert timeline contains facts[0] and includes "- change:" line for that segment.

## Output

- PASS/FAIL with reasons
- Commands executed
- Key artifact snippets (analysis JSON and timeline block)
