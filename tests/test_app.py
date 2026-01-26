"""Tests for the web app viewer."""

import json


class TestAppCreation:
    """Test Flask app creation and configuration."""

    def test_create_app_with_valid_sessions_dir(self, tmp_path):
        """App can be created with a valid sessions directory."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        assert app is not None
        assert app.config["sessions_dir"] == sessions_dir

    def test_create_app_with_jobs_dir_parameter(self, tmp_path):
        """App accepts jobs_dir parameter for backward compatibility."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        custom_jobs_dir = tmp_path / "custom_jobs"
        custom_jobs_dir.mkdir()

        # Test with string path
        app = create_app(sessions_dir, jobs_dir=str(custom_jobs_dir))
        assert app.config["jobs_dir"] == custom_jobs_dir

        # Test with Path object
        app2 = create_app(sessions_dir, jobs_dir=custom_jobs_dir)
        assert app2.config["jobs_dir"] == custom_jobs_dir

        # Test with None (should use default derived path)
        app3 = create_app(sessions_dir, jobs_dir=None)
        expected = sessions_dir.parent / "_queue" / "jobs"
        assert app3.config["jobs_dir"] == expected


class TestSessionListing:
    """Test session listing route."""

    def test_index_lists_sessions_newest_first(self, tmp_path):
        """Index route lists sessions ordered by created_at descending."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create test sessions with different created_at
        session1 = sessions_dir / "2026-01-23_10-00-00_game_run01"
        session1.mkdir()
        (session1 / "manifest.json").write_text(
            json.dumps(
                {
                    "session_id": "2026-01-23_10-00-00_game_run01",
                    "created_at": "2026-01-23T10:00:00",
                    "source_video": "/path/to/video.mp4",
                    "source_video_local": "source/video.mp4",
                    "segment_duration_seconds": 10,
                    "segments": [],
                }
            )
        )

        session2 = sessions_dir / "2026-01-24_10-00-00_game_run02"
        session2.mkdir()
        (session2 / "manifest.json").write_text(
            json.dumps(
                {
                    "session_id": "2026-01-24_10-00-00_game_run02",
                    "created_at": "2026-01-24T10:00:00",  # Newer
                    "source_video": "/path/to/video.mp4",
                    "source_video_local": "source/video.mp4",
                    "segment_duration_seconds": 10,
                    "segments": [],
                }
            )
        )

        app = create_app(sessions_dir)
        client = app.test_client()
        response = client.get("/")

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Verify both sessions are listed
        assert "2026-01-23_10-00-00_game_run01" in html
        assert "2026-01-24_10-00-00_game_run02" in html

        # Verify newer session appears first (simple check)
        pos1 = html.find("2026-01-24_10-00-00_game_run02")
        pos2 = html.find("2026-01-23_10-00-00_game_run01")
        assert pos1 < pos2, "Newer session should appear before older session"

    def test_index_marks_partial_sessions(self, tmp_path):
        """Index route lists sessions with transcribe_coverage."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create partial session
        session = sessions_dir / "2026-01-23_10-00-00_game_run01"
        session.mkdir()
        (session / "manifest.json").write_text(
            json.dumps(
                {
                    "session_id": "2026-01-23_10-00-00_game_run01",
                    "created_at": "2026-01-23T10:00:00",
                    "source_video": "/path/to/video.mp4",
                    "source_video_local": "source/video.mp4",
                    "segment_duration_seconds": 10,
                    "segments": [],
                    "transcribe_coverage": {"processed": 2, "total": 5, "skipped_limit": 3},
                }
            )
        )

        app = create_app(sessions_dir)
        client = app.test_client()
        response = client.get("/")

        assert response.status_code == 200
        html = response.data.decode("utf-8")
        # Verify session is listed with done status
        assert "2026-01-23_10-00-00_game_run01" in html
        assert "status-done" in html

    def test_index_handles_empty_sessions_dir(self, tmp_path):
        """Index route handles empty sessions directory gracefully."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()
        response = client.get("/")

        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "No sessions or jobs found" in html


class TestSessionView:
    """Test session view route."""

    def test_session_view_returns_200_with_required_files(self, tmp_path):
        """Session view returns 200 when all required markdown files exist."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        # Create manifest
        (session_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "session_id": session_id,
                    "created_at": "2026-01-23T10:00:00",
                    "source_video": "/path/to/video.mp4",
                    "source_video_local": "source/video.mp4",
                    "segment_duration_seconds": 10,
                    "segments": [],
                }
            )
        )

        # Create required markdown files
        (session_dir / "overview.md").write_text("# Overview\n\nTest overview")
        (session_dir / "highlights.md").write_text("# Highlights\n\n- [00:00] Test highlight")
        (session_dir / "timeline.md").write_text("# Timeline\n\n### part_0001\n\nTest timeline")

        app = create_app(sessions_dir)
        client = app.test_client()
        response = client.get(f"/s/{session_id}")

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Verify tabs are present
        assert "Overview" in html
        assert "Highlights" in html
        assert "Timeline" in html
        assert "Manifest" in html

        # Verify content is rendered
        assert "Test overview" in html

    def test_session_view_returns_404_for_nonexistent_session(self, tmp_path):
        """Session view returns 404 for nonexistent session."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()
        response = client.get("/s/nonexistent_session")

        assert response.status_code == 404
        assert "not found" in response.data.decode("utf-8").lower()

    def test_session_view_returns_200_with_warning_when_missing_markdown_files(
        self, tmp_path
    ):
        """Session view returns 200 with warning when markdown files are missing (Step 32.14)."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        # Only create manifest, no markdown files
        (session_dir / "manifest.json").write_text(
            json.dumps({"session_id": session_id})
        )

        app = create_app(sessions_dir)
        client = app.test_client()
        response = client.get(f"/s/{session_id}")

        # Step 32.14: Changed to return 200 with warning instead of 404
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        # Should have warning banner about session being finalized
        assert "Session is still being finalized" in html
        # Should list missing files
        assert "overview.md" in html
        assert "timeline.md" in html
        assert "highlights.md" in html


class TestProgressRoute:
    """Test progress.json route."""

    def test_progress_returns_json_when_present(self, tmp_path):
        """Progress route returns JSON when progress.json exists."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        progress_data = {
            "session_id": session_id,
            "stage": "transcribe",
            "done": 5,
            "total": 10,
            "elapsed_sec": 30.5,
            "eta_sec": 30.5,
            "updated_at": "2026-01-23T10:00:00+00:00",
        }
        (outputs_dir / "progress.json").write_text(json.dumps(progress_data))

        app = create_app(sessions_dir)
        client = app.test_client()
        response = client.get(f"/s/{session_id}/progress")

        assert response.status_code == 200
        data = response.get_json()
        assert data["session_id"] == session_id
        assert data["stage"] == "transcribe"
        assert data["done"] == 5
        assert data["total"] == 10

    def test_progress_returns_starting_payload_when_absent(self, tmp_path):
        """Progress route returns 200 with starting payload when progress.json missing."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()
        response = client.get(f"/s/{session_id}/progress")

        # Step 32.9: Returns 200 with starting payload (not 404) to avoid errors
        assert response.status_code == 200
        data = response.get_json()
        assert data["session_id"] == session_id
        assert data["stage"] == "starting"
        assert data["done"] == 0
        assert data["total"] == 0


