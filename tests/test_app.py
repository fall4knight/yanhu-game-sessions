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

    def test_session_view_returns_404_when_missing_markdown_files(self, tmp_path):
        """Session view returns 404 when required markdown files are missing."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        # Only create manifest, no markdown files
        (session_dir / "manifest.json").write_text(json.dumps({"session_id": session_id}))

        app = create_app(sessions_dir)
        client = app.test_client()
        response = client.get(f"/s/{session_id}")

        assert response.status_code == 404
        assert "incomplete" in response.data.decode("utf-8").lower()


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

    def test_progress_returns_404_when_absent(self, tmp_path):
        """Progress route returns 404 when progress.json does not exist."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-23_10-00-00_game_run01"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()
        response = client.get(f"/s/{session_id}/progress")

        assert response.status_code == 404
        data = response.get_json()
        assert "error" in data


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

        def mock_process_job(job, output_dir, force, source_mode, run_config):
            from yanhu.watcher import JobResult

            process_calls.append(
                {
                    "job": job,
                    "output_dir": output_dir,
                    "run_config": run_config,
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
        def mock_process_job(job, output_dir, force, source_mode, run_config):
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

    def test_job_detail_includes_calibrated_eta_javascript(self, tmp_path):
        """Job detail page includes JavaScript for calibrated ETA computation."""
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

        # Verify JavaScript includes calibrated ETA computation
        assert "rateEma" in html  # EMA variable
        assert "Observed rate" in html  # Label
        assert "Calibrated ETA" in html  # Label
        assert "Est. finish" in html  # Label
        assert "0.2 * currentRate + 0.8 * rateEma" in html  # EMA formula

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
