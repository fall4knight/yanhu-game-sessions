"""Tests for Step 32.19: Job detail status rendering with stable DOM anchors."""


def test_job_detail_has_status_dom_anchors(tmp_path):
    """Verify job detail page has id='job-status-text' and id='job-session-link'."""
    from yanhu.app import create_app
    from yanhu.watcher import QueueJob, save_job_to_file

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    # Create a processing job
    job = QueueJob(
        job_id="test_job",
        created_at="2026-01-25T00:00:00",
        raw_path="/path/to/video.mp4",
        status="processing",
        session_id="test_session",
    )
    save_job_to_file(job, jobs_dir)

    app = create_app(sessions_dir, jobs_dir=jobs_dir)
    client = app.test_client()

    # Request job detail page
    response = client.get("/jobs/test_job")
    assert response.status_code == 200

    html = response.data.decode("utf-8")

    # Verify DOM anchors exist
    assert 'id="job-status-text"' in html, "Missing id='job-status-text' anchor"
    assert 'id="job-session-link"' in html, "Missing id='job-session-link' anchor"
    assert 'id="job-session-link-container"' in html, \
        "Missing id='job-session-link-container' anchor"

    # Verify only one instance of each anchor (no duplicates)
    assert html.count('id="job-status-text"') == 1, "Duplicate job-status-text anchor"
    assert html.count('id="job-session-link"') == 1, "Duplicate job-session-link anchor"


def test_job_detail_has_render_status_payload_function(tmp_path):
    """Verify job detail page JS contains renderStatusPayload() function."""
    from yanhu.app import create_app
    from yanhu.watcher import QueueJob, save_job_to_file

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    # Create a processing job
    job = QueueJob(
        job_id="test_job",
        created_at="2026-01-25T00:00:00",
        raw_path="/path/to/video.mp4",
        status="processing",
        session_id="test_session",
    )
    save_job_to_file(job, jobs_dir)

    app = create_app(sessions_dir, jobs_dir=jobs_dir)
    client = app.test_client()

    # Request job detail page
    response = client.get("/jobs/test_job")
    assert response.status_code == 200

    html = response.data.decode("utf-8")

    # Verify renderStatusPayload function exists
    assert "function renderStatusPayload(payload)" in html, \
        "Missing renderStatusPayload() function"

    # Verify it updates job-status-text
    assert "getElementById('job-status-text')" in html, \
        "renderStatusPayload doesn't update job-status-text"

    # Verify it updates session link
    assert "getElementById('job-session-link')" in html, \
        "renderStatusPayload doesn't update job-session-link"

    # Verify Step 32.19 marker
    assert "Step 32.19" in html, "Missing Step 32.19 implementation marker"


def test_render_status_payload_called_with_fresh_data(tmp_path):
    """Step 32.20: Verify renderStatusPayload is called with data (not __YANHU_LAST_JOB)."""
    from yanhu.app import create_app
    from yanhu.watcher import QueueJob, save_job_to_file

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    # Create a processing job
    job = QueueJob(
        job_id="test_job",
        created_at="2026-01-25T00:00:00",
        raw_path="/path/to/video.mp4",
        status="processing",
        session_id="test_session",
    )
    save_job_to_file(job, jobs_dir)

    app = create_app(sessions_dir, jobs_dir=jobs_dir)
    client = app.test_client()

    response = client.get("/")
    html = response.data.decode("utf-8")

    # Step 32.20: Verify renderStatusPayload is called with data (fresh from fetch)
    # It should be called INSIDE the fetch promise chain with the response data
    assert "renderStatusPayload(data)" in html, \
        "renderStatusPayload must be called with data (not __YANHU_LAST_JOB)"

    # Verify it's called after setting __YANHU_LAST_JOB but inside promise chain
    last_job_pos = html.find("window.__YANHU_LAST_JOB = data")
    render_call_pos = html.find("renderStatusPayload(data)")

    assert last_job_pos != -1, "window.__YANHU_LAST_JOB = data not found"
    assert render_call_pos != -1, "renderStatusPayload(data) not found"

    # renderStatusPayload should be called AFTER __YANHU_LAST_JOB is set
    assert last_job_pos < render_call_pos, \
        "renderStatusPayload(data) should be called after setting __YANHU_LAST_JOB"

    # Verify Step 32.20 marker
    assert "Step 32.20" in html, "Missing Step 32.20 implementation marker"


def test_status_update_has_debug_log(tmp_path):
    """Step 32.20: Verify debug log prints status updates."""
    from yanhu.app import create_app

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    app = create_app(sessions_dir)
    client = app.test_client()

    response = client.get("/")
    html = response.data.decode("utf-8")

    # Verify debug console.log exists
    assert "console.log('[status]'" in html, \
        "Missing debug console.log for status updates"

    # Verify it logs status, stage, done/total
    assert "data.status" in html
    assert "progress.stage" in html
    assert "done" in html and "total" in html


def test_render_status_payload_called_inside_fetch_promise(tmp_path):
    """Step 32.20: Verify renderStatusPayload is called inside fetch promise chain."""
    from yanhu.app import create_app

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()

    app = create_app(sessions_dir)
    client = app.test_client()

    response = client.get("/")
    html = response.data.decode("utf-8")

    # Find the fetch call
    fetch_pos = html.find("fetch('/api/jobs/' + globalProgressState.jobId + '/status')")
    assert fetch_pos != -1, "Fetch call not found"

    # Find the renderStatusPayload call
    render_pos = html.find("renderStatusPayload(data)")
    assert render_pos != -1, "renderStatusPayload(data) call not found"

    # renderStatusPayload should be called AFTER the fetch (inside the promise chain)
    assert fetch_pos < render_pos, \
        "renderStatusPayload must be called inside the fetch promise chain"

    # Find the terminal lock check
    lock_check_pos = html.find("if (globalProgressState.terminalLocked && !isTerminalStatus)")

    if lock_check_pos != -1:
        # The terminal lock check happens at the beginning of the promise handler
        # renderStatusPayload is called after passing the lock check
        # This is correct because terminal updates bypass the lock
        pass