class TestManifestRoute:
    """Test manifest.json route."""

    def test_manifest_returns_json_when_present(self, tmp_path):
        """Manifest route returns JSON when manifest.json exists."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        manifest_data = {
            "session_id": session_id,
            "created_at": "2026-01-23T10:00:00",
            "source_video": "/path/to/video.mp4",
            "source_video_local": "source/video.mp4",
            "segment_duration_seconds": 10,
            "segments": [],
        }
        (session_dir / "manifest.json").write_text(json.dumps(manifest_data))

        app = create_app(sessions_dir)
        client = app.test_client()
        response = client.get(f"/s/{session_id}/manifest")

        assert response.status_code == 200
        data = response.get_json()
        assert data["session_id"] == session_id
        assert data["segment_duration_seconds"] == 10

    def test_manifest_returns_404_when_absent(self, tmp_path):
        """Manifest route returns 404 when manifest.json does not exist."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()
        response = client.get(f"/s/{session_id}/manifest")

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data


class TestJobSubmission:
    """Test job submission endpoint."""

    def test_submit_job_rejects_missing_file(self, tmp_path):
        """POST /api/jobs rejects job when file does not exist."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True)
        client = app.test_client()

        response = client.post(
            "/api/jobs",
            data={"raw_path": str(raw_dir / "nonexistent.mp4")},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "not found" in data["error"].lower()

    def test_submit_job_rejects_path_outside_raw_dir(self, tmp_path):
        """POST /api/jobs rejects job when path is outside raw_dir."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Create video outside raw_dir
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        video_file = other_dir / "video.mp4"
        video_file.write_bytes(b"fake video")

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True, allow_any_path=False)
        client = app.test_client()

        response = client.post(
            "/api/jobs",
            data={"raw_path": str(video_file)},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "must be under raw_dir" in data["error"].lower()

    def test_submit_job_accepts_valid_file(self, tmp_path):
        """POST /api/jobs accepts job when file is valid."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Create valid video file
        video_file = raw_dir / "video.mp4"
        video_file.write_bytes(b"fake video")

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True)
        client = app.test_client()

        response = client.post(
            "/api/jobs",
            data={
                "raw_path": str(video_file),
                "game": "testgame",
                "transcribe_limit": "5",
            },
        )

        # Should redirect to home page
        assert response.status_code == 302
        assert response.location == "/"

        # Verify job was written to jobs directory
        jobs_dir = sessions_dir.parent / "_queue" / "jobs"
        assert jobs_dir.exists()

        from yanhu.watcher import list_all_jobs

        jobs = list_all_jobs(jobs_dir)
        assert len(jobs) == 1
        assert jobs[0].raw_path == str(video_file.resolve())
        assert jobs[0].suggested_game == "testgame"
        assert jobs[0].status == "pending"
        assert jobs[0].job_id is not None  # Job ID should be generated

    def test_submit_job_with_allow_any_path(self, tmp_path):
        """POST /api/jobs accepts any path when allow_any_path is True."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create video outside sessions dir
        video_file = tmp_path / "anywhere" / "video.mp4"
        video_file.parent.mkdir()
        video_file.write_bytes(b"fake video")

        app = create_app(sessions_dir, raw_dir=None, worker_enabled=True, allow_any_path=True)
        client = app.test_client()

        response = client.post(
            "/api/jobs",
            data={"raw_path": str(video_file)},
        )

        # Should redirect to home page
        assert response.status_code == 302


class TestBackgroundWorker:
    """Test background worker integration."""

    def test_worker_processes_pending_job(self, tmp_path, monkeypatch):
        """Worker picks up pending job and calls process_job."""
        from yanhu.app import BackgroundWorker
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create test video
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        video_file = raw_dir / "test.mp4"
        video_file.write_bytes(b"fake video")

        # Create a pending job
        job = QueueJob(
            created_at="2026-01-23T10:00:00",
            raw_path=str(video_file),
            status="pending",
            suggested_game="testgame",
        )
        save_job_to_file(job, jobs_dir)

        # Track process_job calls
        process_calls = []

        def mock_process_job(job, output_dir, force, source_mode, run_config, jobs_dir=None):
            from yanhu.watcher import JobResult

            process_calls.append(
                {
                    "job": job,
                    "output_dir": output_dir,
                    "run_config": run_config,
                    "jobs_dir": jobs_dir,
                }
            )
            return JobResult(success=True, session_id="2026-01-23_10-00-00_testgame_test")

        # Import process_job in worker module
        import yanhu.watcher
        monkeypatch.setattr(yanhu.watcher, "process_job", mock_process_job)

        # Start worker
        worker = BackgroundWorker(jobs_dir=jobs_dir, output_dir=sessions_dir, preset="fast")
        worker.start()

        # Wait for worker to process job (max 5 seconds)
        import time

        max_wait = 5
        waited = 0
        while len(process_calls) == 0 and waited < max_wait:
            time.sleep(0.1)
            waited += 0.1

        # Stop worker
        worker.stop()

        # Verify process_job was called
        assert len(process_calls) == 1
        call = process_calls[0]
        assert call["job"].raw_path == str(video_file)
        assert call["run_config"]["preset"] == "fast"

    def test_worker_updates_job_status_on_completion(self, tmp_path, monkeypatch):
        """Worker updates job status to done when processing succeeds."""
        from yanhu.app import BackgroundWorker
        from yanhu.watcher import QueueJob, list_all_jobs, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create test video
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        # Create a pending job
        job = QueueJob(
            created_at="2026-01-23T10:00:00",
            raw_path=str(video_file),
            status="pending",
        )
        save_job_to_file(job, jobs_dir)

        # Mock process_job to return success
        def mock_process_job(job, output_dir, force, source_mode, run_config, jobs_dir=None):
            from yanhu.watcher import JobResult

            return JobResult(success=True, session_id="test_session", outputs={})

        # Import process_job in worker module
        import yanhu.watcher
        monkeypatch.setattr(yanhu.watcher, "process_job", mock_process_job)

        # Start worker
        worker = BackgroundWorker(jobs_dir=jobs_dir, output_dir=sessions_dir)
        worker.start()

        # Wait for processing
        import time

        time.sleep(0.5)
        worker.stop()

        # Verify job status was updated
        jobs = list_all_jobs(jobs_dir)
        assert len(jobs) == 1
        assert jobs[0].status == "done"
        assert jobs[0].session_id == "test_session"


class TestJobDetail:
    """Test job detail routes."""

    def test_job_detail_returns_200_for_existing_job(self, tmp_path):
        """GET /jobs/<job_id> returns 200 for existing job."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create a job
        job = QueueJob(
            job_id="job_20260123_100000_abc12345",
            created_at="2026-01-23T10:00:00",
            raw_path="/path/to/video.mp4",
            status="pending",
            suggested_game="testgame",
            preset="fast",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.get("/jobs/job_20260123_100000_abc12345")

        assert response.status_code == 200
        html = response.data.decode("utf-8")
        assert "job_20260123_100000_abc12345" in html
        assert "pending" in html
        assert "testgame" in html
        assert "fast" in html

    def test_job_detail_returns_404_for_nonexistent_job(self, tmp_path):
        """GET /jobs/<job_id> returns 404 for nonexistent job."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.get("/jobs/nonexistent_job")

        assert response.status_code == 404
        assert "not found" in response.data.decode("utf-8").lower()

    def test_get_job_json_returns_job_data(self, tmp_path):
        """GET /api/jobs/<job_id> returns JSON job data."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create a job
        job = QueueJob(
            job_id="job_20260123_100000_abc12345",
            created_at="2026-01-23T10:00:00",
            raw_path="/path/to/video.mp4",
            status="processing",
            suggested_game="testgame",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.get("/api/jobs/job_20260123_100000_abc12345")

        assert response.status_code == 200
        data = response.get_json()
        assert data["job_id"] == "job_20260123_100000_abc12345"
        assert data["status"] == "processing"
        assert data["suggested_game"] == "testgame"


class TestJobCancellation:
    """Test job cancellation endpoint."""

    def test_cancel_pending_job(self, tmp_path):
        """POST /api/jobs/<job_id>/cancel cancels pending job."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, get_job_by_id, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create a pending job
        job = QueueJob(
            job_id="job_20260123_100000_abc12345",
            created_at="2026-01-23T10:00:00",
            raw_path="/path/to/video.mp4",
            status="pending",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.post("/api/jobs/job_20260123_100000_abc12345/cancel")

        # Should redirect to job detail page
        assert response.status_code == 302
        assert "/jobs/job_20260123_100000_abc12345" in response.location

        # Verify job was cancelled
        updated_job = get_job_by_id("job_20260123_100000_abc12345", jobs_dir)
        assert updated_job is not None
        assert updated_job.status == "cancelled"

    def test_cancel_processing_job(self, tmp_path):
        """POST /api/jobs/<job_id>/cancel sets cancel_requested for processing job."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, get_job_by_id, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create a processing job
        job = QueueJob(
            job_id="job_20260123_100000_abc12345",
            created_at="2026-01-23T10:00:00",
            raw_path="/path/to/video.mp4",
            status="processing",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.post("/api/jobs/job_20260123_100000_abc12345/cancel")

        # Should redirect to job detail page
        assert response.status_code == 302

        # Verify job status was set to cancel_requested
        updated_job = get_job_by_id("job_20260123_100000_abc12345", jobs_dir)
        assert updated_job is not None
        assert updated_job.status == "cancel_requested"

    def test_cancel_nonexistent_job_returns_404(self, tmp_path):
        """POST /api/jobs/<job_id>/cancel returns 404 for nonexistent job."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.post("/api/jobs/nonexistent_job/cancel")

        assert response.status_code == 404

    def test_worker_skips_cancelled_job(self, tmp_path, monkeypatch):
        """Worker skips job that was cancelled while pending."""
        from yanhu.app import BackgroundWorker
        from yanhu.watcher import QueueJob, cancel_job, list_all_jobs, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create test video
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video")

        # Create a pending job
        job = QueueJob(
            created_at="2026-01-23T10:00:00",
            raw_path=str(video_file),
            status="pending",
        )
        save_job_to_file(job, jobs_dir)
        job_id = job.job_id

        # Cancel the job
        cancel_job(job_id, jobs_dir)

        # Track process_job calls
        process_calls = []

        def mock_process_job(job, output_dir, force, source_mode, run_config):
            from yanhu.watcher import JobResult

            process_calls.append(job.job_id)
            return JobResult(success=True, session_id="test_session")

        # Import process_job in worker module
        import yanhu.watcher
        monkeypatch.setattr(yanhu.watcher, "process_job", mock_process_job)

        # Start worker
        worker = BackgroundWorker(jobs_dir=jobs_dir, output_dir=sessions_dir)
        worker.start()

        # Wait briefly
        import time

        time.sleep(0.5)
        worker.stop()

        # Verify process_job was NOT called
        assert len(process_calls) == 0

        # Verify job remains cancelled
        jobs = list_all_jobs(jobs_dir)
        assert len(jobs) == 1
        assert jobs[0].status == "cancelled"


class TestUpload:
    """Test video upload endpoint."""

    def test_upload_video_success(self, tmp_path):
        """POST /api/uploads successfully uploads and enqueues job."""
        from io import BytesIO

        from yanhu.app import create_app
        from yanhu.watcher import list_all_jobs

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True)
        client = app.test_client()

        # Create fake video file
        video_data = BytesIO(b"fake video data")
        video_data.name = "test_video.mp4"

        response = client.post(
            "/api/uploads",
            data={
                "file": (video_data, "test_video.mp4"),
                "game": "testgame",
                "preset": "fast",
            },
            content_type="multipart/form-data",
        )

        # Should redirect to job detail page
        assert response.status_code == 302
        assert "/jobs/job_" in response.location

        # Verify file was saved to raw_dir
        uploaded_files = list(raw_dir.glob("*test_video.mp4"))
        assert len(uploaded_files) == 1
        assert uploaded_files[0].read_bytes() == b"fake video data"

        # Verify job was created
        jobs_dir = sessions_dir.parent / "_queue" / "jobs"
        jobs = list_all_jobs(jobs_dir)
        assert len(jobs) == 1
        assert jobs[0].status == "pending"
        assert jobs[0].suggested_game == "testgame"
        assert jobs[0].preset == "fast"
        assert str(uploaded_files[0]) in jobs[0].raw_path

    def test_upload_rejects_invalid_extension(self, tmp_path):
        """POST /api/uploads rejects files with invalid extensions."""
        from io import BytesIO

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True)
        client = app.test_client()

        # Create fake file with invalid extension
        file_data = BytesIO(b"fake data")
        file_data.name = "test.txt"

        response = client.post(
            "/api/uploads",
            data={"file": (file_data, "test.txt")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "invalid file type" in data["error"].lower()

    def test_upload_sanitizes_path_traversal(self, tmp_path):
        """POST /api/uploads sanitizes path traversal attempts."""
        from io import BytesIO

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True)
        client = app.test_client()

        # Attempt path traversal
        video_data = BytesIO(b"fake video")
        video_data.name = "../../evil.mp4"

        response = client.post(
            "/api/uploads",
            data={"file": (video_data, "../../evil.mp4")},
            content_type="multipart/form-data",
        )

        # Should succeed but sanitize filename
        assert response.status_code == 302

        # Verify file is saved under raw_dir (not escaped)
        uploaded_files = list(raw_dir.glob("*evil.mp4"))
        assert len(uploaded_files) == 1
        # File should be in raw_dir, not parent directories
        assert uploaded_files[0].parent == raw_dir

    def test_upload_rejects_oversized_file(self, tmp_path):
        """POST /api/uploads rejects files exceeding max size."""
        from io import BytesIO

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Create app with very small max size (1KB)
        app = create_app(
            sessions_dir, raw_dir=raw_dir, worker_enabled=True, max_upload_size=1024
        )
        client = app.test_client()

        # Create file larger than max size
        video_data = BytesIO(b"x" * 2048)  # 2KB
        video_data.name = "large.mp4"

        response = client.post(
            "/api/uploads",
            data={"file": (video_data, "large.mp4")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 413
        data = response.get_json()
        assert "too large" in data["error"].lower()

    def test_upload_requires_file(self, tmp_path):
        """POST /api/uploads requires file field."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True)
        client = app.test_client()

        response = client.post("/api/uploads", data={}, content_type="multipart/form-data")

        assert response.status_code == 400
        data = response.get_json()
        assert "no file" in data["error"].lower()

    def test_upload_with_transcribe_options(self, tmp_path):
        """POST /api/uploads accepts transcribe options."""
        from io import BytesIO

        from yanhu.app import create_app
        from yanhu.watcher import list_all_jobs

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True)
        client = app.test_client()

        video_data = BytesIO(b"fake video")
        video_data.name = "test.mp4"

        response = client.post(
            "/api/uploads",
            data={
                "file": (video_data, "test.mp4"),
                "transcribe_limit": "5",
                "transcribe_max_seconds": "120.5",
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 302

        # Verify job has transcribe options
        jobs_dir = sessions_dir.parent / "_queue" / "jobs"
        jobs = list_all_jobs(jobs_dir)
        assert len(jobs) == 1
        assert jobs[0].outputs is not None
        assert jobs[0].outputs["transcribe_limit"] == 5
        assert jobs[0].outputs["transcribe_max_seconds"] == 120.5


class TestAsrModelSelection:
    """Test ASR model dropdown selection UI."""

    def test_submit_job_with_whisper_local_and_cpu(self, tmp_path):
        """POST /api/jobs accepts whisper_local with CPU device."""
        from yanhu.app import create_app
        from yanhu.watcher import list_all_jobs

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Create valid video file
        video_file = raw_dir / "video.mp4"
        video_file.write_bytes(b"fake video")

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True)
        client = app.test_client()

        # Submit with whisper_local and CPU device
        response = client.post(
            "/api/jobs",
            data={
                "raw_path": str(video_file),
                "asr_model": "whisper_local",
                "whisper_device": "cpu",
            },
        )

        # Should redirect to home page
        assert response.status_code == 302
        assert response.location == "/"

        # Verify job was written with whisper_local and cpu device
        jobs_dir = sessions_dir.parent / "_queue" / "jobs"
        jobs = list_all_jobs(jobs_dir)
        assert len(jobs) == 1
        assert jobs[0].asr_models == ["whisper_local"]
        assert jobs[0].whisper_device == "cpu"

    def test_submit_job_with_whisper_local_and_cuda(self, tmp_path):
        """POST /api/jobs accepts whisper_local with CUDA device."""
        from yanhu.app import create_app
        from yanhu.watcher import list_all_jobs

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Create valid video file
        video_file = raw_dir / "video.mp4"
        video_file.write_bytes(b"fake video")

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True)
        client = app.test_client()

        # Submit with whisper_local and CUDA device
        response = client.post(
            "/api/jobs",
            data={
                "raw_path": str(video_file),
                "asr_model": "whisper_local",
                "whisper_device": "cuda",
            },
        )

        # Should redirect to home page
        assert response.status_code == 302

        # Verify job has CUDA device
        jobs_dir = sessions_dir.parent / "_queue" / "jobs"
        jobs = list_all_jobs(jobs_dir)
        assert len(jobs) == 1
        assert jobs[0].asr_models == ["whisper_local"]
        assert jobs[0].whisper_device == "cuda"

    def test_upload_with_asr_model_and_device(self, tmp_path):
        """POST /api/uploads accepts ASR model and whisper device."""
        from io import BytesIO

        from yanhu.app import create_app
        from yanhu.watcher import list_all_jobs

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True)
        client = app.test_client()

        # Create fake video file
        video_data = BytesIO(b"fake video data")
        video_data.name = "test_video.mp4"

        response = client.post(
            "/api/uploads",
            data={
                "file": (video_data, "test_video.mp4"),
                "asr_model": "mock",
                "whisper_device": "cpu",
            },
            content_type="multipart/form-data",
        )

        # Should redirect to job detail page
        assert response.status_code == 302

        # Verify job has mock model
        jobs_dir = sessions_dir.parent / "_queue" / "jobs"
        jobs = list_all_jobs(jobs_dir)
        assert len(jobs) == 1
        assert jobs[0].asr_models == ["mock"]

    def test_index_provides_asr_model_dropdown(self, tmp_path):
        """GET / provides ASR model dropdown UI."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.get("/")

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Verify dropdown select is present
        assert '<select id="asr_model"' in html
        assert 'name="asr_model"' in html
        assert 'value="mock"' in html
        assert 'value="whisper_local"' in html

        # Verify whisper_local is selected by default
        assert 'value="whisper_local"' in html
        # Check that selected appears near whisper_local option
        assert 'whisper_local' in html and 'selected' in html

        # Verify Whisper device dropdown is present
        assert '<select id="whisper_device"' in html
        assert 'name="whisper_device"' in html
        assert 'value="cpu"' in html
        assert 'value="cuda"' in html

        # Verify display names appear
        assert "Mock ASR" in html
        assert "Whisper (Local)" in html


class TestFrameServing:
    """Test frame image serving route."""

    def test_serve_frame_returns_200_for_existing_frame(self, tmp_path):
        """GET /s/<session_id>/frames/<part_id>/<filename> returns 200 for existing frame."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create session with frame
        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()
        frames_dir = session_dir / "frames" / "part_0001"
        frames_dir.mkdir(parents=True)

        # Create a dummy frame file
        frame_file = frames_dir / "frame_0001.jpg"
        frame_file.write_bytes(b"\xff\xd8\xff\xe0")  # Minimal JPEG header

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}/frames/part_0001/frame_0001.jpg")

        assert response.status_code == 200
        assert response.data == b"\xff\xd8\xff\xe0"

    def test_serve_frame_returns_404_for_missing_frame(self, tmp_path):
        """GET /s/<session_id>/frames/<part_id>/<filename> returns 404 for missing frame."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create session without frames
        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}/frames/part_0001/frame_0001.jpg")

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_serve_frame_blocks_dotdot_in_part_id(self, tmp_path):
        """Frames route validates part_id contains no '..'."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        # Try .. in part_id (Flask route still accepts it, but our code rejects)
        response = client.get(f"/s/{session_id}/frames/part..001/frame_0001.jpg")

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "Invalid" in data["error"]

    def test_serve_frame_blocks_dotdot_in_filename(self, tmp_path):
        """Frames route validates filename contains no '..'."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        # Try .. in filename
        response = client.get(f"/s/{session_id}/frames/part_0001/frame..jpg")

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "Invalid" in data["error"]

    def test_serve_frame_returns_404_for_nonexistent_session(self, tmp_path):
        """GET /s/<session_id>/frames/<part_id>/<filename> returns 404 for nonexistent session."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/s/nonexistent_session/frames/part_0001/frame_0001.jpg")

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data


class TestAnalysisTab:
    """Test analysis tab and routes."""

    def test_analysis_list_returns_parts(self, tmp_path):
        """GET /s/<session_id>/analysis returns list of analysis parts."""
        import json

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create session with analysis files
        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        # Create sample analysis file
        analysis_data = {
            "segment_id": "part_0001",
            "scene_label": "menu",
            "what_changed": "Player navigates to settings",
            "ui_key_text": ["Settings", "Audio"],
            "ocr_items": [{"text": "Settings", "x": 100, "y": 200}],
            "asr_items": [],
            "aligned_quotes": [],
            "ui_symbol_items": [],
        }
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}/analysis")

        assert response.status_code == 200
        data = response.get_json()
        assert "parts" in data
        assert len(data["parts"]) == 1
        assert data["parts"][0]["part_id"] == "part_0001"
        assert data["parts"][0]["scene_label"] == "menu"
        assert data["parts"][0]["ocr_count"] == 1

    def test_analysis_list_returns_empty_for_no_analysis(self, tmp_path):
        """GET /s/<session_id>/analysis returns empty list when no analysis exists."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create session without analysis directory
        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}/analysis")

        assert response.status_code == 200
        data = response.get_json()
        assert "parts" in data
        assert len(data["parts"]) == 0
        assert "message" in data

    def test_analysis_part_returns_json(self, tmp_path):
        """GET /s/<session_id>/analysis/<part_id> returns analysis JSON."""
        import json

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create session with analysis file
        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        analysis_data = {"segment_id": "part_0001", "scene_label": "menu", "facts": ["test fact"]}
        (analysis_dir / "part_0001.json").write_text(json.dumps(analysis_data))

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}/analysis/part_0001")

        assert response.status_code == 200
        data = response.get_json()
        assert data["segment_id"] == "part_0001"
        assert data["scene_label"] == "menu"

    def test_analysis_part_blocks_invalid_part_id(self, tmp_path):
        """GET /s/<session_id>/analysis/<part_id> blocks invalid part_id patterns."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        # Try various invalid patterns
        invalid_ids = ["part_1", "evil", "part_..01", "part_0001.json"]

        for invalid_id in invalid_ids:
            response = client.get(f"/s/{session_id}/analysis/{invalid_id}")
            assert response.status_code == 400, f"Should reject {invalid_id}"
            data = response.get_json()
            assert "error" in data
            assert "Invalid" in data["error"]

    def test_analysis_part_returns_404_for_missing_file(self, tmp_path):
        """GET /s/<session_id>/analysis/<part_id> returns 404 for missing file."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        # Create analysis dir but no files
        analysis_dir = session_dir / "analysis"
        analysis_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}/analysis/part_0001")

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data

    def test_session_view_includes_analysis_tab(self, tmp_path):
        """Session view page includes Analysis tab."""
        import json

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create complete session
        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        # Create required markdown files
        (session_dir / "overview.md").write_text("# Overview\n\nTest")
        (session_dir / "highlights.md").write_text("# Highlights\n\n- Test")
        (session_dir / "timeline.md").write_text("# Timeline\n\nTest")
        (session_dir / "manifest.json").write_text(json.dumps({"session_id": session_id}))

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}")

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Verify Analysis tab exists
        assert "Analysis" in html
        assert 'onclick="showTab(\'analysis\')"' in html
        assert 'id="analysis"' in html


