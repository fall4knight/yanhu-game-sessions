"""Tests for Step 32.14: Terminal state handling."""

import json


class TestProgressTerminalStage:
    """Test that progress.json ends with stage='done' after pipeline completes."""

    def test_progress_tracker_terminal_lock_prevents_updates(self):
        """ProgressTracker locks after finalize(stage='done') to prevent overwrites."""
        import tempfile
        from pathlib import Path

        from yanhu.progress import ProgressTracker

        with tempfile.TemporaryDirectory() as tmp_dir:
            session_dir = Path(tmp_dir)

            # Create progress tracker for transcribe stage
            tracker = ProgressTracker(
                session_id="test_session",
                session_dir=session_dir,
                stage="transcribe",
                total=10,
            )

            # Update progress
            tracker.update(5)

            # Verify progress is at 5
            progress_file = session_dir / "outputs" / "progress.json"
            with open(progress_file, encoding="utf-8") as f:
                data = json.load(f)
            assert data["stage"] == "transcribe"
            assert data["done"] == 5

            # Finalize to compose stage
            tracker.finalize(stage="compose")

            # Verify stage is compose
            with open(progress_file, encoding="utf-8") as f:
                data = json.load(f)
            assert data["stage"] == "compose"
            assert data["done"] == 10

            # Finalize to done (terminal state)
            tracker.finalize(stage="done")

            # Verify stage is done
            with open(progress_file, encoding="utf-8") as f:
                data = json.load(f)
            assert data["stage"] == "done"
            assert data["done"] == 10

            # Try to update after terminal state (should be ignored)
            tracker.update(3)

            # Verify stage is still done and done count is still 10
            with open(progress_file, encoding="utf-8") as f:
                data = json.load(f)
            assert data["stage"] == "done"
            assert data["done"] == 10  # Should NOT revert to 3

    def test_progress_tracker_finalize_done_sets_terminal_lock(self):
        """ProgressTracker sets terminal lock when finalize(stage='done') is called."""
        import tempfile
        from pathlib import Path

        from yanhu.progress import ProgressTracker

        with tempfile.TemporaryDirectory() as tmp_dir:
            session_dir = Path(tmp_dir)

            tracker = ProgressTracker(
                session_id="test_session",
                session_dir=session_dir,
                stage="transcribe",
                total=10,
            )

            # Initially not locked
            assert tracker._terminal_locked is False

            # Finalize to done
            tracker.finalize(stage="done")

            # Should be locked now
            assert tracker._terminal_locked is True

            # Try to finalize again (should be ignored)
            tracker.finalize(stage="transcribe")

            # Verify stage is still done
            progress_file = session_dir / "outputs" / "progress.json"
            with open(progress_file, encoding="utf-8") as f:
                data = json.load(f)
            assert data["stage"] == "done"

    def test_progress_tracker_failed_state_sets_terminal_lock(self):
        """ProgressTracker sets terminal lock when finalize(stage='failed') is called."""
        import tempfile
        from pathlib import Path

        from yanhu.progress import ProgressTracker

        with tempfile.TemporaryDirectory() as tmp_dir:
            session_dir = Path(tmp_dir)

            tracker = ProgressTracker(
                session_id="test_session",
                session_dir=session_dir,
                stage="transcribe",
                total=10,
            )

            # Finalize to failed (terminal state)
            tracker.finalize(stage="failed")

            # Should be locked
            assert tracker._terminal_locked is True

            # Try to update (should be ignored)
            tracker.update(5)

            # Verify stage is still failed
            progress_file = session_dir / "outputs" / "progress.json"
            with open(progress_file, encoding="utf-8") as f:
                data = json.load(f)
            assert data["stage"] == "failed"

    def test_progress_tracker_cancelled_state_sets_terminal_lock(self):
        """ProgressTracker sets terminal lock when finalize(stage='cancelled') is called."""
        import tempfile
        from pathlib import Path

        from yanhu.progress import ProgressTracker

        with tempfile.TemporaryDirectory() as tmp_dir:
            session_dir = Path(tmp_dir)

            tracker = ProgressTracker(
                session_id="test_session",
                session_dir=session_dir,
                stage="transcribe",
                total=10,
            )

            # Finalize to cancelled (terminal state)
            tracker.finalize(stage="cancelled")

            # Should be locked
            assert tracker._terminal_locked is True


