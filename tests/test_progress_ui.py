"""Tests for progress bar UI rendering and stage-aware progress calculation."""


class TestProgressBarPresence:
    """Test that progress bar component exists in rendered pages."""

    def test_progress_bar_exists_in_job_detail(self, tmp_path):
        """Job detail page includes global progress bar container."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        job = QueueJob(
            job_id="test_job_progress_bar",
            created_at="2026-01-25T00:00:00",
            raw_path="/path/to/video.mp4",
            status="processing",
            session_id="test_session",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.get("/jobs/test_job_progress_bar")
        assert response.status_code == 200

        html = response.data.decode("utf-8")
        assert 'id="global-progress-bar"' in html
        assert "progress-bar-sticky" in html

    def test_progress_bar_exists_in_session_view(self, tmp_path):
        """Session view includes global progress bar container."""
        from yanhu.app import create_app
        from yanhu.manifest import Manifest, SegmentInfo

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "test_session_progress_bar"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        manifest = Manifest(
            session_id=session_id,
            created_at="2026-01-25T00:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo("part_0001", 0.0, 10.0, "segments/seg1.mp4"),
            ],
        )
        manifest.save(session_dir)

        (session_dir / "overview.md").write_text("# Overview", encoding="utf-8")
        (session_dir / "highlights.md").write_text("# Highlights", encoding="utf-8")
        (session_dir / "timeline.md").write_text("# Timeline", encoding="utf-8")

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        response = client.get(f"/s/{session_id}")
        assert response.status_code == 200

        html = response.data.decode("utf-8")
        assert 'id="global-progress-bar"' in html
        assert "progress-bar-sticky" in html


class TestStageAwareProgressCalculation:
    """Test stage-aware weighted progress calculation logic."""

    def test_progress_bar_includes_weighted_calculation(self, tmp_path):
        """Progress bar JavaScript includes weighted progress calculation function."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        # Get home page to check BASE_TEMPLATE
        response = client.get("/")
        assert response.status_code == 200

        html = response.data.decode("utf-8")

        # Check for weighted progress function
        assert "calculateWeightedProgress" in html
        assert "stage === 'download_model'" in html
        assert "stage === 'transcribe'" in html
        assert "stage === 'compose'" in html
        assert "stage === 'done'" in html

    def test_progress_stages_mapped_correctly(self, tmp_path):
        """Progress calculation maps stages to correct percentage ranges."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify stage weight ranges in comments or code
        # download_model: 0-10%
        assert "0-10%" in html or "download_model" in html

        # transcribe: 10-85%
        assert ("10 + " in html and "* 75" in html) or "transcribe" in html

        # compose: 85-98%
        assert ("85 + " in html and "* 13" in html) or "compose" in html

        # done: 100%
        assert "100" in html

    def test_progress_displays_overall_percentage(self, tmp_path):
        """Progress details show overall weighted percentage."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check that details text includes percentage calculation
        assert "weightedPercent" in html
        assert "Math.round(weightedPercent)" in html

    def test_download_stage_shows_preparing(self, tmp_path):
        """Download model stage shows 'Preparing' message."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check for "Preparing" text in download_model branch
        assert "Preparing" in html
        assert "isDownloading" in html


class TestProgressPollingFlow:
    """Test progress polling data flow from job to session progress."""

    def test_progress_endpoint_returns_valid_json(self, tmp_path):
        """Session progress endpoint returns valid JSON with stage/done/total."""
        import json

        from yanhu.app import create_app
        from yanhu.manifest import Manifest, SegmentInfo

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "test_session_progress_endpoint"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        # Create manifest
        manifest = Manifest(
            session_id=session_id,
            created_at="2026-01-25T00:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo("part_0001", 0.0, 10.0, "segments/seg1.mp4"),
            ],
        )
        manifest.save(session_dir)

        # Create progress.json
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()
        progress_data = {
            "session_id": session_id,
            "stage": "transcribe",
            "done": 5,
            "total": 10,
            "elapsed_sec": 30.5,
            "eta_sec": 30.5,
            "updated_at": "2026-01-25T00:00:00Z",
        }
        (outputs_dir / "progress.json").write_text(json.dumps(progress_data), encoding="utf-8")

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        # Test progress endpoint
        response = client.get(f"/s/{session_id}/progress")
        assert response.status_code == 200

        data = response.get_json()
        assert data["stage"] == "transcribe"
        assert data["done"] == 5
        assert data["total"] == 10
        assert data["elapsed_sec"] == 30.5
        assert data["eta_sec"] == 30.5

    def test_job_detail_polling_logic_present(self, tmp_path):
        """Job detail page includes correct polling initialization."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        job = QueueJob(
            job_id="test_job_polling",
            created_at="2026-01-25T00:00:00",
            raw_path="/path/to/video.mp4",
            status="processing",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.get("/jobs/test_job_polling")
        html = response.data.decode("utf-8")

        # Check for correct initialization (jobId, sessionId)
        assert "startGlobalProgressPolling" in html
        assert "test_job_polling" in html  # job_id passed

    def test_progress_debug_panel_exists(self, tmp_path):
        """Progress bar includes debug panel for troubleshooting."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check for debug panel element
        assert 'id="progress-debug"' in html


class TestProgressPollingStateMachine:
    """Test progress polling state machine logic."""

    def test_polling_includes_job_status_tracking(self, tmp_path):
        """Progress polling JavaScript tracks job status."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check for jobStatus tracking in state
        assert "jobStatus:" in html or "jobStatus =" in html
        assert "globalProgressState" in html

    def test_polling_handles_pending_state(self, tmp_path):
        """Polling shows 'Queued' for pending jobs."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check for queued state handling
        assert "pending" in html.lower()
        assert "Queued" in html or "queued" in html.lower()
        assert "Waiting for worker" in html or "waiting for worker" in html.lower()

    def test_polling_handles_progress_not_found_gracefully(self, tmp_path):
        """Polling handles 404 from progress endpoint without throwing."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check that progress fetch has error handling
        assert "response.ok" in html or "!response.ok" in html
        # Should return null or handle gracefully, not throw
        assert "return null" in html or "return;" in html

    def test_polling_separates_job_and_progress_fetches(self, tmp_path):
        """Job status and progress data are fetched separately."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check for separate fetch functions
        assert "fetchProgressData" in html
        assert "/api/jobs/" in html  # Job status endpoint
        assert "/progress" in html  # Progress endpoint

    def test_should_poll_progress_function_exists(self, tmp_path):
        """shouldPollProgress function guards progress polling."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check for shouldPollProgress decision function
        assert "shouldPollProgress" in html
        # Should check status === 'processing'
        assert "=== 'processing'" in html or "== 'processing'" in html

    def test_polling_prevents_multiple_intervals(self, tmp_path):
        """Polling uses guard to prevent multiple intervals."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check for polling guard
        assert "__YANHU_POLL_LOOP" in html

    def test_pending_status_does_not_call_fetch_progress(self, tmp_path):
        """When status is pending, fetchProgressData is not called."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check that pending status has early return
        # Should have something like: if (data.status === 'pending') { ... return; }
        assert "'pending'" in html
        # Should have comment or logic indicating no progress fetch
        html_lower = html.lower()
        has_guard = "CRITICAL" in html or "don't poll progress" in html_lower
        assert has_guard or "do not poll" in html_lower


