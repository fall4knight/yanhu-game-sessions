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
python3 -c "from dotenv import dotenv_values; env = dotenv_values('.env'); print(f\"ANTHROPIC_API_KEY={'SET' if env.get('ANTHROPIC_API_KEY') else 'NOT_SET'}\")"
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

A) Source video observability (P2.1):
- Check manifest contains source_metadata:
  ```bash
  cat sessions/<sid>/manifest.json | jq '.source_metadata'
  ```
- Assert fields exist: source_mode, source_inode_raw, source_inode_session, source_link_count
- Verify with stat (use platform-appropriate stat command):
  ```bash
  # macOS: stat -f, Linux: stat -c
  # Get raw video inode
  stat -f "%i" <raw_video_path> || stat -c "%i" <raw_video_path>
  # Get session source inode and link count
  stat -f "%i %l" sessions/<sid>/source/<video_name> || stat -c "%i %h" sessions/<sid>/source/<video_name>
  # Check if symlink
  ls -l sessions/<sid>/source/<video_name> | grep -q '^l' && echo "SYMLINK" || echo "NOT_SYMLINK"
  # If symlink, get target
  readlink sessions/<sid>/source/<video_name>
  ```
- Assert based on source_mode:
  - **hardlink**: source_inode_raw == source_inode_session AND source_link_count >= 2
  - **symlink**: ls -l shows 'l' at start AND source_symlink_target matches readlink output
  - **copy**: source_inode_raw != source_inode_session AND source_link_count >= 1
- If source_fallback_error exists, verify it contains expected errno (EXDEV/EPERM/EACCES) or fallback description
- Print full source_metadata for inspection
- **FAIL** if:
  - source_metadata is missing
  - source_mode is not one of: hardlink, symlink, copy
  - hardlink mode but inode_raw != inode_session
  - hardlink mode but link_count < 2
  - symlink mode but readlink fails or target doesn't match source_symlink_target
  - Actual file type doesn't match source_mode

B) L1 Claude Vision analysis correctness:
- Run (using helper to load .env without shell noise):
  ```bash
  .claude/skills/yanhu-verify/run_with_env.py yanhu analyze --session <sid> --backend claude --segments <seg> --detail-level L1 --max-facts 3 --max-frames 3 --force
  ```
- Assert in analysis/<seg>.json:
  - model starts with "claude-"
  - facts length in [1, max-facts]
  - facts must NOT contain meta terms: "帧", "segment_id", "模型", "path", "json"
  - scene_label in allowed enum
  - what_changed is non-empty and not "mock"
- Then run:
  ```bash
  .claude/skills/yanhu-verify/run_with_env.py yanhu compose --session <sid>
  ```
- Assert timeline contains facts[0] and includes "- change:" line for that segment.

C) Timeline pollution check (always run after compose):
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

D) Highlights check (always run after compose):
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

E) ASR transcription check (mock backend, no cloud key required):
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

F) ASR timestamp validation:
- Read analysis JSON and verify:
  ```python
  for i, item in enumerate(asr_items):
      assert item["t_start"] <= item["t_end"], f"t_start > t_end at item {i}"
      if i > 0:
          assert item["t_start"] >= asr_items[i-1]["t_end"], f"Not monotonic at item {i}"
  ```
- If validation fails, **FAIL** and print the specific violation.

G) ASR whisper_local backend check (requires faster-whisper installed):
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

## Self-Recommendation Checklist (REQUIRED)

**CRITICAL**: Claude Code must ALWAYS run these checks before claiming any work is complete. Failure of ANY check means the work is NOT done.

### 1. Code Quality Check (ruff)
```bash
ruff check src/ tests/ scripts/
```

**Expected Output**: No errors (exit code 0)

**If FAILED**:
- Print all ruff errors verbatim
- **FAIL** with message: "Code quality check failed. Fix ruff errors before proceeding."
- Do NOT claim work is done

### 2. Test Suite Check (pytest)

**CRITICAL**: You MUST run the EXACT command below. Do NOT use --ignore flags or other filters.

```bash
pytest -q
```

**Expected Output**:
- All tests pass (including E2E tests, unless excluded by marker)
- Exit code 0
- No failures, no errors

**To exclude E2E tests (ONLY if Playwright not installed)**:
```bash
pytest -m "not e2e" -q
```

**FORBIDDEN**:
- ❌ `pytest -q --ignore=tests/e2e` (NEVER use --ignore)
- ❌ `pytest -q tests/` (excludes root tests)
- ❌ Any path-based exclusion that silently skips test files

**If FAILED**:
- Print pytest output showing failures
- **FAIL** with message: "Test suite has failures. Fix failing tests before proceeding."
- Do NOT claim work is done

### 3. Runtime Dependency Check (Default Gate)

**ALWAYS run these profiles for standard development work**:

```bash
python scripts/runtime_selfcheck.py --profile core
python scripts/runtime_selfcheck.py --profile app
python scripts/runtime_selfcheck.py --profile desktop
```

**Expected Output** (for each):
```
============================================================
SELF-CHECK PASSED: All dependencies present for profile '<name>'
============================================================
```

**If ANY profile FAILS**:
- Print full selfcheck output showing missing imports
- **FAIL** with message: "Runtime dependencies missing for profile '<name>'. See docs/DEPENDENCY_MATRIX.md for installation."
- Do NOT claim work is done

**These profiles do NOT require ASR dependencies** (faster-whisper, tiktoken, etc.), so they MUST pass in all dev environments.

---

### 4. E2E UI/Progress Tests (Conditional)

**ONLY run when UI or progress polling logic is changed**:

**When to run**: If ANY of these conditions are true:
- `src/yanhu/app.py` was modified (Flask routes, templates, or JS inline code)
- `src/yanhu/watcher.py` progress logic was modified (write_stage_heartbeat, progress_tracker)
- `scripts/runtime_selfcheck.py` was modified
- `tests/e2e/` directory was modified or added
- Any Jinja2 templates in `src/yanhu/templates/` were modified
- User explicitly requests "e2e tests" or mentions progress/polling/UI changes

**Prerequisites**:
- Playwright browsers must be installed (one-time setup):
  ```bash
  python -m playwright install --with-deps chromium
  ```
- If not installed, skip this check with note: "Playwright not installed, skipping E2E tests"

**Command**:
```bash
pytest -m e2e -v
```

**Expected Output**:
- All 5 E2E tests pass (test_pending_job, test_processing_no_session, test_session_appears, test_terminal_lock, test_stop_polling)
- Exit code 0
- No browser errors in output

**If FAILED**:
- Print pytest output showing which E2E test failed
- **FAIL** with message: "E2E tests failed. Fix UI/progress logic before proceeding."
- Do NOT claim work is done

**Note**: E2E tests verify progress polling behavior, job state machine, and terminal lock enforcement. They run fast (no real video processing, uses fixtures).

---

### 5. Release Gate (ASR + CI Rehearsal)

**ONLY run when preparing desktop releases or ASR-related changes**:

**When to run**: If ANY of these conditions are true:
- Files in `.github/workflows/` were modified
- `yanhu.spec` was modified
- `scripts/ci_rehearsal_desktop.sh` was modified
- `docs/DEPENDENCY_MATRIX.md` was modified
- User intends to create a release tag (v*)
- User explicitly requests "desktop ASR build" or ASR features
- Any packaging or build-related changes

**Commands**:
```bash
# Full ASR dependency check
python scripts/runtime_selfcheck.py --profile asr
python scripts/runtime_selfcheck.py --profile all

# Full CI rehearsal (installs deps in clean venv)
bash scripts/ci_rehearsal_desktop.sh
```

**Expected Output** (selfcheck):
```
============================================================
SELF-CHECK PASSED: All dependencies present for profile 'asr'
============================================================
SELF-CHECK PASSED: All dependencies present for profile 'all'
============================================================
```

**Expected Output** (CI rehearsal):
```
============================================================
CI REHEARSAL PASSED
============================================================

All checks completed successfully:
  ✓ ruff check
  ✓ pytest
  ✓ runtime self-check (--profile all)
  ✓ PyInstaller build
  ✓ macOS bundle structure

Build artifacts:
  dist/Yanhu Sessions.app (macOS)
  dist/yanhu/ (Windows)

Ready for release tagging!
============================================================
```

**If FAILED**:
- Print full output showing which check/step failed
- **FAIL** with message: "Release gate failed. Install missing dependencies or fix build issues before proceeding."
- Do NOT claim work is done
- Do NOT suggest creating a tag or release

**Note**: The CI rehearsal script creates a clean venv and installs all deps, so it WILL pass on a clean machine (unlike local dev selfchecks).

### Self-Recommendation Output Format

**CRITICAL REQUIREMENT**: You MUST paste the EXACT command lines you ran and their exit codes. Claims without evidence are FORBIDDEN.

After running all applicable checks, report:

**Default Gate (standard work)**:
```
## Self-Recommendation: [PASS|FAIL]

Default Gate checks (with exact commands and exit codes):

1. Ruff check:
   Command: ruff check src/ tests/ scripts/
   Exit code: [0 or non-zero]

2. Test suite:
   Command: pytest -q
   Exit code: [0 or non-zero]
   Output: [X passed, Y skipped, etc.]

3. Runtime selfcheck:
   Command: python scripts/runtime_selfcheck.py --profile core
   Exit code: [0 or non-zero]

   Command: python scripts/runtime_selfcheck.py --profile app
   Exit code: [0 or non-zero]

   Command: python scripts/runtime_selfcheck.py --profile desktop
   Exit code: [0 or non-zero]

[If any check failed, list details here]

[If all passed:]
All default gate checks passed. Work is ready.

[If any failed:]
Work is NOT complete. Fix failures above and rerun verification.
```

