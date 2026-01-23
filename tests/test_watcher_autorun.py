"""Tests for watcher auto-run functionality (M7 v0.3)."""

from yanhu.watcher import (
    RunQueueConfig,
    WatcherConfig,
    scan_once,
    start_polling,
)


class TestAutoRunScanOnce:
    """Test auto-run with --once mode."""

    def test_scan_once_auto_run_callback_called_on_new_files(self, tmp_path, monkeypatch):
        """Should call auto-run callback when new files are queued."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        # Create 2 video files
        (raw_dir / "video1.mp4").write_bytes(b"video1")
        (raw_dir / "video2.mkv").write_bytes(b"video2")

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)

        # Track auto-run callback invocations
        auto_run_calls = []

        def mock_auto_run(queued_count: int):
            auto_run_calls.append(queued_count)

        # Scan with callback
        result = scan_once(config)

        # Manually call the callback (simulating CLI behavior)
        if result.queued > 0:
            mock_auto_run(result.queued)

        # Verify callback was called with correct count
        assert len(auto_run_calls) == 1
        assert auto_run_calls[0] == 2

    def test_scan_once_auto_run_not_called_when_no_new_files(self, tmp_path):
        """Should not call auto-run when no files are queued."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)

        # Track callback calls
        auto_run_calls = []

        def mock_auto_run(queued_count: int):
            auto_run_calls.append(queued_count)

        # Scan empty directory
        result = scan_once(config)

        # Only call callback if files were queued
        if result.queued > 0:
            mock_auto_run(result.queued)

        # Callback should NOT be called
        assert len(auto_run_calls) == 0

    def test_scan_once_auto_run_skips_already_seen(self, tmp_path):
        """Should not trigger auto-run for already-seen files."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        (raw_dir / "video.mp4").write_bytes(b"video")

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)

        auto_run_calls = []

        def mock_auto_run(queued_count: int):
            auto_run_calls.append(queued_count)

        # First scan - should queue and trigger callback
        result1 = scan_once(config)
        if result1.queued > 0:
            mock_auto_run(result1.queued)

        assert len(auto_run_calls) == 1
        assert auto_run_calls[0] == 1

        # Second scan - should skip (dedup) and NOT trigger callback
        result2 = scan_once(config)
        if result2.queued > 0:
            mock_auto_run(result2.queued)

        # Still only 1 call (second scan queued nothing)
        assert len(auto_run_calls) == 1


class TestAutoRunPolling:
    """Test auto-run with --interval mode."""

    def test_polling_auto_run_callback_on_scan_complete(self, tmp_path, monkeypatch):
        """Should call on_scan_complete callback after each scan."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        # Create video file
        (raw_dir / "video.mp4").write_bytes(b"video")

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)

        scan_complete_calls = []

        def mock_scan_complete(queued_count: int):
            scan_complete_calls.append(queued_count)

        # Mock time.sleep to prevent actual polling
        sleep_calls = []

        def mock_sleep(seconds):
            sleep_calls.append(seconds)
            # Raise KeyboardInterrupt after first scan to stop polling
            raise KeyboardInterrupt()

        monkeypatch.setattr("time.sleep", mock_sleep)

        # Start polling (will run once then interrupt)
        try:
            start_polling(
                config,
                interval=5,
                on_scan_complete=mock_scan_complete,
            )
        except KeyboardInterrupt:
            pass

        # Callback should be called once with queued count
        assert len(scan_complete_calls) == 1
        assert scan_complete_calls[0] == 1

    def test_polling_auto_run_callback_error_handled(self, tmp_path, monkeypatch, capsys):
        """Should handle callback errors gracefully without stopping polling."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        (raw_dir / "video.mp4").write_bytes(b"video")

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)

        def failing_callback(queued_count: int):
            raise RuntimeError("Callback failed!")

        # Mock sleep to stop after first iteration
        def mock_sleep(seconds):
            raise KeyboardInterrupt()

        monkeypatch.setattr("time.sleep", mock_sleep)

        # Should not raise, even with failing callback
        try:
            start_polling(config, interval=5, on_scan_complete=failing_callback)
        except KeyboardInterrupt:
            pass

        # Check warning message was printed
        captured = capsys.readouterr()
        assert "on_scan_complete callback failed" in captured.out


class TestAutoRunIntegration:
    """Integration tests for auto-run with run_queue."""

    def test_auto_run_respects_limit(self, tmp_path, monkeypatch):
        """Should respect auto-run-limit parameter."""
        from yanhu.watcher import run_queue

        queue_dir = tmp_path / "queue"
        output_dir = tmp_path / "output"

        # Create 3 pending jobs manually
        from yanhu.watcher import QueueJob, write_queue

        jobs = [
            QueueJob(
                created_at="2026-01-22T10:00:00",
                raw_path=str(tmp_path / f"video{i}.mp4"),
                status="pending",
            )
            for i in range(3)
        ]
        write_queue(jobs, queue_dir / "pending.jsonl")

        # Mock process_job to avoid actual processing
        def mock_process_job(job, output_dir, force):
            from yanhu.watcher import JobResult

            return JobResult(success=False, error="Mocked - file not found")

        monkeypatch.setattr("yanhu.watcher.process_job", mock_process_job)

        # Run with limit=2
        config = RunQueueConfig(
            queue_dir=queue_dir,
            output_dir=output_dir,
            limit=2,
            dry_run=False,
        )

        result = run_queue(config)

        # Should process exactly 2 jobs (respecting limit)
        assert result.processed == 2

    def test_auto_run_dry_run_mode(self, tmp_path):
        """Should not process jobs in dry-run mode."""
        from yanhu.watcher import run_queue

        queue_dir = tmp_path / "queue"
        output_dir = tmp_path / "output"

        # Create 2 pending jobs
        from yanhu.watcher import QueueJob, write_queue

        jobs = [
            QueueJob(
                created_at="2026-01-22T10:00:00",
                raw_path=str(tmp_path / f"video{i}.mp4"),
                status="pending",
            )
            for i in range(2)
        ]
        write_queue(jobs, queue_dir / "pending.jsonl")

        # Run in dry-run mode
        config = RunQueueConfig(
            queue_dir=queue_dir,
            output_dir=output_dir,
            limit=10,
            dry_run=True,
        )

        result = run_queue(config)

        # Should skip all jobs (dry-run)
        assert result.processed == 0
        assert result.skipped == 2

    def test_auto_run_callback_tracks_invocations(self, tmp_path):
        """Should track callback invocations correctly."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        queue_dir = tmp_path / "queue"

        # Create files
        (raw_dir / "video1.mp4").write_bytes(b"v1")
        (raw_dir / "video2.mp4").write_bytes(b"v2")

        config = WatcherConfig(raw_dirs=[raw_dir], queue_dir=queue_dir)

        callback_invocations = []

        def track_callback(queued_count: int):
            callback_invocations.append(queued_count)

        # Scan and trigger
        result = scan_once(config)
        if result.queued > 0:
            track_callback(result.queued)

        # Verify exactly one invocation with correct count
        assert len(callback_invocations) == 1
        assert callback_invocations[0] == 2
