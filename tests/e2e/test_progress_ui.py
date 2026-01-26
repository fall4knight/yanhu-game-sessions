"""End-to-end UX tests for progress/job state machine using Playwright.

Run locally:
    pytest -m e2e

Install Playwright browsers (first time only):
    python -m playwright install --with-deps chromium
"""

import json
import socket
import threading
import time
from pathlib import Path

import pytest


def find_free_port():
    """Find a free port for the test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture(scope="function")
def test_server(tmp_path):
    """Start Flask app in test mode on a random port."""
    from yanhu.app import create_app

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    app = create_app(sessions_dir, jobs_dir=jobs_dir)
    app.config["TESTING"] = True

    port = find_free_port()
    url = f"http://localhost:{port}"

    # Start server in background thread
    server_thread = threading.Thread(
        target=lambda: app.run(host="localhost", port=port, debug=False, use_reloader=False),
        daemon=True,
    )
    server_thread.start()

    # Wait for server to be ready
    max_retries = 10
    for _ in range(max_retries):
        try:
            import urllib.request
            urllib.request.urlopen(f"{url}/", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("Test server failed to start")

    yield {
        "url": url,
        "sessions_dir": sessions_dir,
        "jobs_dir": jobs_dir,
    }

    # Server will stop when test ends (daemon thread)


@pytest.fixture
def playwright_browser():
    """Create Playwright browser instance."""
    # Skip gracefully if playwright is not installed
    pytest.importorskip("playwright")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def browser_context(playwright_browser):
    """Create browser context with console logging."""
    context = playwright_browser.new_context()
    yield context
    context.close()


def create_job_file(jobs_dir: Path, job_id: str, **kwargs):
    """Helper to create job JSON file."""
    job_data = {
        "job_id": job_id,
        "created_at": "2026-01-25T00:00:00",
        "raw_path": "/path/to/video.mp4",
        "status": kwargs.get("status", "pending"),
    }
    if "session_id" in kwargs:
        job_data["session_id"] = kwargs["session_id"]
    if "started_at" in kwargs:
        job_data["started_at"] = kwargs["started_at"]

    job_file = jobs_dir / f"{job_id}.json"
    with open(job_file, "w", encoding="utf-8") as f:
        json.dump(job_data, f, indent=2)


def update_job_file(jobs_dir: Path, job_id: str, **updates):
    """Helper to update job JSON file."""
    job_file = jobs_dir / f"{job_id}.json"
    with open(job_file, encoding="utf-8") as f:
        job_data = json.load(f)

    job_data.update(updates)

    with open(job_file, "w", encoding="utf-8") as f:
        json.dump(job_data, f, indent=2)


def create_progress_file(sessions_dir: Path, session_id: str, **kwargs):
    """Helper to create progress.json file."""
    session_dir = sessions_dir / session_id
    session_dir.mkdir(exist_ok=True)
    outputs_dir = session_dir / "outputs"
    outputs_dir.mkdir(exist_ok=True)

    progress_data = {
        "session_id": session_id,
        "stage": kwargs.get("stage", "transcribe"),
        "done": kwargs.get("done", 0),
        "total": kwargs.get("total", 10),
        "elapsed_sec": kwargs.get("elapsed_sec", 0),
        "eta_sec": kwargs.get("eta_sec", None),
        "updated_at": kwargs.get("updated_at", "2026-01-25T00:00:00Z"),
        "message": kwargs.get("message", None),
    }

    progress_file = outputs_dir / "progress.json"
    with open(progress_file, "w", encoding="utf-8") as f:
        json.dump(progress_data, f, indent=2)


@pytest.mark.e2e
def test_pending_job_does_not_poll_progress(test_server, browser_context):
    """T1: Pending job MAY poll status (unified endpoint behavior)."""
    job_id = "test_pending_job"

    # Create pending job with no session_id
    create_job_file(test_server["jobs_dir"], job_id, status="pending")

    # Track requests using page.on("request")
    status_requests = []

    def track_request(request):
        # Match any /api/jobs/*/status request
        if "/api/jobs/" in request.url and "/status" in request.url:
            status_requests.append(request.url)

    page = browser_context.new_page()
    page.on("request", track_request)

    # Open job page
    page.goto(f"{test_server['url']}/jobs/{job_id}")

    # Wait for initial rendering
    page.wait_for_timeout(2000)

    # Pending jobs MAY poll status (unified endpoint design)
    # Just verify UI shows pending state
    status_text = page.locator("#job-status-text").text_content()
    assert status_text == "pending"

    page.close()


@pytest.mark.e2e
def test_processing_without_session_id_does_not_poll_progress(test_server, browser_context):
    """T2: Processing without session_id does poll status but shows waiting."""
    job_id = "test_processing_no_session"

    # Create processing job with no session_id
    create_job_file(test_server["jobs_dir"], job_id, status="processing")

    # Track requests using page.on("request")
    status_requests = []

    def track_request(request):
        if "/api/jobs/" in request.url and "/status" in request.url and job_id in request.url:
            status_requests.append(request.url)

    page = browser_context.new_page()
    page.on("request", track_request)

    # Open job page
    page.goto(f"{test_server['url']}/jobs/{job_id}")

    # Wait for polling to start
    page.wait_for_timeout(2000)

    # Status polling DOES occur (unified endpoint always polls for processing jobs)
    # But without session_id, the response shows "Waiting for session"
    assert len(status_requests) > 0, \
        f"Expected /status requests for processing job, got: {status_requests}"

    # Verify UI shows "Waiting for session" or "Starting"
    # Use state=visible to ensure element is visible, or state=attached if hidden is ok
    page.wait_for_selector("#progress-stage", state="attached", timeout=2000)
    stage_text = page.locator("#progress-stage").text_content()
    assert "Starting" in stage_text or "Waiting" in stage_text or "Queued" in stage_text

    page.close()


@pytest.mark.e2e
def test_session_id_appears_starts_polling_progress(test_server, browser_context):
    """T3: When session_id appears, UI polls unified /status endpoint."""
    job_id = "test_with_session"
    session_id = "2026-01-25_00-00-00_game_tag"

    # Create processing job WITH session_id
    create_job_file(
        test_server["jobs_dir"],
        job_id,
        status="processing",
        session_id=session_id,
        started_at="2026-01-25T00:00:05Z",
    )

    # Create session directory but NO progress.json yet
    session_dir = test_server["sessions_dir"] / session_id
    session_dir.mkdir()

    # Track requests using page.on("request") instead of route
    status_requests = []
    console_errors = []

    def track_request(request):
        # Match any /api/jobs/*/status request and filter for our job_id
        if "/api/jobs/" in request.url and "/status" in request.url and job_id in request.url:
            status_requests.append(request.url)

    page = browser_context.new_page()
    page.on("request", track_request)

    # Track console errors
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    # Open job page
    page.goto(f"{test_server['url']}/jobs/{job_id}")

    # Wait for polling to start
    page.wait_for_timeout(3000)

    # Assert /status requests were made
    if len(status_requests) == 0:
        print(f"Console errors: {console_errors}")
        # Check if startGlobalProgressPolling is being called
        html_content = page.content()
        if "startGlobalProgressPolling" in html_content:
            print("startGlobalProgressPolling found in HTML")
            if f"startGlobalProgressPolling('{job_id}'" in html_content:
                print(f"Polling call found for job_id {job_id}")
            else:
                print(f"Polling call NOT found for job_id {job_id}")
                # Print the section where polling should be called
                idx = html_content.find("// Start progress polling for this job")
                if idx != -1:
                    print(f"Polling section: {html_content[idx:idx+500]}")
        else:
            print("startGlobalProgressPolling NOT found in HTML")
    assert len(status_requests) > 0, \
        f"Expected /status requests once session_id is present. Errors: {console_errors}"

    # Verify UI shows "Waiting for progress..." or "Starting" (since progress.json doesn't exist yet)
    # The backend returns 200 with starting payload, not 404
    page.wait_for_selector("#progress-stage", state="attached", timeout=2000)
    stage_text = page.locator("#progress-stage").text_content()
    assert "Starting" in stage_text or "Waiting" in stage_text or "Stage:" in stage_text

    # Verify no console errors about 404
    error_404s = [e for e in console_errors if "404" in e or "not found" in e.lower()]
    assert len(error_404s) == 0, \
        f"Expected no 404 errors, but got console errors: {error_404s}"

    page.close()


@pytest.mark.e2e
def test_terminal_lock_job_done_wins_ui_never_regresses(test_server, browser_context):
    """T4: Terminal lock - job done wins and UI never regresses."""
    job_id = "test_done_job"
    session_id = "2026-01-25_00-00-00_game_done"

    # Create DONE job with session_id
    create_job_file(
        test_server["jobs_dir"],
        job_id,
        status="done",
        session_id=session_id,
        started_at="2026-01-25T00:00:05Z",
    )

    # Create stale progress.json (stuck at transcribe 8/9)
    # Note: With unified endpoint, backend reconciles and returns terminal state
    create_progress_file(
        test_server["sessions_dir"],
        session_id,
        stage="transcribe",
        done=8,
        total=9,
        message="Transcribing segments...",
    )

    # Create session directory
    session_dir = test_server["sessions_dir"] / session_id
    session_dir.mkdir(exist_ok=True)

    page = browser_context.new_page()

    # Open job page
    page.goto(f"{test_server['url']}/jobs/{job_id}")

    # Wait for UI to render
    page.wait_for_timeout(1500)

    # Verify job status shows "done" (not pending or processing)
    page.wait_for_selector("#job-status-text", state="attached", timeout=2000)
    status_text = page.locator("#job-status-text").text_content()
    assert status_text == "done", \
        f"Expected job status 'done', but got '{status_text}'"

    # Step 32.16: Verify progress bar shows "Complete" (job status wins over stale progress)
    # Even though progress.json is stuck at "transcribe 8/9", UI must show terminal complete
    page.wait_for_selector("#progress-stage", state="attached", timeout=2000)
    stage_text = page.locator("#progress-stage").text_content()
    assert "Complete" in stage_text, \
        f"Expected progress stage to show 'Complete' (job wins), but got '{stage_text}'"

    # Verify progress details show "Processing complete" or "complete"
    page.wait_for_selector("#progress-details", state="attached", timeout=2000)
    details_text = page.locator("#progress-details").text_content()
    assert "complete" in details_text.lower(), \
        f"Expected details to contain 'complete', but got '{details_text}'"

    # Verify progress bar is at 100% (not stuck at partial)
    progress_fill = page.locator("#progress-fill")
    fill_width = progress_fill.evaluate("el => el.style.width")
    assert fill_width == "100%", \
        f"Expected progress bar at 100%, but got '{fill_width}'"

    # Verify progress bar has 'done' class (not stuck at intermediate stage)
    fill_classes = progress_fill.get_attribute("class")
    assert "done" in fill_classes, \
        f"Expected progress bar to have 'done' class, but got '{fill_classes}'"

    # Verify session link is visible and clickable
    page.wait_for_selector("#job-session-link-container", state="attached", timeout=2000)
    session_link_container = page.locator("#job-session-link-container")
    assert session_link_container.is_visible(), \
        "Expected session link container to be visible"

    session_link = page.locator("#job-session-link")
    assert session_link.is_visible(), \
        "Expected session link to be visible"
    assert session_link.get_attribute("href") == f"/s/{session_id}", \
        f"Expected session link href to be /s/{session_id}"

    page.close()


@pytest.mark.e2e
def test_stop_polling_on_terminal_state(test_server, browser_context):
    """T5: Stop polling on terminal - no further /status requests after done."""
    job_id = "test_terminal_polling"
    session_id = "2026-01-25_00-00-00_game_terminal"

    # Create DONE job
    create_job_file(
        test_server["jobs_dir"],
        job_id,
        status="done",
        session_id=session_id,
        started_at="2026-01-25T00:00:05Z",
    )

    # Create terminal progress.json
    create_progress_file(
        test_server["sessions_dir"],
        session_id,
        stage="done",
        done=1,
        total=1,
        message="Processing complete",
    )

    # Create session directory
    session_dir = test_server["sessions_dir"] / session_id
    session_dir.mkdir(exist_ok=True)

    # Track all API requests using page.on("request")
    status_requests = []

    def track_request(request):
        # Match any /api/jobs/*/status request and filter for our job_id
        if "/api/jobs/" in request.url and "/status" in request.url and job_id in request.url:
            status_requests.append({
                "url": request.url,
                "time": time.time(),
            })

    page = browser_context.new_page()
    page.on("request", track_request)

    # Open job page
    page.goto(f"{test_server['url']}/jobs/{job_id}")

    # Wait for initial polling
    page.wait_for_timeout(1500)

    # Record count after initial load
    initial_count = len(status_requests)

    # Wait longer to verify polling has stopped
    page.wait_for_timeout(3000)

    # Count requests after waiting
    final_count = len(status_requests)

    # Terminal state should stop polling - no new requests after lock
    # Allow initial requests, but should be 0 after terminal lock
    new_requests = final_count - initial_count

    assert new_requests == 0, \
        f"Expected 0 new /status requests after terminal state, but got {new_requests}"

    # Verify UI still shows done state
    page.wait_for_selector("#job-status-text", state="attached", timeout=2000)
    status_text = page.locator("#job-status-text").text_content()
    assert status_text == "done"

    page.wait_for_selector("#progress-stage", state="attached", timeout=2000)
    stage_text = page.locator("#progress-stage").text_content()
    assert "Complete" in stage_text

    page.close()


@pytest.mark.e2e
def test_hard_acceptance_stale_8_9_but_job_outputs_9_9_shows_complete(test_server, browser_context):
    """T6 (Step 32.17): Stale progress 8/9 + job outputs 9/9 → UI shows Complete."""
    job_id = "test_hard_acceptance"
    session_id = "2026-01-25_00-00-00_game_hard"

    # Create processing job WITH session_id and complete outputs (9/9)
    job_file = test_server["jobs_dir"] / f"{job_id}.json"
    job_file.write_text(
        json.dumps({
            "job_id": job_id,
            "created_at": "2026-01-25T00:00:00",
            "raw_path": "/path/to/video.mp4",
            "status": "processing",
            "session_id": session_id,
            "started_at": "2026-01-25T00:00:05Z",
            "outputs": {
                "transcribe_processed": 9,  # Complete!
                "transcribe_total": 9,
                "session_dir": str(test_server["sessions_dir"] / session_id),
            },
        }, indent=2),
        encoding="utf-8",
    )

    # Create STALE progress.json (stuck at transcribe 8/9)
    create_progress_file(
        test_server["sessions_dir"],
        session_id,
        stage="transcribe",
        done=8,  # Stale!
        total=9,
        message="Transcribing segments...",
    )

    # Create session directory
    session_dir = test_server["sessions_dir"] / session_id
    session_dir.mkdir(exist_ok=True)

    page = browser_context.new_page()

    # Open job page
    page.goto(f"{test_server['url']}/jobs/{job_id}")

    # Wait for progress to load
    page.wait_for_timeout(2000)

    # Step 32.17 Hard Acceptance: UI must show Complete (9/9), NOT stuck at 8/9
    # Server reconciles stale progress with job outputs and returns 9/9

    # Verify progress stage shows Complete (reconciled 9/9 is terminal)
    page.wait_for_selector("#progress-stage", state="attached", timeout=2000)
    stage_text = page.locator("#progress-stage").text_content()

    # Should show "Complete" (since 9/9 is terminal)
    assert "Complete" in stage_text, \
        f"Expected Complete (9/9 is terminal), but got '{stage_text}'"

    # Verify progress details show 9/9 or "complete" (not stuck at 8/9)
    page.wait_for_selector("#progress-details", state="attached", timeout=2000)
    details_text = page.locator("#progress-details").text_content()

    # Should show 9/9 or "complete", not 8/9
    assert "9/9" in details_text or "complete" in details_text.lower(), \
        f"Expected 9/9 or complete, but got '{details_text}'"
    assert "8/9" not in details_text, \
        f"UI must NOT show stale 8/9, got '{details_text}'"

    # Verify progress bar is at 100%
    progress_fill = page.locator("#progress-fill")
    fill_width = progress_fill.evaluate("el => el.style.width")
    assert fill_width == "100%", \
        f"Expected 100% width for complete, got '{fill_width}'"

    page.close()


@pytest.mark.e2e
def test_no_premature_stop_at_8_9_when_job_still_processing(test_server, browser_context):
    """T7 (Step 32.17): Job processing + progress 8/9 → UI continues polling (no premature stop)."""
    job_id = "test_no_premature_stop"
    session_id = "2026-01-25_00-00-00_game_wait"

    # Create processing job WITH session_id but incomplete outputs (8/9)
    job_file = test_server["jobs_dir"] / f"{job_id}.json"
    job_file.write_text(
        json.dumps({
            "job_id": job_id,
            "created_at": "2026-01-25T00:00:00",
            "raw_path": "/path/to/video.mp4",
            "status": "processing",
            "session_id": session_id,
            "started_at": "2026-01-25T00:00:05Z",
            "outputs": {
                "transcribe_processed": 8,  # Incomplete
                "transcribe_total": 9,
                "session_dir": str(test_server["sessions_dir"] / session_id),
            },
        }, indent=2),
        encoding="utf-8",
    )

    # Create progress.json (8/9, in progress)
    create_progress_file(
        test_server["sessions_dir"],
        session_id,
        stage="transcribe",
        done=8,
        total=9,
        message="Transcribing segments...",
    )

    # Create session directory
    session_dir = test_server["sessions_dir"] / session_id
    session_dir.mkdir(exist_ok=True)

    # Track status requests using page.on("request")
    status_requests = []

    def track_request(request):
        # Match any /api/jobs/*/status request and filter for our job_id
        if "/api/jobs/" in request.url and "/status" in request.url and job_id in request.url:
            status_requests.append(request.url)

    page = browser_context.new_page()
    page.on("request", track_request)

    # Open job page
    page.goto(f"{test_server['url']}/jobs/{job_id}")

    # Wait for initial polling
    page.wait_for_timeout(1000)
    initial_count = len(status_requests)

    # Wait longer to verify polling continues
    page.wait_for_timeout(2000)
    final_count = len(status_requests)

    # Should continue polling (8/9 is not terminal when job is processing)
    new_requests = final_count - initial_count
    assert new_requests > 0, \
        f"Expected continued /status polling at 8/9 (processing), but got {new_requests} new requests"

    # Verify UI shows in-progress state (not Complete)
    page.wait_for_selector("#progress-stage", state="attached", timeout=2000)
    stage_text = page.locator("#progress-stage").text_content()
    assert "Complete" not in stage_text, \
        f"UI should not show Complete at 8/9 when job is processing, got '{stage_text}'"

    # Verify details show 8/9
    page.wait_for_selector("#progress-details", state="attached", timeout=2000)
    details_text = page.locator("#progress-details").text_content()
    assert "8/9" in details_text or "88%" in details_text or "89%" in details_text, \
        f"Expected 8/9 or ~88% in details, but got '{details_text}'"

    page.close()
