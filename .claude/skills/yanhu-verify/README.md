# Yanhu-Verify Helper

## Purpose

This directory contains helper scripts for the `/yanhu-verify` skill to eliminate shell noise from verification runs.

## Problem

Previously, the verify skill used `bash -lc 'set -a; source .env; ...'` patterns to load environment variables. The `-l` flag makes bash a login shell, which sources profile files (like `~/.zshrc`, `~/.bash_profile`) that may contain tool initializations (gvm, nvm, rvm, etc.), producing noise like:

```
cd:1: command not found: __gvm_is_function
cd:16: command not found: __gvm_read_environment_file
...
```

## Solution

### `run_with_env.py`

A Python helper script that:
1. Loads `.env` using `python-dotenv` (or manual parsing as fallback)
2. Runs commands via `subprocess.run()` without invoking bash as a login shell
3. Filters shell noise from stderr (gvm, encode/decode functions, cd errors)

**Usage:**
```bash
.claude/skills/yanhu-verify/run_with_env.py yanhu analyze --session <id> --backend claude
```

**Benefits:**
- No `bash -lc` invocation → no profile sourcing → no gvm noise in command output
- Python-native env loading (python-dotenv)
- Stderr filtering removes noise from command output
- Deterministic, testable behavior

## Verification Semantic Guarantee

The helper script **does not change verification semantics**:
- ✅ Same environment variables loaded (.env file)
- ✅ Same commands executed
- ✅ Same verification checks
- ✅ Same pass/fail criteria

Only the **method of loading .env** changed: from bash sourcing to Python dotenv.

## Testing

See `tests/test_verify_helper.py` for tests that verify:
- Helper script exists and is executable
- Helper uses python-dotenv (not bash -lc)
- Helper filters shell noise
- skill.md no longer uses bash -lc patterns
- Verification tasks and checks are unchanged

## Note on Remaining Noise

If you still see gvm/cd noise in Bash tool output, it's from **Claude Code's Bash tool wrapper**, not from the commands themselves. The helper script ensures clean command output, but cannot control Claude Code's tool initialization.

To verify clean output, check that actual command results appear without noise interspersed:
```
yanhu, version 0.1.0   ← Clean output
```

Not:
```
cd:1: __gvm_is_function
yanhu, version 0.1.0   ← Noise interspersed with output
cd:16: __gvm_read...
```
