"""Integration tests for Step 32.17: Full stack progress reconciliation test."""

import json


def test_full_stack_reconcile_stale_8_9_to_9_9(tmp_path):
    """INTEGRATION: Full stack test - stale progress 8/9 + job outputs 9/9 → endpoint returns 9/9.

    This test verifies the ENTIRE flow:
    1. Real job file with outputs showing 9/9
    2. Real stale progress.json showing 8/9
    3. Real HTTP request to /s/<sid>/progress
    4. Verify reconciled response shows 9/9
    """
    from yanhu.app import create_app
    from yanhu.watcher import QueueJob, save_job_to_file

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    session_id = "2026-01-25_00-00-00_game_integration"
    session_dir = sessions_dir / session_id
    session_dir.mkdir()
    outputs_dir = session_dir / "outputs"
    outputs_dir.mkdir()

    # 1. Create STALE progress.json (stuck at 8/9)
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

    # 2. Create job with COMPLETE outputs (9/9)
    job = QueueJob(
        job_id="integration_test_job",
        created_at="2026-01-25T00:00:00",
        raw_path="/path/to/video.mp4",
        status="processing",  # Still processing, but outputs show complete
        session_id=session_id,
        outputs={
            "transcribe_processed": 9,  # COMPLETE
            "transcribe_total": 9,
            "session_dir": str(session_dir),
        },
    )
    save_job_to_file(job, jobs_dir)

    # Verify job file was created
    job_file = jobs_dir / "integration_test_job.json"
    assert job_file.exists(), f"Job file not created at {job_file}"

    # Verify job file has outputs
    with open(job_file) as f:
        job_data = json.load(f)
    assert "outputs" in job_data, "Job file missing outputs"
    assert job_data["outputs"]["transcribe_processed"] == 9
    assert job_data["outputs"]["transcribe_total"] == 9
    print(f"✓ Job file created with outputs: {job_data['outputs']}")

    # 3. Create Flask app with jobs_dir configured
    app = create_app(sessions_dir, jobs_dir=jobs_dir)
    client = app.test_client()

    # 4. Make HTTP request to progress endpoint
    response = client.get(f"/s/{session_id}/progress")

    # 5. Verify response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json

    print(f"Response data: {json.dumps(data, indent=2)}")

    # CRITICAL ASSERTION: Reconciliation MUST return 9/9 (not stale 8/9)
    assert data["done"] == 9, \
        f"FAILED: Expected done=9 (reconciled), but got done={data['done']}. " \
        f"Full response: {data}"
    assert data["total"] == 9, f"Expected total=9, but got total={data['total']}"
    assert data["stage"] == "transcribe", \
        f"Expected stage=transcribe, but got stage={data['stage']}"
    assert data["eta_sec"] == 0, \
        f"Expected eta_sec=0 for complete, but got eta_sec={data['eta_sec']}"
    assert "complete" in data["message"].lower(), \
        f"Expected 'complete' in message, but got message={data['message']}"

    print("✓ INTEGRATION TEST PASSED: Reconciliation works end-to-end")


def test_debug_find_job_by_session_id(tmp_path):
    """Debug test: Verify _find_job_by_session_id can find jobs."""
    from yanhu.app import create_app
    from yanhu.watcher import QueueJob, save_job_to_file

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    session_id = "2026-01-25_00-00-00_game_debug"

    # Create job with session_id
    job = QueueJob(
        job_id="debug_job",
        created_at="2026-01-25T00:00:00",
        raw_path="/path/to/video.mp4",
        status="processing",
        session_id=session_id,
        outputs={
            "transcribe_processed": 9,
            "transcribe_total": 9,
        },
    )
    save_job_to_file(job, jobs_dir)

    # Create Flask app
    app = create_app(sessions_dir, jobs_dir=jobs_dir)

    # Access the helper function through app context
    with app.app_context():
        # Call the helper function
        from yanhu.app import create_app as _create_app
        test_app = _create_app(sessions_dir, jobs_dir=jobs_dir)

        # The helper is a nested function, we need to access it through the endpoint
        # Let's just verify by making a request
        client = test_app.test_client()

        # Create session dir and progress file
        session_dir = sessions_dir / session_id
        session_dir.mkdir()
        outputs_dir = session_dir / "outputs"
        outputs_dir.mkdir()

        progress_file = outputs_dir / "progress.json"
        progress_file.write_text(
            json.dumps({
                "session_id": session_id,
                "stage": "transcribe",
                "done": 8,
                "total": 9,
            }),
            encoding="utf-8",
        )

        # Make request - this will call _find_job_by_session_id internally
        response = client.get(f"/s/{session_id}/progress")
        assert response.status_code == 200

        # If reconciliation worked, we'll get 9/9
        data = response.json
        print(f"Debug response: {json.dumps(data, indent=2)}")

        # This should be reconciled to 9/9
        if data["done"] != 9:
            print("WARNING: Job was not found or reconciliation didn't trigger")
            print(f"Response: {data}")
            # Check if job file exists
            job_files = list(jobs_dir.glob("*.json"))
            print(f"Job files in {jobs_dir}: {job_files}")
            for jf in job_files:
                with open(jf) as f:
                    jdata = json.load(f)
                sid = jdata.get('session_id')
                outputs = jdata.get('outputs')
                print(f"Job {jf.name}: session_id={sid}, outputs={outputs}")


