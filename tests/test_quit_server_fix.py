"""Tests for Step 23: Quit Server token fix on all pages."""


class TestQuitServerTokenInjection:
    """Test that shutdown_token is injected on all pages."""

    def test_home_page_has_shutdown_token(self, tmp_path):
        """Home page should include shutdown token in template."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        response = client.get("/")
        assert response.status_code == 200

        # Check that shutdown token is rendered in JavaScript
        assert "const SHUTDOWN_TOKEN" in response.get_data(as_text=True)
        # Token should be non-empty
        assert app.config.get("shutdown_token")
        token = app.config["shutdown_token"]
        assert token in response.get_data(as_text=True)

    def test_session_page_has_shutdown_token(self, tmp_path):
        """Session detail page should include shutdown token."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir=str(sessions_dir))
        client = app.test_client()

        # Create a test session
        from yanhu.manifest import Manifest, SegmentInfo

        session_id = "test_session_quit"
        session_dir = tmp_path / "sessions" / session_id
        session_dir.mkdir(parents=True)

        # Create minimal session files
        manifest = Manifest(
            session_id=session_id,
            created_at="2026-01-24T00:00:00",
            source_video="/path/to/video.mp4",
            source_video_local="source/video.mp4",
            segment_duration_seconds=10,
            segments=[
                SegmentInfo("part_0001", 0.0, 10.0, "segments/seg1.mp4"),
            ],
        )
        manifest.save(session_dir)

        # Create markdown files
        (session_dir / "overview.md").write_text("# Overview", encoding="utf-8")
        (session_dir / "highlights.md").write_text("# Highlights", encoding="utf-8")
        (session_dir / "timeline.md").write_text("# Timeline", encoding="utf-8")

        # Override sessions_dir in app config
        app.config["sessions_dir"] = str(tmp_path / "sessions")

        response = client.get(f"/s/{session_id}")
        assert response.status_code == 200

        # Check that shutdown token is rendered
        assert "const SHUTDOWN_TOKEN" in response.get_data(as_text=True)
        token = app.config["shutdown_token"]
        assert token in response.get_data(as_text=True)

    def test_job_page_has_shutdown_token(self, tmp_path):
        """Job detail page should include shutdown token."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        # Create a test job
        job = QueueJob(
            job_id="test_job_quit",
            raw_path="/path/to/video.mp4",
            status="pending",
            created_at="2026-01-24T00:00:00",
        )
        save_job_to_file(job, jobs_dir)

        # Create app with worker enabled
        app = create_app(sessions_dir=str(sessions_dir), worker_enabled=True)
        client = app.test_client()

        response = client.get("/jobs/test_job_quit")
        assert response.status_code == 200

        # Check that shutdown token is rendered
        assert "const SHUTDOWN_TOKEN" in response.get_data(as_text=True)
        token = app.config["shutdown_token"]
        assert token in response.get_data(as_text=True)

    def test_shutdown_endpoint_accepts_token_from_any_page(self, tmp_path, monkeypatch):
        """Shutdown endpoint should accept token regardless of source page."""
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

        monkeypatch.setattr("os._exit", mock_os_exit)

        # Test shutdown with valid token (simulating request from any page)
        response = client.post(
            "/api/shutdown",
            data={"token": token},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )

        # Should accept token and schedule shutdown
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
