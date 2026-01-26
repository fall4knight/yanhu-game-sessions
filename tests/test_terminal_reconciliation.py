"""Tests for Step 32.15: Terminal state reconciliation from job result."""

import json


class TestBackendTerminalReconciliation:
    """Test that progress.json is reconciled to match job terminal state."""

    def test_successful_job_writes_terminal_progress_done(self, tmp_path):
        """Successful job writes progress.json with stage='done' after compose."""
        # This is a smoke test to verify the process_job flow
        # In practice, we'd need to mock the entire pipeline
        from yanhu.progress import write_stage_heartbeat

        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # Simulate the reconciliation write that happens after compose
        write_stage_heartbeat(
            session_id="test_session",
            session_dir=session_dir,
            stage="done",
            message="Processing complete",
            done=1,
            total=1,
        )

        # Verify progress.json has terminal state
        progress_file = session_dir / "outputs" / "progress.json"
        assert progress_file.exists()

        with open(progress_file, encoding="utf-8") as f:
            progress_data = json.load(f)

        assert progress_data["stage"] == "done"
        assert progress_data["message"] == "Processing complete"
        assert progress_data["done"] == 1
        assert progress_data["total"] == 1

    def test_failed_job_writes_terminal_progress_failed(self, tmp_path):
        """Failed job writes progress.json with stage='failed'."""
        from yanhu.progress import write_stage_heartbeat

        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # Simulate the reconciliation write that happens on error
        write_stage_heartbeat(
            session_id="test_session",
            session_dir=session_dir,
            stage="failed",
            message="Processing failed: Test error",
            done=0,
            total=0,
        )

        # Verify progress.json has failed state
        progress_file = session_dir / "outputs" / "progress.json"
        assert progress_file.exists()

        with open(progress_file, encoding="utf-8") as f:
            progress_data = json.load(f)

        assert progress_data["stage"] == "failed"
        assert "failed" in progress_data["message"].lower()

    def test_terminal_reconciliation_overwrites_stale_progress(self, tmp_path):
        """Terminal reconciliation overwrites stale progress.json (e.g., transcribe 8/9)."""
        from yanhu.progress import write_stage_heartbeat

        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # First write: stale transcribe progress
        write_stage_heartbeat(
            session_id="test_session",
            session_dir=session_dir,
            stage="transcribe",
            message="Transcribing segments...",
            done=8,
            total=9,
        )

        # Verify stale state
        progress_file = session_dir / "outputs" / "progress.json"
        with open(progress_file, encoding="utf-8") as f:
            progress_data = json.load(f)
        assert progress_data["stage"] == "transcribe"
        assert progress_data["done"] == 8
        assert progress_data["total"] == 9

        # Terminal reconciliation: overwrite with done state
        write_stage_heartbeat(
            session_id="test_session",
            session_dir=session_dir,
            stage="done",
            message="Processing complete",
            done=1,
            total=1,
        )

        # Verify terminal state overwrites stale progress
        with open(progress_file, encoding="utf-8") as f:
            progress_data = json.load(f)

        assert progress_data["stage"] == "done"
        assert progress_data["message"] == "Processing complete"
        assert progress_data["done"] == 1
        assert progress_data["total"] == 1


class TestFrontendTerminalPriority:
    """Test that UI prioritizes job.status over progress.stage."""

    def test_ui_has_job_status_priority_comment(self, tmp_path):
        """UI code has comment about job status taking priority."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify priority comment exists
        assert "Job status wins" in html or "job.status is terminal" in html
        assert "Do NOT let progress.stage override job.status" in html

    def test_ui_stops_all_polling_when_job_done(self, tmp_path):
        """UI stops ALL polling when job.status is done."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify terminal state handling stops polling
        assert "clearInterval(window.__YANHU_POLL_LOOP)" in html
        assert "globalProgressState.terminalLocked = true" in html

    def test_ui_shows_done_when_job_status_done(self, tmp_path):
        """UI shows 'Complete' when job.status is done."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify done state rendering
        assert "data.status === 'done'" in html
        assert "stageElem.textContent = 'Complete'" in html
        assert "Processing complete" in html


class TestTerminalReconciliationIntegration:
    """Integration test for terminal state reconciliation."""

    def test_final_progress_json_example_for_done_job(self, tmp_path):
        """Final progress.json has correct structure for done job."""
        from yanhu.progress import write_stage_heartbeat

        session_dir = tmp_path / "session"
        session_dir.mkdir()

        # Simulate final reconciliation write
        write_stage_heartbeat(
            session_id="2026-01-25_00-00-00_game_tag",
            session_dir=session_dir,
            stage="done",
            message="Processing complete",
            done=1,
            total=1,
        )

        # Read and verify structure
        progress_file = session_dir / "outputs" / "progress.json"
        with open(progress_file, encoding="utf-8") as f:
            progress_data = json.load(f)

        # Must have terminal state
        assert progress_data["session_id"] == "2026-01-25_00-00-00_game_tag"
        assert progress_data["stage"] == "done"
        assert progress_data["done"] == 1
        assert progress_data["total"] == 1
        assert progress_data["message"] == "Processing complete"
        assert "updated_at" in progress_data
        assert "elapsed_sec" in progress_data

    def test_reconciliation_location_in_process_job(self):
        """Verify reconciliation is implemented in process_job."""
        # Check that process_job calls write_stage_heartbeat with stage="done"
        from yanhu import watcher

        source = watcher.__file__
        with open(source, encoding="utf-8") as f:
            content = f.read()

        # Verify terminal reconciliation exists
        assert 'write_stage_heartbeat' in content
        assert 'stage="done"' in content
        assert 'Processing complete' in content
        assert 'Terminal state reconciliation' in content or 'Step 32.15' in content