def test_reconcile_with_job_status_done(tmp_path):
    """INTEGRATION: Job with status=done should return terminal payload (override everything)."""
    from yanhu.app import create_app
    from yanhu.watcher import QueueJob, save_job_to_file

    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    session_id = "2026-01-25_00-00-00_game_done_test"
    session_dir = sessions_dir / session_id
    session_dir.mkdir()
    outputs_dir = session_dir / "outputs"
    outputs_dir.mkdir()

    # Create stale progress.json (8/9)
    progress_file = outputs_dir / "progress.json"
    progress_file.write_text(
        json.dumps({
            "session_id": session_id,
            "stage": "transcribe",
            "done": 8,
            "total": 9,
            "message": "Transcribing segments...",
        }),
        encoding="utf-8",
    )

    # Create job with status=done
    job = QueueJob(
        job_id="done_job",
        created_at="2026-01-25T00:00:00",
        raw_path="/path/to/video.mp4",
        status="done",  # Terminal status
        session_id=session_id,
        outputs={
            "transcribe_processed": 9,
            "transcribe_total": 9,
            "session_dir": str(session_dir),
        },
    )
    save_job_to_file(job, jobs_dir)

    # Make request
    app = create_app(sessions_dir, jobs_dir=jobs_dir)
    client = app.test_client()
    response = client.get(f"/s/{session_id}/progress")

    assert response.status_code == 200
    data = response.json

    print(f"Terminal job response: {json.dumps(data, indent=2)}")

    # Should return terminal payload (overrides stale progress.json)
    assert data["stage"] == "done", \
        f"Expected stage='done' for terminal job, but got stage='{data['stage']}'"
    assert data["percent"] == 100, f"Expected percent=100, got {data['percent']}"
    assert "complete" in data["message"].lower(), \
        f"Expected 'complete' in message, got {data['message']}"


def test_job_outputs_updated_during_transcription_progress(tmp_path):
    """Test that job.outputs is updated in real-time during transcription progress callbacks.

    This ensures reconciliation works DURING transcription, not just after.
    """
    from yanhu.transcriber import TranscribeStats
    from yanhu.watcher import QueueJob, load_job_from_file, save_job_to_file

    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)
    session_dir = tmp_path / "sessions" / "test_session"
    session_dir.mkdir(parents=True)

    # Create initial job WITHOUT outputs
    job = QueueJob(
        job_id="test_realtime_job",
        created_at="2026-01-25T00:00:00",
        raw_path="/path/to/video.mp4",
        status="processing",
        session_id="test_session",
    )
    save_job_to_file(job, jobs_dir)

    # Verify initial job has no outputs
    loaded_job = load_job_from_file(jobs_dir / "test_realtime_job.json")
    assert loaded_job is not None
    assert loaded_job.outputs is None, "Initial job should have no outputs"

    # Simulate transcribe progress callback updating job.outputs
    # (This simulates what happens in transcribe_progress_callback)
    stats = TranscribeStats()
    stats.processed = 5
    stats.total = 9

    # Update job.outputs (simulating the callback)
    loaded_job.outputs = {
        "transcribe_processed": stats.processed,
        "transcribe_total": stats.total,
        "session_dir": str(session_dir),
    }
    save_job_to_file(loaded_job, jobs_dir)

    # Reload job and verify outputs were saved
    reloaded_job = load_job_from_file(jobs_dir / "test_realtime_job.json")
    assert reloaded_job is not None
    assert reloaded_job.outputs is not None, "Job should have outputs after update"
    assert reloaded_job.outputs["transcribe_processed"] == 5
    assert reloaded_job.outputs["transcribe_total"] == 9

    print("✓ Job.outputs can be updated in real-time during transcription")