**Default Gate + E2E (UI/progress work)**:
```
## Self-Recommendation: [PASS|FAIL]

Default Gate checks (with exact commands and exit codes):

1. Ruff check:
   Command: ruff check src/ tests/ scripts/
   Exit code: [0 or non-zero]

2. Test suite:
   Command: pytest -q
   Exit code: [0 or non-zero]
   Output: [X passed, Y skipped, etc.]

3. Runtime selfcheck:
   Command: python scripts/runtime_selfcheck.py --profile core
   Exit code: [0 or non-zero]

   Command: python scripts/runtime_selfcheck.py --profile app
   Exit code: [0 or non-zero]

   Command: python scripts/runtime_selfcheck.py --profile desktop
   Exit code: [0 or non-zero]

E2E Gate (UI/progress touched):
   Command: pytest -m e2e -v
   Exit code: [0 or non-zero]
   Output: [X passed, Y skipped, etc.]

[If any check failed, list details here]

[If all passed:]
All checks passed (including E2E). Work is ready.

[If any failed:]
Work is NOT complete. Fix failures above and rerun verification.
```

**Release Gate (packaging/ASR work)**:
```
## Self-Recommendation: [PASS|FAIL]

Release Gate checks (with exact commands and exit codes):

1. Ruff check:
   Command: ruff check src/ tests/ scripts/
   Exit code: [0 or non-zero]

2. Test suite:
   Command: pytest -q
   Exit code: [0 or non-zero]
   Output: [X passed, Y skipped, etc.]

3. Runtime selfcheck:
   Command: python scripts/runtime_selfcheck.py --profile core
   Exit code: [0 or non-zero]

   Command: python scripts/runtime_selfcheck.py --profile app
   Exit code: [0 or non-zero]

   Command: python scripts/runtime_selfcheck.py --profile desktop
   Exit code: [0 or non-zero]

   Command: python scripts/runtime_selfcheck.py --profile asr
   Exit code: [0 or non-zero]

   Command: python scripts/runtime_selfcheck.py --profile all
   Exit code: [0 or non-zero]

4. CI Rehearsal:
   Command: bash scripts/ci_rehearsal_desktop.sh
   Exit code: [0 or non-zero]

[If any check failed, list details here]

[If all passed:]
All release gate checks passed. Ready for release tagging.

[If any failed:]
Release NOT ready. Fix failures above and rerun verification.
```

---

### Self-Lint Check (Anti-Cheat Enforcement)

**Before claiming any work is complete**, run this self-audit on your completion summary:

**FORBIDDEN PATTERNS** (immediate FAIL if found):

1. ❌ `--ignore=tests/e2e` in any command
   - If found: **FAIL** with message: "CHEATING DETECTED: Do not use --ignore to skip tests. Use markers: pytest -m 'not e2e' -q"

2. ❌ Claims like "All tests passed" without exact command and exit code
   - If found: **FAIL** with message: "EVIDENCE MISSING: Must paste exact pytest command and exit code. Example: 'Command: pytest -q, Exit code: 0'"

3. ❌ Claims like "ruff check passed" without showing the command
   - If found: **FAIL** with message: "EVIDENCE MISSING: Must paste exact ruff command and exit code. Example: 'Command: ruff check src/ tests/ scripts/, Exit code: 0'"

4. ❌ `pytest -q tests/` or any path-based filter that excludes root tests
   - If found: **FAIL** with message: "INVALID FILTER: Use 'pytest -q' (all tests) or 'pytest -m \"not e2e\" -q' (exclude E2E via marker)"

**REQUIRED EVIDENCE** in every completion summary:
- Exact command line for each check (copy-pasteable)
- Exit code for each command (0 = pass, non-zero = fail)
- Test count output (e.g., "1055 passed, 1 skipped")

**Example of VALID evidence**:
```
Command: pytest -q
Exit code: 0
Output: 1055 passed, 1 skipped in 45.2s
```

**Example of INVALID (FORBIDDEN)**:
```
✓ All tests passed
```
(Missing command, exit code, and test count)

**If self-lint detects any forbidden pattern or missing evidence**:
- Immediately **FAIL** the verification
- Print: "Self-lint FAILED: [specific violation]"
- Rerun checks and regenerate completion summary with proper evidence

---

## Output

- PASS/FAIL with reasons
- Commands executed (EXACT command lines, not paraphrases)
- Exit codes for every command
- Key artifact snippets (analysis JSON and timeline block)
- Self-Recommendation results (REQUIRED with evidence)
- Self-Lint Check results (REQUIRED before claiming completion)