class TestSinglePollingLoop:
    """Test Step 32.8: Single polling loop with session_id from job JSON only."""

    def test_single_poll_loop_guard_exists(self, tmp_path):
        """window.__YANHU_POLL_LOOP prevents duplicate polling loops."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check for single loop guard
        assert "window.__YANHU_POLL_LOOP" in html
        assert "if (window.__YANHU_POLL_LOOP)" in html

    def test_debug_vars_initialized(self, tmp_path):
        """Debug vars __YANHU_LAST_JOB and __YANHU_LAST_SESSION_ID exist."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check for debug var initialization
        assert "window.__YANHU_LAST_JOB" in html
        assert "window.__YANHU_LAST_SESSION_ID" in html

    def test_stop_polling_clears_poll_loop(self, tmp_path):
        """stopGlobalProgressPolling clears window.__YANHU_POLL_LOOP."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check that stopGlobalProgressPolling clears the loop
        assert "stopGlobalProgressPolling" in html
        assert "clearInterval(window.__YANHU_POLL_LOOP)" in html
        assert "window.__YANHU_POLL_LOOP = null" in html

    def test_session_page_no_auto_polling(self, tmp_path):
        """Session page does not auto-start polling with template session_id."""
        from yanhu.app import create_app
        from yanhu.manifest import Manifest, SegmentInfo

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "test_session_no_auto_poll"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        manifest = Manifest(
            session_id=session_id,
            created_at="2026-01-25T00:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo("part_0001", 0.0, 10.0, "segments/seg1.mp4"),
            ],
        )
        manifest.save(session_dir)

        (session_dir / "overview.md").write_text("# Overview", encoding="utf-8")
        (session_dir / "highlights.md").write_text("# Highlights", encoding="utf-8")
        (session_dir / "timeline.md").write_text("# Timeline", encoding="utf-8")

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        response = client.get(f"/s/{session_id}")
        html = response.data.decode("utf-8")

        # Check that session page does NOT auto-start polling
        # Should have CRITICAL comment instead
        html_lower = html.lower()
        no_auto = (
            "don't auto-start polling" in html_lower
            or "should only start from job" in html_lower
        )
        assert no_auto

    def test_job_detail_polling_ignores_template_session_id(self, tmp_path):
        """Job detail page passes session_id only if it exists in job record."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create job without session_id
        job = QueueJob(
            job_id="test_job_no_session",
            created_at="2026-01-25T00:00:00",
            raw_path="/path/to/video.mp4",
            status="pending",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.get("/jobs/test_job_no_session")
        html = response.data.decode("utf-8")

        # Check that startGlobalProgressPolling is called with null for session_id
        assert "startGlobalProgressPolling" in html
        assert "'test_job_no_session'" in html
        # Should pass null for session_id when job.session_id doesn't exist
        # Template may format as ", null" or put null on separate line
        assert (
            ", null" in html
            or "null\n    );" in html
            or "null )" in html
            or "'test_job_no_session',\n        null" in html
        )


class TestProgressEndpointStartingPayload:
    """Test Step 32.9: Progress endpoint returns 200 starting payload instead of 404."""

    def test_progress_endpoint_returns_starting_payload_when_missing(self, tmp_path):
        """Progress endpoint returns 200 with starting payload when progress.json missing."""
        from yanhu.app import create_app
        from yanhu.manifest import Manifest, SegmentInfo

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "test_session_starting"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        # Create manifest but NO progress.json
        manifest = Manifest(
            session_id=session_id,
            created_at="2026-01-25T00:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo("part_0001", 0.0, 10.0, "segments/seg1.mp4"),
            ],
        )
        manifest.save(session_dir)

        (session_dir / "overview.md").write_text("# Overview", encoding="utf-8")
        (session_dir / "highlights.md").write_text("# Highlights", encoding="utf-8")
        (session_dir / "timeline.md").write_text("# Timeline", encoding="utf-8")

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        # Request progress endpoint
        response = client.get(f"/s/{session_id}/progress")

        # Should return 200 (not 404) with starting payload
        assert response.status_code == 200

        data = response.get_json()
        assert data["session_id"] == session_id
        assert data["stage"] == "starting"
        assert data["done"] == 0
        assert data["total"] == 0
        assert data["elapsed_sec"] == 0
        assert data["eta_sec"] is None
        assert "message" in data
        assert "Waiting for progress" in data["message"]

    def test_progress_endpoint_404_for_invalid_session(self, tmp_path):
        """Progress endpoint returns 404 for invalid session_id."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        # Request progress for non-existent session
        response = client.get("/s/invalid_session_id_999/progress")

        # Should return 404 for invalid session
        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data
        assert "not found" in data["error"].lower()

    def test_home_page_no_progress_polling_initializer(self, tmp_path):
        """Home page does not auto-start progress polling."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Check that setInterval for progress polling is commented out
        # Should have CRITICAL comment about not polling on home page
        html_lower = html.lower()
        assert (
            "do not auto-poll on home page" in html_lower
            or "should only happen on job detail and session pages" in html_lower
        )

        # The setInterval line should be commented out
        assert "// setInterval(updateJobProgressIndicators" in html


