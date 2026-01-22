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

B) Timeline pollution check (always run after compose):
- Check that timeline.md does NOT contain JSON fragments:
  ```bash
  grep -E '^\s*>\s*\{' sessions/<sid>/timeline.md && echo "POLLUTED" || echo "CLEAN"
  ```
- If output is "POLLUTED", immediately **FAIL** and print:
  ```
  ## FAIL: Timeline contains JSON fragments

  The timeline is polluted with raw JSON output from a failed analysis.
  Fix: rerun the analysis with --force flag:
    yanhu analyze --session <sid> --backend claude --force
    yanhu compose --session <sid>
  ```

C) Highlights check (always run after compose):
- Check that highlights.md exists and contains at least one highlight item:
  ```bash
  [ -f sessions/<sid>/highlights.md ] && grep -c '^\- \[' sessions/<sid>/highlights.md || echo "0"
  ```
- If file missing or count is 0, **FAIL** and print:
  ```
  ## FAIL: highlights.md missing or empty

  The highlights file should contain at least one `- [HH:MM:SS]` entry.
  Fix: ensure analysis exists and rerun compose:
    yanhu analyze --session <sid> --backend claude
    yanhu compose --session <sid>
  ```

D) ASR transcription check (mock backend, no cloud key required):
- Run:
  ```bash
  source .venv/bin/activate && yanhu transcribe --session <sid> --backend mock --force
  ```
- Assert in analysis/<seg>.json:
  - asr_items exists with at least 1 item OR asr_error exists
  - For each asr_item: t_start <= t_end
  - Timestamps are monotonically increasing (item[i].t_start >= item[i-1].t_end)
  - asr_backend == "mock"
- Then run compose and check timeline:
  ```bash
  source .venv/bin/activate && yanhu compose --session <sid>
  ```
- Assert timeline contains "- asr:" line for segments with asr_items

E) ASR timestamp validation:
- Read analysis JSON and verify:
  ```python
  for i, item in enumerate(asr_items):
      assert item["t_start"] <= item["t_end"], f"t_start > t_end at item {i}"
      if i > 0:
          assert item["t_start"] >= asr_items[i-1]["t_end"], f"Not monotonic at item {i}"
  ```
- If validation fails, **FAIL** and print the specific violation.

F) ASR whisper_local backend check (requires faster-whisper installed):
- Prerequisites:
  - Check faster-whisper is installed: `pip show faster-whisper`
  - If not installed, skip this check with note: "faster-whisper not installed, skipping"
- Run:
  ```bash
  source .venv/bin/activate && yanhu transcribe --session <sid> --backend whisper_local --segments <seg> --model-size base --force
  ```
- Assert in analysis/<seg>.json:
  - asr_items exists with at least 1 item OR asr_error exists
  - asr_backend == "whisper_local"
  - If asr_items exists: timestamps are session-relative (t_start >= segment.start_time)
  - Timestamps are monotonically increasing
- Check audio file was created:
  ```bash
  [ -f sessions/<sid>/audio/<seg>.wav ] && echo "AUDIO EXISTS" || echo "AUDIO MISSING"
  ```
- If AUDIO MISSING and no asr_error, **FAIL**

## Output

- PASS/FAIL with reasons
- Commands executed
- Key artifact snippets (analysis JSON and timeline block)
