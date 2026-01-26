"""Tests for Step 32.17: Unified job status endpoint.

This endpoint merges /api/jobs/<job_id> and /s/<sid>/progress into a single
response to eliminate race conditions.
"""

import json


def test_unified_endpoint_with_stale_progress_8_9(tmp_path):
    """UNIFIED: Endpoint returns reconciled 9/9 when job outputs show complete."""
    from yanhu.app import create_app
    from yanhu.watcher import QueueJob, save_job_to_file

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    session_id = "2026-01-25_00-00-00_game_unified"
    session_dir = sessions_dir / session_id
    session_dir.mkdir()
    outputs_dir = session_dir / "outputs"
    outputs_dir.mkdir()

    # Create STALE progress.json (8/9)
    progress_file = outputs_dir / "progress.json"
    progress_file.write_text(
        json.dumps({
            "session_id": session_id,
            "stage": "transcribe",
            "done": 8,  # STALE
            "total": 9,
            "elapsed_sec": 120,
            "eta_sec": 10,
            "message": "Transcribing segments...",
        }),
        encoding="utf-8",
    )

    # Create job with COMPLETE outputs (9/9)
    job = QueueJob(
        job_id="unified_test_job",
        created_at="2026-01-25T00:00:00",
        raw_path="/path/to/video.mp4",
        status="processing",
        session_id=session_id,
        outputs={
            "transcribe_processed": 9,  # COMPLETE
            "transcribe_total": 9,
            "session_dir": str(session_dir),
        },
    )
    save_job_to_file(job, jobs_dir)

    # Create Flask app
    app = create_app(sessions_dir, jobs_dir=jobs_dir)
    client = app.test_client()

    # Make request to UNIFIED endpoint
    response = client.get("/api/jobs/unified_test_job/status")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json

    print(f"Unified response: {json.dumps(data, indent=2)}")

    # Verify job metadata is present
    assert data["job_id"] == "unified_test_job"
    assert data["status"] == "processing"
    assert data["session_id"] == session_id

    # Verify progress is reconciled to 9/9 (NOT stale 8/9)
    assert "progress" in data, "Missing progress field in unified response"
    progress = data["progress"]
    assert progress["done"] == 9, \
        f"FAILED: Expected progress.done=9 (reconciled), got {progress['done']}"
    assert progress["total"] == 9, f"Expected progress.total=9, got {progress['total']}"
    assert progress["stage"] == "transcribe"
    assert progress["eta_sec"] == 0, f"Expected eta_sec=0 for complete, got {progress['eta_sec']}"
    assert "complete" in progress["message"].lower(), \
        f"Expected 'complete' in message, got {progress['message']}"

    print("✓ UNIFIED ENDPOINT: Reconciliation works (8/9 → 9/9)")


def test_unified_endpoint_terminal_job_status_done(tmp_path):
    """UNIFIED: Endpoint returns terminal payload when job.status=done."""
    from yanhu.app import create_app
    from yanhu.watcher import QueueJob, save_job_to_file

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    session_id = "2026-01-25_00-00-00_game_done"
    session_dir = sessions_dir / session_id
    session_dir.mkdir()

    # Create job with status=done
    job = QueueJob(
        job_id="done_job",
        created_at="2026-01-25T00:00:00",
        raw_path="/path/to/video.mp4",
        status="done",  # Terminal
        session_id=session_id,
    )
    save_job_to_file(job, jobs_dir)

    # Create Flask app
    app = create_app(sessions_dir, jobs_dir=jobs_dir)
    client = app.test_client()

    # Make request to unified endpoint
    response = client.get("/api/jobs/done_job/status")

    assert response.status_code == 200
    data = response.json

    # Verify job metadata
    assert data["status"] == "done"

    # Verify progress shows terminal state
    progress = data["progress"]
    assert progress["stage"] == "done"
    assert progress["percent"] == 100
    assert "complete" in progress["message"].lower()

    print("✓ UNIFIED ENDPOINT: Terminal job status returns terminal payload")