class TestSessionEarlyOpenUX:
    """Test that session view shows banner instead of 404 when opened early."""

    def test_session_view_returns_200_with_warning_when_files_missing(self, tmp_path):
        """Session view returns 200 with warning banner when output files are missing."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        # Create session directory but no output files
        session_id = "2026-01-25_00-00-00_game_tag"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}")

        # Should return 200, not 404
        assert response.status_code == 200

        html = response.data.decode("utf-8")

        # Should have warning banner
        assert "session_incomplete_warning" in html or "Session Processing" in html
        assert "Session is still being finalized" in html

    def test_session_view_shows_refresh_button_when_incomplete(self, tmp_path):
        """Session view shows refresh button when files are missing."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-25_00-00-00_game_tag"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}")
        html = response.data.decode("utf-8")

        # Should have refresh button
        assert "Refresh Page" in html or "location.reload()" in html

    def test_session_view_shows_placeholders_for_missing_tabs(self, tmp_path):
        """Session view shows placeholders for missing overview/timeline/highlights."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-25_00-00-00_game_tag"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}")
        html = response.data.decode("utf-8")

        # Should have placeholders for missing content
        assert (
            "Overview is being generated" in html
            or "Highlights are being generated" in html
            or "Timeline is being generated" in html
        )

    def test_session_view_lists_missing_files_in_warning(self, tmp_path):
        """Session view warning banner lists which files are missing."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-25_00-00-00_game_tag"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}")
        html = response.data.decode("utf-8")

        # Should list missing files
        assert "overview.md" in html
        assert "highlights.md" in html
        assert "timeline.md" in html

    def test_session_view_renders_normally_when_files_exist(self, tmp_path):
        """Session view renders normally without warning when all files exist."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-25_00-00-00_game_tag"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        # Create all required files
        (session_dir / "overview.md").write_text(
            "# Overview\nTest overview", encoding="utf-8"
        )
        (session_dir / "highlights.md").write_text(
            "# Highlights\nTest highlights", encoding="utf-8"
        )
        (session_dir / "timeline.md").write_text(
            "# Timeline\nTest timeline", encoding="utf-8"
        )

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}")
        html = response.data.decode("utf-8")

        # Should return 200
        assert response.status_code == 200

        # Should NOT have warning banner
        assert "Session is still being finalized" not in html

        # Should have actual content
        assert "Test overview" in html or "Overview" in html
        assert "Test highlights" in html or "Highlights" in html
        assert "Test timeline" in html or "Timeline" in html

    def test_session_view_partial_files_shows_specific_placeholders(self, tmp_path):
        """Session view shows placeholders only for missing files when some exist."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        session_id = "2026-01-25_00-00-00_game_tag"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()

        # Create only overview and highlights, not timeline
        (session_dir / "overview.md").write_text(
            "# Overview\nTest overview", encoding="utf-8"
        )
        (session_dir / "highlights.md").write_text(
            "# Highlights\nTest highlights", encoding="utf-8"
        )

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get(f"/s/{session_id}")
        html = response.data.decode("utf-8")

        # Should return 200
        assert response.status_code == 200

        # Should have warning banner (timeline missing)
        assert "Session is still being finalized" in html
        assert "timeline.md" in html

        # Should NOT mention overview or highlights as missing
        assert "Missing: timeline.md" in html

        # Should have actual content for existing files
        assert "Test overview" in html
        assert "Test highlights" in html

        # Should have placeholder for timeline
        assert "Timeline is being generated" in html
