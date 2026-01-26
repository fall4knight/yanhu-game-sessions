"""Tests for Step 32.17: Progress endpoint reconciliation (hard acceptance for 9/9)."""

import json


class TestProgressReconcileEndpoint:
    """Test /s/<sid>/progress endpoint reconciliation with job outputs."""

    def test_reconcile_stale_progress_with_complete_job_outputs(self, tmp_path):
        """Stale progress.json (8/9) + job outputs (9/9) → endpoint returns 9/9."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        session_id = "2026-01-25_00-00-00_game_tag"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        # Create stale progress.json (stuck at transcribe 8/9)
        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(
            json.dumps({
                "session_id": session_id,
                "stage": "transcribe",
                "done": 8,
                "total": 9,
                "elapsed_sec": 120,
                "eta_sec": 10,
                "message": "Transcribing segments...",
            }),
            encoding="utf-8",
        )

        # Create job with complete outputs (9/9)
        job = QueueJob(
            job_id="test_job",
            created_at="2026-01-25T00:00:00",
            raw_path="/path/to/video.mp4",
            status="processing",
            session_id=session_id,
            outputs={
                "transcribe_processed": 9,
                "transcribe_total": 9,
                "session_dir": str(session_dir),
            },
        )
        save_job_to_file(job, jobs_dir)

        # Request progress
        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()
        response = client.get(f"/s/{session_id}/progress")

        assert response.status_code == 200
        data = response.json

        # Step 32.17: Reconcile should return 9/9 (not stale 8/9)
        assert data["done"] == 9, \
            f"Expected done=9 (reconciled), but got done={data['done']}"
        assert data["total"] == 9
        assert data["stage"] == "transcribe"
        assert data["eta_sec"] == 0, "ETA should be 0 for complete"
        assert "complete" in data["message"].lower()

    def test_reconcile_terminal_job_overrides_progress(self, tmp_path):
        """Job status=done → endpoint returns terminal payload (overrides progress.json)."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        session_id = "2026-01-25_00-00-00_game_done"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        # Create stale progress.json (still shows transcribe 8/9)
        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(
            json.dumps({
                "session_id": session_id,
                "stage": "transcribe",
                "done": 8,
                "total": 9,
                "elapsed_sec": 120,
                "eta_sec": 10,
                "message": "Transcribing segments...",
            }),
            encoding="utf-8",
        )

        # Create terminal job (status=done)
        job = QueueJob(
            job_id="test_job_done",
            created_at="2026-01-25T00:00:00",
            raw_path="/path/to/video.mp4",
            status="done",
            session_id=session_id,
            outputs={
                "transcribe_processed": 9,
                "transcribe_total": 9,
                "session_dir": str(session_dir),
            },
        )
        save_job_to_file(job, jobs_dir)

        # Request progress
        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()
        response = client.get(f"/s/{session_id}/progress")

        assert response.status_code == 200
        data = response.json

        # Step 32.17: Terminal job should return terminal payload
        assert data["stage"] == "done", \
            f"Expected stage='done', but got stage='{data['stage']}'"
        assert data["percent"] == 100
        assert "complete" in data["message"].lower()

    def test_no_reconcile_when_progress_not_stale(self, tmp_path):
        """If progress.json is up-to-date, no reconciliation needed."""
        from yanhu.app import create_app
        from yanhu.watcher import QueueJob, save_job_to_file

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        session_id = "2026-01-25_00-00-00_game_ok"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        # Create up-to-date progress.json (5/9)
        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(
            json.dumps({
                "session_id": session_id,
                "stage": "transcribe",
                "done": 5,
                "total": 9,
                "elapsed_sec": 60,
                "eta_sec": 40,
                "message": "Transcribing segments...",
            }),
            encoding="utf-8",
        )

        # Create job with matching outputs (5/9)
        job = QueueJob(
            job_id="test_job_ok",
            created_at="2026-01-25T00:00:00",
            raw_path="/path/to/video.mp4",
            status="processing",
            session_id=session_id,
            outputs={
                "transcribe_processed": 5,
                "transcribe_total": 9,
                "session_dir": str(session_dir),
            },
        )
        save_job_to_file(job, jobs_dir)

        # Request progress
        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()
        response = client.get(f"/s/{session_id}/progress")

        assert response.status_code == 200
        data = response.json

        # Should return progress.json as-is (5/9)
        assert data["done"] == 5
        assert data["total"] == 9
        assert data["stage"] == "transcribe"
        assert data["eta_sec"] == 40

    def test_no_reconcile_when_no_job(self, tmp_path):
        """If no job found, return progress.json as-is."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jobs_dir = tmp_path / "_queue" / "jobs"
        jobs_dir.mkdir(parents=True)

        session_id = "2026-01-25_00-00-00_game_nojob"
        session_dir = sessions_dir / session_id
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        # Create progress.json (8/9)
        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(
            json.dumps({
                "session_id": session_id,
                "stage": "transcribe",
                "done": 8,
                "total": 9,
                "elapsed_sec": 120,
                "eta_sec": 10,
                "message": "Transcribing segments...",
            }),
            encoding="utf-8",
        )

        # No job file exists

        # Request progress
        app = create_app(sessions_dir, jobs_dir=jobs_dir)
        client = app.test_client()
        response = client.get(f"/s/{session_id}/progress")

        assert response.status_code == 200
        data = response.json

        # Should return progress.json as-is (8/9) since no job to reconcile with
        assert data["done"] == 8
        assert data["total"] == 9
        assert data["stage"] == "transcribe"


class TestFrontendHardAcceptance:
    """Test frontend hard acceptance rule: done == total is terminal."""

    def test_frontend_has_hard_acceptance_rule(self, tmp_path):
        """Verify frontend treats done == total as terminal (isComplete)."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify Step 32.17 hard acceptance comment
        assert "Step 32.17" in html, "Missing Step 32.17 implementation marker"

        # Verify isComplete logic
        assert "const isComplete = done >= total && total > 0" in html, \
            "Missing hard acceptance: done >= total check"

        # Verify isDone includes isComplete
        assert "const isDone = stage === 'done' || isComplete" in html, \
            "Missing: isDone must include isComplete"

    def test_frontend_shows_complete_label_at_9_9(self, tmp_path):
        """Verify frontend shows 'Complete' when done == total (not 'Stage: transcribe')."""
        from yanhu.app import create_app

        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()

        app = create_app(sessions_dir)
        client = app.test_client()

        response = client.get("/")
        html = response.data.decode("utf-8")

        # Verify label override for done == total
        assert "Show \"Complete\" if done == total" in html, \
            "Missing comment about showing 'Complete' for done == total"

        # Verify the actual logic
        assert "stageElem.textContent = 'Complete'" in html, \
            "Missing: stageElem.textContent = 'Complete' for done == total"
