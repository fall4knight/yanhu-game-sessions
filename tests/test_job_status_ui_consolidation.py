"""Tests for Step 32.13.1: Job status UI with unique DOM anchor."""


class TestJobStatusUIConsolidation:
    """Test that job page has unique DOM anchor for status updates."""

    def test_job_page_has_unique_status_text_id(self, tmp_path):
        """Job page template contains id='job-status-text' exactly once."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create a job
        job = QueueJob(
            job_id="test_job",
            raw_path="/path/to/video.mp4",
            status="pending",
            created_at="2026-01-25T00:00:00",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()

        response = client.get("/jobs/test_job")
        html = response.data.decode("utf-8")

        # Verify unique id exists
        assert 'id="job-status-text"' in html
        # Should appear exactly once
        assert html.count('id="job-status-text"') == 1
        # Should have status-pill class
        assert 'class="status-pill status-' in html

    def test_job_page_has_session_link_container(self, tmp_path):
        """Job page has session link container that can be shown/hidden."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create a job with session_id
        job = QueueJob(
            job_id="test_job_with_session",
            raw_path="/path/to/video.mp4",
            status="processing",
            session_id="2026-01-25_00-00-00_game_tag",
            created_at="2026-01-25T00:00:00",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()

        response = client.get("/jobs/test_job_with_session")
        html = response.data.decode("utf-8")

        # Verify session link container exists
        assert 'id="job-session-link-container"' in html
        assert 'id="job-session-link"' in html

    def test_polling_updates_status_text_element(self, tmp_path):
        """JavaScript polling updates #job-status-text element."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        job = QueueJob(
            job_id="test_job",
            raw_path="/path/to/video.mp4",
            status="processing",
            created_at="2026-01-25T00:00:00",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()

        response = client.get("/jobs/test_job")
        html = response.data.decode("utf-8")

        # Verify polling code accesses #job-status-text
        assert "getElementById('job-status-text')" in html

    def test_status_text_content_updated(self, tmp_path):
        """Polling sets statusText.textContent to job.status."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        job = QueueJob(
            job_id="test_job",
            raw_path="/path/to/video.mp4",
            status="processing",
            created_at="2026-01-25T00:00:00",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()

        response = client.get("/jobs/test_job")
        html = response.data.decode("utf-8")

        # Step 32.19: Verify status text content is updated via renderStatusPayload
        assert "statusText.textContent = payload.status" in html or \
               "statusText.textContent = job.status" in html

    def test_status_class_updated(self, tmp_path):
        """Polling sets statusText.className to status-pill status-<status>."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        job = QueueJob(
            job_id="test_job",
            raw_path="/path/to/video.mp4",
            status="processing",
            created_at="2026-01-25T00:00:00",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()

        response = client.get("/jobs/test_job")
        html = response.data.decode("utf-8")

        # Step 32.19: Verify class is updated with status-pill and status-*
        assert "statusText.className = 'status-pill status-' + payload.status" in html or \
               "statusText.className = 'status-pill status-' + job.status" in html

    def test_terminal_lock_prevents_status_regression(self, tmp_path):
        """Step 32.20: Terminal lock prevents rendering after job reaches done/failed."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        job = QueueJob(
            job_id="test_job",
            raw_path="/path/to/video.mp4",
            status="done",
            created_at="2026-01-25T00:00:00",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()

        response = client.get("/jobs/test_job")
        html = response.data.decode("utf-8")

        # Step 32.20: Terminal lock is now handled by global updateGlobalProgress
        # Verify global terminal lock variable exists
        assert "globalProgressState.terminalLocked" in html
        # Verify lock is set on terminal states
        assert "terminalLocked = true" in html

    def test_polling_sets_last_job_for_debugging(self, tmp_path):
        """Step 32.20: Polling sets window.__YANHU_LAST_JOB for debugging.

        It should not render UI from that variable.
        """
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        job = QueueJob(
            job_id="test_job",
            raw_path="/path/to/video.mp4",
            status="processing",
            created_at="2026-01-25T00:00:00",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Step 32.20: __YANHU_LAST_JOB is still set for debugging
        assert "window.__YANHU_LAST_JOB = data" in html

        # But rendering uses fresh data from fetch response, not cached __YANHU_LAST_JOB
        assert "renderStatusPayload(data)" in html

    def test_session_link_hidden_initially_for_pending_job(self, tmp_path):
        """Session link container is hidden when job has no session_id."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create a pending job without session_id
        job = QueueJob(
            job_id="test_pending_job",
            raw_path="/path/to/video.mp4",
            status="pending",
            created_at="2026-01-25T00:00:00",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()

        response = client.get("/jobs/test_pending_job")
        html = response.data.decode("utf-8")

        # Verify session link container is hidden initially
        assert 'id="job-session-link-container"' in html
        assert 'style="display: none;"' in html

    def test_session_link_visible_for_job_with_session(self, tmp_path):
        """Session link container is visible when job has session_id."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create a job with session_id
        job = QueueJob(
            job_id="test_with_session",
            raw_path="/path/to/video.mp4",
            status="processing",
            session_id="2026-01-25_12-00-00_game_tag",
            created_at="2026-01-25T00:00:00",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()

        response = client.get("/jobs/test_with_session")
        html = response.data.decode("utf-8")

        # Verify session link is present and visible
        assert 'id="job-session-link-container"' in html
        # When session_id exists, the style="display: none;" should NOT be present
        # Check that the container doesn't have display:none
        import re

        link_container_match = re.search(
            r'<div id="job-session-link-container"[^>]*>', html
        )
        assert link_container_match
        # Should not have style="display: none;" when session exists
        assert 'style="display: none;"' not in link_container_match.group(0)