class TestSessionNavigation:
    """Test session navigation UX enhancements."""

    def test_session_view_includes_tab_hash_navigation_js(self, tmp_path):
        """Session view includes JavaScript for tab hash navigation."""
        import json

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create complete session
        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        (session_dir / "overview.md").write_text("# Overview\n\nTest")
        (session_dir / "highlights.md").write_text("# Highlights\n\n- Test")
        (session_dir / "timeline.md").write_text("# Timeline\n\nTest")
        (session_dir / "manifest.json").write_text(json.dumps({"session_id": session_id}))

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}")

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Verify hash navigation functions exist
        assert "getActiveTabFromHash" in html
        assert "activateTabFromHash" in html
        assert "window.location.hash" in html
        assert "hashchange" in html

    def test_session_view_includes_frame_link_patcher_js(self, tmp_path):
        """Session view includes JavaScript to patch frame links."""
        import json

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create complete session
        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        (session_dir / "overview.md").write_text("# Overview\n\nTest")
        (session_dir / "highlights.md").write_text("# Highlights\n\n- Test")
        (session_dir / "timeline.md").write_text("# Timeline\n\nTest")
        (session_dir / "manifest.json").write_text(json.dumps({"session_id": session_id}))

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}")

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Verify frame link patcher function exists
        assert "patchFrameLinks" in html
        assert 'href*="/frames/"' in html
        assert "target" in html
        assert "noopener noreferrer" in html

    def test_timeline_with_frames_renders_links(self, tmp_path):
        """Timeline with frame links renders correctly."""
        import json

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create session with timeline containing frame links
        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        timeline_md = """# Timeline

### part_0001 (00:00 - 00:05)

**Frames**: [frame_0001.jpg](/s/2026-01-23_10-00-00_game_run01/frames/part_0001/frame_0001.jpg)

> Test segment
"""
        (session_dir / "overview.md").write_text("# Overview")
        (session_dir / "highlights.md").write_text("# Highlights")
        (session_dir / "timeline.md").write_text(timeline_md)
        (session_dir / "manifest.json").write_text(json.dumps({"session_id": session_id}))

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}")

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Verify frame link is present in timeline
        assert "/frames/part_0001/frame_0001.jpg" in html
        assert "frame_0001.jpg" in html

    def test_show_tab_function_signature_accepts_skip_hash(self, tmp_path):
        """showTab function accepts skipHashUpdate parameter."""
        import json

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        (session_dir / "overview.md").write_text("# Overview")
        (session_dir / "highlights.md").write_text("# Highlights")
        (session_dir / "timeline.md").write_text("# Timeline")
        (session_dir / "manifest.json").write_text(json.dumps({"session_id": session_id}))

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}")

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Verify function signature includes skipHashUpdate parameter
        assert "function showTab(tabName, skipHashUpdate)" in html
        assert "skipHashUpdate" in html