def test_unified_endpoint_pending_job(tmp_path):
    """UNIFIED: Endpoint returns pending state for queued job."""
    from yanhu.app import create_app
    from yanhu.watcher import QueueJob, save_job_to_file

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    # Create pending job (no session yet)
    job = QueueJob(
        job_id="pending_job",
        created_at="2026-01-25T00:00:00",
        raw_path="/path/to/video.mp4",
        status="pending",
        session_id=None,  # No session yet
    )
    save_job_to_file(job, jobs_dir)

    # Create Flask app
    app = create_app(sessions_dir, jobs_dir=jobs_dir)
    client = app.test_client()

    # Make request
    response = client.get("/api/jobs/pending_job/status")

    assert response.status_code == 200
    data = response.json

    # Verify job metadata
    assert data["status"] == "pending"
    assert data["session_id"] is None

    # Verify progress shows pending state
    progress = data["progress"]
    assert progress["stage"] == "pending"
    assert progress["done"] == 0
    assert progress["total"] == 0
    assert "waiting" in progress["message"].lower()

    print("✓ UNIFIED ENDPOINT: Pending job returns pending state")


def test_unified_endpoint_processing_no_progress_yet(tmp_path):
    """UNIFIED: Endpoint returns starting state when processing but no progress.json yet."""
    from yanhu.app import create_app
    from yanhu.watcher import QueueJob, save_job_to_file

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    session_id = "2026-01-25_00-00-00_game_starting"
    session_dir = sessions_dir / session_id
    session_dir.mkdir()

    # Create processing job with session but no progress.json yet
    job = QueueJob(
        job_id="starting_job",
        created_at="2026-01-25T00:00:00",
        raw_path="/path/to/video.mp4",
        status="processing",
        session_id=session_id,
    )
    save_job_to_file(job, jobs_dir)

    # Create Flask app
    app = create_app(sessions_dir, jobs_dir=jobs_dir)
    client = app.test_client()

    # Make request
    response = client.get("/api/jobs/starting_job/status")

    assert response.status_code == 200
    data = response.json

    # Verify job metadata
    assert data["status"] == "processing"
    assert data["session_id"] == session_id

    # Verify progress shows starting state
    progress = data["progress"]
    assert progress["stage"] == "starting"
    assert progress["done"] == 0
    assert progress["total"] == 0
    assert "waiting" in progress["message"].lower()

    print("✓ UNIFIED ENDPOINT: Processing job with no progress.json returns starting state")


def test_unified_endpoint_not_found(tmp_path):
    """UNIFIED: Endpoint returns 404 for non-existent job."""
    from yanhu.app import create_app

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    # Create Flask app
    app = create_app(sessions_dir, jobs_dir=jobs_dir)
    client = app.test_client()

    # Make request for non-existent job
    response = client.get("/api/jobs/nonexistent_job/status")

    assert response.status_code == 404
    data = response.json
    assert "error" in data
    assert "not found" in data["error"].lower()

    print("✓ UNIFIED ENDPOINT: Non-existent job returns 404")


def test_unified_endpoint_preserves_actual_transcription_progress(tmp_path):
    """UNIFIED: Terminal job preserves actual 9/9 progress, not hardcoded 1/1."""
    from yanhu.app import create_app
    from yanhu.watcher import QueueJob, save_job_to_file

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    session_id = "2026-01-25_00-00-00_game_done_with_outputs"
    session_dir = sessions_dir / session_id
    session_dir.mkdir()

    # Create job with status=done AND job.outputs showing 9/9
    job = QueueJob(
        job_id="done_job_with_outputs",
        created_at="2026-01-25T00:00:00",
        raw_path="/path/to/video.mp4",
        status="done",  # Terminal
        session_id=session_id,
        outputs={
            "transcribe_processed": 9,
            "transcribe_total": 9,
            "session_dir": str(session_dir),
        },
    )
    save_job_to_file(job, jobs_dir)

    # Create Flask app
    app = create_app(sessions_dir, jobs_dir=jobs_dir)
    client = app.test_client()

    # Make request
    response = client.get("/api/jobs/done_job_with_outputs/status")

    assert response.status_code == 200
    data = response.json

    # Verify job metadata
    assert data["status"] == "done"

    # CRITICAL: Verify progress preserves actual 9/9, NOT hardcoded 1/1
    progress = data["progress"]
    assert progress["stage"] == "done"
    assert progress["done"] == 9, \
        f"Expected done=9 (actual transcription progress), got {progress['done']}"
    assert progress["total"] == 9, \
        f"Expected total=9 (actual transcription progress), got {progress['total']}"
    assert progress["percent"] == 100
    assert "complete" in progress["message"].lower()

    print("✓ UNIFIED ENDPOINT: Terminal job preserves actual 9/9 progress")
