# Testing Guide

This document describes how to run tests for the Yanhu Game Sessions project.

## Test Categories

### Unit Tests (Default)

Standard pytest tests that verify individual components.

```bash
# Run all unit tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_watcher.py

# Run specific test
pytest tests/test_watcher.py::TestJobQueue::test_create_job
```

### End-to-End (E2E) Tests

Browser-based tests using Playwright that verify the full UX flow for progress tracking and job state management.

**First-time setup:**

1. Install dev dependencies including Playwright:
   ```bash
   pip install -e ".[dev,app]"
   ```

2. Install Playwright browsers (one-time setup):
   ```bash
   python -m playwright install --with-deps chromium
   ```

**Running e2e tests:**

```bash
# Run all e2e tests
pytest -m e2e

# Run with verbose output
pytest -m e2e -v

# Run specific e2e test
pytest -m e2e -k test_pending_job_does_not_poll_progress
```

**What e2e tests cover:**
- Progress polling behavior (when to poll, when to stop)
- Job status state machine (pending → processing → done)
- Terminal lock enforcement (UI never regresses after done)
- Session link visibility
- Console error prevention (no 404 spam)

See `tests/e2e/README.md` for detailed e2e test documentation.

## Running Specific Test Suites

```bash
# Run only unit tests (exclude e2e)
pytest -m "not e2e"

# Run only e2e tests
pytest -m e2e

# Run tests matching a pattern
pytest -k "progress"

# Run with coverage
pytest --cov=yanhu --cov-report=html

# Run with markers
pytest -m "slow"  # Run slow tests
pytest -m "not slow"  # Skip slow tests
```

## Linting

```bash
# Run ruff linter
ruff check src/ tests/

# Auto-fix issues
ruff check --fix src/ tests/

# Check specific directory
ruff check src/yanhu/
```

## Continuous Integration

The project uses GitHub Actions for CI:

1. **Unit Tests**: Run on every push/PR
2. **E2E Tests**: Run separately with Playwright browser installation
3. **Linting**: Run ruff on all Python code

See `.github/workflows/` for workflow definitions.

## Release Gate

Before a release tag (`v*`) can publish binaries, the following checks must pass in order:

1. **E2E Tests** (ubuntu-latest): All 5 end-to-end UX tests must pass
   - Runs first as a gate for desktop builds
   - Verifies progress polling, job state machine, terminal lock
   - Fast (no real video processing, uses fixtures)

2. **Desktop Builds** (macOS + Windows): Both platforms must build successfully
   - Depends on E2E tests passing
   - Includes runtime self-check (pre-packaging) with `--profile all`
   - Includes packaged import selfcheck for ASR dependencies
   - Bundles app into `.app` (macOS) or `.exe` (Windows) with PyInstaller

3. **Release Job**: Creates GitHub release and uploads artifacts
   - Depends on both desktop builds completing
   - Uploads `Yanhu-Sessions-macOS.zip` and `Yanhu-Sessions-Windows.zip`
   - Only runs on tags (not manual workflow_dispatch)

**Workflow dependency chain:**
```
e2e-tests (ubuntu-latest)
    ↓
    ├── build-macos (macos-latest)
    └── build-windows (windows-latest)
           ↓
        release (ubuntu-latest, tags only)
```

If E2E tests fail, the entire workflow stops and no binaries are published.

**Trigger conditions:**
- **Tags** (`v*`): Full workflow (e2e → builds → release)
- **Manual** (`workflow_dispatch`): Partial workflow (e2e → builds, no release)
- **PRs/Pushes to main**: E2E tests only (separate workflow)

See `.github/workflows/build-desktop.yml` for the full release workflow.

## Test Organization

```
tests/
├── e2e/                    # End-to-end browser tests
│   ├── __init__.py
│   ├── README.md          # E2E test documentation
│   └── test_progress_ui.py
├── test_*.py              # Unit tests
└── conftest.py            # Shared fixtures (if needed)
```

## Writing Tests

### Unit Test Example

```python
def test_my_function():
    """Test description."""
    from yanhu.mymodule import my_function

    result = my_function("input")
    assert result == "expected"
```

### E2E Test Example

```python
@pytest.mark.e2e
def test_ui_behavior(test_server, browser_context):
    """Test UI behavior."""
    page = browser_context.new_page()
    page.goto(f"{test_server['url']}/jobs/test_job")

    # Interact with page
    element = page.locator("#my-element")
    assert element.text_content() == "expected"

    page.close()
```

## Troubleshooting

### Playwright Issues

**Error: Browser not found**
```bash
python -m playwright install --with-deps chromium
```

**Error: Port already in use**
- E2E tests use random ports, should not conflict
- If issues persist, check for lingering Flask processes

### Test Failures

**Flaky tests**
- E2E tests include timeouts and waits to handle async behavior
- If tests fail intermittently, check network timing

**Import errors**
- Make sure you've installed the package: `pip install -e ".[dev,app]"`
- Check Python path: `echo $PYTHONPATH`

## Test Markers

Available pytest markers:

- `e2e`: End-to-end browser tests using Playwright
- (Add more markers as needed)

Define markers in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "e2e: end-to-end tests using Playwright",
]
```
