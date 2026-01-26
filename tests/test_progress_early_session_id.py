"""Test that session_id is written to job record early during processing."""

import json


def test_process_job_signature_includes_jobs_dir():
    """process_job function signature includes jobs_dir parameter."""
    import inspect

    from yanhu.watcher import process_job

    sig = inspect.signature(process_job)
    params = sig.parameters

    # Verify jobs_dir parameter exists
    assert "jobs_dir" in params
    # Verify it's optional (has default value)
    assert params["jobs_dir"].default is not inspect.Parameter.empty or params[
        "jobs_dir"
    ].default is None


def test_update_job_by_id_can_write_session_id(tmp_path):
    """update_job_by_id can write session_id to job record."""
    from yanhu.watcher import QueueJob, get_job_by_id, save_job_to_file, update_job_by_id

    jobs_dir = tmp_path / "_queue" / "jobs"
    jobs_dir.mkdir(parents=True)

    # Create a job
    job = QueueJob(
        job_id="test_job_update_session",
        raw_path="/path/to/video.mp4",
        status="pending",
        created_at="2026-01-25T12:00:00",
    )
    save_job_to_file(job, jobs_dir)

    # Update with session_id
    update_job_by_id(
        "test_job_update_session",
        jobs_dir,
        session_id="2026-01-25_12-00-00_game_tag",
    )

    # Verify session_id was written
    updated_job = get_job_by_id("test_job_update_session", jobs_dir)
    assert updated_job is not None
    assert updated_job.session_id == "2026-01-25_12-00-00_game_tag"

    # Verify JSON file contains session_id
    job_file = jobs_dir / "test_job_update_session.json"
    with open(job_file, encoding="utf-8") as f:
        job_data = json.load(f)

    assert job_data["session_id"] == "2026-01-25_12-00-00_game_tag"


def test_background_worker_signature_passes_jobs_dir():
    """BackgroundWorker _worker_loop calls process_job with jobs_dir."""
    import inspect
    import textwrap

    from yanhu.app import BackgroundWorker

    # Get the source code of _worker_loop

    source = inspect.getsource(BackgroundWorker._worker_loop)
    source = textwrap.dedent(source)

    # Verify process_job is called with jobs_dir parameter
    assert "process_job(" in source
    assert "jobs_dir=" in source or "jobs_dir:" in source
