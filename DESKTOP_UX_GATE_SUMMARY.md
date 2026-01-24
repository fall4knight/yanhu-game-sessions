# Desktop UX Verification Gate - Implementation Summary

## Overview

Added deterministic verification gate (`yanhu verify --desktop-ux`) to enforce critical non-programmer UX contracts before release. Prevents regressions in:
- ffprobe discovery for packaged apps
- Quit Server hard-stop reliability
- Launcher compatibility contracts

## Implementation

### 1. Core Verification Module (`src/yanhu/verify.py`)

Added `verify_desktop_ux()` function with three checks:

**Check A: ffprobe Discovery Robustness**
- Verifies `find_ffprobe()` exists and is callable
- Inspects source code to ensure `shutil.which` is used for PATH lookup
- Inspects source code to ensure fallback paths exist (`/opt/homebrew/bin`, `/usr/local/bin`)
- Catches packaged app regressions where shell PATH is not available

**Check B: Quit Server Hard-Stop**
- Verifies `/api/shutdown` endpoint exists
- Inspects source code for `os._exit(0)` fallback (reliable process termination)
- Verifies `shutdown_token` security is present
- Verifies localhost-only restriction (`127.0.0.1`, `localhost`)

**Check C: Launcher Compatibility Contract**
- Verifies `create_app()` accepts `jobs_dir` kwarg
- Verifies `create_app()` accepts str paths (not just Path objects)
- Verifies `run_app()` accepts `debug` kwarg (backward compatibility)
- Dry-run test: calls `create_app()` with str paths to ensure no crashes

### 2. CLI Command (`src/yanhu/cli.py`)

Added `yanhu verify --desktop-ux` command:
```bash
yanhu verify --desktop-ux
```

Output format:
```
Running Desktop UX Smoke Gate...

✓ Desktop UX verification passed

All checks:
  ✓ ffprobe discovery (shutil.which + fallback paths)
  ✓ Quit Server hard-stop (os._exit fallback)
  ✓ Launcher compatibility (create_app/run_app kwargs)
```

If checks fail, exits with non-zero code and detailed error messages.

### 3. Test Suite (`tests/test_verify_desktop_ux.py`)

**18 new tests** covering:

**TestVerifyDesktopUX** (7 tests):
- `test_passes_in_current_codebase` - End-to-end validation
- `test_checks_ffprobe_discovery` - Monkeypatched missing function
- `test_checks_shutdown_endpoint_exists` - Endpoint presence
- `test_checks_os_exit_fallback` - Hard-stop verification
- `test_checks_launcher_compatibility` - Signature validation
- `test_catches_missing_create_app` - Monkeypatched missing function
- `test_all_checks_return_detailed_errors` - Error format validation

**TestFFprobeDiscoveryContract** (3 tests):
- `test_find_ffprobe_exists_and_is_callable`
- `test_find_ffprobe_uses_shutil_which`
- `test_find_ffprobe_has_fallback_paths`

**TestQuitServerContract** (4 tests):
- `test_shutdown_endpoint_exists`
- `test_shutdown_has_os_exit_fallback`
- `test_shutdown_requires_token`
- `test_shutdown_localhost_only`

**TestLauncherCompatibilityContract** (4 tests):
- `test_create_app_accepts_jobs_dir`
- `test_create_app_accepts_str_paths`
- `test_run_app_accepts_debug_kwarg`
- `test_create_app_callable_with_str_paths`

All tests use source code inspection (`inspect.getsource()`) and signature validation (`inspect.signature()`) for deterministic checks.

### 4. CI Integration (`.github/workflows/ci.yml`)

Added step after pytest:
```yaml
- name: Verify desktop UX contracts
  run: yanhu verify --desktop-ux
```

Any regression now fails CI before merge/release.

### 5. Documentation Updates

**RUNBOOK.md** - Added "Release Smoke Test (Desktop UX Gate)" section:
- Command usage: `yanhu verify --desktop-ux`
- What it checks (3 bullet points)
- Release checklist (4 steps):
  1. Run `yanhu verify --desktop-ux` (must pass)
  2. Run full test suite (must pass)
  3. Manual smoke tests (4 items)

**PROJECT_PLAN.md** - Added to M9.0 checklist:
- Desktop UX verification gate checklist (6 items, all marked [x])
- Progress log entry with full details

## Test Results

```bash
$ pytest tests/test_verify_desktop_ux.py -v
==================== 18 passed in 0.14s ====================

$ pytest tests/ -q
==================== 852 passed in 8.25s ====================

$ yanhu verify --desktop-ux
Running Desktop UX Smoke Gate...

✓ Desktop UX verification passed

All checks:
  ✓ ffprobe discovery (shutil.which + fallback paths)
  ✓ Quit Server hard-stop (os._exit fallback)
  ✓ Launcher compatibility (create_app/run_app kwargs)
```

## CI Invocation

```yaml
# .github/workflows/ci.yml
- name: Run tests
  run: pytest -q

- name: Verify desktop UX contracts
  run: yanhu verify --desktop-ux
```

CI runs on every push/PR to main. Failures block merge.

## Acceptance Criteria (Met)

✓ CI runs `yanhu verify --desktop-ux` with [dev,app] extras installed
✓ Any regression (ffprobe PATH, quit not exiting, kwargs mismatch) fails CI before release
✓ Verification gate is deterministic and testable
✓ RUNBOOK includes "Release Smoke Test" guidance
✓ PROJECT_PLAN checklist updated with all items marked [x]

## Files Changed

**New files:**
- `tests/test_verify_desktop_ux.py` (212 lines, 18 tests)
- `DESKTOP_UX_GATE_SUMMARY.md` (this file)

**Modified files:**
- `src/yanhu/verify.py` (+108 lines: verify_desktop_ux function)
- `src/yanhu/cli.py` (+43 lines: verify command)
- `.github/workflows/ci.yml` (+3 lines: verification step)
- `docs/RUNBOOK.md` (+28 lines: Release Smoke Test section)
- `docs/PROJECT_PLAN.md` (+8 lines: M9.0 checklist + progress log)

**Total test count:** 852 tests (was 834, added 18)

## Future Enhancements (Not in Scope)

These checks are **deliberately scoped** to non-programmer-critical UX:
- ❌ Not checking: API key management (programmer concern)
- ❌ Not checking: Pipeline correctness (covered by test suite)
- ❌ Not checking: Performance benchmarks (future milestone)
- ❌ Not checking: UI styling/layout (subjective)

The gate is **release-blocking** and **deterministic only**.
