# End-to-End UX Tests

End-to-end tests for the progress/job state machine using Playwright for Python.

## Setup

1. Install Playwright as a dev dependency:
   ```bash
   pip install -e ".[dev,app]"
   ```

2. Install Playwright browsers (first time only):
   ```bash
   python -m playwright install --with-deps chromium
   ```

## Running Tests Locally

Run all e2e tests:
```bash
pytest -m e2e
```

Run specific test:
```bash
pytest -m e2e -k test_pending_job_does_not_poll_progress
```

Run with verbose output:
```bash
pytest -m e2e -v
```

Run with headed browser (to see the UI):
```bash
# Modify test file to set headless=False in playwright_browser fixture
```

## Test Coverage

The e2e tests verify the following UX behaviors:

1. **T1: Pending job does NOT poll /progress**
   - Job with status="pending" and no session_id
   - UI should not make any requests to /s/*/progress
   - Prevents unnecessary 404 errors and network noise

2. **T2: Processing without session_id does NOT poll /progress**
   - Job with status="processing" but no session_id yet
   - UI shows "Waiting for session..." or "Queued"
   - No /progress requests until session_id is available

3. **T3: When session_id appears, UI starts polling /progress**
   - Job with status="processing" and session_id
   - UI starts polling /s/<session_id>/progress
   - Backend returns 200 with starting payload (not 404)
   - No console errors

4. **T4: Terminal lock - job done wins and UI never regresses**
   - Job with status="done" and session_id
   - Even if progress.json is stale (e.g., transcribe 8/9), UI shows "Complete"
   - Session link remains visible and clickable
   - Job status takes priority over progress stage

5. **T5: Stop polling on terminal state**
   - After job reaches "done", verify no further polling requests
   - Terminal lock prevents unnecessary API calls
   - UI remains frozen in terminal state

## CI Integration

Add this step to your GitHub Actions workflow:

```yaml
- name: Install Playwright
  run: python -m playwright install --with-deps chromium

- name: Run e2e tests
  run: pytest -m e2e -v
```

Or run as a separate job:

```yaml
e2e-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.10'
    - name: Install dependencies
      run: |
        pip install -e ".[dev,app]"
        python -m playwright install --with-deps chromium
    - name: Run e2e tests
      run: pytest -m e2e -v
```

## Test Architecture

- **Fixtures**:
  - `test_server`: Starts Flask app in test mode on random port
  - `playwright_browser`: Creates Playwright browser instance
  - `browser_context`: Creates browser context with console logging

- **Helpers**:
  - `create_job_file()`: Write job JSON to jobs directory
  - `update_job_file()`: Update existing job JSON
  - `create_progress_file()`: Write progress.json to session directory

- **Approach**:
  - No real video processing - tests write JSON files directly
  - Flask app runs in test mode with temp directories
  - Playwright intercepts network requests to verify polling behavior
  - Console logging captures errors for debugging

## Debugging

If tests fail:

1. Check console output for errors
2. Verify Flask server started correctly
3. Check that Playwright browsers are installed
4. Run with `-v` for verbose output
5. Temporarily set `headless=False` to see browser UI

Common issues:
- Port already in use: Test uses random port, should not conflict
- Browser not found: Run `python -m playwright install --with-deps chromium`
- Flask app not starting: Check that all dependencies are installed (`pip install -e ".[dev,app]"`)
