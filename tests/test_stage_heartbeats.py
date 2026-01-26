"""Tests for Step 32.11: Stage heartbeats and terminal lock."""

import json


class TestStageHeartbeats:
    """Test that progress.json is created early with stage transitions."""

    def test_write_stage_heartbeat_function_exists(self):
        """write_stage_heartbeat function exists and can write progress.json."""
        import tempfile
        from pathlib import Path

        from yanhu.progress import write_stage_heartbeat

        # Create a temporary session dir
        with tempfile.TemporaryDirectory() as tmp_dir:
            session_dir = Path(tmp_dir)

            # Write a stage heartbeat
            write_stage_heartbeat(
                session_id="test_session",
                session_dir=session_dir,
                stage="segment",
                message="Segmenting video...",
            )

            # Verify progress.json exists
            progress_file = session_dir / "outputs" / "progress.json"
            assert progress_file.exists()

            # Verify it has valid JSON with expected fields
            with open(progress_file, encoding="utf-8") as f:
                progress_data = json.load(f)

            assert progress_data["session_id"] == "test_session"
            assert progress_data["stage"] == "segment"
            assert progress_data["message"] == "Segmenting video..."
            assert progress_data["done"] == 0
            assert progress_data["total"] == 0


class TestTerminalLock:
    """Test Step 32.11: Terminal lock prevents status regression."""

    def test_terminal_locked_field_in_global_state(self, tmp_path):
        """JavaScript includes terminalLocked field in globalProgressState."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify terminalLocked field exists
        assert "terminalLocked: false" in html
        assert "Step 32.11: Prevent status regression" in html

    def test_terminal_lock_check_at_start_of_update(self, tmp_path):
        """updateGlobalProgress checks terminalLocked and returns early if locked."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify terminal lock check exists
        assert "if (globalProgressState.terminalLocked)" in html
        assert "return; // Do not update UI or poll anymore" in html

    def test_terminal_lock_set_on_job_done(self, tmp_path):
        """Terminal lock is set when job.status reaches done/failed/cancelled."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify terminal lock is set in terminal states
        assert "globalProgressState.terminalLocked = true;" in html
        # Should appear in both job terminal state and progress terminal state
        assert html.count("globalProgressState.terminalLocked = true;") >= 2

    def test_terminal_lock_set_on_progress_done(self, tmp_path):
        """Terminal lock is set when progress.stage reaches 'done'."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify terminal lock is set when progress stage is done
        # Look for the pattern in fetchProgressData where isDone is checked
        assert "if (isDone || isFailed)" in html
        assert "globalProgressState.terminalLocked = true;" in html