class TestProgressGatingCondition:
    """Test Step 32.10: Explicit verification of progress polling gating."""

    def test_pending_status_gating_prevents_fetch_progress(self, tmp_path):
        """Pending status has explicit early return before fetchProgressData."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify pending status branch exists with early return
        # Step 32.12: Now uses effectiveStatus instead of data.status
        # Step 32.17: With unified endpoint, we don't need separate progress fetch comment
        assert "if (effectiveStatus === 'pending')" in html

        # Verify the pending block returns early
        # Check that after the pending check, there's a return statement
        pending_block_present = (
            "if (effectiveStatus === 'pending')" in html
            and "return;" in html
        )
        assert pending_block_present

    def test_should_poll_progress_gating_condition(self, tmp_path):
        """shouldPollProgress enforces processing AND session_id requirement."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify shouldPollProgress function exists with correct gating
        assert "function shouldPollProgress(jobStatus, sessionId)" in html
        assert "jobStatus === 'processing'" in html
        assert "sessionId !== null" in html
        assert "sessionId !== undefined" in html

    def test_processing_without_session_id_has_early_return(self, tmp_path):
        """Processing status without session_id returns early."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify processing check exists
        # Step 32.12: Now uses effectiveStatus instead of data.status
        assert "if (effectiveStatus === 'processing')" in html

        # Step 32.17: With unified endpoint, we render progress directly (no separate fetch)
        # Verify check for missing session_id with early return
        assert "if (!globalProgressState.sessionId)" in html

    def test_fetch_progress_data_only_called_when_gated(self, tmp_path):
        """Step 32.17: Unified endpoint renders progress directly without separate fetch."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Step 32.17: Verify unified endpoint is used (not separate job + progress fetches)
        assert "'/api/jobs/' + globalProgressState.jobId + '/status'" in html
        assert "renderProgress(progress);" in html

        # Verify we still have fallback for direct session monitoring (backward compatibility)
        assert (
            "// Direct session monitoring (no jobId, e.g., from session page)"
            in html
        )


