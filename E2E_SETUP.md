# E2E UX Test Setup

This document provides a quick start guide for the new end-to-end UX tests.

## What Was Added

**New files:**
- `tests/e2e/test_progress_ui.py` - 5 E2E tests for progress/job state machine
- `tests/e2e/README.md` - Detailed E2E test documentation
- `tests/e2e/__init__.py` - Package marker
- `.github/workflows/e2e-tests.yml` - GitHub Actions workflow for E2E tests
- `TESTING.md` - Complete testing guide
- `E2E_SETUP.md` - This file

**Modified files:**
- `pyproject.toml` - Added `playwright>=1.40` to dev dependencies, added `e2e` pytest marker

## Quick Start

### 1. Install Dependencies

```bash
# Install package with dev dependencies
pip install -e ".[dev,app]"

# Install Playwright browsers (one-time setup)
python -m playwright install --with-deps chromium
```

### 2. Run E2E Tests Locally

```bash
# Run all e2e tests
pytest -m e2e

# Run with verbose output
pytest -m e2e -v

# Run specific test
pytest -m e2e -k test_pending_job_does_not_poll_progress
```

### 3. Run Unit Tests (Excluding E2E)

```bash
# Run all unit tests (skip e2e)
pytest -m "not e2e"

# Or just run pytest (e2e tests require explicit marker)
pytest
```

## Test Coverage

The E2E tests verify these critical UX flows:

### T1: Pending Job Does Not Poll Progress
- **What it tests**: Job with `status="pending"` and no `session_id`
- **Expected**: No requests to `/s/*/progress` endpoints
- **Why**: Prevents 404 errors and unnecessary network traffic

### T2: Processing Without Session ID Does Not Poll Progress
- **What it tests**: Job with `status="processing"` but no `session_id` yet
- **Expected**: No `/progress` requests, UI shows "Waiting for session..."
- **Why**: UI shouldn't poll progress until session is ready

### T3: Session ID Appears, Starts Polling Progress
- **What it tests**: Job with `status="processing"` and `session_id`
- **Expected**:
  - UI polls `/s/<session_id>/progress`
  - Backend returns 200 with starting payload (not 404)
  - No console errors
- **Why**: Once session exists, UI should poll for progress updates

### T4: Terminal Lock - Job Done Wins
- **What it tests**: Job with `status="done"`, even if progress.json is stale
- **Expected**:
  - UI shows "Complete" (not stuck at "transcribe 8/9")
  - Session link visible and clickable
  - Job status takes priority over progress stage
- **Why**: Terminal state from job result is authoritative

### T5: Stop Polling on Terminal State
- **What it tests**: After job reaches "done", verify no more polling
- **Expected**:
  - No new requests to `/api/jobs/<id>` or `/progress`
  - Terminal lock prevents unnecessary API calls
  - UI remains frozen in "done" state
- **Why**: Saves resources and prevents UI flicker

## How E2E Tests Work

1. **Test Server**: Each test starts Flask app on random port with temp directories
2. **Browser Automation**: Playwright controls headless Chromium
3. **Network Interception**: Tests track which endpoints are called
4. **File Manipulation**: Tests write job.json and progress.json directly to temp dirs
5. **UI Verification**: Tests check DOM elements and console logs

**No real video processing** - tests are fast and deterministic.

## CI Integration

The e2e tests run in GitHub Actions:

```yaml
# .github/workflows/e2e-tests.yml
- name: Install Playwright browsers
  run: python -m playwright install --with-deps chromium

- name: Run e2e tests
  run: pytest -m e2e -v
```

Runs on:
- Every push to main
- Every pull request

## Troubleshooting

### Browser Not Found

```bash
# Install Playwright browsers
python -m playwright install --with-deps chromium
```

### Tests Timeout

- Tests use 1-3 second waits for polling behavior
- If tests timeout, check that Flask server starts correctly
- Verify port is available (tests use random ports)

### Import Errors

```bash
# Make sure package is installed in dev mode
pip install -e ".[dev,app]"
```

### See Actual Browser

Edit `tests/e2e/test_progress_ui.py`:

```python
@pytest.fixture
def playwright_browser():
    """Create Playwright browser instance."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Change to False
        yield browser
        browser.close()
```

## Development Workflow

When making UI changes:

1. **Run unit tests** to verify backend logic:
   ```bash
   pytest -m "not e2e"
   ```

2. **Run e2e tests** to verify UX behavior:
   ```bash
   pytest -m e2e
   ```

3. **Fix any failures** - e2e tests catch UX regressions that unit tests miss

## Adding New E2E Tests

Example template:

```python
@pytest.mark.e2e
def test_my_ux_behavior(test_server, browser_context):
    """Test description."""
    # Create test data
    create_job_file(test_server["jobs_dir"], "test_job", status="pending")

    # Open page
    page = browser_context.new_page()
    page.goto(f"{test_server['url']}/jobs/test_job")

    # Verify behavior
    element = page.locator("#my-element")
    assert element.text_content() == "expected"

    page.close()
```

## Resources

- **Playwright Docs**: https://playwright.dev/python/
- **Pytest Markers**: https://docs.pytest.org/en/stable/mark.html
- **Flask Testing**: https://flask.palletsprojects.com/en/stable/testing/

## Questions?

See `tests/e2e/README.md` for detailed documentation on:
- Test architecture
- Helper functions
- Debugging tips
- CI integration
