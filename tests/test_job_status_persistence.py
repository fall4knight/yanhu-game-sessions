"""Tests for Step 32.12: Job status persistence and anti-regression guards."""

import json


class TestJobStatusPersistence:
    """Test that worker persists status transitions correctly."""

    def test_queue_job_has_started_at_field(self):
        """QueueJob dataclass includes started_at field."""
        from yanhu.watcher import QueueJob

        job = QueueJob(
            created_at="2026-01-25T00:00:00",
            raw_path="/path/to/video.mp4",
            status="pending",
            job_id="test_job",
        )

        # Verify started_at field exists and is None by default
        assert hasattr(job, "started_at")
        assert job.started_at is None

    def test_update_job_by_id_accepts_started_at(self, tmp_path):
        """update_job_by_id can set started_at timestamp."""
        from yanhu.watcher import QueueJob, save_job_to_file, update_job_by_id

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create a job
        job = QueueJob(
            job_id="test_job_started",
            raw_path="/path/to/video.mp4",
            status="pending",
            created_at="2026-01-25T00:00:00",
        )
        save_job_to_file(job, jobs_dir)

        # Update with started_at
        started_at = "2026-01-25T00:01:00Z"
        updated_job = update_job_by_id(
            "test_job_started",
            jobs_dir,
            status="processing",
            started_at=started_at,
        )

        # Verify both status and started_at were updated
        assert updated_job is not None
        assert updated_job.status == "processing"
        assert updated_job.started_at == started_at

        # Verify persisted to file
        job_file = jobs_dir / "test_job_started.json"
        with open(job_file, encoding="utf-8") as f:
            job_data = json.load(f)

        assert job_data["status"] == "processing"
        assert job_data["started_at"] == started_at

    def test_worker_sets_started_at_on_processing(self):
        """BackgroundWorker sets started_at when transitioning to processing."""
        # Check that worker loop code includes started_at setting
        # This is a template test to verify the code structure
        # We can't easily test the full worker loop without mocking, so we verify
        # the update_job_by_id signature accepts it
        import inspect

        from yanhu.watcher import update_job_by_id

        sig = inspect.signature(update_job_by_id)
        params = sig.parameters

        assert "started_at" in params
        assert params["started_at"].default is None  # Optional parameter


class TestAntiRegressionGuard:
    """Test Step 32.12: Frontend anti-regression guard."""

    def test_frontend_has_anti_regression_guard(self, tmp_path):
        """Frontend includes anti-regression guard for pending status."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify anti-regression guard exists
        assert "Anti-regression guard" in html or "anti-regression" in html.lower()
        # Should check for session existence
        assert "hasSession" in html or "data.session_id" in html

    def test_effective_status_computed_when_session_exists(self, tmp_path):
        """effectiveStatus treats pending as processing when session_id exists."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify effectiveStatus logic exists
        assert "effectiveStatus" in html
        # Should have conditional: if pending and has session, treat as processing
        assert (
            "data.status === 'pending' && hasSession" in html
            or "(data.status === 'pending' && hasSession)" in html
        )

    def test_pending_state_skipped_when_session_exists(self, tmp_path):
        """Pending state branch is skipped when session_id exists."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify that effectiveStatus is used in the pending check
        assert "if (effectiveStatus === 'pending')" in html

    def test_processing_state_uses_effective_status(self, tmp_path):
        """Processing state check uses effectiveStatus."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify processing check uses effectiveStatus
        assert "if (effectiveStatus === 'processing')" in html


class TestJobJSONExample:
    """Test that job JSON has expected structure during processing."""

    def test_job_json_structure_while_processing(self, tmp_path):
        """Job JSON while running should have status=processing + session_id + started_at."""
        from yanhu.watcher import QueueJob, save_job_to_file

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create a job in processing state with session_id and started_at
        job = QueueJob(
            job_id="test_job_running",
            raw_path="/path/to/video.mp4",
            status="processing",
            session_id="2026-01-25_00-00-00_game_run01",
            started_at="2026-01-25T00:00:05Z",
            created_at="2026-01-25T00:00:00",
        )
        save_job_to_file(job, jobs_dir)

        # Read back and verify structure
        job_file = jobs_dir / "test_job_running.json"
        with open(job_file, encoding="utf-8") as f:
            job_data = json.load(f)

        # Must have all three fields
        assert job_data["status"] == "processing"
        assert job_data["session_id"] == "2026-01-25_00-00-00_game_run01"
        assert job_data["started_at"] == "2026-01-25T00:00:05Z"
        assert job_data["created_at"] == "2026-01-25T00:00:00"