class TestMediaPreflight:
    """Test media probing and estimates."""

    def test_upload_probes_media_info(self, tmp_path, monkeypatch):
        """Upload probes media and stores metadata in job."""
        from io import BytesIO

        from yanhu.app import create_app
        from yanhu.watcher import MediaInfo, list_all_jobs

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Mock probe_media to return fake metadata
        def mock_probe_media(path):
            return MediaInfo(
                duration_sec=120.5,
                file_size_bytes=1024 * 1024 * 100,  # 100MB
                container="mp4",
                video_codec="h264",
                audio_codec="aac",
                width=1920,
                height=1080,
                fps=30.0,
                bitrate_kbps=5000,
            )

        import yanhu.watcher

        monkeypatch.setattr(yanhu.watcher, "probe_media", mock_probe_media)

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True)
        client = app.test_client()

        video_data = BytesIO(b"fake video")
        video_data.name = "test.mp4"

        response = client.post(
            "/api/uploads",
            data={"file": (video_data, "test.mp4")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302

        # Verify job has media info
        jobs_dir = sessions_dir.parent / "_queue" / "jobs"
        jobs = list_all_jobs(jobs_dir)
        assert len(jobs) == 1
        job = jobs[0]

        assert job.media is not None
        assert job.media["duration_sec"] == 120.5
        assert job.media["file_size_bytes"] == 1024 * 1024 * 100
        assert job.media["width"] == 1920
        assert job.media["height"] == 1080
        assert job.media["fps"] == 30.0
        assert job.media["video_codec"] == "h264"

    def test_upload_calculates_estimates(self, tmp_path, monkeypatch):
        """Upload calculates estimated segments and runtime."""
        from io import BytesIO

        from yanhu.app import create_app
        from yanhu.watcher import MediaInfo, list_all_jobs

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Mock probe_media to return 90 second video
        def mock_probe_media(path):
            return MediaInfo(duration_sec=90.0, file_size_bytes=1024 * 1024 * 50)

        import yanhu.watcher

        monkeypatch.setattr(yanhu.watcher, "probe_media", mock_probe_media)

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True, preset="fast")
        client = app.test_client()

        video_data = BytesIO(b"fake video")
        video_data.name = "test.mp4"

        response = client.post(
            "/api/uploads",
            data={"file": (video_data, "test.mp4")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302

        # Verify estimates
        jobs_dir = sessions_dir.parent / "_queue" / "jobs"
        jobs = list_all_jobs(jobs_dir)
        assert len(jobs) == 1
        job = jobs[0]

        # 90 seconds with auto strategy (<=3min) = 5s segments = ceil(90/5) = 18 segments
        assert job.estimated_segments == 18
        # Fast preset: 18 segments * 3 sec/segment + 10 base = 64 seconds
        assert job.estimated_runtime_sec == 64

    def test_job_detail_displays_media_info(self, tmp_path):
        """Job detail page displays media info and estimates."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create job with media info
        job = QueueJob(
            job_id="job_20260123_100000_abc12345",
            created_at="2026-01-23T10:00:00",
            raw_path="/path/to/video.mp4",
            status="pending",
            media={
                "duration_sec": 120.5,
                "file_size_bytes": 104857600,  # 100MB
                "width": 1920,
                "height": 1080,
                "fps": 30.0,
                "video_codec": "h264",
                "audio_codec": "aac",
                "container": "mp4",
            },
            estimated_segments=24,
            estimated_runtime_sec=82,
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.get("/jobs/job_20260123_100000_abc12345")

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Verify media info is displayed
        assert "Media Info" in html
        assert "2m 0s" in html or "2m" in html  # Duration formatting
        assert "100" in html  # File size (MB)
        assert "1920×1080" in html  # Resolution
        assert "h264" in html  # Video codec
        assert "aac" in html  # Audio codec

        # Verify estimates are displayed
        assert "Estimates" in html
        assert "24" in html  # Estimated segments
        assert "1m 22s" in html or "82s" in html  # Estimated runtime

    def test_existing_file_job_probes_media(self, tmp_path, monkeypatch):
        """Creating job from existing file probes media."""
        from yanhu.app import create_app
        from yanhu.watcher import MediaInfo, list_all_jobs

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Create existing video file
        video_file = raw_dir / "existing.mp4"
        video_file.write_bytes(b"fake video")

        # Mock probe_media
        def mock_probe_media(path):
            return MediaInfo(duration_sec=60.0, file_size_bytes=1024 * 1024 * 25)

        import yanhu.watcher

        monkeypatch.setattr(yanhu.watcher, "probe_media", mock_probe_media)

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True)
        client = app.test_client()

        response = client.post(
            "/api/jobs",
            data={"raw_path": str(video_file)},
        )

        assert response.status_code == 302

        # Verify job has media info
        jobs_dir = sessions_dir.parent / "_queue" / "jobs"
        jobs = list_all_jobs(jobs_dir)
        assert len(jobs) == 1
        assert jobs[0].media is not None
        assert jobs[0].media["duration_sec"] == 60.0
        assert jobs[0].estimated_segments == 12  # 60s / 5s = 12 segments


class TestCalibratedEta:
    """Test calibrated ETA in UI."""

    def test_job_detail_includes_progress_polling_javascript(self, tmp_path):
        """Job detail page includes JavaScript for global progress polling."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create a processing job
        job = QueueJob(
            job_id="job_20260123_100000_abc12345",
            created_at="2026-01-23T10:00:00",
            raw_path="/path/to/video.mp4",
            status="processing",
            session_id="test_session",
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir, worker_enabled=True)
        client = app.test_client()

        response = client.get("/jobs/job_20260123_100000_abc12345")

        assert response.status_code == 200
        html = response.data.decode("utf-8")

        # Verify JavaScript includes global progress polling system
        assert "startGlobalProgressPolling" in html  # Global progress function
        assert "updateGlobalProgress" in html  # Update function
        assert "global-progress-bar" in html  # Progress bar container
        assert "formatDuration" in html  # Duration formatting function

    def test_upload_uses_metrics_for_estimate(self, tmp_path, monkeypatch):
        """Upload uses metrics to improve estimate when available."""
        from io import BytesIO

        from yanhu.app import create_app
        from yanhu.metrics import MetricsStore
        from yanhu.watcher import MediaInfo, list_all_jobs

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        # Create metrics with observed rate
        metrics_file = sessions_dir.parent / "_metrics.json"
        store = MetricsStore(metrics_file)
        store.update_metrics(preset="fast", segment_duration=5, observed_rate=0.4)

        # Mock probe_media to return 90s video
        def mock_probe_media(path):
            return MediaInfo(duration_sec=90.0, file_size_bytes=1024 * 1024)

        import yanhu.watcher

        monkeypatch.setattr(yanhu.watcher, "probe_media", mock_probe_media)

        app = create_app(sessions_dir, raw_dir=raw_dir, worker_enabled=True, preset="fast")
        client = app.test_client()

        video_data = BytesIO(b"fake video")
        video_data.name = "test.mp4"

        response = client.post(
            "/api/uploads",
            data={"file": (video_data, "test.mp4")},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302

        # Verify estimate used metrics
        jobs_dir = sessions_dir.parent / "_queue" / "jobs"
        jobs = list_all_jobs(jobs_dir)
        assert len(jobs) == 1
        job = jobs[0]

        # 90s / 5s = 18 segments
        assert job.estimated_segments == 18
        # With metrics: 10 + 18 / 0.4 = 55 seconds (not heuristic 64)
        assert job.estimated_runtime_sec == 55


class TestFfprobeValidation:
    """Test ffprobe validation in job submission."""

    def test_submit_job_rejected_without_ffprobe(self, tmp_path):
        """Test POST /api/jobs returns 400 when ffprobe not found."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        raw_dir = tmp_path / "raw"
        sessions_dir.mkdir()
        raw_dir.mkdir()

        # Create test video
        test_video = raw_dir / "test.mp4"
        test_video.write_text("fake video")

        app = create_app(
            sessions_dir=str(sessions_dir),
            raw_dir=str(raw_dir),
            worker_enabled=True,
        )

        # Force ffprobe_path to None (simulate not found)
        app.config["ffprobe_path"] = None

        client = app.test_client()

        response = client.post(
            "/api/jobs",
            data={
                "raw_path": str(test_video),
                "game": "test",
            },
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "ffprobe not found" in data["error"]

    def test_upload_rejected_without_ffprobe(self, tmp_path):
        """Test POST /api/uploads returns 400 when ffprobe not found."""
        from io import BytesIO

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        raw_dir = tmp_path / "raw"
        sessions_dir.mkdir()
        raw_dir.mkdir()

        app = create_app(
            sessions_dir=str(sessions_dir),
            raw_dir=str(raw_dir),
            worker_enabled=True,
        )

        # Force ffprobe_path to None (simulate not found)
        app.config["ffprobe_path"] = None

        client = app.test_client()

        response = client.post(
            "/api/uploads",
            data={
                "file": (BytesIO(b"fake video data"), "test.mp4"),
                "game": "test",
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "ffprobe not found" in data["error"]


class TestShutdownEndpoint:
    """Test server shutdown endpoint."""

    def test_shutdown_requires_token(self, tmp_path):
        """Test POST /api/shutdown requires valid token."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        # Try without token
        response = client.post("/api/shutdown", data={})
        assert response.status_code == 403
        data = response.get_json()
        assert "Invalid shutdown token" in data["error"]

        # Try with wrong token
        response = client.post("/api/shutdown", data={"token": "wrong"})
        assert response.status_code == 403
        data = response.get_json()
        assert "Invalid shutdown token" in data["error"]

    def test_shutdown_with_valid_token(self, tmp_path, monkeypatch):
        """Test POST /api/shutdown succeeds with valid token and schedules termination."""
        import os
        from threading import Timer

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        # Get the shutdown token from config
        token = app.config["shutdown_token"]

        # Mock os._exit to prevent actual shutdown
        exit_called = []

        def mock_os_exit(code):
            exit_called.append(code)

        monkeypatch.setattr(os, "_exit", mock_os_exit)

        # Track Timer creation to verify shutdown is scheduled
        timers_started = []

        def mock_timer_start(self):
            timers_started.append((self.interval, self.function))
            # Don't actually start the timer to avoid calling os._exit during test

        monkeypatch.setattr(Timer, "start", mock_timer_start)

        # Submit with valid token
        response = client.post("/api/shutdown", data={"token": token})

        # Should succeed with ok: true
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("ok") is True

        # Should have scheduled a timer with ~0.3s delay
        assert len(timers_started) == 1
        interval, func = timers_started[0]
        assert interval == 0.3  # 300ms delay

        # Verify the termination function would call os._exit
        # (We don't actually call it to avoid exiting the test process)
        # The function is a lambda/closure, we just verify it was scheduled

    def test_shutdown_rejects_non_local_requests(self, tmp_path):
        """Test shutdown endpoint rejects non-localhost requests (best-effort)."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        token = app.config["shutdown_token"]

        # Simulate remote request by setting REMOTE_ADDR
        response = client.post(
            "/api/shutdown",
            data={"token": token},
            environ_base={"REMOTE_ADDR": "192.168.1.100"},
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "localhost" in data["error"].lower()


class TestQuitButtonRendering:
    """Test Quit Server button renders cleanly."""

    def test_quit_button_renders_without_noqa_comments(self, tmp_path):
        """Test quit button label is clean without noqa comments in HTML."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        # Get the home page
        response = client.get("/")
        html = response.get_data(as_text=True)

        # Should contain clean "Quit Server" button
        assert "Quit Server" in html
        # Should NOT contain noqa comments in rendered HTML
        assert "noqa" not in html
        assert "E501" not in html
        # Should have the quit button element
        assert 'id="quitButton"' in html
        assert 'onclick="quitServer()"' in html

    def test_shutdown_termination_calls_os_exit(self, tmp_path, monkeypatch):
        """Test termination function calls os._exit(0) as final fallback."""
        import os
        from threading import Timer

        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        token = app.config["shutdown_token"]

        # Mock os._exit to prevent actual shutdown
        exit_called = []

        def mock_os_exit(code):
            exit_called.append(code)

        monkeypatch.setattr(os, "_exit", mock_os_exit)

        # Capture the termination function
        captured_func = []
        original_timer_init = Timer.__init__

        def mock_timer_init(self, *args, **kwargs):
            original_timer_init(self, *args, **kwargs)
            if len(args) >= 2:
                captured_func.append(args[1])  # The function argument

        monkeypatch.setattr(Timer, "__init__", mock_timer_init)

        # Don't actually start the timer
        monkeypatch.setattr(Timer, "start", lambda self: None)

        # Submit with valid token
        response = client.post("/api/shutdown", data={"token": token})
        assert response.status_code == 200

        # Should have captured the termination function
        assert len(captured_func) == 1
        terminate_func = captured_func[0]

        # Call the termination function directly
        terminate_func()

        # Should have called os._exit(0)
        assert exit_called == [0]



class TestFFmpegErrorBannerStyling:
    """Test readable ffmpeg fix instructions banner (hotfix)."""

    def test_session_error_banner_has_readable_commands(self, tmp_path):
        """Session page error banner should have readable command blocks with copy buttons."""
        from yanhu.app import create_app
        from yanhu.manifest import Manifest, SegmentInfo

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "test_error_banner"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        # Create session with ASR errors
        manifest = Manifest(
            session_id=session_id,
            created_at="2026-01-24T00:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[SegmentInfo("part_0001", 0.0, 10.0, "segments/seg1.mp4")],
            asr_models=["whisper_local"],
        )
        manifest.save(session_dir)

        # Create markdown files
        (session_dir / "overview.md").write_text("# Overview", encoding="utf-8")
        (session_dir / "highlights.md").write_text("# Highlights", encoding="utf-8")
        (session_dir / "timeline.md").write_text("# Timeline", encoding="utf-8")

        # Create ASR transcript with ffmpeg error
        asr_dir = session_dir / "outputs" / "asr" / "whisper_local"
        asr_dir.mkdir(parents=True)
        import json

        (asr_dir / "transcript.json").write_text(
            json.dumps(
                [
                    {
                        "segment_id": "part_0001",
                        "asr_backend": "whisper_local",
                        "asr_error": (
                            "ffmpeg not found. "
                            "Install ffmpeg to use whisper_local backend."
                        ),
                    }
                ]
            ),
            encoding="utf-8",
        )

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        response = client.get(f"/s/{session_id}")
        assert response.status_code == 200

        html = response.get_data(as_text=True)

        # Check for command block CSS classes
        assert "cmd-block" in html
        assert "cmd-label" in html
        assert "cmd-text" in html
        assert "cmd-copy-btn" in html

        # Check for actual commands
        assert "brew install ffmpeg" in html
        assert "sudo apt install ffmpeg" in html

        # Check for copy button functionality
        assert "copyCommand" in html

    def test_job_error_banner_has_readable_commands(self, tmp_path):
        """Job page error banner should have readable command blocks with copy buttons."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create job with ffmpeg error
        job = QueueJob(
            job_id="test_error_job",
            raw_path="/path/to/video.mp4",
            status="failed",
            created_at="2026-01-24T00:00:00",
            error=(
                "ffmpeg not found - whisper_local requires ffmpeg to extract audio. "
                "Install ffmpeg and retry."
            ),
        )
        save_job_to_file(job, jobs_dir)

        app = create_app(sessions_dir=str(sessions_dir), worker_enabled=True)
        client = app.test_client()

        response = client.get("/jobs/test_error_job")
        assert response.status_code == 200

        html = response.get_data(as_text=True)

        # Check for command block CSS classes
        assert "cmd-block" in html
        assert "cmd-label" in html
        assert "cmd-text" in html
        assert "cmd-copy-btn" in html

        # Check for actual commands
        assert "brew install ffmpeg" in html
        assert "sudo apt install ffmpeg" in html

        # Check for copy button functionality
        assert "copyCommand" in html


class TestSettingsRoutes:
    """Test Settings page and API key management routes."""

    def test_settings_page_loads(self, tmp_path):
        """Settings page should load successfully."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/settings")
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        assert "Settings" in html
        assert "API Keys" in html

    def test_get_api_keys_returns_masked_values(self, tmp_path, monkeypatch):
        """GET /api/settings/keys returns masked values only."""
        from yanhu.app import create_app
        from yanhu.keystore import EnvFileKeyStore

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create a key store with a test key
        env_file = tmp_path / ".env"
        store = EnvFileKeyStore(env_file)
        store.set_key("ANTHROPIC_API_KEY", "sk-ant-1234567890abcdef")

        # Mock get_default_keystore to return our test store
        def mock_get_default_keystore():
            return store

        import yanhu.keystore
        monkeypatch.setattr(yanhu.keystore, "get_default_keystore", mock_get_default_keystore)

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/api/settings/keys")
        assert response.status_code == 200

        data = response.get_json()
        assert "keys" in data
        assert "backend" in data

        # Check ANTHROPIC_API_KEY status
        anthropic_status = data["keys"]["ANTHROPIC_API_KEY"]
        assert anthropic_status["set"] is True
        assert anthropic_status["masked"] == "sk-ant…cdef"
        assert "1234567890ab" not in anthropic_status["masked"]  # Full key not exposed

    def test_post_api_keys_requires_local_only(self, tmp_path):
        """POST /api/settings/keys requires local-only access."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        # Simulate non-local request
        response = client.post(
            "/api/settings/keys",
            json={"key_name": "ANTHROPIC_API_KEY", "key_value": "test-key"},
            environ_base={"REMOTE_ADDR": "192.168.1.100"},
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "localhost" in data["error"]

    def test_post_api_keys_requires_token(self, tmp_path):
        """POST /api/settings/keys requires valid token."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        # Request without token
        response = client.post(
            "/api/settings/keys",
            json={"key_name": "ANTHROPIC_API_KEY", "key_value": "test-key"},
        )

        assert response.status_code == 403
        data = response.get_json()
        assert "token" in data["error"].lower()

    def test_post_api_keys_save_and_retrieve(self, tmp_path, monkeypatch):
        """POST /api/settings/keys saves key and returns masked value."""
        from yanhu.app import create_app
        from yanhu.keystore import EnvFileKeyStore

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create a key store
        env_file = tmp_path / ".env"
        store = EnvFileKeyStore(env_file)

        # Mock get_default_keystore
        def mock_get_default_keystore():
            return store

        import yanhu.keystore
        monkeypatch.setattr(yanhu.keystore, "get_default_keystore", mock_get_default_keystore)

        app = create_app(sessions_dir)
        client = app.test_client()

        # Get shutdown token
        token = app.config["shutdown_token"]

        # Save key
        response = client.post(
            "/api/settings/keys",
            json={
                "token": token,
                "key_name": "ANTHROPIC_API_KEY",
                "key_value": "sk-ant-test123456789",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["status"]["set"] is True
        assert data["status"]["masked"] == "sk-ant…6789"
        assert "test12345" not in data["status"]["masked"]  # Full key not exposed

        # Verify key was saved
        saved_key = store.get_key("ANTHROPIC_API_KEY")
        assert saved_key == "sk-ant-test123456789"

    def test_post_api_keys_clear(self, tmp_path, monkeypatch):
        """POST /api/settings/keys can clear a key."""
        from yanhu.app import create_app
        from yanhu.keystore import EnvFileKeyStore

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create a key store with an existing key
        env_file = tmp_path / ".env"
        store = EnvFileKeyStore(env_file)
        store.set_key("ANTHROPIC_API_KEY", "sk-ant-existing")

        # Mock get_default_keystore
        def mock_get_default_keystore():
            return store

        import yanhu.keystore
        monkeypatch.setattr(yanhu.keystore, "get_default_keystore", mock_get_default_keystore)

        app = create_app(sessions_dir)
        client = app.test_client()

        # Get shutdown token
        token = app.config["shutdown_token"]

        # Clear key (null value)
        response = client.post(
            "/api/settings/keys",
            json={
                "token": token,
                "key_name": "ANTHROPIC_API_KEY",
                "key_value": None,
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["status"]["set"] is False

        # Verify key was cleared
        saved_key = store.get_key("ANTHROPIC_API_KEY")
        assert saved_key is None

    def test_post_api_keys_rejects_unsupported_key(self, tmp_path):
        """POST /api/settings/keys rejects unsupported key names."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        token = app.config["shutdown_token"]

        response = client.post(
            "/api/settings/keys",
            json={
                "token": token,
                "key_name": "UNSUPPORTED_KEY",
                "key_value": "test-value",
            },
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "Unsupported key" in data["error"]

    def test_settings_page_includes_mode_indicator(self, tmp_path):
        """Settings page includes mode indicator in header."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/settings")
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        # Mode indicator should be present
        assert "mode-indicator" in html
        assert "updateModeIndicator" in html  # JavaScript function

    def test_index_page_includes_mode_indicator(self, tmp_path):
        """Index page includes mode indicator in header."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        assert response.status_code == 200

        html = response.get_data(as_text=True)
        # Mode indicator should be present in global header
        assert "mode-indicator" in html
        # Should show server-rendered mode (no keys in test environment)
        assert "Mode: ASR-only (no keys)" in html
        assert "updateModeIndicator" in html