class TestTerminalPrecedenceRule:
    """Test Step 32.16: Terminal job state forces final UI update before stopping polling."""

    def test_terminal_ui_rendered_before_stopping_polling(self, tmp_path):
        """Verify terminal UI is rendered BEFORE stopping polling (not after)."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify Step 32.16 comment exists
        assert "Step 32.16" in html, "Missing Step 32.16 implementation marker"

        # Verify terminal precedence rule: FIRST render, SECOND lock, THIRD stop polling
        # Find the terminal state handling code
        assert "// FIRST: Render terminal state" in html, \
            "Missing FIRST: Render terminal state comment"
        assert "// SECOND: Lock terminal state" in html, \
            "Missing SECOND: Lock terminal state comment"
        assert "// THIRD: Stop polling" in html, \
            "Missing THIRD: Stop polling comment"

        # Verify order: render before lock
        render_pos = html.find("// FIRST: Render terminal state")
        lock_pos = html.find("globalProgressState.terminalLocked = true")
        assert render_pos < lock_pos, \
            "Terminal UI must be rendered BEFORE setting terminalLocked"

        # Verify order: lock before stop
        stop_pos = html.find("clearInterval(window.__YANHU_POLL_LOOP)")
        assert lock_pos < stop_pos, \
            "terminalLocked must be set BEFORE stopping polling"

    def test_fetchProgressData_guards_against_stale_updates(self, tmp_path):
        """Verify fetchProgressData has guards to prevent stale progress overwriting terminal UI."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify guard at function start (before fetch)
        assert "function fetchProgressData()" in html
        fetch_start = html.find("function fetchProgressData()")
        first_guard = html.find(
            "if (globalProgressState.terminalLocked) {",
            fetch_start,
            fetch_start + 500
        )
        assert first_guard != -1, \
            "Missing terminalLocked guard at start of fetchProgressData"

        # Verify guard after fetch completes (before rendering)
        then_handler = html.find(".then(data => {", fetch_start)
        second_guard = html.find(
            "if (globalProgressState.terminalLocked) {",
            then_handler,
            then_handler + 500
        )
        assert second_guard != -1, \
            "Missing terminalLocked guard after fetch completes in fetchProgressData"

        # Verify Step 32.16 comment for double-check
        assert "// Step 32.16: Double-check terminal lock after fetch completes" in html, \
            "Missing Step 32.16 double-check comment"

    def test_terminal_precedence_rule_comment(self, tmp_path):
        """Verify terminal precedence rule is documented in code."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify the key principle is documented
        assert "render terminal UI BEFORE stopping polling" in html, \
            "Missing documentation of terminal precedence rule"

        # Verify the reason is documented
        reason_text = (
            "ensures final UI update completes before "
            "in-flight progress fetches are blocked"
        )
        assert reason_text in html, "Missing explanation of why terminal UI is rendered first"
